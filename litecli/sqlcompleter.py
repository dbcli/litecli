from __future__ import annotations

import logging
from collections import Counter
from re import compile, escape
from typing import Any, Collection, Generator, Iterable, Literal, Sequence

from prompt_toolkit.completion import CompleteEvent, Completer, Completion
from prompt_toolkit.completion.base import Document

from .packages.completion_engine import suggest_type
from .packages.filepaths import complete_path, parse_path, suggest_path
from .packages.parseutils import LAST_WORD_INCLUDE_TYPE, last_word
from .packages.special import llm
from .packages.special.iocommands import favoritequeries

_logger = logging.getLogger(__name__)


class SQLCompleter(Completer):
    keywords: list[str] = [
        "ABORT",
        "ACTION",
        "ADD",
        "AFTER",
        "ALL",
        "ALTER",
        "ANALYZE",
        "AND",
        "AS",
        "ASC",
        "ATTACH",
        "AUTOINCREMENT",
        "BEFORE",
        "BEGIN",
        "BETWEEN",
        "BIGINT",
        "BLOB",
        "BOOLEAN",
        "BY",
        "CASCADE",
        "CASE",
        "CAST",
        "CHARACTER",
        "CHECK",
        "CLOB",
        "COLLATE",
        "COLUMN",
        "COMMIT",
        "CONFLICT",
        "CONSTRAINT",
        "CREATE",
        "CROSS",
        "CURRENT",
        "CURRENT_DATE",
        "CURRENT_TIME",
        "CURRENT_TIMESTAMP",
        "DATABASE",
        "DATE",
        "DATETIME",
        "DECIMAL",
        "DEFAULT",
        "DEFERRABLE",
        "DEFERRED",
        "DELETE",
        "DETACH",
        "DISTINCT",
        "DO",
        "DOUBLE PRECISION",
        "DOUBLE",
        "DROP",
        "EACH",
        "ELSE",
        "END",
        "ESCAPE",
        "EXCEPT",
        "EXCLUSIVE",
        "EXISTS",
        "EXPLAIN",
        "FAIL",
        "FILTER",
        "FLOAT",
        "FOLLOWING",
        "FOR",
        "FOREIGN",
        "FROM",
        "FULL",
        "GLOB",
        "GROUP",
        "HAVING",
        "IF",
        "IGNORE",
        "IMMEDIATE",
        "IN",
        "INDEX",
        "INDEXED",
        "INITIALLY",
        "INNER",
        "INSERT",
        "INSTEAD",
        "INT",
        "INT2",
        "INT8",
        "INTEGER",
        "INTERSECT",
        "INTO",
        "IS",
        "ISNULL",
        "JOIN",
        "KEY",
        "LEFT",
        "LIKE",
        "LIMIT",
        "MATCH",
        "MEDIUMINT",
        "NATIVE CHARACTER",
        "NATURAL",
        "NCHAR",
        "NO",
        "NOT",
        "NOTHING",
        "NULL",
        "NULLS FIRST",
        "NULLS LAST",
        "NUMERIC",
        "NVARCHAR",
        "OF",
        "OFFSET",
        "ON",
        "OR",
        "ORDER BY",
        "OUTER",
        "OVER",
        "PARTITION",
        "PLAN",
        "PRAGMA",
        "PRECEDING",
        "PRIMARY",
        "QUERY",
        "RAISE",
        "RANGE",
        "REAL",
        "RECURSIVE",
        "REFERENCES",
        "REGEXP",
        "REINDEX",
        "RELEASE",
        "RENAME",
        "REPLACE",
        "RESTRICT",
        "RIGHT",
        "ROLLBACK",
        "ROW",
        "ROWS",
        "SAVEPOINT",
        "SELECT",
        "SET",
        "SMALLINT",
        "TABLE",
        "TEMP",
        "TEMPORARY",
        "TEXT",
        "THEN",
        "TINYINT",
        "TO",
        "TRANSACTION",
        "TRIGGER",
        "UNBOUNDED",
        "UNION",
        "UNIQUE",
        "UNSIGNED BIG INT",
        "UPDATE",
        "USING",
        "VACUUM",
        "VALUES",
        "VARCHAR",
        "VARYING CHARACTER",
        "VIEW",
        "VIRTUAL",
        "WHEN",
        "WHERE",
        "WINDOW",
        "WITH",
        "WITHOUT",
    ]

    functions: list[str] = [
        "ABS",
        "AVG",
        "CHANGES",
        "CHAR",
        "COALESCE",
        "COUNT",
        "CUME_DIST",
        "DATE",
        "DATETIME",
        "DENSE_RANK",
        "GLOB",
        "GROUP_CONCAT",
        "HEX",
        "IFNULL",
        "INSTR",
        "JSON",
        "JSON_ARRAY",
        "JSON_ARRAY_LENGTH",
        "JSON_EACH",
        "JSON_EXTRACT",
        "JSON_GROUP_ARRAY",
        "JSON_GROUP_OBJECT",
        "JSON_INSERT",
        "JSON_OBJECT",
        "JSON_PATCH",
        "JSON_QUOTE",
        "JSON_REMOVE",
        "JSON_REPLACE",
        "JSON_SET",
        "JSON_TREE",
        "JSON_TYPE",
        "JSON_VALID",
        "JULIANDAY",
        "LAG",
        "LAST_INSERT_ROWID",
        "LENGTH",
        "LIKELIHOOD",
        "LIKELY",
        "LOAD_EXTENSION",
        "LOWER",
        "LTRIM",
        "MAX",
        "MIN",
        "NTILE",
        "NULLIF",
        "PERCENT_RANK",
        "PRINTF",
        "QUOTE",
        "RANDOM",
        "RANDOMBLOB",
        "RANK",
        "REPLACE",
        "ROUND",
        "ROW_NUMBER",
        "RTRIM",
        "SOUNDEX",
        "SQLITE_COMPILEOPTION_GET",
        "SQLITE_COMPILEOPTION_USED",
        "SQLITE_OFFSET",
        "SQLITE_SOURCE_ID",
        "SQLITE_VERSION",
        "STRFTIME",
        "SUBSTR",
        "SUM",
        "TIME",
        "TOTAL",
        "TOTAL_CHANGES",
        "TRIM",
    ]

    def __init__(self, supported_formats: Iterable[str] = (), keyword_casing: Literal["upper", "lower", "auto"] = "auto"):
        super(self.__class__, self).__init__()
        self.reserved_words: set[str] = set()
        for x in self.keywords:
            self.reserved_words.update(x.split())
        self.name_pattern = compile(r"^[_a-zA-Z][_a-zA-Z0-9\$]*$")

        self.special_commands: list[str] = []
        self.table_formats: list[str] = list(supported_formats)
        if keyword_casing not in ("upper", "lower", "auto"):
            keyword_casing = "auto"
        self.keyword_casing: Literal["upper", "lower", "auto"] = keyword_casing
        self.reset_completions()

    def escape_name(self, name: str) -> str:
        if name and ((not self.name_pattern.match(name)) or (name.upper() in self.reserved_words) or (name.upper() in self.functions)):
            name = "`%s`" % name

        return name

    def unescape_name(self, name: str) -> str:
        """Unquote a string."""
        if name and name[0] == '"' and name[-1] == '"':
            name = name[1:-1]

        return name

    def escaped_names(self, names: Iterable[str]) -> list[str]:
        return [self.escape_name(name) for name in names]

    def extend_special_commands(self, special_commands: Iterable[str]) -> None:
        # Special commands are not part of all_completions since they can only
        # be at the beginning of a line.
        self.special_commands.extend(special_commands)

    def extend_database_names(self, databases: Iterable[str]) -> None:
        self.databases.extend(databases)

    def extend_keywords(self, additional_keywords: Iterable[str]) -> None:
        self.keywords.extend(additional_keywords)
        self.all_completions.update(additional_keywords)

    def extend_schemata(self, schema: str | None) -> None:
        if schema is None:
            return
        metadata = self.dbmetadata["tables"]
        metadata[schema] = {}

        # dbmetadata.values() are the 'tables' and 'functions' dicts
        for metadata in self.dbmetadata.values():
            metadata[schema] = {}
        self.all_completions.update(schema)

    def extend_relations(self, data: Iterable[Sequence[str]], kind: str) -> None:
        """Extend metadata for tables or views

        :param data: list of (rel_name, ) tuples
        :param kind: either 'tables' or 'views'
        :return:
        """
        # 'data' is a generator object. It can throw an exception while being
        # consumed. This could happen if the user has launched the app without
        # specifying a database name. This exception must be handled to prevent
        # crashing.
        try:
            data = [self.escaped_names(d) for d in data]
        except Exception:
            _logger.exception("Failed to get relation names.")
            data = []

        # dbmetadata['tables'][$schema_name][$table_name] should be a list of
        # column names. Default to an asterisk
        metadata = self.dbmetadata[kind]
        for relname in data:
            try:
                metadata[self.dbname][relname[0]] = ["*"]
            except KeyError:
                _logger.error(
                    "%r %r listed in unrecognized schema %r",
                    kind,
                    relname[0],
                    self.dbname,
                )
            self.all_completions.add(relname[0])

    def extend_columns(self, column_data: Iterable[Sequence[str]], kind: str) -> None:
        """Extend column metadata

        :param column_data: list of (rel_name, column_name) tuples
        :param kind: either 'tables' or 'views'
        :return:
        """
        # 'column_data' is a generator object. It can throw an exception while
        # being consumed. This could happen if the user has launched the app
        # without specifying a database name. This exception must be handled to
        # prevent crashing.
        try:
            column_data = [self.escaped_names(d) for d in column_data]
        except Exception:
            _logger.exception("Failed to get column names.")
            column_data = []

        metadata = self.dbmetadata[kind]
        for relname, column in column_data:
            metadata[self.dbname][relname].append(column)
            self.all_completions.add(column)

    def extend_functions(self, func_data: Iterable[Sequence[str]]) -> None:
        # 'func_data' is a generator object. It can throw an exception while
        # being consumed. This could happen if the user has launched the app
        # without specifying a database name. This exception must be handled to
        # prevent crashing.
        try:
            func_data = [self.escaped_names(d) for d in func_data]
        except Exception:
            _logger.exception("Failed to get function names.")
            func_data = []

        # dbmetadata['functions'][$schema_name][$function_name] should return
        # function metadata.
        metadata = self.dbmetadata["functions"]

        for func in func_data:
            metadata[self.dbname][func[0]] = None
            self.all_completions.add(func[0])

    def set_dbname(self, dbname: str | None) -> None:
        self.dbname = dbname

    def reset_completions(self) -> None:
        self.databases: list[str] = []
        self.dbname = ""
        self.dbmetadata: dict[str, Any] = {"tables": {}, "views": {}, "functions": {}}
        self.all_completions: set[str] = set(self.keywords + self.functions)

    @staticmethod
    def find_matches(
        text: str,
        collection: Collection[str],
        start_only: bool = False,
        fuzzy: bool = True,
        casing: str | None = None,
        punctuations: LAST_WORD_INCLUDE_TYPE = "most_punctuations",
    ) -> Generator[Completion, None, None]:
        """Find completion matches for the given text.

        Given the user's input text and a collection of available
        completions, find completions matching the last word of the
        text.

        If `start_only` is True, the text will match an available
        completion only at the beginning. Otherwise, a completion is
        considered a match if the text appears anywhere within it.

        yields prompt_toolkit Completion instances for any matches found
        in the collection of available completions.
        """
        last = last_word(text, include=punctuations)
        text = last.lower()

        completions = []

        if fuzzy:
            regex = ".*?".join(map(escape, text))
            pat = compile("(%s)" % regex)
            for item in sorted(collection):
                r = pat.search(item.lower())
                if r:
                    completions.append((len(r.group()), r.start(), item))
        else:
            match_end_limit = len(text) if start_only else None
            for item in sorted(collection):
                match_point = item.lower().find(text, 0, match_end_limit)
                if match_point >= 0:
                    completions.append((len(text), match_point, item))

        if casing == "auto":
            casing = "lower" if last and last[-1].islower() else "upper"

        def apply_case(kw: str) -> str:
            if casing == "upper":
                return kw.upper()
            return kw.lower()

        return (Completion(z if casing is None else apply_case(z), -len(text)) for x, y, z in sorted(completions))

    def get_completions(
        self,
        document: Document,
        complete_event: CompleteEvent | None,
    ) -> Iterable[Completion]:
        word_before_cursor = document.get_word_before_cursor(WORD=True)
        completions: list[Completion] = []
        suggestions = suggest_type(document.text, document.text_before_cursor)

        for suggestion in suggestions:
            _logger.debug("Suggestion type: %r", suggestion["type"])

            if suggestion["type"] == "column":
                tables = suggestion["tables"]
                _logger.debug("Completion column scope: %r", tables)
                scoped_cols = self.populate_scoped_cols(tables)
                if suggestion.get("drop_unique"):
                    # drop_unique is used for 'tb11 JOIN tbl2 USING (...'
                    # which should suggest only columns that appear in more than
                    # one table
                    scoped_cols = [col for (col, count) in Counter(scoped_cols).items() if count > 1 and col != "*"]

                cols = self.find_matches(word_before_cursor, scoped_cols)
                completions.extend(cols)

            elif suggestion["type"] == "function":
                # suggest user-defined functions using substring matching
                funcs = self.populate_schema_objects(suggestion["schema"], "functions")
                user_funcs = self.find_matches(word_before_cursor, funcs)
                completions.extend(user_funcs)

                # suggest hardcoded functions using startswith matching only if
                # there is no schema qualifier. If a schema qualifier is
                # present it probably denotes a table.
                # eg: SELECT * FROM users u WHERE u.
                if not suggestion["schema"]:
                    predefined_funcs = self.find_matches(
                        word_before_cursor,
                        self.functions,
                        start_only=True,
                        fuzzy=False,
                        casing=self.keyword_casing,
                    )
                    completions.extend(predefined_funcs)

            elif suggestion["type"] == "table":
                table_names = self.populate_schema_objects(suggestion["schema"], "tables")
                table_matches = self.find_matches(word_before_cursor, table_names)
                completions.extend(table_matches)

            elif suggestion["type"] == "view":
                view_names = self.populate_schema_objects(suggestion["schema"], "views")
                view_matches = self.find_matches(word_before_cursor, view_names)
                completions.extend(view_matches)

            elif suggestion["type"] == "alias":
                aliases = suggestion["aliases"]
                alias_matches = self.find_matches(word_before_cursor, aliases)
                completions.extend(alias_matches)

            elif suggestion["type"] == "database":
                dbs = self.find_matches(word_before_cursor, self.databases)
                completions.extend(dbs)

            elif suggestion["type"] == "keyword":
                keywords = self.find_matches(
                    word_before_cursor,
                    self.keywords,
                    start_only=True,
                    fuzzy=False,
                    casing=self.keyword_casing,
                    punctuations="many_punctuations",
                )
                completions.extend(keywords)

            elif suggestion["type"] == "special":
                special = self.find_matches(
                    word_before_cursor,
                    self.special_commands,
                    start_only=True,
                    fuzzy=False,
                    punctuations="many_punctuations",
                )
                completions.extend(special)
            elif suggestion["type"] == "favoritequery":
                queries = self.find_matches(
                    word_before_cursor,
                    favoritequeries.list(),
                    start_only=False,
                    fuzzy=True,
                )
                completions.extend(queries)
            elif suggestion["type"] == "table_format":
                formats = self.find_matches(word_before_cursor, self.table_formats, start_only=True, fuzzy=False)
                completions.extend(formats)
            elif suggestion["type"] == "file_name":
                file_names = self.find_files(word_before_cursor)
                completions.extend(file_names)
            elif suggestion["type"] == "llm":
                if not word_before_cursor:
                    tokens = document.text.split()[1:]
                else:
                    tokens = document.text.split()[1:-1]
                possible_entries = llm.get_completions(tokens)
                subcommands = self.find_matches(
                    word_before_cursor,
                    possible_entries,
                    start_only=False,
                    fuzzy=True,
                )
                completions.extend(subcommands)

        return completions

    def find_files(self, word: str) -> Generator[Completion, None, None]:
        """Yield matching directory or file names.

        :param word:
        :return: iterable

        """
        base_path, last_path, position = parse_path(word)
        paths = suggest_path(word)
        for name in sorted(paths):
            suggestion = complete_path(name, last_path)
            if suggestion:
                yield Completion(suggestion, position)

    def populate_scoped_cols(self, scoped_tbls: list[tuple[str | None, str, str | None]]) -> list[str]:
        """Find all columns in a set of scoped_tables
        :param scoped_tbls: list of (schema, table, alias) tuples
        :return: list of column names
        """
        columns = []
        meta = self.dbmetadata

        for tbl in scoped_tbls:
            # A fully qualified schema.relname reference or default_schema
            # DO NOT escape schema names.
            schema = tbl[0] or self.dbname
            relname = tbl[1]
            escaped_relname = self.escape_name(tbl[1])

            # We don't know if schema.relname is a table or view. Since
            # tables and views cannot share the same name, we can check one
            # at a time
            try:
                columns.extend(meta["tables"][schema][relname])

                # Table exists, so don't bother checking for a view
                continue
            except KeyError:
                try:
                    columns.extend(meta["tables"][schema][escaped_relname])
                    # Table exists, so don't bother checking for a view
                    continue
                except KeyError:
                    pass

            try:
                columns.extend(meta["views"][schema][relname])
            except KeyError:
                pass

        return columns

    def populate_schema_objects(self, schema: str | None, obj_type: str) -> list[str]:
        """Returns list of tables or functions for a (optional) schema"""
        metadata = self.dbmetadata[obj_type]
        schema = schema or self.dbname

        try:
            keys = list(metadata[schema].keys())
        except KeyError:
            # schema doesn't exist
            keys = []

        return keys
