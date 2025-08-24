# coding: utf-8
# mypy: ignore-errors
from __future__ import unicode_literals
import pytest
from unittest.mock import patch
from prompt_toolkit.completion import Completion
from prompt_toolkit.document import Document

metadata = {
    "users": ["id", "email", "first_name", "last_name"],
    "orders": ["id", "ordered_date", "status"],
    "select": ["id", "insert", "ABC"],
    "réveillé": ["id", "insert", "ABC"],
}


@pytest.fixture
def completer():
    import litecli.sqlcompleter as sqlcompleter

    comp = sqlcompleter.SQLCompleter()

    tables, columns = [], []

    for table, cols in metadata.items():
        tables.append((table,))
        columns.extend([(table, col) for col in cols])

    comp.set_dbname("test")
    comp.extend_schemata("test")
    comp.extend_relations(tables, kind="tables")
    comp.extend_columns(columns, kind="tables")

    return comp


@pytest.fixture
def complete_event():
    from unittest.mock import Mock

    return Mock()


def test_escape_name(completer):
    for name, expected_name in [  # Upper case name shouldn't be escaped
        ("BAR", "BAR"),
        # This name is escaped and should start with back tick
        ("2025todos", "`2025todos`"),
        # normal case
        ("people", "people"),
        # table name with _underscore should not be escaped
        ("django_users", "django_users"),
    ]:
        assert completer.escape_name(name) == expected_name


def test_empty_string_completion(completer, complete_event):
    text = ""
    position = 0
    result = list(completer.get_completions(Document(text=text, cursor_position=position), complete_event))
    assert list(map(Completion, sorted(completer.keywords))) == result


def test_select_keyword_completion(completer, complete_event):
    text = "SEL"
    position = len("SEL")
    result = completer.get_completions(Document(text=text, cursor_position=position), complete_event)
    assert list(result) == list([Completion(text="SELECT", start_position=-3)])


def test_table_completion(completer, complete_event):
    text = "SELECT * FROM "
    position = len(text)
    result = completer.get_completions(Document(text=text, cursor_position=position), complete_event)
    assert list(result) == list(
        [
            Completion(text="`réveillé`", start_position=0),
            Completion(text="`select`", start_position=0),
            Completion(text="orders", start_position=0),
            Completion(text="users", start_position=0),
        ]
    )


def test_function_name_completion(completer, complete_event):
    text = "SELECT MA"
    position = len("SELECT MA")
    result = completer.get_completions(Document(text=text, cursor_position=position), complete_event)
    assert list(result) == list(
        [
            Completion(text="MAX", start_position=-2),
            Completion(text="MATCH", start_position=-2),
        ]
    )


def test_suggested_column_names(completer, complete_event):
    """Suggest column and function names when selecting from table.

    :param completer:
    :param complete_event:
    :return:

    """
    text = "SELECT  from users"
    position = len("SELECT ")
    result = list(completer.get_completions(Document(text=text, cursor_position=position), complete_event))
    assert result == list(
        [
            Completion(text="*", start_position=0),
            Completion(text="email", start_position=0),
            Completion(text="first_name", start_position=0),
            Completion(text="id", start_position=0),
            Completion(text="last_name", start_position=0),
        ]
        + list(map(Completion, completer.functions))
        + [Completion(text="users", start_position=0)]
        + list(map(Completion, sorted(completer.keywords)))
    )


def test_suggested_column_names_in_function(completer, complete_event):
    """Suggest column and function names when selecting multiple columns from
    table.

    :param completer:
    :param complete_event:
    :return:

    """
    text = "SELECT MAX( from users"
    position = len("SELECT MAX(")
    result = completer.get_completions(Document(text=text, cursor_position=position), complete_event)
    assert list(result) == list(
        [
            Completion(text="*", start_position=0),
            Completion(text="email", start_position=0),
            Completion(text="first_name", start_position=0),
            Completion(text="id", start_position=0),
            Completion(text="last_name", start_position=0),
        ]
    )


def test_suggested_column_names_with_table_dot(completer, complete_event):
    """Suggest column names on table name and dot.

    :param completer:
    :param complete_event:
    :return:

    """
    text = "SELECT users. from users"
    position = len("SELECT users.")
    result = list(completer.get_completions(Document(text=text, cursor_position=position), complete_event))
    assert result == list(
        [
            Completion(text="*", start_position=0),
            Completion(text="email", start_position=0),
            Completion(text="first_name", start_position=0),
            Completion(text="id", start_position=0),
            Completion(text="last_name", start_position=0),
        ]
    )


def test_suggested_column_names_with_alias(completer, complete_event):
    """Suggest column names on table alias and dot.

    :param completer:
    :param complete_event:
    :return:

    """
    text = "SELECT u. from users u"
    position = len("SELECT u.")
    result = list(completer.get_completions(Document(text=text, cursor_position=position), complete_event))
    assert result == list(
        [
            Completion(text="*", start_position=0),
            Completion(text="email", start_position=0),
            Completion(text="first_name", start_position=0),
            Completion(text="id", start_position=0),
            Completion(text="last_name", start_position=0),
        ]
    )


def test_suggested_multiple_column_names(completer, complete_event):
    """Suggest column and function names when selecting multiple columns from
    table.

    :param completer:
    :param complete_event:
    :return:

    """
    text = "SELECT id,  from users u"
    position = len("SELECT id, ")
    result = list(completer.get_completions(Document(text=text, cursor_position=position), complete_event))
    assert result == list(
        [
            Completion(text="*", start_position=0),
            Completion(text="email", start_position=0),
            Completion(text="first_name", start_position=0),
            Completion(text="id", start_position=0),
            Completion(text="last_name", start_position=0),
        ]
        + list(map(Completion, completer.functions))
        + [Completion(text="u", start_position=0)]
        + list(map(Completion, sorted(completer.keywords)))
    )


def test_suggested_multiple_column_names_with_alias(completer, complete_event):
    """Suggest column names on table alias and dot when selecting multiple
    columns from table.

    :param completer:
    :param complete_event:
    :return:

    """
    text = "SELECT u.id, u. from users u"
    position = len("SELECT u.id, u.")
    result = list(completer.get_completions(Document(text=text, cursor_position=position), complete_event))
    assert result == list(
        [
            Completion(text="*", start_position=0),
            Completion(text="email", start_position=0),
            Completion(text="first_name", start_position=0),
            Completion(text="id", start_position=0),
            Completion(text="last_name", start_position=0),
        ]
    )


def test_suggested_multiple_column_names_with_dot(completer, complete_event):
    """Suggest column names on table names and dot when selecting multiple
    columns from table.

    :param completer:
    :param complete_event:
    :return:

    """
    text = "SELECT users.id, users. from users u"
    position = len("SELECT users.id, users.")
    result = list(completer.get_completions(Document(text=text, cursor_position=position), complete_event))
    assert result == list(
        [
            Completion(text="*", start_position=0),
            Completion(text="email", start_position=0),
            Completion(text="first_name", start_position=0),
            Completion(text="id", start_position=0),
            Completion(text="last_name", start_position=0),
        ]
    )


def test_suggested_aliases_after_on(completer, complete_event):
    text = "SELECT u.name, o.id FROM users u JOIN orders o ON "
    position = len("SELECT u.name, o.id FROM users u JOIN orders o ON ")
    result = list(completer.get_completions(Document(text=text, cursor_position=position), complete_event))
    assert result == list([Completion(text="o", start_position=0), Completion(text="u", start_position=0)])


def test_suggested_aliases_after_on_right_side(completer, complete_event):
    text = "SELECT u.name, o.id FROM users u JOIN orders o ON o.user_id = "
    position = len("SELECT u.name, o.id FROM users u JOIN orders o ON o.user_id = ")
    result = list(completer.get_completions(Document(text=text, cursor_position=position), complete_event))
    assert result == list([Completion(text="o", start_position=0), Completion(text="u", start_position=0)])


def test_suggested_tables_after_on(completer, complete_event):
    text = "SELECT users.name, orders.id FROM users JOIN orders ON "
    position = len("SELECT users.name, orders.id FROM users JOIN orders ON ")
    result = list(completer.get_completions(Document(text=text, cursor_position=position), complete_event))
    assert result == list(
        [
            Completion(text="orders", start_position=0),
            Completion(text="users", start_position=0),
        ]
    )


def test_suggested_tables_after_on_right_side(completer, complete_event):
    text = "SELECT users.name, orders.id FROM users JOIN orders ON orders.user_id = "
    position = len("SELECT users.name, orders.id FROM users JOIN orders ON orders.user_id = ")
    result = list(completer.get_completions(Document(text=text, cursor_position=position), complete_event))
    assert list(result) == list(
        [
            Completion(text="orders", start_position=0),
            Completion(text="users", start_position=0),
        ]
    )


def test_table_names_after_from(completer, complete_event):
    text = "SELECT * FROM "
    position = len("SELECT * FROM ")
    result = list(completer.get_completions(Document(text=text, cursor_position=position), complete_event))
    assert list(result) == list(
        [
            Completion(text="`réveillé`", start_position=0),
            Completion(text="`select`", start_position=0),
            Completion(text="orders", start_position=0),
            Completion(text="users", start_position=0),
        ]
    )


def test_auto_escaped_col_names(completer, complete_event):
    text = "SELECT  from `select`"
    position = len("SELECT ")
    result = list(completer.get_completions(Document(text=text, cursor_position=position), complete_event))
    assert result == [
        Completion(text="*", start_position=0),
        Completion(text="ABC", start_position=0),
        Completion(text="`insert`", start_position=0),
        Completion(text="id", start_position=0),
    ] + list(map(Completion, completer.functions)) + [Completion(text="select", start_position=0)] + list(
        map(Completion, sorted(completer.keywords))
    )


def test_un_escaped_table_names(completer, complete_event):
    text = "SELECT  from réveillé"
    position = len("SELECT ")
    result = list(completer.get_completions(Document(text=text, cursor_position=position), complete_event))
    assert result == list(
        [
            Completion(text="*", start_position=0),
            Completion(text="ABC", start_position=0),
            Completion(text="`insert`", start_position=0),
            Completion(text="id", start_position=0),
        ]
        + list(map(Completion, completer.functions))
        + [Completion(text="réveillé", start_position=0)]
        + list(map(Completion, sorted(completer.keywords)))
    )


def dummy_list_path(dir_name):
    dirs = {
        "/": ["dir1", "file1.sql", "file2.sql"],
        "/dir1": ["subdir1", "subfile1.sql", "subfile2.sql"],
        "/dir1/subdir1": ["lastfile.sql"],
    }
    return dirs.get(dir_name, [])


@patch("litecli.packages.filepaths.list_path", new=dummy_list_path)
@pytest.mark.parametrize(
    "text,expected",
    [
        ("source ", [(".", 0), ("..", 0), ("/", 0), ("~", 0)]),
        ("source /", [("dir1", 0), ("file1.sql", 0), ("file2.sql", 0)]),
        ("source /dir1/", [("subdir1", 0), ("subfile1.sql", 0), ("subfile2.sql", 0)]),
        ("source /dir1/subdir1/", [("lastfile.sql", 0)]),
    ],
)
def test_file_name_completion(completer, complete_event, text, expected):
    position = len(text)
    result = list(completer.get_completions(Document(text=text, cursor_position=position), complete_event))
    expected = list([Completion(txt, pos) for txt, pos in expected])
    assert result == expected
