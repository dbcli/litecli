import os

from click.testing import CliRunner

from litecli.main import cli
from utils import dbtest, run

test_dir = os.path.abspath(os.path.dirname(__file__))
project_dir = os.path.dirname(test_dir)
default_config_file = os.path.join(project_dir, "tests", "liteclirc")

CLI_ARGS = ["--liteclirc", default_config_file, "_test_db"]


@dbtest
def test_execute_arg(executor):
    run(executor, "create table test (a text)")
    run(executor, 'insert into test values("abc")')

    sql = "select * from test;"
    runner = CliRunner()
    result = runner.invoke(cli, args=CLI_ARGS + ["-e", sql])

    assert result.exit_code == 0
    assert '"abc"' in result.output

    result = runner.invoke(cli, args=CLI_ARGS + ["--execute", sql])

    assert result.exit_code == 0
    assert '"abc"' in result.output

    expected = '"a"\n"abc"\n'

    assert expected in result.output
