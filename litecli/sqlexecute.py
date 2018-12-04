import logging
import sqlite3
import uuid
from contextlib import closing
from sqlite3 import OperationalError

import sqlparse
import os.path

from .packages import special

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
        WHERE type IN ('table','view') AND name NOT LIKE 'sqlite_%'
        ORDER BY 1
    """

    table_columns_query = """
        SELECT m.name as tableName, p.name as columnName
        FROM sqlite_master m
        LEFT OUTER JOIN pragma_table_info((m.name)) p ON m.name <> p.name
        WHERE m.type IN ('table','view') AND m.name NOT LIKE 'sqlite_%'
        ORDER BY tableName, columnName
    """

    functions_query = '''SELECT ROUTINE_NAME FROM INFORMATION_SCHEMA.ROUTINES
    WHERE ROUTINE_TYPE="FUNCTION" AND ROUTINE_SCHEMA = "%s"'''

    def __init__(self, database):
        self.dbname = database
        self._server_type = None
        self.connection_id = None
        self.conn = None
        if not database:
            _logger.debug("Database is not specified. Skip connection.")
            return
        self.connect()

    def connect(self, database=None):
        db = database or self.dbname
        _logger.debug("Connection DB Params: \n" "\tdatabase: %r", database)

        conn = sqlite3.connect(database=os.path.expanduser(db), isolation_level=None)
        if self.conn:
            self.conn.close()

        self.conn = conn
        # Update them after the connection is made to ensure that it was a
        # successful connection.
        self.dbname = db
        # retrieve connection id
        self.reset_connection_id()

    def run(self, statement):
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
                _logger.debug(
                    "Not connected to database. Will not run statement: %s.", sql
                )
                raise OperationalError("Not connected to database.")
                # yield ('Not connected to database', None, None, None)
                # return

            cur = self.conn.cursor() if self.conn else None
            try:  # Special command
                _logger.debug("Trying a dbspecial command. sql: %r", sql)
                for result in special.execute(cur, sql):
                    yield result
            except special.CommandNotFound:  # Regular SQL
                _logger.debug("Regular sql statement. sql: %r", sql)
                cur.execute(sql)
                yield self.get_result(cur)

    def get_result(self, cursor):
        """Get the current result's data from the cursor."""
        title = headers = None

        # cursor.description is not None for queries that return result sets,
        # e.g. SELECT.
        if cursor.description is not None:
            headers = [x[0] for x in cursor.description]
            status = "{0} row{1} in set"
            cursor = list(cursor)
            rowcount = len(cursor)
        else:
            _logger.debug("No rows in result.")
            status = "Query OK, {0} row{1} affected"
            rowcount = 0 if cursor.rowcount == -1 else cursor.rowcount
            cursor = None

        status = status.format(rowcount, "" if rowcount == 1 else "s")

        return (title, cursor, headers, status)

    def tables(self):
        """Yields table names"""

        with closing(self.conn.cursor()) as cur:
            _logger.debug("Tables Query. sql: %r", self.tables_query)
            cur.execute(self.tables_query)
            for row in cur:
                yield row

    def table_columns(self):
        """Yields column names"""
        with closing(self.conn.cursor()) as cur:
            _logger.debug("Columns Query. sql: %r", self.table_columns_query)
            cur.execute(self.table_columns_query)
            for row in cur:
                yield row

    def databases(self):
        if not self.conn:
            return

        with closing(self.conn.cursor()) as cur:
            _logger.debug("Databases Query. sql: %r", self.databases_query)
            for row in cur.execute(self.databases_query):
                yield row[1]

    def functions(self):
        """Yields tuples of (schema_name, function_name)"""

        with closing(self.conn.cursor()) as cur:
            _logger.debug("Functions Query. sql: %r", self.functions_query)
            cur.execute(self.functions_query % self.dbname)
            for row in cur:
                yield row

    def show_candidates(self):
        with closing(self.conn.cursor()) as cur:
            _logger.debug("Show Query. sql: %r", self.show_candidates_query)
            try:
                cur.execute(self.show_candidates_query)
            except sqlite3.DatabaseError as e:
                _logger.error("No show completions due to %r", e)
                yield ""
            else:
                for row in cur:
                    yield (row[0].split(None, 1)[-1],)

    def server_type(self):
        self._server_type = ("sqlite3", "3")
        return self._server_type

    def get_connection_id(self):
        if not self.connection_id:
            self.reset_connection_id()
        return self.connection_id

    def reset_connection_id(self):
        # Remember current connection id
        _logger.debug("Get current connection id")
        # res = self.run('select connection_id()')
        self.connection_id = uuid.uuid4()
        # for title, cur, headers, status in res:
        #     self.connection_id = cur.fetchone()[0]
        _logger.debug("Current connection id: %s", self.connection_id)
