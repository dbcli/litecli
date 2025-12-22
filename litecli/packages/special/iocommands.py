from __future__ import annotations

import locale
import logging
import os
import re
import shlex
import subprocess
from io import open
from time import sleep
from typing import Any, Generator, TextIO

import click
import sqlparse
from configobj import ConfigObj

from ..prompt_utils import confirm_destructive_query
from . import export
from .favoritequeries import FavoriteQueries
from .main import NO_QUERY, PARSED_QUERY, special_command
from .utils import handle_cd_command

use_expanded_output: bool = False
PAGER_ENABLED: bool = True
tee_file: TextIO | None = None
once_file: TextIO | None = None
written_to_once_file: bool = False
pipe_once_process: subprocess.Popen[str] | None = None
written_to_pipe_once_process: bool = False
favoritequeries: FavoriteQueries = FavoriteQueries(ConfigObj())

log = logging.getLogger(__name__)


@export
def set_favorite_queries(config: Any) -> None:
    global favoritequeries
    favoritequeries = FavoriteQueries(config)


@export
def set_pager_enabled(val: bool) -> None:
    global PAGER_ENABLED
    PAGER_ENABLED = val


@export
def is_pager_enabled() -> bool:
    return PAGER_ENABLED


@export
@special_command(
    "pager",
    "\\P [command]",
    "Set PAGER. Print the query results via PAGER.",
    arg_type=PARSED_QUERY,
    aliases=("\\P",),
    case_sensitive=True,
)
def set_pager(arg: str, **_: Any) -> list[tuple]:
    if arg:
        os.environ["PAGER"] = arg
        msg = "PAGER set to %s." % arg
        set_pager_enabled(True)
    else:
        if "PAGER" in os.environ:
            msg = "PAGER set to %s." % os.environ["PAGER"]
        else:
            # This uses click's default per echo_via_pager.
            msg = "Pager enabled."
        set_pager_enabled(True)

    return [(None, None, None, msg)]


@export
@special_command(
    "nopager",
    "\\n",
    "Disable pager, print to stdout.",
    arg_type=NO_QUERY,
    aliases=("\\n",),
    case_sensitive=True,
)
def disable_pager() -> list[tuple]:
    set_pager_enabled(False)
    return [(None, None, None, "Pager disabled.")]


@export
def set_expanded_output(val: bool) -> None:
    global use_expanded_output
    use_expanded_output = val


@export
def is_expanded_output() -> bool:
    return use_expanded_output


@export
def editor_command(command: str) -> bool:
    """
    Is this an external editor command?
    :param command: string
    """
    # It is possible to have `\e filename` or `SELECT * FROM \e`. So we check
    # for both conditions.
    return command.strip().endswith("\\e") or command.strip().startswith("\\e")


@export
def get_filename(sql: str) -> str | None:
    if sql.strip().startswith("\\e"):
        _cmd, _sep, filename = sql.partition(" ")
        return filename.strip() or None
    return None


@export
def get_editor_query(sql: str) -> str:
    """Get the query part of an editor command."""
    sql = sql.strip()

    # The reason we can't simply do .strip('\e') is that it strips characters,
    # not a substring. So it'll strip "e" in the end of the sql also!
    # Ex: "select * from style\e" -> "select * from styl".
    pattern = re.compile(r"(^\\e|\\e$)")
    while pattern.search(sql):
        sql = pattern.sub("", sql)

    return sql


@export
def open_external_editor(filename: str | None = None, sql: str | None = None) -> tuple[str, str | None]:
    """Open external editor, wait for the user to type in their query, return the query."""
    message: str | None = None
    sql = sql or ""
    MARKER = "# Type your query above this line.\n"

    if filename:
        filename = filename.strip().split(" ", 1)[0]
        click.edit(filename=filename)
        try:
            with open(filename, encoding="utf-8") as f:
                text = f.read()
        except IOError:
            message = f"Error reading file: {filename}."
            text = sql
        return (text, message)

    edited = click.edit(f"{sql}\n\n{MARKER}", extension=".sql")
    if edited:
        edited = edited.split(MARKER, 1)[0].rstrip("\n")
    else:
        edited = sql
    return (edited, None)


@special_command(
    "\\f",
    "\\f [name [args..]]",
    "List or execute favorite queries.",
    arg_type=PARSED_QUERY,
    case_sensitive=True,
)
def execute_favorite_query(cur: Any, arg: str, verbose: bool = False, **_: Any) -> Generator[tuple, None, None]:
    """Returns (title, rows, headers, status)"""
    if arg == "":
        for result in list_favorite_queries():
            yield result

    """Parse out favorite name and optional substitution parameters"""
    name, _sep, arg_str = arg.partition(" ")
    args = shlex.split(arg_str)

    query = favoritequeries.get(name)
    if query is None:
        message = "No favorite query: %s" % (name)
        yield (None, None, None, message)
    elif "?" in query:
        for sql in sqlparse.split(query):
            sql = sql.rstrip(";")
            title = "> %s" % (sql) if verbose else None
            cur.execute(sql, args)
            if cur.description:
                headers = [x[0] for x in cur.description]
                yield (title, cur, headers, None)
            else:
                yield (title, None, None, None)
    else:
        query, arg_error = subst_favorite_query_args(query, args)
        if arg_error:
            yield (None, None, None, arg_error)
        else:
            assert query, "query should be non-empty"
            for sql in sqlparse.split(query):
                sql = sql.rstrip(";")
                title = "> %s" % (sql) if verbose else None
                cur.execute(sql)
                if cur.description:
                    headers = [x[0] for x in cur.description]
                    yield (title, cur, headers, None)
                else:
                    yield (title, None, None, None)


def list_favorite_queries() -> list[tuple]:
    """List of all favorite queries.
    Returns (title, rows, headers, status)"""

    headers = ["Name", "Query"]
    rows = [(r, favoritequeries.get(r)) for r in favoritequeries.list()]

    if not rows:
        status = "\nNo favorite queries found." + favoritequeries.usage
    else:
        status = ""
    return [("", rows, headers, status)]


def subst_favorite_query_args(query: str, args: list[str]) -> list[str | None]:
    """Replace positional parameters ($1...$N or ?) in query."""
    for idx, val in enumerate(args):
        shell_subst_var = "$" + str(idx + 1)
        question_subst_var = "?"
        if shell_subst_var in query:
            query = query.replace(shell_subst_var, val)
        elif question_subst_var in query:
            query = query.replace(question_subst_var, val, 1)
        else:
            return [
                None,
                "Too many arguments.\nQuery does not have enough place holders to substitute.\n" + query,
            ]

    match = re.search(r"\?|\$\d+", query)
    if match:
        return [
            None,
            "missing substitution for " + match.group(0) + " in query:\n  " + query,
        ]

    return [query, None]


@special_command("\\fs", "\\fs name query", "Save a favorite query.")
def save_favorite_query(arg: str, **_: Any) -> list[tuple]:
    """Save a new favorite query.
    Returns (title, rows, headers, status)"""

    usage = "Syntax: \\fs name query.\n\n" + favoritequeries.usage
    if not arg:
        return [(None, None, None, usage)]

    name, _sep, query = arg.partition(" ")

    # If either name or query is missing then print the usage and complain.
    if (not name) or (not query):
        return [(None, None, None, usage + "Err: Both name and query are required.")]

    favoritequeries.save(name, query)
    return [(None, None, None, "Saved.")]


@special_command("\\fd", "\\fd [name]", "Delete a favorite query.")
def delete_favorite_query(arg: str, **_: Any) -> list[tuple]:
    """Delete an existing favorite query."""
    usage = "Syntax: \\fd name.\n\n" + favoritequeries.usage
    if not arg:
        return [(None, None, None, usage)]

    status = favoritequeries.delete(arg)

    return [(None, None, None, status)]


@special_command("system", "system [command]", "Execute a system shell command.")
def execute_system_command(arg: str, **_: Any) -> list[tuple]:
    """Execute a system shell command."""
    usage = "Syntax: system [command].\n"

    if not arg:
        return [(None, None, None, usage)]

    try:
        command = arg.strip()
        if command.startswith("cd"):
            ok, error_message = handle_cd_command(arg)
            if not ok:
                return [(None, None, None, error_message)]
            return [(None, None, None, "")]

        args = arg.split(" ")
        process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        output, error = process.communicate()
        raw = output if not error else error
        # Python 3 returns bytes. This needs to be decoded to a string.
        encoding = locale.getpreferredencoding(False)
        response: str = raw.decode(encoding) if isinstance(raw, bytes) else str(raw)

        return [(None, None, None, response)]
    except OSError as e:
        return [(None, None, None, "OSError: %s" % e.strerror)]


def parseargfile(arg: str) -> tuple[str, str]:
    if arg.startswith("-o "):
        mode = "w"
        filename = arg[3:]
    else:
        mode = "a"
        filename = arg

    if not filename:
        raise TypeError("You must provide a filename.")

    return (os.path.expanduser(filename), mode)


@special_command(
    ".output",
    ".output [-o] filename",
    "Append all results to an output file (overwrite using -o).",
    aliases=("tee",),
)
def set_tee(arg: str, **_: Any) -> list[tuple]:
    global tee_file

    try:
        file, mode = parseargfile(arg)
        from typing import cast

        tee_file = cast(TextIO, open(file, mode))
    except (IOError, OSError) as e:
        raise OSError("Cannot write to file '{}': {}".format(e.filename, e.strerror))

    return [(None, None, None, "")]


@export
def close_tee() -> None:
    global tee_file
    if tee_file:
        tee_file.close()
        tee_file = None


@special_command("notee", "notee", "Stop writing results to an output file.")
def no_tee(arg: str, **_: Any) -> list[tuple]:
    close_tee()
    return [(None, None, None, "")]


@export
def write_tee(output: str) -> None:
    global tee_file
    if tee_file:
        click.echo(output, file=tee_file, nl=False)
        click.echo("\n", file=tee_file, nl=False)
        tee_file.flush()


@special_command(
    ".once",
    "\\o [-o] filename",
    "Append next result to an output file (overwrite using -o).",
    aliases=("\\o", "\\once"),
)
def set_once(arg: str, **_: Any) -> list[tuple]:
    global once_file, written_to_once_file
    try:
        file, mode = parseargfile(arg)
        from typing import cast

        once_file = cast(TextIO, open(file, mode))
    except (IOError, OSError) as e:
        raise OSError("Cannot write to file '{}': {}".format(e.filename, e.strerror))
    written_to_once_file = False

    return [(None, None, None, "")]


@export
def write_once(output: str) -> None:
    global once_file, written_to_once_file
    if output and once_file:
        click.echo(output, file=once_file, nl=False)
        click.echo("\n", file=once_file, nl=False)
        once_file.flush()
        written_to_once_file = True


@export
def unset_once_if_written() -> None:
    """Unset the once file, if it has been written to."""
    global once_file, written_to_once_file
    if once_file and written_to_once_file:
        once_file.close()
        once_file = None
        written_to_once_file = False


@special_command(
    "\\pipe_once",
    "\\| command",
    "Send next result to a subprocess.",
    aliases=("\\|",),
)
def set_pipe_once(arg: str, **_: Any) -> list[tuple]:
    global pipe_once_process, written_to_pipe_once_process
    pipe_once_cmd = shlex.split(arg)
    if len(pipe_once_cmd) == 0:
        raise OSError("pipe_once requires a command")
    written_to_pipe_once_process = False
    pipe_once_process = subprocess.Popen(
        pipe_once_cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=1,
        encoding="UTF-8",
        universal_newlines=True,
    )
    return [(None, None, None, "")]


@export
def write_pipe_once(output: str) -> None:
    global pipe_once_process, written_to_pipe_once_process
    if output and pipe_once_process:
        try:
            click.echo(output, file=pipe_once_process.stdin, nl=False)
            click.echo("\n", file=pipe_once_process.stdin, nl=False)
        except (IOError, OSError) as e:
            pipe_once_process.terminate()
            raise OSError("Failed writing to pipe_once subprocess: {}".format(e.strerror))
        written_to_pipe_once_process = True


@export
def unset_pipe_once_if_written() -> None:
    """Unset the pipe_once cmd, if it has been written to."""
    global pipe_once_process, written_to_pipe_once_process
    if written_to_pipe_once_process and pipe_once_process:
        (stdout_data, stderr_data) = pipe_once_process.communicate()
        if len(stdout_data) > 0:
            print(stdout_data.rstrip("\n"))
        if len(stderr_data) > 0:
            print(stderr_data.rstrip("\n"))
        pipe_once_process = None
        written_to_pipe_once_process = False


@special_command(
    "watch",
    "watch [seconds] [-c] query",
    "Executes the query every [seconds] seconds (by default 5).",
)
def watch_query(arg: str, **kwargs: Any) -> Generator[tuple, None, None]:
    usage = """Syntax: watch [seconds] [-c] query.
    * seconds: The interval at the query will be repeated, in seconds.
               By default 5.
    * -c: Clears the screen between every iteration.
"""
    if not arg:
        yield (None, None, None, usage)
        raise StopIteration
    seconds: float = 5.0
    clear_screen = False
    statement = None
    while statement is None:
        arg = arg.strip()
        if not arg:
            # Oops, we parsed all the arguments without finding a statement
            yield (None, None, None, usage)
            raise StopIteration
        (current_arg, _, arg) = arg.partition(" ")
        try:
            seconds = float(current_arg)
            continue
        except ValueError:
            pass
        if current_arg == "-c":
            clear_screen = True
            continue
        statement = "{0!s} {1!s}".format(current_arg, arg)
    destructive_prompt = confirm_destructive_query(statement)
    if destructive_prompt is False:
        click.secho("Wise choice!")
        raise StopIteration
    elif destructive_prompt is True:
        click.secho("Your call!")
    cur = kwargs["cur"]
    sql_list = [(sql.rstrip(";"), "> {0!s}".format(sql)) for sql in sqlparse.split(statement)]
    old_pager_enabled = is_pager_enabled()
    while True:
        if clear_screen:
            click.clear()
        try:
            # Somewhere in the code the pager its activated after every yield,
            # so we disable it in every iteration
            set_pager_enabled(False)
            for sql, title in sql_list:
                cur.execute(sql)
                if cur.description:
                    headers = [x[0] for x in cur.description]
                    yield (title, cur, headers, None)
                else:
                    yield (title, None, None, None)
            sleep(seconds)
        except KeyboardInterrupt:
            # This prints the Ctrl-C character in its own line, which prevents
            # to print a line with the cursor positioned behind the prompt
            click.secho("", nl=True)
            raise StopIteration
        finally:
            set_pager_enabled(old_pager_enabled)
