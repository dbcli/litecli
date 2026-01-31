from __future__ import annotations

import logging
import os.path
from contextlib import closing
from typing import Any, Generator, Iterable, cast
from urllib.parse import urlparse

import sqlparse

try:
    import sqlean as _sqlite3

    _sqlite3.extensions.enable_all()
except ImportError:
    import sqlite3 as _sqlite3

from litecli.packages import special
from litecli.packages.special.utils import check_if_sqlitedotcommand

sqlite3 = cast(Any, _sqlite3)
OperationalError = sqlite3.OperationalError

_logger = logging.getLogger(__name__)

# FIELD_TYPES = decoders.copy()
# FIELD_TYPES.update({
#     FIELD_TYPE.NULL: type(None)
# })


class SQLExecute(object):
    databases_query = """
        PRAGMA database_list
    """

    tables_query = """
        SELECT name
        FROM sqlite_master
        WHERE type IN ('table','view') AND name NOT LIKE 'sqlite_%' AND name NOT LIKE 'sqlean_%'
        ORDER BY 1
    """

    table_columns_query = """
        SELECT m.name as tableName, p.name as columnName
        FROM sqlite_master m
        JOIN pragma_table_info((m.name)) p
        WHERE m.type IN ('table','view') AND m.name NOT LIKE 'sqlite_%' AND m.name NOT LIKE 'sqlean_%'
        ORDER BY tableName, columnName
    """

    indexes_query = """
        SELECT name, sql
        FROM sqlite_master
        WHERE type = 'index' AND name NOT LIKE 'sqlite_%'
        ORDER BY 1
    """

    functions_query = '''SELECT ROUTINE_NAME FROM INFORMATION_SCHEMA.ROUTINES
    WHERE ROUTINE_TYPE="FUNCTION" AND ROUTINE_SCHEMA = "%s"'''

    def __init__(self, database: str | None):
        self.dbname: str | None = database
        self._server_type: tuple[str, str] | None = None
        # Connection can be sqlite3.Connection or sqlean.sqlite3 connection.
        self.conn: Any | None = None
        if not database:
            _logger.debug("Database is not specified. Skip connection.")
            return
        self.connect()

    def connect(self, database: str | None = None) -> None:
        db = database or self.dbname
        _logger.debug("Connection DB Params: \n\tdatabase: %r", db)
        if db is None:
            # Nothing to connect to.
            return

        location = urlparse(db)
        if location.scheme and location.scheme == "file":
            uri = True
            db_name = db
            db_filename = location.path
        else:
            uri = False
            db_filename = db_name = os.path.expanduser(db)
            db_dir_name = os.path.dirname(os.path.abspath(db_filename))
            if not os.path.exists(db_dir_name):
                raise Exception("Path does not exist: {}".format(db_dir_name))

        conn = sqlite3.connect(database=db_name, isolation_level=None, uri=uri)
        conn.text_factory = lambda x: x.decode("utf-8", "backslashreplace")
        if self.conn:
            self.conn.close()

        self.conn = conn
        # Update them after the connection is made to ensure that it was a
        # successful connection.
        self.dbname = db_filename

    def run(self, statement: str) -> Iterable[tuple]:
        """Execute the sql in the database and return the results. The results
        are a list of tuples. Each tuple has 4 values
        (title, rows, headers, status).
        """
        # Remove spaces and EOL
        statement = statement.strip()
        if not statement:  # Empty string
            yield (None, None, None, None)

        # Split the sql into separate queries and run each one.
        # Unless it's saving a favorite query, in which case we
        # want to save them all together.
        if statement.startswith("\\fs"):
            components = [statement]
        else:
            components = sqlparse.split(statement)

        for sql in components:
            # Remove spaces, eol and semi-colons.
            sql = sql.rstrip(";")

            # \G is treated specially since we have to set the expanded output.
            if sql.endswith("\\G"):
                special.set_expanded_output(True)
                sql = sql[:-2].strip()

            if not self.conn and not (
                sql.startswith(".open")
                or sql.lower().startswith("use")
                or sql.startswith("\\u")
                or sql.startswith("\\?")
                or sql.startswith("\\q")
                or sql.startswith("help")
                or sql.startswith("exit")
                or sql.startswith("quit")
            ):
                _logger.debug("Not connected to database. Will not run statement: %s.", sql)
                raise OperationalError("Not connected to database.")
                # yield ('Not connected to database', None, None, None)
                # return

            cur = self.conn.cursor() if self.conn else None
            try:  # Special command
                _logger.debug("Trying a dbspecial command. sql: %r", sql)
                for result in special.execute(cur, sql):
                    yield result
            except special.CommandNotFound:  # Regular SQL
                if check_if_sqlitedotcommand(sql):
                    yield ("dot command not implemented", None, None, None)
                else:
                    _logger.debug("Regular sql statement. sql: %r", sql)
                    assert cur is not None
                    cur.execute(sql)
                    yield self.get_result(cur)

    def get_result(self, cursor: Any) -> tuple[str | None, list | None, list | None, str]:
        """Get the current result's data from the cursor."""
        title = headers = None

        # cursor.description is not None for queries that return result sets,
        # e.g. SELECT.
        if cursor.description is not None:
            headers = [x[0] for x in cursor.description]
            status = "{count} row{s} in set"
            cursor = list(cursor)
            rowcount = len(cursor)
        else:
            _logger.debug("No rows in result.")
            if cursor.rowcount == -1:
                status = "Query OK"
            else:
                status = "Query OK, {count} row{s} affected"
            rowcount = cursor.rowcount
            cursor = None

        status = status.format(count=rowcount, s="" if rowcount == 1 else "s")

        return (title, cursor, headers, status)

    def tables(self) -> Generator[tuple[str], None, None]:
        """Yields table names"""
        if not self.conn:
            return
        with closing(self.conn.cursor()) as cur:
            _logger.debug("Tables Query. sql: %r", self.tables_query)
            cur.execute(self.tables_query)
            for row in cur:
                yield row

    def table_columns(self) -> Generator[tuple[str, str], None, None]:
        """Yields column names"""
        if not self.conn:
            return
        with closing(self.conn.cursor()) as cur:
            _logger.debug("Columns Query. sql: %r", self.table_columns_query)
            cur.execute(self.table_columns_query)
            for row in cur:
                yield row

    def databases(self) -> Generator[str, None, None]:
        if not self.conn:
            return

        with closing(self.conn.cursor()) as cur:
            _logger.debug("Databases Query. sql: %r", self.databases_query)
            for row in cur.execute(self.databases_query):
                yield row[1]

    def functions(self) -> Iterable[tuple]:
        """Yields tuples of (schema_name, function_name)"""
        if not self.conn:
            return
        with closing(self.conn.cursor()) as cur:
            _logger.debug("Functions Query. sql: %r", self.functions_query)
            cur.execute(self.functions_query % self.dbname)
            for row in cur:
                yield row

    def server_type(self) -> tuple[str, str]:
        self._server_type = ("sqlite3", "3")
        return self._server_type
