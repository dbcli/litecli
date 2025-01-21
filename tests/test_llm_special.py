import pytest
from unittest.mock import patch
from litecli.packages.special.llm import handle_llm, FinishIteration, USAGE


@patch("litecli.packages.special.llm.initialize_llm")
@patch("litecli.packages.special.llm.llm", new=None)
def test_llm_command_without_install(mock_initialize_llm, executor):
    """
    Test that handle_llm initializes llm when it is None and raises FinishIteration.
    """
    test_text = r"\llm"
    cur_mock = executor

    with pytest.raises(FinishIteration) as exc_info:
        handle_llm(test_text, cur_mock)

    mock_initialize_llm.assert_called_once()
    assert exc_info.value.args[0] is None


@patch("litecli.packages.special.llm.llm")
def test_llm_command_without_args(mock_llm, executor):
    r"""
    Invoking \llm without any arguments should print the usage and raise
    FinishIteration.
    """
    assert mock_llm is not None
    test_text = r"\llm"
    cur_mock = executor

    with pytest.raises(FinishIteration) as exc_info:
        handle_llm(test_text, cur_mock)

    assert exc_info.value.args[0] == [(None, None, None, USAGE)]


@patch("litecli.packages.special.llm.llm")
@patch("litecli.packages.special.llm.run_external_cmd")
def test_llm_command_with_c_flag(mock_run_cmd, mock_llm, executor):
    # Suppose the LLM returns some text without fenced SQL
    mock_run_cmd.return_value = (0, "Hello, I have no SQL for you today.")

    test_text = r"\llm -c 'Something interesting?'"

    with pytest.raises(FinishIteration) as exc_info:
        handle_llm(test_text, executor)

    # We expect no code fence => FinishIteration with that output
    assert exc_info.value.args[0] == [(None, None, None, "Hello, I have no SQL for you today.")]


@patch("litecli.packages.special.llm.llm")
@patch("litecli.packages.special.llm.run_external_cmd")
def test_llm_command_with_c_flag_and_fenced_sql(mock_run_cmd, mock_llm, executor):
    # The luscious SQL is inside triple backticks
    return_text = "Here is your query:\n" "```sql\nSELECT * FROM table;\n```"
    mock_run_cmd.return_value = (0, return_text)

    test_text = r"\llm -c 'Rewrite the SQL without CTE'"

    result, sql = handle_llm(test_text, executor)

    # We expect the function to return (result, sql), but result might be "" if verbose is not set
    # By default, `verbose` is false unless text has something like \llm --verbose?
    # The function code: return result if verbose else "", sql
    # Our test_text doesn't set verbose => we expect "" for the returned context.
    assert result == ""
    assert sql == "SELECT * FROM table;"


@patch("litecli.packages.special.llm.llm")
@patch("litecli.packages.special.llm.run_external_cmd")
def test_llm_command_known_subcommand(mock_run_cmd, mock_llm, executor):
    """
    If the parts[0] is in LLM_CLI_COMMANDS, we do NOT capture output, we just call run_external_cmd
    and then raise FinishIteration.
    """
    # Let's assume 'models' is in LLM_CLI_COMMANDS
    test_text = r"\llm models"

    with pytest.raises(FinishIteration) as exc_info:
        handle_llm(test_text, executor)

    # We check that run_external_cmd was called with these arguments:
    mock_run_cmd.assert_called_once_with("llm", "models", restart_cli=False)
    # And the function should raise FinishIteration(None)
    assert exc_info.value.args[0] is None


@patch("litecli.packages.special.llm.llm")
@patch("litecli.packages.special.llm.run_external_cmd")
def test_llm_command_with_install_flag(mock_run_cmd, mock_llm, executor):
    """
    If 'install' or 'uninstall' is in the parts, we do not capture output but restart the CLI.
    """
    test_text = r"\llm install openai"

    with pytest.raises(FinishIteration) as exc_info:
        handle_llm(test_text, executor)

    # We expect a restart
    mock_run_cmd.assert_called_once_with("llm", "install", "openai", restart_cli=True)
    assert exc_info.value.args[0] is None


@patch("litecli.packages.special.llm.llm")
@patch("litecli.packages.special.llm.ensure_litecli_template")
@patch("litecli.packages.special.llm.sql_using_llm")
def test_llm_command_with_prompt(mock_sql_using_llm, mock_ensure_template, mock_llm, executor):
    r"""
    \llm prompt "some question"
    Should use context, capture output, and call sql_using_llm.
    """
    # Mock out the return from sql_using_llm
    mock_sql_using_llm.return_value = ("context from LLM", "SELECT 1;")

    test_text = r"\llm prompt 'Magic happening here?'"
    context, sql = handle_llm(test_text, executor)

    # ensure_litecli_template should be called
    mock_ensure_template.assert_called_once()
    # sql_using_llm should be called with question=arg, which is "prompt 'Magic happening here?'"
    # Actually, the question is the entire "prompt 'Magic happening here?'" minus the \llm
    # But in the function we do parse shlex.split.
    mock_sql_using_llm.assert_called()
    assert context == ""
    assert sql == "SELECT 1;"


@patch("litecli.packages.special.llm.llm")
@patch("litecli.packages.special.llm.ensure_litecli_template")
@patch("litecli.packages.special.llm.sql_using_llm")
def test_llm_command_question_with_context(mock_sql_using_llm, mock_ensure_template, mock_llm, executor):
    """
    If arg doesn't contain any known command, it's treated as a question => capture output + context.
    """
    mock_sql_using_llm.return_value = ("You have context!", "SELECT 2;")

    test_text = r"\llm 'Top 10 downloads by size.'"
    context, sql = handle_llm(test_text, executor)

    mock_ensure_template.assert_called_once()
    mock_sql_using_llm.assert_called()
    assert context == ""
    assert sql == "SELECT 2;"


@patch("litecli.packages.special.llm.llm")
@patch("litecli.packages.special.llm.ensure_litecli_template")
@patch("litecli.packages.special.llm.sql_using_llm")
def test_llm_command_question_verbose(mock_sql_using_llm, mock_ensure_template, mock_llm, executor):
    r"""
    Invoking \llm+ returns the context and the SQL query.
    """
    mock_sql_using_llm.return_value = ("Verbose context, oh yeah!", "SELECT 42;")

    test_text = r"\llm+ 'Top 10 downloads by size.'"
    context, sql = handle_llm(test_text, executor)

    assert context == "Verbose context, oh yeah!"
    assert sql == "SELECT 42;"
