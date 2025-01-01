import logging
import re
import sys
from runpy import run_module
from typing import Optional, Tuple

import click
import llm
from llm.cli import cli

from . import export
from .main import parse_special_command

log = logging.getLogger(__name__)
LLM_CLI_COMMANDS = list(cli.commands.keys())
MODELS = {x.model_id: None for x in llm.get_models()}


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
    current_tree = tree
    for token in tokens:
        if token.startswith("-"):
            # Skip options (flags)
            continue
        if token in current_tree:
            current_tree = current_tree[token]
        else:
            # No completions available
            return []

    # Return possible completions (keys of the current tree level)
    return list(current_tree.keys()) if current_tree else []


@export
class FinishIteration(Exception):
    def __init__(self, results=None):
        self.results = results


USAGE = """
Use an LLM to create SQL queries to answer questions from your database.
Examples:

# Ask a question.
> \\llm Most visited urls?

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


@export
def handle_llm(text, cur) -> Tuple[str, Optional[str]]:
    cmd, verbose, arg = parse_special_command(text)

    if not arg.strip():  # No question provided. Print usage and bail.
        output = [(None, None, None, USAGE)]
        raise FinishIteration(output)

    parts = arg.split()

    if parts[0].startswith("-") or parts[0] in LLM_CLI_COMMANDS:
        # If the first argument is a flag or a valid llm command then
        # invoke the llm cli.
        sys.argv = ["llm"] + parts
        try:
            run_module("llm", run_name="__main__")
        except SystemExit:
            raise FinishIteration(None)

    try:
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
    _pattern = r"```sql\n(.*?)\n```"
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

    sys_prompt = f"""A SQLite database has the following schema:
    {db_schema}

    Here is a sample row of data from each table: {sample_data}

    Use the provided schema and the sample data to construct a SQL query that
    can be run in SQLite3 to answer

    {question}

    Explain the reason for choosing each table in the SQL query you have
    written. Keep the explanation concise and to the point.
    Finally include the sql query in a code fence such as this one:

    ```sql
    SELECT count(*) FROM table_name;
    ```
    """
    log.debug(sys_prompt)
    # model = llm.get_model("llama3.3")
    # model = llm.get_model("qwq")
    # model = llm.get_model("o1-preview")
    # model = llm.get_model("o1-mini")
    # model = llm.get_model("llama3.2")
    model = llm.get_model("gpt-4o")
    # model = llm.get_model("gemini-2.0-flash-exp")
    # model = llm.get_model("claude-3.5-haiku")
    resp = model.prompt(sys_prompt)
    result = resp.text()
    match = re.search(_pattern, result, re.DOTALL)
    if match:
        sql = match.group(1).strip()
    else:
        sql = ""

    return result, sql
