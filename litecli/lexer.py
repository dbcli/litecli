from pygments.lexer import inherit
from pygments.lexers.sql import SqliteConsoleLexer
from pygments.token import Keyword


class LiteCliLexer(SqliteConsoleLexer):
    """Extends SQLite lexer to add keywords."""

    tokens = {
        'root': [(r'\brepair\b', Keyword),
                 (r'\boffset\b', Keyword), inherit],
    }
