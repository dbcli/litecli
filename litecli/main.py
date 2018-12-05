from __future__ import unicode_literals
from __future__ import print_function

import os
import sys
import traceback
import logging
import threading
from time import time
from datetime import datetime
from io import open
from collections import namedtuple
from sqlite3 import OperationalError

from cli_helpers.tabular_output import TabularOutputFormatter
from cli_helpers.tabular_output import preprocessors
import click
import sqlparse
from prompt_toolkit.completion import DynamicCompleter
from prompt_toolkit.enums import DEFAULT_BUFFER, EditingMode
from prompt_toolkit.shortcuts import PromptSession, CompleteStyle
from prompt_toolkit.styles.pygments import style_from_pygments_cls
from prompt_toolkit.document import Document
from prompt_toolkit.filters import HasFocus, IsDone
from prompt_toolkit.layout.processors import (
    HighlightMatchingBracketProcessor,
    ConditionalProcessor,
)
from prompt_toolkit.lexers import PygmentsLexer
from prompt_toolkit.history import FileHistory
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory

from .packages.special.main import NO_QUERY
from .packages.prompt_utils import confirm, confirm_destructive_query
from .packages import special
from .sqlcompleter import SQLCompleter
from .clitoolbar import create_toolbar_tokens_func
from .clistyle import style_factory, style_factory_output
from .sqlexecute import SQLExecute
from .clibuffer import cli_is_multiline
from .completion_refresher import CompletionRefresher
from .config import config_location, ensure_dir_exists, get_config
from .key_bindings import cli_bindings
from .encodingutils import utf8tounicode, text_type
from .lexer import LiteCliLexer
from .__init__ import __version__
from .packages.filepaths import dir_path_exists

import itertools

click.disable_unicode_literals_warning = True

# Query tuples are used for maintaining history
Query = namedtuple("Query", ["query", "successful", "mutating"])

PACKAGE_ROOT = os.path.abspath(os.path.dirname(__file__))


class LiteCli(object):

    default_prompt = "\\d> "
    max_len_prompt = 45

    def __init__(
        self,
        sqlexecute=None,
        prompt=None,
        logfile=None,
        auto_vertical_output=False,
        warn=None,
        liteclirc=None,
    ):
        self.sqlexecute = sqlexecute
        self.logfile = logfile

        # Load config.
        c = self.config = get_config(liteclirc)

        self.multi_line = c["main"].as_bool("multi_line")
        self.key_bindings = c["main"]["key_bindings"]
        self.formatter = TabularOutputFormatter(format_name=c["main"]["table_format"])
        self.formatter.litecli = self
        self.syntax_style = c["main"]["syntax_style"]
        self.less_chatty = c["main"].as_bool("less_chatty")
        self.cli_style = c["colors"]
        self.output_style = style_factory_output(self.syntax_style, self.cli_style)
        self.wider_completion_menu = c["main"].as_bool("wider_completion_menu")
        c_dest_warning = c["main"].as_bool("destructive_warning")
        self.destructive_warning = c_dest_warning if warn is None else warn
        self.login_path_as_host = c["main"].as_bool("login_path_as_host")

        # read from cli argument or user config file
        self.auto_vertical_output = auto_vertical_output or c["main"].as_bool(
            "auto_vertical_output"
        )

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

        self.completion_refresher = CompletionRefresher()

        self.logger = logging.getLogger(__name__)
        self.initialize_logging()

        prompt_cnf = self.read_my_cnf_files(["prompt"])["prompt"]
        self.prompt_format = (
            prompt or prompt_cnf or c["main"]["prompt"] or self.default_prompt
        )
        self.prompt_continuation_format = c["main"]["prompt_continuation"]
        keyword_casing = c["main"].get("keyword_casing", "auto")

        self.query_history = []

        # Initialize completer.
        self.completer = SQLCompleter(
            supported_formats=self.formatter.supported_formats,
            keyword_casing=keyword_casing,
        )
        self._completer_lock = threading.Lock()

        # Register custom special commands.
        self.register_special_commands()

        self.prompt_app = None

    def register_special_commands(self):
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
            "tableformat",
            "\\T",
            "Change the table format used to output results.",
            aliases=("\\T",),
            case_sensitive=True,
        )
        special.register_special_command(
            self.execute_from_file,
            "source",
            "\\. filename",
            "Execute commands from file.",
            aliases=("\\.",),
        )
        special.register_special_command(
            self.change_prompt_format,
            "prompt",
            "\\R",
            "Change prompt format.",
            aliases=("\\R",),
            case_sensitive=True,
        )

    def change_table_format(self, arg, **_):
        try:
            self.formatter.format_name = arg
            yield (None, None, None, "Changed table format to {}".format(arg))
        except ValueError:
            msg = "Table format {} not recognized. Allowed formats:".format(arg)
            for table_type in self.formatter.supported_formats:
                msg += "\n\t{}".format(table_type)
            yield (None, None, None, msg)

    def change_db(self, arg, **_):
        if arg is None:
            self.sqlexecute.connect()
        else:
            self.sqlexecute.connect(database=arg)

        self.refresh_completions()
        yield (
            None,
            None,
            None,
            'You are now connected to database "%s"' % (self.sqlexecute.dbname),
        )

    def execute_from_file(self, arg, **_):
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

        return self.sqlexecute.run(query)

    def change_prompt_format(self, arg, **_):
        """
        Change the prompt format.
        """
        if not arg:
            message = "Missing required argument, format."
            return [(None, None, None, message)]

        self.prompt_format = self.get_prompt(arg)
        return [(None, None, None, "Changed prompt format to %s" % arg)]

    def initialize_logging(self):

        log_file = self.config["main"]["log_file"]
        if log_file == "default":
            log_file = config_location() + "log"
        ensure_dir_exists(log_file)

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
            handler = logging.NullHandler()
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

        formatter = logging.Formatter(
            "%(asctime)s (%(process)d/%(threadName)s) "
            "%(name)s %(levelname)s - %(message)s"
        )

        handler.setFormatter(formatter)

        root_logger = logging.getLogger("litecli")
        root_logger.addHandler(handler)
        root_logger.setLevel(level_map[log_level.upper()])

        logging.captureWarnings(True)

        root_logger.debug("Initializing litecli logging.")
        root_logger.debug("Log file %r.", log_file)

    def read_my_cnf_files(self, keys):
        """
        Reads a list of config files and merges them. The last one will win.
        :param files: list of files to read
        :param keys: list of keys to retrieve
        :returns: tuple, with None for missing keys.
        """
        cnf = self.config

        sections = ["client"]

        def get(key):
            result = None
            for sect in cnf:
                if sect in sections and key in cnf[sect]:
                    result = cnf[sect][key]
            return result

        return {x: get(x) for x in keys}

    def connect(self, database=""):

        cnf = {"database": None}

        cnf = self.read_my_cnf_files(cnf.keys())

        # Fall back to config values only if user did not specify a value.

        database = database or cnf["database"]

        # Connect to the database.

        def _connect():
            self.sqlexecute = SQLExecute(database)

        try:
            _connect()
        except Exception as e:  # Connecting to a database could fail.
            self.logger.debug("Database connection failed: %r.", e)
            self.logger.error("traceback: %r", traceback.format_exc())
            self.echo(str(e), err=True, fg="red")
            exit(1)

    def handle_editor_command(self, text):
        """Editor command is any query that is prefixed or suffixed by a '\e'.
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
                    text = self.prompt_app.prompt(default=sql)
                    break
                except KeyboardInterrupt:
                    sql = ""

            continue
        return text

    def run_cli(self):
        iterations = 0
        sqlexecute = self.sqlexecute
        logger = self.logger
        self.configure_pager()
        self.refresh_completions()

        history_file = os.path.expanduser(
            os.environ.get("LITECLI_HISTFILE", "~/.litecli-history")
        )
        if dir_path_exists(history_file):
            history = FileHistory(history_file)
        else:
            history = None
            self.echo(
                'Error: Unable to open the history file "{}". '
                "Your query history will not be saved.".format(history_file),
                err=True,
                fg="red",
            )

        key_bindings = cli_bindings(self)

        if not self.less_chatty:
            print("Version:", __version__)
            print("Mail: https://groups.google.com/forum/#!forum/litecli-users")
            print("Github: https://github.com/dbcli/litecli")
            # print("Home: https://litecli.com")

        def get_message():
            prompt = self.get_prompt(self.prompt_format)
            if (
                self.prompt_format == self.default_prompt
                and len(prompt) > self.max_len_prompt
            ):
                prompt = self.get_prompt("\\d> ")
            return [("class:prompt", prompt)]

        def get_continuation(width, line_number, is_soft_wrap):
            continuation = " " * (width - 1) + " "
            return [("class:continuation", continuation)]

        def show_suggestion_tip():
            return iterations < 2

        def one_iteration(text=None):
            if text is None:
                try:
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

            # Keep track of whether or not the query is mutating. In case
            # of a multi-statement query, the overall query is considered
            # mutating if any one of the component statements is mutating
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
                self.formatter.query = text
                successful = True
                result_count = 0
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
                        max_width = self.prompt_app.output.get_size().columns
                    else:
                        max_width = None

                    formatted = self.format_output(
                        title, cur, headers, special.is_expanded_output(), max_width
                    )

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
                special.unset_once_if_written()
            except EOFError as e:
                raise e
            except KeyboardInterrupt:
                # get last connection id
                connection_id_to_kill = sqlexecute.connection_id
                logger.debug("connection id to kill: %r", connection_id_to_kill)
                # Restart connection to the database
                sqlexecute.connect()
                try:
                    for title, cur, headers, status in sqlexecute.run(
                        "kill %s" % connection_id_to_kill
                    ):
                        status_str = str(status).lower()
                        if status_str.find("ok") > -1:
                            logger.debug(
                                "cancelled query, connection id: %r, sql: %r",
                                connection_id_to_kill,
                                text,
                            )
                            self.echo("cancelled query", err=True, fg="red")
                except Exception as e:
                    self.echo(
                        "Encountered error while cancelling query: {}".format(e),
                        err=True,
                        fg="red",
                    )
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
                    except OperationalError as e:
                        logger.debug("Reconnect failed. e: %r", e)
                        self.echo(str(e), err=True, fg="red")
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
                if is_dropping_database(text, self.sqlexecute.dbname):
                    self.sqlexecute.dbname = None
                    self.sqlexecute.connect()

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

        with self._completer_lock:

            if self.key_bindings == "vi":
                editing_mode = EditingMode.VI
            else:
                editing_mode = EditingMode.EMACS

            self.prompt_app = PromptSession(
                lexer=PygmentsLexer(LiteCliLexer),
                reserve_space_for_menu=self.get_reserved_space(),
                message=get_message,
                prompt_continuation=get_continuation,
                bottom_toolbar=get_toolbar_tokens,
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

        try:
            while True:
                one_iteration()
                iterations += 1
        except EOFError:
            special.close_tee()
            if not self.less_chatty:
                self.echo("Goodbye!")

    def log_output(self, output):
        """Log the output in the audit log, if it's enabled."""
        if self.logfile:
            click.echo(utf8tounicode(output), file=self.logfile)

    def echo(self, s, **kwargs):
        """Print a message to stdout.

        The message will be logged in the audit log, if enabled.

        All keyword arguments are passed to click.echo().

        """
        self.log_output(s)
        click.secho(s, **kwargs)

    def get_output_margin(self, status=None):
        """Get the output margin (number of rows for the prompt, footer and
        timing message."""
        margin = (
            self.get_reserved_space()
            + self.get_prompt(self.prompt_format).count("\n")
            + 2
        )
        if status:
            margin += 1 + status.count("\n")

        return margin

    def output(self, output, status=None):
        """Output text to stdout or a pager command.

        The status text is not outputted to pager or files.

        The message will be logged in the audit log, if enabled. The
        message will be written to the tee file, if enabled. The
        message will be written to the output file, if enabled.

        """
        if output:
            size = self.prompt_app.output.get_size()

            margin = self.get_output_margin(status)

            fits = True
            buf = []
            output_via_pager = self.explicit_pager and special.is_pager_enabled()
            for i, line in enumerate(output, 1):
                self.log_output(line)
                special.write_tee(line)
                special.write_once(line)

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

    def configure_pager(self):
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

    def refresh_completions(self, reset=False):
        if reset:
            with self._completer_lock:
                self.completer.reset_completions()
        self.completion_refresher.refresh(
            self.sqlexecute,
            self._on_completions_refreshed,
            {
                "supported_formats": self.formatter.supported_formats,
                "keyword_casing": self.completer.keyword_casing,
            },
        )

        return [
            (None, None, None, "Auto-completion refresh started in the background.")
        ]

    def _on_completions_refreshed(self, new_completer):
        """Swap the completer object in cli with the newly created completer.
        """
        with self._completer_lock:
            self.completer = new_completer

        if self.prompt_app:
            # After refreshing, redraw the CLI to clear the statusbar
            # "Refreshing completions..." indicator
            self.prompt_app.app.invalidate()

    def get_completions(self, text, cursor_positition):
        with self._completer_lock:
            return self.completer.get_completions(
                Document(text=text, cursor_position=cursor_positition), None
            )

    def get_prompt(self, string):
        self.logger.debug("Getting prompt")
        sqlexecute = self.sqlexecute
        now = datetime.now()
        string = string.replace("\\d", sqlexecute.dbname or "(none)")
        string = string.replace("\\n", "\n")
        string = string.replace("\\D", now.strftime("%a %b %d %H:%M:%S %Y"))
        string = string.replace("\\m", now.strftime("%M"))
        string = string.replace("\\P", now.strftime("%p"))
        string = string.replace("\\R", now.strftime("%H"))
        string = string.replace("\\r", now.strftime("%I"))
        string = string.replace("\\s", now.strftime("%S"))
        string = string.replace("\\_", " ")
        return string

    def run_query(self, query, new_line=True):
        """Runs *query*."""
        results = self.sqlexecute.run(query)
        for result in results:
            title, cur, headers, status = result
            self.formatter.query = query
            output = self.format_output(title, cur, headers)
            for line in output:
                click.echo(line, nl=new_line)

    def format_output(self, title, cur, headers, expanded=False, max_width=None):
        expanded = expanded or self.formatter.format_name == "vertical"
        output = []

        output_kwargs = {
            "dialect": "unix",
            "disable_numparse": True,
            "preserve_whitespace": True,
            "preprocessors": (preprocessors.align_decimals,),
            "style": self.output_style,
        }

        if title:  # Only print the title if it's not None.
            output = itertools.chain(output, [title])

        if cur:
            column_types = None
            if hasattr(cur, "description"):

                def get_col_type(col):
                    # col_type = FIELD_TYPES.get(col[1], text_type)
                    # return col_type if type(col_type) is type else text_type
                    return text_type

                column_types = [get_col_type(col) for col in cur.description]

            if max_width is not None:
                cur = list(cur)

            formatted = self.formatter.format_output(
                cur,
                headers,
                format_name="vertical" if expanded else None,
                column_types=column_types,
                **output_kwargs
            )

            if isinstance(formatted, (text_type)):
                formatted = formatted.splitlines()
            formatted = iter(formatted)

            first_line = next(formatted)
            formatted = itertools.chain([first_line], formatted)

            if (
                not expanded
                and max_width
                and headers
                and cur
                and len(first_line) > max_width
            ):
                formatted = self.formatter.format_output(
                    cur,
                    headers,
                    format_name="vertical",
                    column_types=column_types,
                    **output_kwargs
                )
                if isinstance(formatted, (text_type)):
                    formatted = iter(formatted.splitlines())

            output = itertools.chain(output, formatted)

        return output

    def get_reserved_space(self):
        """Get the number of lines to reserve for the completion menu."""
        reserved_space_ratio = 0.45
        max_reserved_space = 8
        _, height = click.get_terminal_size()
        return min(int(round(height * reserved_space_ratio)), max_reserved_space)

    def get_last_query(self):
        """Get the last query executed or None."""
        return self.query_history[-1][0] if self.query_history else None


@click.command()
@click.option("-V", "--version", is_flag=True, help="Output litecli's version.")
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
@click.option(
    "-t", "--table", is_flag=True, help="Display batch output in table format."
)
@click.option("--csv", is_flag=True, help="Display batch output in CSV format.")
@click.option(
    "--warn/--no-warn", default=None, help="Warn before running a destructive query."
)
@click.option("-e", "--execute", type=str, help="Execute command and quit.")
@click.argument("database", default="", nargs=1)
def cli(
    database,
    dbname,
    version,
    prompt,
    logfile,
    auto_vertical_output,
    table,
    csv,
    warn,
    execute,
    liteclirc,
):
    """A SQLite terminal client with auto-completion and syntax highlighting.

    \b
    Examples:
      - litecli lite_database

    """

    if version:
        print("Version:", __version__)
        sys.exit(0)

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

    litecli.logger.debug("Launch Params: \n" "\tdatabase: %r", database)

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
        except FileNotFoundError:
            litecli.logger.warning("Unable to open TTY as stdin.")

        if (
            litecli.destructive_warning
            and confirm_destructive_query(stdin_text) is False
        ):
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


def need_completion_refresh(queries):
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


def is_dropping_database(queries, dbname):
    """Determine if the query is dropping a specific database."""
    if dbname is None:
        return False

    def normalize_db_name(db):
        return db.lower().strip('`"')

    dbname = normalize_db_name(dbname)

    for query in sqlparse.parse(queries):
        if query.get_name() is None:
            continue

        first_token = query.token_first(skip_cm=True)
        _, second_token = query.token_next(0, skip_cm=True)
        database_name = normalize_db_name(query.get_name())
        if (
            first_token.value.lower() == "drop"
            and second_token.value.lower() in ("database", "schema")
            and database_name == dbname
        ):
            return True


def need_completion_reset(queries):
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


def is_mutating(status):
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


def is_select(status):
    """Returns true if the first word in status is 'select'."""
    if not status:
        return False
    return status.split(None, 1)[0].lower() == "select"


if __name__ == "__main__":
    cli()
