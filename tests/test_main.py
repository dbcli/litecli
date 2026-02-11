import os
import shutil
from collections import namedtuple
from datetime import datetime
from textwrap import dedent
from unittest.mock import patch

import click
import pytest
from click.testing import CliRunner
from prompt_toolkit import PromptSession

from litecli.main import LiteCli, cli
from litecli.packages.special.main import COMMANDS as SPECIAL_COMMANDS

from .utils import create_db, db_connection, dbtest, run

test_dir = os.path.abspath(os.path.dirname(__file__))
project_dir = os.path.dirname(test_dir)
default_config_file = os.path.join(project_dir, "tests", "liteclirc")

CLI_ARGS = ["--liteclirc", default_config_file, "_test_db"]

clickoutput: str


@dbtest
def test_execute_arg(executor):
    run(executor, "create table test (a text)")
    run(executor, 'insert into test values("abc")')

    sql = "select * from test;"
    runner = CliRunner()
    result = runner.invoke(cli, args=CLI_ARGS + ["-e", sql])

    assert result.exit_code == 0
    assert "abc" in result.output

    result = runner.invoke(cli, args=CLI_ARGS + ["--execute", sql])

    assert result.exit_code == 0
    assert "abc" in result.output

    expected = "a\nabc\n"

    assert expected in result.output


@dbtest
def test_execute_arg_with_table(executor):
    run(executor, "create table test (a text)")
    run(executor, 'insert into test values("abc")')

    sql = "select * from test;"
    runner = CliRunner()
    result = runner.invoke(cli, args=CLI_ARGS + ["-e", sql] + ["--table"])
    expected = "+-----+\n| a   |\n+-----+\n| abc |\n+-----+\n"

    assert result.exit_code == 0
    assert expected in result.output


@dbtest
def test_execute_arg_with_csv(executor):
    run(executor, "create table test (a text)")
    run(executor, 'insert into test values("abc")')

    sql = "select * from test;"
    runner = CliRunner()
    result = runner.invoke(cli, args=CLI_ARGS + ["-e", sql] + ["--csv"])
    expected = '"a"\n"abc"\n'

    assert result.exit_code == 0
    assert expected in "".join(result.output)


@dbtest
def test_batch_mode(executor):
    run(executor, """create table test(a text)""")
    run(executor, """insert into test values('abc'), ('def'), ('ghi')""")

    sql = "select count(*) from test;\nselect * from test limit 1;"

    runner = CliRunner()
    result = runner.invoke(cli, args=CLI_ARGS, input=sql)

    assert result.exit_code == 0
    assert "count(*)\n3\na\nabc\n" in "".join(result.output)


@dbtest
def test_batch_mode_table(executor):
    run(executor, """create table test(a text)""")
    run(executor, """insert into test values('abc'), ('def'), ('ghi')""")

    sql = "select count(*) from test;\nselect * from test limit 1;"

    runner = CliRunner()
    result = runner.invoke(cli, args=CLI_ARGS + ["-t"], input=sql)

    expected = dedent(
        """\
        +----------+
        | count(*) |
        +----------+
        | 3        |
        +----------+
        +-----+
        | a   |
        +-----+
        | abc |
        +-----+"""
    )

    assert result.exit_code == 0
    assert expected in result.output


@dbtest
def test_batch_mode_csv(executor):
    run(executor, """create table test(a text, b text)""")
    run(executor, """insert into test (a, b) values('abc', 'de\nf'), ('ghi', 'jkl')""")

    sql = "select * from test;"

    runner = CliRunner()
    result = runner.invoke(cli, args=CLI_ARGS + ["--csv"], input=sql)

    expected = '"a","b"\n"abc","de\nf"\n"ghi","jkl"\n'

    assert result.exit_code == 0
    assert expected in "".join(result.output)


def test_help_strings_end_with_periods():
    """Make sure click options have help text that end with a period."""
    for param in cli.params:
        if isinstance(param, click.core.Option):
            assert hasattr(param, "help")
            assert isinstance(param.help, str)
            assert param.help.endswith(".")


def output(monkeypatch, terminal_size, testdata, explicit_pager, expect_pager):
    global clickoutput
    clickoutput = ""
    m = LiteCli(liteclirc=default_config_file)

    class TestOutput:
        def get_size(self):
            size = namedtuple("Size", "rows columns")
            size.columns, size.rows = terminal_size
            return size

    class TestExecute:
        host = "test"
        user = "test"
        dbname = "test"
        port = 0

        def server_type(self):
            return ["test"]

    class PromptBuffer(PromptSession):
        output = TestOutput()

    m.prompt_app = PromptBuffer()
    m.sqlexecute = TestExecute()
    m.explicit_pager = explicit_pager

    def echo_via_pager(s):
        assert expect_pager
        global clickoutput
        clickoutput += s

    def secho(s):
        assert not expect_pager
        global clickoutput
        clickoutput += s + "\n"

    monkeypatch.setattr(click, "echo_via_pager", echo_via_pager)
    monkeypatch.setattr(click, "secho", secho)
    m.output(testdata)
    if clickoutput.endswith("\n"):
        clickoutput = clickoutput[:-1]
    assert clickoutput == "\n".join(testdata)


def test_conditional_pager(monkeypatch):
    testdata = "Lorem ipsum dolor sit amet consectetur adipiscing elit sed do".split(" ")
    # User didn't set pager, output doesn't fit screen -> pager
    output(
        monkeypatch,
        terminal_size=(5, 10),
        testdata=testdata,
        explicit_pager=False,
        expect_pager=True,
    )
    # User didn't set pager, output fits screen -> no pager
    output(
        monkeypatch,
        terminal_size=(20, 20),
        testdata=testdata,
        explicit_pager=False,
        expect_pager=False,
    )
    # User manually configured pager, output doesn't fit screen -> pager
    output(
        monkeypatch,
        terminal_size=(5, 10),
        testdata=testdata,
        explicit_pager=True,
        expect_pager=True,
    )
    # User manually configured pager, output fit screen -> pager
    output(
        monkeypatch,
        terminal_size=(20, 20),
        testdata=testdata,
        explicit_pager=True,
        expect_pager=True,
    )

    SPECIAL_COMMANDS["nopager"].handler()
    output(
        monkeypatch,
        terminal_size=(5, 10),
        testdata=testdata,
        explicit_pager=False,
        expect_pager=False,
    )
    SPECIAL_COMMANDS["pager"].handler("")


def test_reserved_space_is_integer():
    """Make sure that reserved space is returned as an integer."""

    def stub_terminal_size():
        return (5, 5)

    old_func = shutil.get_terminal_size

    shutil.get_terminal_size = stub_terminal_size  # type: ignore[assignment]
    lc = LiteCli()
    assert isinstance(lc.get_reserved_space(), int)
    shutil.get_terminal_size = old_func


@dbtest
def test_import_command(executor):
    data_file = os.path.join(project_dir, "tests", "data", "import_data.csv")
    run(executor, """create table tbl1(one varchar(10), two smallint)""")

    # execute
    run(executor, """.import %s tbl1""" % data_file)

    # verify
    sql = "select * from tbl1;"
    runner = CliRunner()
    result = runner.invoke(cli, args=CLI_ARGS + ["--csv"], input=sql)

    expected = """one","two"
"t1","11"
"t2","22"
"""
    assert result.exit_code == 0
    assert expected in "".join(result.output)


def test_startup_commands(executor):
    m = LiteCli(liteclirc=default_config_file)
    assert m.startup_commands
    assert m.startup_commands["commands"] == [
        "create table startupcommands(a text)",
        "insert into startupcommands values('abc')",
    ]

    # implement tests on executions of the startupcommands


@patch("litecli.main.datetime")  # Adjust if your module path is different
def test_get_prompt(mock_datetime):
    # We'll freeze time at 2025-01-20 13:37:42 for comedic effect.
    # Because "leet" times call for 13:37!
    frozen_time = datetime(2025, 1, 20, 13, 37, 42)
    mock_datetime.now.return_value = frozen_time
    # Ensure `datetime` class is still accessible for strftime usage
    mock_datetime.datetime = datetime

    # Instantiate and connect
    lc = LiteCli()
    lc.connect("/tmp/litecli_test.db")

    # 1. Test \d => full path to the DB
    assert lc.get_prompt(r"\d") == "/tmp/litecli_test.db"

    # 2. Test \f => basename of the DB
    #    (because "f" stands for "filename", presumably!)
    assert lc.get_prompt(r"\f") == "litecli_test.db"

    # 3. Test \_ => single space
    assert lc.get_prompt(r"Hello\_World") == "Hello World"

    # 4. Test \n => newline
    #    Just to be sure we're only inserting a newline,
    #    we can check length or assert the presence of "\n".
    expected = f"Line1{os.linesep}Line2"
    assert lc.get_prompt(r"Line1\nLine2") == expected

    # 5. Test date/time placeholders (with frozen time):
    #    \D => e.g. 'Mon Jan 20 13:37:42 2025'
    expected_date_str = frozen_time.strftime("%a %b %d %H:%M:%S %Y")
    assert lc.get_prompt(r"\D") == expected_date_str

    # 6. Test \m => minutes
    assert lc.get_prompt(r"\m") == "37"

    # 7. Test \P => AM/PM
    #    13:37 is PM
    assert lc.get_prompt(r"\P") == "PM"

    # 8. Test \R => 24-hour format hour
    assert lc.get_prompt(r"\R") == "13"

    # 9. Test \r => 12-hour format hour
    #    13:37 is 01 in 12-hour format
    assert lc.get_prompt(r"\r") == "01"

    # 10. Test \s => seconds
    assert lc.get_prompt(r"\s") == "42"

    # 11. Test when dbname is None => (none)
    lc.connect(None)
    # Simulate no DB connection and incorrect argument type
    assert lc.get_prompt(r"\d") == "(none)"
    assert lc.get_prompt(r"\f") == "(none)"

    # 12. Windows path
    lc.connect("C:\\Users\\litecli\\litecli_test.db")
    assert lc.get_prompt(r"\d") == "C:\\Users\\litecli\\litecli_test.db"


@pytest.mark.parametrize(
    "uri, expected_dbname",
    [
        ("file:{tmp_path}/test.db", "{tmp_path}/test.db"),
        ("file:{tmp_path}/test.db?mode=ro", "{tmp_path}/test.db"),
        ("file:{tmp_path}/test.db?mode=ro&cache=shared", "{tmp_path}/test.db"),
    ],
)
def test_file_uri(tmp_path, uri, expected_dbname):
    """
    Test that `file:` URIs are correctly handled
    ref:
        https://docs.python.org/3/library/sqlite3.html#sqlite3-uri-tricks
        https://www.sqlite.org/c3ref/open.html#urifilenameexamples
    """
    # - ensure db exists
    db_path = tmp_path / "test.db"
    create_db(db_path)
    db_connection(db_path)
    uri = uri.format(tmp_path=tmp_path)

    lc = LiteCli()
    lc.connect(uri)

    assert lc.get_prompt(r"\d") == expected_dbname.format(tmp_path=tmp_path)
