from unittest.mock import MagicMock

from prompt_toolkit.enums import EditingMode

from litecli.clitoolbar import create_toolbar_tokens_func


def _cli(multi_line):
    cli = MagicMock()
    cli.multi_line = multi_line
    cli.prompt_app.editing_mode = EditingMode.EMACS
    cli.completion_refresher.is_refreshing.return_value = False
    return cli


def _text(tokens):
    return "".join(text for _, text in tokens)


def test_multiline_toolbar_says_semicolon_runs_the_query():
    tokens = create_toolbar_tokens_func(_cli(True), lambda: False)()
    assert "(Semi-colon [;] will run the query)" in _text(tokens)


def test_single_line_toolbar_has_no_semicolon_hint():
    tokens = create_toolbar_tokens_func(_cli(False), lambda: False)()
    assert "Semi-colon" not in _text(tokens)
