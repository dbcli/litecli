from litecli.packages.completion_engine import suggest_type
from test_completion_engine import sorted_dicts
from litecli.packages.special.utils import format_uptime


def test_import_first_argument():
    test_cases = [
        # text, expecting_arg_idx
        [".import ", 1],
        [".import ./da", 1],
        [".import ./data.csv ", 2],
        [".import ./data.csv t", 2],
        [".import ./data.csv `t", 2],
        ['.import ./data.csv "t', 2],
    ]
    for text, expecting_arg_idx in test_cases:
        suggestions = suggest_type(text, text)
        if expecting_arg_idx == 1:
            assert suggestions == [{"type": "file_name"}]
        else:
            assert suggestions == [{"type": "table", "schema": []}]


def test_u_suggests_databases():
    suggestions = suggest_type("\\u ", "\\u ")
    assert sorted_dicts(suggestions) == sorted_dicts([{"type": "database"}])


def test_describe_table():
    suggestions = suggest_type("\\dt", "\\dt ")
    assert sorted_dicts(suggestions) == sorted_dicts(
        [
            {"type": "table", "schema": []},
            {"type": "view", "schema": []},
            {"type": "schema"},
        ]
    )


def test_list_or_show_create_tables():
    suggestions = suggest_type("\\dt+", "\\dt+ ")
    assert sorted_dicts(suggestions) == sorted_dicts(
        [
            {"type": "table", "schema": []},
            {"type": "view", "schema": []},
            {"type": "schema"},
        ]
    )


def test_format_uptime():
    seconds = 59
    assert "59 sec" == format_uptime(seconds)

    seconds = 120
    assert "2 min 0 sec" == format_uptime(seconds)

    seconds = 54890
    assert "15 hours 14 min 50 sec" == format_uptime(seconds)

    seconds = 598244
    assert "6 days 22 hours 10 min 44 sec" == format_uptime(seconds)

    seconds = 522600
    assert "6 days 1 hour 10 min 0 sec" == format_uptime(seconds)
