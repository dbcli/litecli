from __future__ import annotations

import itertools
import logging
import os
import re
import shutil
import sys
import threading
import traceback
from collections import namedtuple
from datetime import datetime
from io import open
from time import time
from typing import Any, Generator, Iterable, cast

import click
import sqlparse
from cli_helpers.tabular_output import TabularOutputFormatter, preprocessors
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.completion import Completion, DynamicCompleter
from prompt_toolkit.document import Document
from prompt_toolkit.enums import DEFAULT_BUFFER, EditingMode
from prompt_toolkit.filters import HasFocus, IsDone
from prompt_toolkit.formatted_text import ANSI
from prompt_toolkit.history import FileHistory
from prompt_toolkit.layout.processors import (
    ConditionalProcessor,
    HighlightMatchingBracketProcessor,
)
from prompt_toolkit.lexers import PygmentsLexer
from prompt_toolkit.shortcuts import CompleteStyle, PromptSession

from .__init__ import __version__
from .clibuffer import cli_is_multiline
from .clistyle import style_factory, style_factory_output
from .clitoolbar import create_toolbar_tokens_func
from .completion_refresher import CompletionRefresher
from .config import config_location, ensure_dir_exists, get_config
from .key_bindings import cli_bindings
from .lexer import LiteCliLexer
from .packages import special
from .packages.filepaths import dir_path_exists
from .packages.prompt_utils import confirm, confirm_destructive_query
from .packages.special.main import NO_QUERY
from .sqlcompleter import SQLCompleter
from .sqlexecute import SQLExecute


def _load_sqlite3() -> Any:
    try:
        import sqlean
    except ImportError:
        import sqlite3

        return sqlite3
    return sqlean


_sqlite3 = _load_sqlite3()
OperationalError = _sqlite3.OperationalError
sqlite_version = _sqlite3.sqlite_version

# Query tuples are used for maintaining history
Query = namedtuple("Query", ["query", "successful", "mutating"])

PACKAGE_ROOT = os.path.abspath(os.path.dirname(__file__))


class LiteCli(object):
    default_prompt = "\\d> "
    max_len_prompt = 45

    def __init__(
        self,
        sqlexecute: SQLExecute | None = None,
        prompt: str | None = None,
        logfile: Any | None = None,
        auto_vertical_output: bool = False,
        warn: bool | None = None,
        liteclirc: str | None = None,
    ) -> None:
        self.sqlexecute = sqlexecute
        self.logfile = logfile

        # Load config.
        c = self.config = get_config(liteclirc)

        self.multi_line = c["main"].as_bool("multi_line")
        self.key_bindings = c["main"]["key_bindings"]
        special.set_favorite_queries(self.config)
        self.formatter = TabularOutputFormatter(format_name=c["main"]["table_format"])
        # self.formatter.litecli = self, ty raises unresolved-attribute, hence use dynamic assignment
        setattr(self.formatter, "litecli", self)
        self.syntax_style = c["main"]["syntax_style"]
        self.less_chatty = c["main"].as_bool("less_chatty")
        self.show_bottom_toolbar = c["main"].as_bool("show_bottom_toolbar")
        self.cli_style = c["colors"]
        self.output_style = style_factory_output(self.syntax_style, self.cli_style)
        self.wider_completion_menu = c["main"].as_bool("wider_completion_menu")
        self.autocompletion = c["main"].as_bool("autocompletion")
        c_dest_warning = c["main"].as_bool("destructive_warning")
        self.destructive_warning = c_dest_warning if warn is None else warn
        self.login_path_as_host = c["main"].as_bool("login_path_as_host")

        # read from cli argument or user config file
        self.auto_vertical_output = auto_vertical_output or c["main"].as_bool("auto_vertical_output")

        # audit log
        if self.logfile is None and "audit_log" in c["main"]:
            try:
                self.logfile = open(os.path.expanduser(c["main"]["audit_log"]), "a")
            except (IOError, OSError):
                self.echo(
                    "Error: Unable to open the audit log file. Your queries will not be logged.",
                    err=True,
                    fg="red",
                )
                self.logfile = False
        # Load startup commands.
        try:
            self.startup_commands = c["startup_commands"]
        except KeyError:  # Redundant given the load_config() function that merges in the standard config, but put here to avoid fail if user do not have updated config file.
            self.startup_commands = None

        self.completion_refresher = CompletionRefresher()

        self.logger = logging.getLogger(__name__)
        self.initialize_logging()

        prompt_cnf = self.read_my_cnf_files(["prompt"])["prompt"]
        self.prompt_format = prompt or prompt_cnf or c["main"]["prompt"] or self.default_prompt
        self.prompt_continuation_format = c["main"]["prompt_continuation"]
        keyword_casing = c["main"].get("keyword_casing", "auto")

        self.query_history: list[Query] = []

        # Initialize completer.
        self.completer = SQLCompleter(
            supported_formats=self.formatter.supported_formats,
            keyword_casing=keyword_casing,
        )
        self._completer_lock = threading.Lock()

        # Register custom special commands.
        self.register_special_commands()

        self.prompt_app: PromptSession | None = None

    def register_special_commands(self) -> None:
        special.register_special_command(
            self.change_db,
            ".open",
            ".open",
            "Change to a new database.",
            aliases=("use", "\\u"),
        )
        special.register_special_command(
            self.refresh_completions,
            "rehash",
            "\\#",
            "Refresh auto-completions.",
            arg_type=NO_QUERY,
            aliases=("\\#",),
        )
        special.register_special_command(
            self.change_table_format,
            ".mode",
            "\\T",
            "Change the table format used to output results.",
            aliases=("tableformat", "\\T"),
            case_sensitive=True,
        )
        special.register_special_command(
            self.execute_from_file,
            ".read",
            "\\. filename",
            "Execute commands from file.",
            case_sensitive=True,
            aliases=("\\.", "source"),
        )
        special.register_special_command(
            self.change_prompt_format,
            "prompt",
            "\\R",
            "Change prompt format.",
            aliases=("\\R",),
            case_sensitive=True,
        )

    def change_table_format(self, arg: str, **_: Any) -> Generator[tuple[None, None, None, str], None, None]:
        try:
            self.formatter.format_name = arg
            yield (None, None, None, "Changed table format to {}".format(arg))
        except ValueError:
            msg = "Table format {} not recognized. Allowed formats:".format(arg)
            for table_type in self.formatter.supported_formats:
                msg += "\n\t{}".format(table_type)
            yield (None, None, None, msg)

    def change_db(self, arg: str | None, **_: Any) -> Iterable[tuple]:
        if arg is None:
            assert self.sqlexecute is not None
            self.sqlexecute.connect()
        else:
            assert self.sqlexecute is not None
            self.sqlexecute.connect(database=arg)

        self.refresh_completions()
        # guard so that ty doesn't complain
        dbname = self.sqlexecute.dbname if self.sqlexecute is not None else ""

        yield (
            None,
            None,
            None,
            'You are now connected to database "%s"' % (dbname),
        )

    def execute_from_file(self, arg: str | None, **_: Any) -> Iterable[tuple[Any, ...]]:
        if not arg:
            message = "Missing required argument, filename."
            return [(None, None, None, message)]
        try:
            with open(os.path.expanduser(arg), encoding="utf-8") as f:
                query = f.read()
        except IOError as e:
            return [(None, None, None, str(e))]

        if self.destructive_warning and confirm_destructive_query(query) is False:
            message = "Wise choice. Command execution stopped."
            return [(None, None, None, message)]

        assert self.sqlexecute is not None
        return cast(Iterable[tuple[Any, ...]], self.sqlexecute.run(query))

    def change_prompt_format(self, arg: str | None, **_: Any) -> Iterable[tuple]:
        """
        Change the prompt format.
        """
        if not arg:
            message = "Missing required argument, format."
            return [(None, None, None, message)]

        self.prompt_format = self.get_prompt(arg)
        return [(None, None, None, "Changed prompt format to %s" % arg)]

    def initialize_logging(self) -> None:
        log_file = self.config["main"]["log_file"]
        if log_file == "default":
            log_file = config_location() + "log"
        try:
            ensure_dir_exists(log_file)
        except OSError:
            # Unable to create log file, log to temp directory instead.
            log_file = "/tmp/litecli.log"

        log_level = self.config["main"]["log_level"]

        level_map = {
            "CRITICAL": logging.CRITICAL,
            "ERROR": logging.ERROR,
            "WARNING": logging.WARNING,
            "INFO": logging.INFO,
            "DEBUG": logging.DEBUG,
        }

        # Disable logging if value is NONE by switching to a no-op handler
        # Set log level to a high value so it doesn't even waste cycles getting called.
        if log_level.upper() == "NONE":
            handler: logging.Handler = logging.NullHandler()
            log_level = "CRITICAL"
        elif dir_path_exists(log_file):
            handler = logging.FileHandler(log_file)
        else:
            self.echo(
                'Error: Unable to open the log file "{}".'.format(log_file),
                err=True,
                fg="red",
            )
            return

        formatter = logging.Formatter("%(asctime)s (%(process)d/%(threadName)s) %(name)s %(levelname)s - %(message)s")

        handler.setFormatter(formatter)

        root_logger = logging.getLogger("litecli")
        root_logger.addHandler(handler)
        root_logger.setLevel(level_map[log_level.upper()])

        logging.captureWarnings(True)

        root_logger.debug("Initializing litecli logging.")
        root_logger.debug("Log file %r.", log_file)

    def read_my_cnf_files(self, keys: Iterable[str]) -> dict[str, str | None]:
        """
        Reads a list of config files and merges them. The last one will win.
        :param files: list of files to read
        :param keys: list of keys to retrieve
        :returns: tuple, with None for missing keys.
        """
        cnf = self.config

        sections = ["main"]

        def get(key: str) -> str | None:
            result = None
            for sect in cnf:
                if sect in sections and key in cnf[sect]:
                    result = cnf[sect][key]
            return result

        return {x: get(x) for x in keys}

    def connect(self, database: str | None = "") -> None:
        cnf: dict[str, str | None] = {"database": None}

        cnf = self.read_my_cnf_files(cnf.keys())

        # Fall back to config values only if user did not specify a value.

        db_value: str | None = database or cnf["database"]

        # Connect to the database.

        def _connect() -> None:
            self.sqlexecute = SQLExecute(db_value)

        try:
            _connect()
        except Exception as e:  # Connecting to a database could fail.
            self.logger.debug("Database connection failed: %r.", e)
            self.logger.error("traceback: %r", traceback.format_exc())
            self.echo(str(e), err=True, fg="red")
            exit(1)

    def handle_editor_command(self, text: str) -> str:
        R"""Editor command is any query that is prefixed or suffixed by a '\e'.
        The reason for a while loop is because a user might edit a query
        multiple times. For eg:

        "select * from \e"<enter> to edit it in vim, then come
        back to the prompt with the edited query "select * from
        blah where q = 'abc'\e" to edit it again.
        :param text: Document
        :return: Document

        """

        while special.editor_command(text):
            filename = special.get_filename(text)
            query = special.get_editor_query(text) or self.get_last_query()
            sql, message = special.open_external_editor(filename, sql=query)
            if message:
                # Something went wrong. Raise an exception and bail.
                raise RuntimeError(message)
            while True:
                try:
                    assert self.prompt_app is not None
                    text = self.prompt_app.prompt(default=sql)
                    break
                except KeyboardInterrupt:
                    sql = ""

            continue
        return text

    def run_cli(self) -> None:
        iterations = 0
        sqlexecute = self.sqlexecute
        assert sqlexecute is not None
        logger = self.logger
        self.configure_pager()
        self.refresh_completions()

        history_file = self.config["main"]["history_file"]
        if history_file == "default":
            history_file = config_location() + "history"
        history_file = os.path.expanduser(history_file)
        if dir_path_exists(history_file):
            history = FileHistory(history_file)
        else:
            history = None
            self.echo(
                'Error: Unable to open the history file "{}". Your query history will not be saved.'.format(history_file),
                err=True,
                fg="red",
            )

        key_bindings = cli_bindings(self)

        if not self.less_chatty:
            print(f"LiteCli: {__version__} (SQLite: {sqlite_version})")
            print("GitHub: https://github.com/dbcli/litecli")

        def get_message() -> ANSI:
            prompt = self.get_prompt(self.prompt_format)
            if self.prompt_format == self.default_prompt and len(prompt) > self.max_len_prompt:
                prompt = self.get_prompt("\\d> ")
            prompt = prompt.replace("\\x1b", "\x1b")
            return ANSI(prompt)

        def get_continuation(width: int, line_number: int, is_soft_wrap: int) -> list[tuple[str, str]]:
            continuation = " " * (width - 1) + " "
            return [("class:continuation", continuation)]

        def show_suggestion_tip() -> bool:
            return iterations < 2

        def output_res(res: Iterable[tuple[Any, Any, Any, str | None]], start: float) -> bool:
            result_count = 0
            mutating = False
            for title, cur, headers, status in res:
                logger.debug("headers: %r", headers)
                logger.debug("rows: %r", cur)
                logger.debug("status: %r", status)
                threshold = 1000
                if is_select(status) and cur and cur.rowcount > threshold:
                    self.echo(
                        "The result set has more than {} rows.".format(threshold),
                        fg="red",
                    )
                    if not confirm("Do you want to continue?"):
                        self.echo("Aborted!", err=True, fg="red")
                        break

                if self.auto_vertical_output:
                    assert self.prompt_app is not None
                    max_width = self.prompt_app.output.get_size().columns
                else:
                    max_width = None

                formatted = self.format_output(title, cur, headers, special.is_expanded_output(), max_width)

                t = time() - start
                try:
                    if result_count > 0:
                        self.echo("")
                    try:
                        self.output(formatted, status)
                    except KeyboardInterrupt:
                        pass
                    self.echo("Time: %0.03fs" % t)
                except KeyboardInterrupt:
                    pass

                start = time()
                result_count += 1
                mutating = mutating or is_mutating(status)
            return mutating

        def one_iteration(text: str | None = None) -> None:
            if text is None:
                try:
                    assert self.prompt_app is not None
                    text = self.prompt_app.prompt()
                except KeyboardInterrupt:
                    return

                special.set_expanded_output(False)

                try:
                    text = self.handle_editor_command(text)
                except RuntimeError as e:
                    logger.error("sql: %r, error: %r", text, e)
                    logger.error("traceback: %r", traceback.format_exc())
                    self.echo(str(e), err=True, fg="red")
                    return

                while special.is_llm_command(text):
                    try:
                        start = time()
                        assert self.sqlexecute is not None
                        cur = self.sqlexecute.conn and self.sqlexecute.conn.cursor()
                        context, sql, duration = special.handle_llm(text, cur)
                        if context:
                            click.echo("LLM Reponse:")
                            click.echo(context)
                            click.echo("---")
                        click.echo(f"Time: {duration:.2f} seconds")
                        assert self.prompt_app is not None
                        text = self.prompt_app.prompt(default=sql)
                    except KeyboardInterrupt:
                        return
                    except special.FinishIteration as e:
                        if e.results:
                            output_res(e.results, start)
                        return
                    except RuntimeError as e:
                        logger.error("sql: %r, error: %r", text, e)
                        logger.error("traceback: %r", traceback.format_exc())
                        self.echo(str(e), err=True, fg="red")
                        return

            if not text.strip():
                return

            if self.destructive_warning:
                destroy = confirm_destructive_query(text)
                if destroy is None:
                    pass  # Query was not destructive. Nothing to do here.
                elif destroy is True:
                    self.echo("Your call!")
                else:
                    self.echo("Wise choice!")
                    return

            mutating = False

            try:
                logger.debug("sql: %r", text)

                special.write_tee(self.get_prompt(self.prompt_format) + text)
                if self.logfile:
                    self.logfile.write("\n# %s\n" % datetime.now())
                    self.logfile.write(text)
                    self.logfile.write("\n")

                successful = False
                start = time()
                res = sqlexecute.run(text)
                # Set query attribute dynamically on formatter
                setattr(self.formatter, "query", text)
                successful = True
                special.unset_once_if_written()
                # Keep track of whether or not the query is mutating. In case
                # of a multi-statement query, the overall query is considered
                # mutating if any one of the component statements is mutating
                mutating = output_res(res, start)
                special.unset_pipe_once_if_written()
            except EOFError as e:
                raise e
            except KeyboardInterrupt:
                try:
                    # since connection can be sqlite3 or sqlean, it's hard to annotate the type for interrupt. so ignore the type hint warning.
                    sqlexecute.conn.interrupt()  # type: ignore[attr-defined]
                except Exception as e:
                    self.echo(
                        "Encountered error while cancelling query: {}".format(e),
                        err=True,
                        fg="red",
                    )
                else:
                    logger.debug("cancelled query")
                    self.echo("cancelled query", err=True, fg="red")
            except NotImplementedError:
                self.echo("Not Yet Implemented.", fg="yellow")
            except OperationalError as e:
                logger.debug("Exception: %r", e)
                if e.args[0] in (2003, 2006, 2013):
                    logger.debug("Attempting to reconnect.")
                    self.echo("Reconnecting...", fg="yellow")
                    try:
                        sqlexecute.connect()
                        logger.debug("Reconnected successfully.")
                        one_iteration(text)
                        return  # OK to just return, cuz the recursion call runs to the end.
                    except OperationalError as ex:
                        logger.debug("Reconnect failed. e: %r", ex)
                        self.echo(str(ex), err=True, fg="red")
                        # If reconnection failed, don't proceed further.
                        return
                else:
                    logger.error("sql: %r, error: %r", text, e)
                    logger.error("traceback: %r", traceback.format_exc())
                    self.echo(str(e), err=True, fg="red")
            except Exception as e:
                logger.error("sql: %r, error: %r", text, e)
                logger.error("traceback: %r", traceback.format_exc())
                self.echo(str(e), err=True, fg="red")
            else:
                # Refresh the table names and column names if necessary.
                if need_completion_refresh(text):
                    self.refresh_completions(reset=need_completion_reset(text))
            finally:
                if self.logfile is False:
                    self.echo("Warning: This query was not logged.", err=True, fg="red")
            query = Query(text, successful, mutating)
            self.query_history.append(query)

        get_toolbar_tokens = create_toolbar_tokens_func(self, show_suggestion_tip)

        if self.wider_completion_menu:
            complete_style = CompleteStyle.MULTI_COLUMN
        else:
            complete_style = CompleteStyle.COLUMN

        if not self.autocompletion:
            complete_style = CompleteStyle.READLINE_LIKE

        with self._completer_lock:
            if self.key_bindings == "vi":
                editing_mode = EditingMode.VI
            else:
                editing_mode = EditingMode.EMACS

            self.prompt_app = PromptSession(
                lexer=PygmentsLexer(LiteCliLexer),
                reserve_space_for_menu=self.get_reserved_space(),
                message=get_message,
                prompt_continuation=cast(Any, get_continuation),
                bottom_toolbar=get_toolbar_tokens if self.show_bottom_toolbar else None,
                complete_style=complete_style,
                input_processors=[
                    ConditionalProcessor(
                        processor=HighlightMatchingBracketProcessor(chars="[](){}"),
                        filter=HasFocus(DEFAULT_BUFFER) & ~IsDone(),
                    )
                ],
                tempfile_suffix=".sql",
                completer=DynamicCompleter(lambda: self.completer),
                history=history,
                auto_suggest=AutoSuggestFromHistory(),
                complete_while_typing=True,
                multiline=cli_is_multiline(self),
                style=style_factory(self.syntax_style, self.cli_style),
                include_default_pygments_style=False,
                key_bindings=key_bindings,
                enable_open_in_editor=True,
                enable_system_prompt=True,
                enable_suspend=True,
                editing_mode=editing_mode,
                search_ignore_case=True,
            )

        def startup_commands() -> None:
            if self.startup_commands:
                if "commands" in self.startup_commands:
                    if isinstance(self.startup_commands["commands"], str):
                        commands = [self.startup_commands["commands"]]
                    else:
                        commands = self.startup_commands["commands"]
                    for command in commands:
                        try:
                            res = sqlexecute.run(command)
                        except Exception as e:
                            click.echo(command)
                            self.echo(str(e), err=True, fg="red")
                        else:
                            click.echo(command)
                            for title, cur, headers, status in res:
                                if title == "dot command not implemented":
                                    self.echo(
                                        "The SQLite dot command '" + command.split(" ", 1)[0] + "' is not yet implemented.",
                                        fg="yellow",
                                    )
                                else:
                                    output = self.format_output(title, cur, headers)
                                    for line in output:
                                        self.echo(line)
                else:
                    self.echo(
                        "Could not read commands. The startup commands needs to be formatted as: \n commands = 'command1', 'command2', ...",
                        fg="yellow",
                    )

        try:
            startup_commands()
        except Exception as e:
            self.echo("Could not execute all startup commands: \n" + str(e), fg="yellow")

        try:
            while True:
                one_iteration()
                iterations += 1
        except EOFError:
            special.close_tee()
            if not self.less_chatty:
                self.echo("Goodbye!")

    def log_output(self, output: str) -> None:
        """Log the output in the audit log, if it's enabled."""
        if self.logfile:
            click.echo(output, file=self.logfile)

    def echo(self, s: str, **kwargs: Any) -> None:
        """Print a message to stdout.

        The message will be logged in the audit log, if enabled.

        All keyword arguments are passed to click.echo().

        """
        self.log_output(s)
        click.secho(s, **kwargs)

    def get_output_margin(self, status: str | None = None) -> int:
        """Get the output margin (number of rows for the prompt, footer and
        timing message."""
        margin = self.get_reserved_space() + self.get_prompt(self.prompt_format).count("\n") + 2
        if status:
            margin += 1 + status.count("\n")

        return margin

    def output(self, output: Iterable[str], status: str | None = None) -> None:
        """Output text to stdout or a pager command.

        The status text is not outputted to pager or files.

        The message will be logged in the audit log, if enabled. The
        message will be written to the tee file, if enabled. The
        message will be written to the output file, if enabled.

        """
        if output:
            assert self.prompt_app is not None
            size = self.prompt_app.output.get_size()

            margin = self.get_output_margin(status)

            fits = True
            buf = []
            output_via_pager = self.explicit_pager and special.is_pager_enabled()
            for i, line in enumerate(output, 1):
                self.log_output(line)
                special.write_tee(line)
                special.write_once(line)
                special.write_pipe_once(line)

                if fits or output_via_pager:
                    # buffering
                    buf.append(line)
                    if len(line) > size.columns or i > (size.rows - margin):
                        fits = False
                        if not self.explicit_pager and special.is_pager_enabled():
                            # doesn't fit, use pager
                            output_via_pager = True

                        if not output_via_pager:
                            # doesn't fit, flush buffer
                            for line in buf:
                                click.secho(line)
                            buf = []
                else:
                    click.secho(line)

            if buf:
                if output_via_pager:
                    # sadly click.echo_via_pager doesn't accept generators
                    click.echo_via_pager("\n".join(buf))
                else:
                    for line in buf:
                        click.secho(line)

        if status:
            self.log_output(status)
            click.secho(status)

    def configure_pager(self) -> None:
        # Provide sane defaults for less if they are empty.
        if not os.environ.get("LESS"):
            os.environ["LESS"] = "-RXF"

        cnf = self.read_my_cnf_files(["pager", "skip-pager"])
        if cnf["pager"]:
            special.set_pager(cnf["pager"])
            self.explicit_pager = True
        else:
            self.explicit_pager = False

        if cnf["skip-pager"] or not self.config["main"].as_bool("enable_pager"):
            special.disable_pager()

    def refresh_completions(self, reset: bool = False) -> list[tuple]:
        if reset:
            with self._completer_lock:
                self.completer.reset_completions()
        assert self.sqlexecute is not None
        self.completion_refresher.refresh(
            self.sqlexecute,
            self._on_completions_refreshed,
            {
                "supported_formats": self.formatter.supported_formats,
                "keyword_casing": self.completer.keyword_casing,
            },
        )

        return [(None, None, None, "Auto-completion refresh started in the background.")]

    def _on_completions_refreshed(self, new_completer: SQLCompleter) -> None:
        """Swap the completer object in cli with the newly created completer."""
        with self._completer_lock:
            self.completer = new_completer

        if self.prompt_app:
            # After refreshing, redraw the CLI to clear the statusbar
            # "Refreshing completions..." indicator
            self.prompt_app.app.invalidate()

    def get_completions(self, text: str, cursor_positition: int) -> Iterable[Completion]:
        with self._completer_lock:
            return cast(Iterable[Completion], self.completer.get_completions(Document(text=text, cursor_position=cursor_positition), None))

    def get_prompt(self, string: str) -> str:
        self.logger.debug("Getting prompt %r", string)
        sqlexecute = self.sqlexecute
        assert sqlexecute is not None
        now = datetime.now()

        # Prepare the replacements dictionary
        replacements = {
            r"\d": sqlexecute.dbname or "(none)",
            r"\f": os.path.basename(sqlexecute.dbname or "(none)"),
            r"\n": "\n",
            r"\D": now.strftime("%a %b %d %H:%M:%S %Y"),
            r"\m": now.strftime("%M"),
            r"\P": now.strftime("%p"),
            r"\R": now.strftime("%H"),
            r"\r": now.strftime("%I"),
            r"\s": now.strftime("%S"),
            r"\_": " ",
        }
        # Compile a regex pattern that matches any of the keys in replacements
        pattern = re.compile("|".join(re.escape(key) for key in replacements.keys()))

        # Define the replacement function
        def replacer(match: re.Match[str]) -> str:
            return replacements[match.group(0)]

        # Perform the substitution
        return pattern.sub(replacer, string)

    def run_query(self, query: str, new_line: bool = True) -> None:
        """Runs *query*."""
        assert self.sqlexecute is not None
        results = self.sqlexecute.run(query)
        for result in results:
            title, cur, headers, status = result
            setattr(self.formatter, "query", query)
            output = self.format_output(title, cur, headers)
            for line in output:
                click.echo(line, nl=new_line)

    def format_output(self, title: Any, cur: Any, headers: Any, expanded: bool = False, max_width: int | None = None) -> Iterable[str]:
        expanded = expanded or self.formatter.format_name == "vertical"
        output_iter: Iterable[str] = []

        output_kwargs = {
            "dialect": "unix",
            "disable_numparse": True,
            "preserve_whitespace": True,
            "preprocessors": (preprocessors.align_decimals,),
            "style": self.output_style,
        }

        if title:  # Only print the title if it's not None.
            output_iter = itertools.chain(output_iter, [title])

        if cur:
            column_types = None
            if hasattr(cur, "description"):
                column_types = [str(col) for col in cur.description]

            if max_width is not None:
                cur = list(cur)

            formatted = self.formatter.format_output(
                cur,
                headers,
                format_name="vertical" if expanded else None,
                column_types=column_types,
                **output_kwargs,
            )

            if isinstance(formatted, str):
                formatted = formatted.splitlines()
            formatted = iter(formatted)

            first_line = next(formatted)
            formatted = itertools.chain([first_line], formatted)

            if not expanded and max_width and headers and cur and len(first_line) > max_width:
                formatted = self.formatter.format_output(
                    cur,
                    headers,
                    format_name="vertical",
                    column_types=column_types,
                    **output_kwargs,
                )
                if isinstance(formatted, str):
                    formatted = iter(formatted.splitlines())

            output_iter = itertools.chain(output_iter, formatted)

        return output_iter

    def get_reserved_space(self) -> int:
        """Get the number of lines to reserve for the completion menu."""
        reserved_space_ratio = 0.45
        max_reserved_space = 8
        _, height = shutil.get_terminal_size()
        return min(int(round(height * reserved_space_ratio)), max_reserved_space)

    def get_last_query(self) -> str | None:
        """Get the last query executed or None."""
        return self.query_history[-1][0] if self.query_history else None


@click.command()
@click.version_option(__version__, "-V", "--version")
@click.option("-D", "--database", "dbname", help="Database to use.")
@click.option(
    "-R",
    "--prompt",
    "prompt",
    help='Prompt format (Default: "{0}").'.format(LiteCli.default_prompt),
)
@click.option(
    "-l",
    "--logfile",
    type=click.File(mode="a", encoding="utf-8"),
    help="Log every query and its results to a file.",
)
@click.option(
    "--liteclirc",
    default=config_location() + "config",
    help="Location of liteclirc file.",
    type=click.Path(dir_okay=False),
)
@click.option(
    "--auto-vertical-output",
    is_flag=True,
    help="Automatically switch to vertical output mode if the result is wider than the terminal width.",
)
@click.option("-t", "--table", is_flag=True, help="Display batch output in table format.")
@click.option("--csv", is_flag=True, help="Display batch output in CSV format.")
@click.option("--warn/--no-warn", default=None, help="Warn before running a destructive query.")
@click.option("-e", "--execute", type=str, help="Execute command and quit.")
@click.argument("database", default="", nargs=1)
def cli(
    database: str,
    dbname: str,
    prompt: str | None,
    logfile: Any | None,
    auto_vertical_output: bool,
    table: bool,
    csv: bool,
    warn: bool | None,
    execute: str | None,
    liteclirc: str,
) -> None:
    """A SQLite terminal client with auto-completion and syntax highlighting.

    \b
    Examples:
      - litecli lite_database

    """
    litecli = LiteCli(
        prompt=prompt,
        logfile=logfile,
        auto_vertical_output=auto_vertical_output,
        warn=warn,
        liteclirc=liteclirc,
    )

    # Choose which ever one has a valid value.
    database = database or dbname

    litecli.connect(database)

    litecli.logger.debug("Launch Params: \n\tdatabase: %r", database)

    #  --execute argument
    if execute:
        try:
            if csv:
                litecli.formatter.format_name = "csv"
            elif not table:
                litecli.formatter.format_name = "tsv"

            litecli.run_query(execute)
            exit(0)
        except Exception as e:
            click.secho(str(e), err=True, fg="red")
            exit(1)

    if sys.stdin.isatty():
        litecli.run_cli()
    else:
        stdin = click.get_text_stream("stdin")
        stdin_text = stdin.read()

        try:
            sys.stdin = open("/dev/tty")
        except (FileNotFoundError, OSError):
            litecli.logger.warning("Unable to open TTY as stdin.")

        if litecli.destructive_warning and confirm_destructive_query(stdin_text) is False:
            exit(0)
        try:
            new_line = True

            if csv:
                litecli.formatter.format_name = "csv"
            elif not table:
                litecli.formatter.format_name = "tsv"

            litecli.run_query(stdin_text, new_line=new_line)
            exit(0)
        except Exception as e:
            click.secho(str(e), err=True, fg="red")
            exit(1)


def need_completion_refresh(queries: str) -> bool:
    """Determines if the completion needs a refresh by checking if the sql
    statement is an alter, create, drop or change db."""
    for query in sqlparse.split(queries):
        try:
            first_token = query.split()[0]
            if first_token.lower() in (
                "alter",
                "create",
                "use",
                "\\r",
                "\\u",
                "connect",
                "drop",
            ):
                return True
        except Exception:
            return False
    return False


def need_completion_reset(queries: str) -> bool:
    """Determines if the statement is a database switch such as 'use' or '\\u'.
    When a database is changed the existing completions must be reset before we
    start the completion refresh for the new database.
    """
    for query in sqlparse.split(queries):
        try:
            first_token = query.split()[0]
            if first_token.lower() in ("use", "\\u"):
                return True
        except Exception:
            return False
    return False


def is_mutating(status: str | None) -> bool:
    """Determines if the statement is mutating based on the status."""
    if not status:
        return False

    mutating = set(
        [
            "insert",
            "update",
            "delete",
            "alter",
            "create",
            "drop",
            "replace",
            "truncate",
            "load",
        ]
    )
    return status.split(None, 1)[0].lower() in mutating


def is_select(status: str | None) -> bool:
    """Returns true if the first word in status is 'select'."""
    if not status:
        return False
    return status.split(None, 1)[0].lower() == "select"


if __name__ == "__main__":
    cli()
