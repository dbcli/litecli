import contextlib
import io
import logging
import os
import re
import shlex
import sys
from runpy import run_module
from typing import Optional, Tuple

import click

try:
    import llm
    from llm.cli import cli

    LLM_CLI_COMMANDS = list(cli.commands.keys())
    MODELS = {x.model_id: None for x in llm.get_models()}
except ImportError:
    llm = None
    cli = None

from . import export
from .main import parse_special_command

log = logging.getLogger(__name__)


def run_external_cmd(cmd, *args, capture_output=False, restart_cli=False, raise_exception=True):
    original_exe = sys.executable
    original_args = sys.argv

    try:
        sys.argv = [cmd] + list(args)
        code = 0

        if capture_output:
            buffer = io.StringIO()
            redirect = contextlib.ExitStack()
            redirect.enter_context(contextlib.redirect_stdout(buffer))
            redirect.enter_context(contextlib.redirect_stderr(buffer))
        else:
            redirect = contextlib.nullcontext()

        with redirect:
            try:
                run_module(cmd, run_name="__main__")
            except SystemExit as e:
                code = e.code
                if code != 0 and raise_exception:
                    if capture_output:
                        raise RuntimeError(buffer.getvalue())
                    else:
                        raise RuntimeError(f"Command {cmd} failed with exit code {code}.")

        if restart_cli and code == 0:
            os.execv(original_exe, [original_exe] + original_args)

        if capture_output:
            return code, buffer.getvalue()
        else:
            return code, ""
    finally:
        sys.argv = original_args


def build_command_tree(cmd):
    """Recursively build a command tree for a Click app.

    Args:
        cmd (click.Command or click.Group): The Click command/group to inspect.

    Returns:
        dict: A nested dictionary representing the command structure.
    """
    tree = {}
    if isinstance(cmd, click.Group):
        for name, subcmd in cmd.commands.items():
            if cmd.name == "models" and name == "default":
                tree[name] = MODELS
            else:
                # Recursively build the tree for subcommands
                tree[name] = build_command_tree(subcmd)
    else:
        # Leaf command with no subcommands
        tree = None
    return tree


# Generate the tree
COMMAND_TREE = build_command_tree(cli)


def get_completions(tokens, tree=COMMAND_TREE):
    """Get autocompletions for the current command tokens.

    Args:
        tree (dict): The command tree.
        tokens (list): List of tokens (command arguments).

    Returns:
        list: List of possible completions.
    """
    for token in tokens:
        if token.startswith("-"):
            # Skip options (flags)
            continue
        if tree and token in tree:
            tree = tree[token]
        else:
            # No completions available
            return []

    # Return possible completions (keys of the current tree level)
    return list(tree.keys()) if tree else []


@export
class FinishIteration(Exception):
    def __init__(self, results=None):
        self.results = results


USAGE = """
Use an LLM to create SQL queries to answer questions from your database.
Examples:

# Ask a question.
> \\llm 'Most visited urls?'

# List available models
> \\llm models
gpt-4o
gpt-3.5-turbo
qwq

# Change default model
> \\llm models default llama3

# Set api key (not required for local models)
> \\llm keys set openai sg-1234
API key set for openai.

# Install a model plugin
> \\llm install llm-ollama
llm-ollama installed.

# Models directory
# https://llm.datasette.io/en/stable/plugins/directory.html
"""

_SQL_CODE_FENCE = r"```sql\n(.*?)\n```"
PROMPT = """A SQLite database has the following schema:

$db_schema

Here is a sample row of data from each table: $sample_data

Use the provided schema and the sample data to construct a SQL query that
can be run in SQLite3 to answer

$question

Explain the reason for choosing each table in the SQL query you have
written. Keep the explanation concise.
Finally include a sql query in a code fence such as this one:

```sql
SELECT count(*) FROM table_name;
```
"""


def initialize_llm():
    # Initialize the LLM library.
    if click.confirm("This feature requires additional libraries. Install LLM library?", default=True):
        click.echo("Installing LLM library. Please wait...")
        run_external_cmd("pip", "install", "--quiet", "llm", restart_cli=True)


def ensure_litecli_template(replace=False):
    """
    Create a template called litecli with the default prompt.
    """
    if not replace:
        # Check if it already exists.
        code, _ = run_external_cmd("llm", "templates", "show", "litecli", capture_output=True, raise_exception=False)
        if code == 0:  # Template already exists. No need to create it.
            return

    run_external_cmd("llm", PROMPT, "--save", "litecli")
    return


@export
def handle_llm(text, cur) -> Tuple[str, Optional[str]]:
    """This function handles the special command `\\llm`.

    If it deals with a question that results in a SQL query then it will return
    the query.
    If it deals with a subcommand like `models` or `keys` then it will raise
    FinishIteration() which will be caught by the main loop AND print any
    output that was supplied (or None).
    """
    _, verbose, arg = parse_special_command(text)

    # LLM is not installed.
    if llm is None:
        initialize_llm()
        raise FinishIteration(None)

    if not arg.strip():  # No question provided. Print usage and bail.
        output = [(None, None, None, USAGE)]
        raise FinishIteration(output)

    parts = shlex.split(arg)

    restart = False
    # If the parts has `-c` then capture the output and check for fenced SQL.
    # User is continuing a previous question.
    # eg: \llm -m ollama -c "Show only the top 5 results"
    if "-c" in parts:
        capture_output = True
        use_context = False
    # If the parts has `pormpt` command without `-c` then use context to the prompt.
    # \llm -m ollama prompt "Most visited urls?"
    elif "prompt" in parts:  # User might invoke prompt with an option flag in the first argument.
        capture_output = True
        use_context = True
    elif "install" in parts or "uninstall" in parts:
        capture_output = False
        use_context = False
        restart = True
    # If the parts starts with any of the known LLM_CLI_COMMANDS then invoke
    # the llm and don't capture output. This is to handle commands like `models` or `keys`.
    elif parts[0] in LLM_CLI_COMMANDS:
        capture_output = False
        use_context = False
    # If the parts doesn't have any known LLM_CLI_COMMANDS then the user is
    # invoking a question. eg: \llm -m ollama "Most visited urls?"
    elif not set(parts).intersection(LLM_CLI_COMMANDS):
        capture_output = True
        use_context = True
    # User invoked llm with a question without `prompt` subcommand. Capture the
    # output and check for fenced SQL. eg: \llm "Most visited urls?"
    else:
        capture_output = True
        use_context = True

    if not use_context:
        args = parts
        if capture_output:
            _, result = run_external_cmd("llm", *args, capture_output=capture_output)
            match = re.search(_SQL_CODE_FENCE, result, re.DOTALL)
            if match:
                sql = match.group(1).strip()
            else:
                output = [(None, None, None, result)]
                raise FinishIteration(output)

            return result if verbose else "", sql
        else:
            run_external_cmd("llm", *args, restart_cli=restart)
            raise FinishIteration(None)

    try:
        ensure_litecli_template()
        context, sql = sql_using_llm(cur=cur, question=arg, verbose=verbose)
        if not verbose:
            context = ""
        return context, sql
    except Exception as e:
        # Something went wrong. Raise an exception and bail.
        raise RuntimeError(e)


@export
def is_llm_command(command) -> bool:
    """
    Is this an llm/ai command?
    """
    cmd, _, _ = parse_special_command(command)
    return cmd in ("\\llm", "\\ai", ".llm", ".ai")


@export
def sql_using_llm(cur, question=None, verbose=False) -> Tuple[str, Optional[str]]:
    if cur is None:
        raise RuntimeError("Connect to a datbase and try again.")
    schema_query = """
        SELECT sql FROM sqlite_master
        WHERE sql IS NOT NULL
        ORDER BY tbl_name, type DESC, name
    """
    tables_query = """
            SELECT name FROM sqlite_master
            WHERE type IN ('table','view') AND name NOT LIKE 'sqlite_%'
            ORDER BY 1
    """
    sample_row_query = "SELECT * FROM {table} LIMIT 1"
    log.debug(schema_query)
    cur.execute(schema_query)
    db_schema = "\n".join([x for (x,) in cur.fetchall()])

    log.debug(tables_query)
    cur.execute(tables_query)
    sample_data = {}
    for (table,) in cur.fetchall():
        sample_row = sample_row_query.format(table=table)
        cur.execute(sample_row)
        cols = [x[0] for x in cur.description]
        row = cur.fetchone()
        if row is None:  # Skip empty tables
            continue
        sample_data[table] = list(zip(cols, row))

    args = [
        "--template",
        "litecli",
        "--param",
        "db_schema",
        db_schema,
        "--param",
        "sample_data",
        sample_data,
        "--param",
        "question",
        question,
        " ",  # Dummy argument to prevent llm from waiting on stdin
    ]
    _, result = run_external_cmd("llm", *args, capture_output=True)
    match = re.search(_SQL_CODE_FENCE, result, re.DOTALL)
    if match:
        sql = match.group(1).strip()
    else:
        sql = ""

    return result, sql
