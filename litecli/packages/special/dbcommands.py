from __future__ import unicode_literals
import logging
import os
import platform
from sqlite3 import ProgrammingError

from litecli import __version__
from litecli.packages.special import iocommands
from litecli.packages.special.utils import format_uptime
from .main import special_command, RAW_QUERY, PARSED_QUERY

log = logging.getLogger(__name__)


@special_command(
    ".tables",
    "\\dt[+] [table]",
    "List or describe tables.",
    arg_type=PARSED_QUERY,
    case_sensitive=True,
    aliases=("\\dt",),
)
def list_tables(cur, arg=None, arg_type=PARSED_QUERY, verbose=False):
    if arg:
        args = ("{0}%".format(arg),)
        query = """
            SELECT name FROM sqlite_master
            WHERE type IN ('table','view') AND name LIKE ? AND name NOT LIKE 'sqlite_%'
            ORDER BY 1
        """
    else:
        args = tuple()
        query = """
            SELECT name FROM sqlite_master
            WHERE type IN ('table','view') AND name NOT LIKE 'sqlite_%'
            ORDER BY 1
        """

    log.debug(query)
    cur.execute(query, args)
    tables = cur.fetchall()
    status = ""
    if cur.description:
        headers = [x[0] for x in cur.description]
    else:
        return [(None, None, None, "")]

    # if verbose and arg:
    #     query = "SELECT sql FROM sqlite_master WHERE name LIKE ?"
    #     log.debug(query)
    #     cur.execute(query)
    #     status = cur.fetchone()[1]

    return [(None, tables, headers, status)]


@special_command(
    ".schema",
    ".schema[+] [table]",
    "The complete schema for the database or a single table",
    arg_type=PARSED_QUERY,
    case_sensitive=True,
    aliases=("\\d",),
)
def show_schema(cur, arg=None, **_):
    if arg:
        args = (arg,)
        query = """
            SELECT sql FROM sqlite_master
            WHERE name==?
            ORDER BY tbl_name, type DESC, name
        """
    else:
        args = tuple()
        query = """
            SELECT sql FROM sqlite_master
            ORDER BY tbl_name, type DESC, name
        """

    log.debug(query)
    cur.execute(query, args)
    tables = cur.fetchall()
    status = ""
    if cur.description:
        headers = [x[0] for x in cur.description]
    else:
        return [(None, None, None, "")]

    return [(None, tables, headers, status)]


@special_command(
    ".databases",
    ".databases",
    "List databases.",
    arg_type=RAW_QUERY,
    case_sensitive=True,
    aliases=("\\l",),
)
def list_databases(cur, **_):
    query = "PRAGMA database_list"
    log.debug(query)
    cur.execute(query)
    if cur.description:
        headers = [x[0] for x in cur.description]
        return [(None, cur, headers, "")]
    else:
        return [(None, None, None, "")]


@special_command(
    ".status",
    "\\s",
    "Show current settings.",
    arg_type=RAW_QUERY,
    aliases=("\\s",),
    case_sensitive=True,
)
def status(cur, **_):
    # Create output buffers.
    footer = []
    footer.append("--------------")

    # Output the litecli client information.
    implementation = platform.python_implementation()
    version = platform.python_version()
    client_info = []
    client_info.append("litecli {0},".format(__version__))
    client_info.append("running on {0} {1}".format(implementation, version))
    footer.append(" ".join(client_info))

    # Build the output that will be displayed as a table.
    query = "SELECT file from pragma_database_list() where name = 'main';"
    log.debug(query)
    cur.execute(query)
    db = cur.fetchone()[0]
    if db is None:
        db = ""

    footer.append("Current database: " + db)
    if iocommands.is_pager_enabled():
        if "PAGER" in os.environ:
            pager = os.environ["PAGER"]
        else:
            pager = "System default"
    else:
        pager = "stdout"
    footer.append("Current pager:" + pager)

    footer.append("--------------")
    return [(None, None, "", "\n".join(footer))]
