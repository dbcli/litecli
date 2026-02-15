from __future__ import annotations

import csv
import logging
import os
import sys
import platform
import shlex
from typing import Any, cast


from litecli import __version__
from litecli.packages.special import iocommands
from .main import special_command, RAW_QUERY, PARSED_QUERY
from .types import DBCursor

log = logging.getLogger(__name__)


@special_command(
    ".tables",
    "\\dt",
    "List tables.",
    arg_type=PARSED_QUERY,
    case_sensitive=True,
    aliases=("\\dt",),
)
def list_tables(
    cur: DBCursor,
    arg: str | None = None,
    arg_type: int = PARSED_QUERY,
    verbose: bool = False,
) -> list[tuple]:
    if arg:
        args: tuple[str, ...] = ("{0}%".format(arg),)
        query = """
            SELECT name FROM sqlite_master
            WHERE type IN ('table','view') AND name LIKE ? AND name NOT LIKE 'sqlite_%' AND name NOT LIKE 'sqlean_%'
            ORDER BY 1
        """
    else:
        args = tuple()
        query = """
            SELECT name FROM sqlite_master
            WHERE type IN ('table','view') AND name NOT LIKE 'sqlite_%' AND name NOT LIKE 'sqlean_%'
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
    ".views",
    "\\dv",
    "List views.",
    arg_type=PARSED_QUERY,
    case_sensitive=True,
    aliases=("\\dv",),
)
def list_views(
    cur: DBCursor,
    arg: str | None = None,
    arg_type: int = PARSED_QUERY,
    verbose: bool = False,
) -> list[tuple]:
    if arg:
        args: tuple[str, ...] = ("{0}%".format(arg),)
        query = """
            SELECT name FROM sqlite_master
            WHERE type = 'view' AND name LIKE ? AND name NOT LIKE 'sqlite_%' AND name NOT LIKE 'sqlean_%'
            ORDER BY 1
        """
    else:
        args = tuple()
        query = """
            SELECT name FROM sqlite_master
            WHERE type = 'view' AND name NOT LIKE 'sqlite_%' AND name NOT LIKE 'sqlean_%'
            ORDER BY 1
        """
    log.debug(query)
    cur.execute(query, args)
    views = cur.fetchall()
    status = ""
    if cur.description:
        headers = [x[0] for x in cur.description]
    else:
        return [(None, None, None, "")]
    return [(None, views, headers, status)]


@special_command(
    ".schema",
    ".schema[+] [table]",
    "The complete schema for the database or a single table",
    arg_type=PARSED_QUERY,
    case_sensitive=True,
)
def show_schema(cur: DBCursor, arg: str | None = None, **_: Any) -> list[tuple]:
    if arg:
        args: tuple[str, ...] = (arg,)
        query = """
            SELECT sql FROM sqlite_master
            WHERE tbl_name==? AND sql IS NOT NULL
            ORDER BY tbl_name, type DESC, name
        """
    else:
        args = tuple()
        query = """
            SELECT sql FROM sqlite_master
            WHERE sql IS NOT NULL
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
def list_databases(cur: DBCursor, **_: Any) -> list[tuple]:
    query = "PRAGMA database_list"
    log.debug(query)
    cur.execute(query)
    if cur.description:
        headers = [x[0] for x in cur.description]
        return [(None, cur, headers, "")]
    else:
        return [(None, None, None, "")]


@special_command(
    ".indexes",
    ".indexes [tablename]",
    "List indexes.",
    arg_type=PARSED_QUERY,
    case_sensitive=True,
    aliases=("\\di",),
)
def list_indexes(
    cur: DBCursor,
    arg: str | None = None,
    arg_type: int = PARSED_QUERY,
    verbose: bool = False,
) -> list[tuple]:
    if arg:
        args: tuple[str, ...] = ("{0}%".format(arg),)
        query = """
            SELECT name, sql FROM sqlite_master
            WHERE type = 'index' AND tbl_name LIKE ? AND name NOT LIKE 'sqlite_%'
            ORDER BY 1
        """
    else:
        args = tuple()
        query = """
            SELECT name, sql FROM sqlite_master
            WHERE type = 'index' AND name NOT LIKE 'sqlite_%'
            ORDER BY 1
        """

    log.debug(query)
    cur.execute(query, args)
    indexes = cur.fetchall()
    status = ""
    if cur.description:
        headers = [x[0] for x in cur.description]
    else:
        return [(None, None, None, "")]
    return [(None, indexes, headers, status)]


@special_command(
    ".status",
    "\\s",
    "Show current settings.",
    arg_type=RAW_QUERY,
    aliases=("\\s",),
    case_sensitive=True,
)
def status(cur: DBCursor, **_: Any) -> list[tuple]:
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
    row = cur.fetchone()
    db = row[0] if row else ""

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


@special_command(
    ".load",
    ".load path",
    "Load an extension library.",
    arg_type=PARSED_QUERY,
    case_sensitive=True,
)
def load_extension(cur: DBCursor, arg: str, **_: Any) -> None:
    args = shlex.split(arg)
    if len(args) != 1:
        raise TypeError(".load accepts exactly one path")
    path = args[0]
    conn = cur.connection
    conn.enable_load_extension(True)
    conn.load_extension(path)


@special_command(
    "describe",
    "\\d [table]",
    "Description of a table",
    arg_type=PARSED_QUERY,
    case_sensitive=True,
    aliases=("\\d", "desc"),
)
def describe(cur: DBCursor, arg: str | None, **_: Any) -> list[tuple]:
    if arg:
        query = """
            PRAGMA table_info({})
        """.format(arg)
    else:
        return cast(list[tuple[Any, ...]], list_tables(cur))

    log.debug(query)
    cur.execute(query)
    tables = cur.fetchall()
    status = ""
    if cur.description:
        headers = [x[0] for x in cur.description]
    else:
        return [(None, None, None, "")]

    return [(None, tables, headers, status)]


@special_command(
    ".import",
    ".import filename table",
    "Import data from filename into an existing table",
    arg_type=PARSED_QUERY,
    case_sensitive=True,
)
def import_file(cur: DBCursor, arg: str | None = None, **_: Any) -> list[tuple]:
    def split(s: str) -> list[str]:
        # this is a modification of shlex.split function, just to make it support '`',
        # because table name might contain '`' character.
        lex = shlex.shlex(s, posix=True)
        lex.whitespace_split = True
        lex.commenters = ""
        lex.quotes += "`"
        return list(lex)

    if arg is None:
        raise TypeError("Usage: .import filename table")
    args = split(arg)
    log.debug("[arg = %r], [args = %r]", arg, args)
    if len(args) != 2:
        raise TypeError("Usage: .import filename table")

    filename, table = args
    cur.execute('PRAGMA table_info("%s")' % table)
    ncols = len(cur.fetchall())
    insert_tmpl = 'INSERT INTO "%s" VALUES (?%s)' % (table, ",?" * (ncols - 1))

    with open(filename, "r") as csvfile:
        dialect = csv.Sniffer().sniff(csvfile.read(1024))
        csvfile.seek(0)
        reader = csv.reader(csvfile, dialect)

        cur.execute("BEGIN")
        ninserted, nignored = 0, 0
        for i, row in enumerate(reader):
            if len(row) != ncols:
                print(
                    "%s:%d expected %d columns but found %d - ignored" % (filename, i, ncols, len(row)),
                    file=sys.stderr,
                )
                nignored += 1
                continue
            cur.execute(insert_tmpl, row)
            ninserted += 1
        cur.execute("COMMIT")

    status = "Inserted %d rows into %s" % (ninserted, table)
    if nignored > 0:
        status += " (%d rows are ignored)" % nignored
    return [(None, None, None, status)]
