from __future__ import annotations
import logging
from collections import namedtuple
from enum import Enum
from typing import Any, Callable, cast

from . import export

log = logging.getLogger(__name__)

try:
    import llm  # noqa: F401

    LLM_IMPORTED = True
except ImportError:
    LLM_IMPORTED = False

NO_QUERY = 0
PARSED_QUERY = 1
RAW_QUERY = 2

SpecialCommand = namedtuple(
    "SpecialCommand",
    [
        "handler",
        "command",
        "shortcut",
        "description",
        "arg_type",
        "hidden",
        "case_sensitive",
    ],
)

COMMANDS = {}


@export
class ArgumentMissing(Exception):
    pass


@export
class CommandNotFound(Exception):
    pass


class Verbosity(Enum):
    """Invocation verbosity: succinct (-), normal, or verbose (+)."""

    SUCCINCT = "succinct"
    NORMAL = "normal"
    VERBOSE = "verbose"


@export
def parse_special_command(sql: str) -> tuple[str, "Verbosity", str]:
    """
    Parse a special command, extracting the base command name, verbosity
    (normal, verbose (+), or succinct (-)), and the remaining argument.
    Mirrors the behavior used in similar CLI tools.
    """
    command, _, arg = sql.partition(" ")
    verbosity = Verbosity.NORMAL
    if "+" in command:
        verbosity = Verbosity.VERBOSE
    elif "-" in command:
        verbosity = Verbosity.SUCCINCT
    command = command.strip().strip("+-")
    return (command, verbosity, arg.strip())


@export
def special_command(
    command: str,
    shortcut: str,
    description: str,
    arg_type: int = PARSED_QUERY,
    hidden: bool = False,
    case_sensitive: bool = False,
    aliases: tuple[str, ...] = (),
) -> Callable:
    def wrapper(wrapped: Callable) -> Callable:
        register_special_command(
            wrapped,
            command,
            shortcut,
            description,
            arg_type,
            hidden,
            case_sensitive,
            aliases,
        )
        return wrapped

    return wrapper


@export
def register_special_command(
    handler: Callable,
    command: str,
    shortcut: str,
    description: str,
    arg_type: int = PARSED_QUERY,
    hidden: bool = False,
    case_sensitive: bool = False,
    aliases: tuple[str, ...] = (),
) -> None:
    cmd = command.lower() if not case_sensitive else command
    COMMANDS[cmd] = SpecialCommand(handler, command, shortcut, description, arg_type, hidden, case_sensitive)
    for alias in aliases:
        cmd = alias.lower() if not case_sensitive else alias
        COMMANDS[cmd] = SpecialCommand(
            handler,
            command,
            shortcut,
            description,
            arg_type,
            case_sensitive=case_sensitive,
            hidden=True,
        )


@export
def execute(cur: Any, sql: str) -> list[tuple[Any, ...]]:
    """Execute a special command and return the results. If the special command
    is not supported a KeyError will be raised.
    """
    command, verbosity, arg = parse_special_command(sql)

    if (command not in COMMANDS) and (command.lower() not in COMMANDS):
        raise CommandNotFound

    try:
        special_cmd = COMMANDS[command]
    except KeyError:
        special_cmd = COMMANDS[command.lower()]
        if special_cmd.case_sensitive:
            raise CommandNotFound("Command not found: %s" % command)

    if special_cmd.arg_type == NO_QUERY:
        return cast(list[tuple[Any, ...]], special_cmd.handler())
    elif special_cmd.arg_type == PARSED_QUERY:
        return cast(
            list[tuple[Any, ...]],
            special_cmd.handler(cur=cur, arg=arg, verbose=(verbosity == Verbosity.VERBOSE)),
        )
    elif special_cmd.arg_type == RAW_QUERY:
        return cast(list[tuple[Any, ...]], special_cmd.handler(cur=cur, query=sql))

    raise CommandNotFound(f"Command type not found: {command}")


@special_command("help", "\\?", "Show this help.", arg_type=NO_QUERY, aliases=("\\?", "?"))
def show_help() -> list[tuple]:  # All the parameters are ignored.
    headers = ["Command", "Shortcut", "Description"]
    result = []

    for _, value in sorted(COMMANDS.items()):
        if not value.hidden:
            result.append((value.command, value.shortcut, value.description))
    return [(None, result, headers, None)]


@special_command(".exit", "\\q", "Exit.", arg_type=NO_QUERY, aliases=("\\q", "exit"))
@special_command("quit", "\\q", "Quit.", arg_type=NO_QUERY)
def quit(*_args: Any) -> None:
    raise EOFError


@special_command(
    "\\e",
    "\\e",
    "Edit command with editor (uses $EDITOR).",
    arg_type=NO_QUERY,
    case_sensitive=True,
)
@special_command(
    "\\G",
    "\\G",
    "Display current query results vertically.",
    arg_type=NO_QUERY,
    case_sensitive=True,
)
def stub() -> None:
    raise NotImplementedError


if LLM_IMPORTED:

    @special_command(
        "\\llm",
        "\\ai",
        "Use LLM to construct a SQL query.",
        arg_type=NO_QUERY,
        case_sensitive=False,
        aliases=(".ai", ".llm"),
    )
    def llm_stub() -> None:
        raise NotImplementedError
