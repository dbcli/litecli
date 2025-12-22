from litecli.packages.completion_engine import suggest_type
from litecli.packages.special.utils import check_if_sqlitedotcommand, format_uptime

from .test_completion_engine import sorted_dicts
from .utils import assert_result_equal, dbtest, run


def test_import_first_argument():
    test_cases: list[tuple[str, int]] = [
        # text, expecting_arg_idx
        (".import ", 1),
        (".import ./da", 1),
        (".import ./data.csv ", 2),
        (".import ./data.csv t", 2),
        (".import ./data.csv `t", 2),
        ('.import ./data.csv "t', 2),
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
    for seconds, human_readable_text in [
        ("59", "59 sec"),
        ("120", "2 min 0 sec"),
        ("54890", "15 hours 14 min 50 sec"),
        ("598244", "6 days 22 hours 10 min 44 sec"),
        ("522600", "6 days 1 hour 10 min 0 sec"),
    ]:
        assert human_readable_text == format_uptime(seconds)


def test_indexes():
    suggestions = suggest_type(".indexes", ".indexes ")
    assert sorted_dicts(suggestions) == sorted_dicts(
        [
            {"type": "table", "schema": []},
            {"type": "view", "schema": []},
            {"type": "schema"},
        ]
    )


def test_check_if_sqlitedotcommand():
    test_cases = [
        [".tables", True],
        [".BiNarY", True],
        ["binary", False],
        [234, False],
        [".changes   test! test", True],
        ["NotDotcommand", False],
    ]
    for command, expected_result in test_cases:
        assert check_if_sqlitedotcommand(command) == expected_result


@dbtest
def test_special_d(executor):
    run(executor, """create table tst_tbl1(a text)""")
    results = run(executor, """\\d""")

    assert_result_equal(results, headers=["name"], rows=[("tst_tbl1",)], status="")


@dbtest
def test_special_d_w_arg(executor):
    run(executor, """create table tst_tbl1(a text)""")
    results = run(executor, """\\d tst_tbl1""")

    assert_result_equal(
        results, headers=["cid", "name", "type", "notnull", "dflt_value", "pk"], rows=[(0, "a", "TEXT", 0, None, 0)], status=""
    )
