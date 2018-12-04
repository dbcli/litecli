# coding=UTF-8

import os

import pytest

from utils import run, dbtest, set_expanded_output, is_expanded_output
from sqlite3 import OperationalError


def assert_result_equal(
    result,
    title=None,
    rows=None,
    headers=None,
    status=None,
    auto_status=True,
    assert_contains=False,
):
    """Assert that an sqlexecute.run() result matches the expected values."""
    if status is None and auto_status and rows:
        status = "{} row{} in set".format(len(rows), "s" if len(rows) > 1 else "")
    fields = {"title": title, "rows": rows, "headers": headers, "status": status}

    if assert_contains:
        # Do a loose match on the results using the *in* operator.
        for key, field in fields.items():
            if field:
                assert field in result[0][key]
    else:
        # Do an exact match on the fields.
        assert result == [fields]


@dbtest
def test_conn(executor):
    run(executor, """create table test(a text)""")
    run(executor, """insert into test values('abc')""")
    results = run(executor, """select * from test""")

    assert_result_equal(results, headers=["a"], rows=[("abc",)])


@dbtest
def test_bools(executor):
    run(executor, """create table test(a boolean)""")
    run(executor, """insert into test values(1)""")
    results = run(executor, """select * from test""")

    assert_result_equal(results, headers=["a"], rows=[(1,)])


@dbtest
def test_binary(executor):
    run(executor, """create table foo(blb BLOB NOT NULL)""")
    run(executor, """INSERT INTO foo VALUES ('\x01\x01\x01\n')""")
    results = run(executor, """select * from foo""")

    expected = "\x01\x01\x01\n"

    assert_result_equal(results, headers=["blb"], rows=[(expected,)])


## Failing in Travis for some unknown reason.
# @dbtest
# def test_table_and_columns_query(executor):
#     run(executor, "create table a(x text, y text)")
#     run(executor, "create table b(z text)")

#     assert set(executor.tables()) == set([("a",), ("b",)])
#     assert set(executor.table_columns()) == set([("a", "x"), ("a", "y"), ("b", "z")])


@dbtest
def test_database_list(executor):
    databases = executor.databases()
    assert "main" in list(databases)


@dbtest
def test_invalid_syntax(executor):
    with pytest.raises(OperationalError) as excinfo:
        run(executor, "invalid syntax!")
    assert "syntax error" in str(excinfo.value)


@dbtest
def test_invalid_column_name(executor):
    with pytest.raises(OperationalError) as excinfo:
        run(executor, "select invalid command")
    assert "no such column: invalid" in str(excinfo.value)


@dbtest
def test_unicode_support_in_output(executor):
    run(executor, "create table unicodechars(t text)")
    run(executor, u"insert into unicodechars (t) values ('é')")

    # See issue #24, this raises an exception without proper handling
    results = run(executor, u"select * from unicodechars")
    assert_result_equal(results, headers=["t"], rows=[(u"é",)])


@dbtest
def test_multiple_queries_same_line(executor):
    results = run(executor, "select 'foo'; select 'bar'")

    expected = [
        {
            "title": None,
            "headers": ["'foo'"],
            "rows": [(u"foo",)],
            "status": "1 row in set",
        },
        {
            "title": None,
            "headers": ["'bar'"],
            "rows": [(u"bar",)],
            "status": "1 row in set",
        },
    ]
    assert expected == results


@dbtest
def test_multiple_queries_same_line_syntaxerror(executor):
    with pytest.raises(OperationalError) as excinfo:
        run(executor, "select 'foo'; invalid syntax")
    assert "syntax error" in str(excinfo.value)


@dbtest
def test_favorite_query(executor):
    set_expanded_output(False)
    run(executor, "create table test(a text)")
    run(executor, "insert into test values('abc')")
    run(executor, "insert into test values('def')")

    results = run(executor, "\\fs test-a select * from test where a like 'a%'")
    assert_result_equal(results, status="Saved.")

    results = run(executor, "\\f test-a")
    assert_result_equal(
        results,
        title="> select * from test where a like 'a%'",
        headers=["a"],
        rows=[("abc",)],
        auto_status=False,
    )

    results = run(executor, "\\fd test-a")
    assert_result_equal(results, status="test-a: Deleted")


@dbtest
def test_favorite_query_multiple_statement(executor):
    set_expanded_output(False)
    run(executor, "create table test(a text)")
    run(executor, "insert into test values('abc')")
    run(executor, "insert into test values('def')")

    results = run(
        executor,
        "\\fs test-ad select * from test where a like 'a%'; "
        "select * from test where a like 'd%'",
    )
    assert_result_equal(results, status="Saved.")

    results = run(executor, "\\f test-ad")
    expected = [
        {
            "title": "> select * from test where a like 'a%'",
            "headers": ["a"],
            "rows": [("abc",)],
            "status": None,
        },
        {
            "title": "> select * from test where a like 'd%'",
            "headers": ["a"],
            "rows": [("def",)],
            "status": None,
        },
    ]
    assert expected == results

    results = run(executor, "\\fd test-ad")
    assert_result_equal(results, status="test-ad: Deleted")


@dbtest
def test_favorite_query_expanded_output(executor):
    set_expanded_output(False)
    run(executor, """create table test(a text)""")
    run(executor, """insert into test values('abc')""")

    results = run(executor, "\\fs test-ae select * from test")
    assert_result_equal(results, status="Saved.")

    results = run(executor, "\\f test-ae \G")
    assert is_expanded_output() is True
    assert_result_equal(
        results,
        title="> select * from test",
        headers=["a"],
        rows=[("abc",)],
        auto_status=False,
    )

    set_expanded_output(False)

    results = run(executor, "\\fd test-ae")
    assert_result_equal(results, status="test-ae: Deleted")


@dbtest
def test_special_command(executor):
    results = run(executor, "\\?")
    assert_result_equal(
        results,
        rows=("quit", "\\q", "Quit."),
        headers="Command",
        assert_contains=True,
        auto_status=False,
    )


@dbtest
def test_cd_command_without_a_folder_name(executor):
    results = run(executor, "system cd")
    assert_result_equal(results, status="No folder name was provided.")


@dbtest
def test_system_command_not_found(executor):
    results = run(executor, "system xyz")
    assert_result_equal(
        results, status="OSError: No such file or directory", assert_contains=True
    )


@dbtest
def test_system_command_output(executor):
    test_dir = os.path.abspath(os.path.dirname(__file__))
    test_file_path = os.path.join(test_dir, "test.txt")
    results = run(executor, "system cat {0}".format(test_file_path))
    assert_result_equal(results, status="litecli is awesome!\n")


@dbtest
def test_cd_command_current_dir(executor):
    test_path = os.path.abspath(os.path.dirname(__file__))
    run(executor, "system cd {0}".format(test_path))
    assert os.getcwd() == test_path
    run(executor, "system cd ..")


@dbtest
def test_unicode_support(executor):
    results = run(executor, u"SELECT '日本語' AS japanese;")
    assert_result_equal(results, headers=["japanese"], rows=[(u"日本語",)])


@dbtest
def test_timestamp_null(executor):
    run(executor, """create table ts_null(a timestamp null)""")
    run(executor, """insert into ts_null values(null)""")
    results = run(executor, """select * from ts_null""")
    assert_result_equal(results, headers=["a"], rows=[(None,)])


@dbtest
def test_datetime_null(executor):
    run(executor, """create table dt_null(a datetime null)""")
    run(executor, """insert into dt_null values(null)""")
    results = run(executor, """select * from dt_null""")
    assert_result_equal(results, headers=["a"], rows=[(None,)])


@dbtest
def test_date_null(executor):
    run(executor, """create table date_null(a date null)""")
    run(executor, """insert into date_null values(null)""")
    results = run(executor, """select * from date_null""")
    assert_result_equal(results, headers=["a"], rows=[(None,)])


@dbtest
def test_time_null(executor):
    run(executor, """create table time_null(a time null)""")
    run(executor, """insert into time_null values(null)""")
    results = run(executor, """select * from time_null""")
    assert_result_equal(results, headers=["a"], rows=[(None,)])
