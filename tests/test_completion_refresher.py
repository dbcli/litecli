import time
from unittest.mock import Mock, patch

import pytest


@pytest.fixture
def refresher():
    from litecli.completion_refresher import CompletionRefresher

    return CompletionRefresher()


def test_ctor(refresher):
    """Refresher object should contain a few handlers.

    :param refresher:
    :return:

    """
    assert len(refresher.refreshers) > 0
    actual_handlers = list(refresher.refreshers.keys())
    expected_handlers = [
        "databases",
        "schemata",
        "tables",
        "functions",
        "special_commands",
    ]
    assert expected_handlers == actual_handlers


def test_refresh_called_once(refresher):
    """

    :param refresher:
    :return:
    """
    callbacks = Mock()
    sqlexecute = Mock()

    with patch.object(refresher, "_bg_refresh") as bg_refresh:
        actual = refresher.refresh(sqlexecute, callbacks)
        time.sleep(1)  # Wait for the thread to work.
        assert len(actual) == 1
        assert len(actual[0]) == 4
        assert actual[0][3] == "Auto-completion refresh started in the background."
        bg_refresh.assert_called_with(sqlexecute, callbacks, {})


def test_refresh_called_twice(refresher):
    """If refresh is called a second time, it should be restarted.

    :param refresher:
    :return:

    """
    callbacks = Mock()

    sqlexecute = Mock()

    def dummy_bg_refresh(*args):
        time.sleep(3)  # seconds

    refresher._bg_refresh = dummy_bg_refresh

    actual1 = refresher.refresh(sqlexecute, callbacks)
    time.sleep(1)  # Wait for the thread to work.
    assert len(actual1) == 1
    assert len(actual1[0]) == 4
    assert actual1[0][3] == "Auto-completion refresh started in the background."

    actual2 = refresher.refresh(sqlexecute, callbacks)
    time.sleep(1)  # Wait for the thread to work.
    assert len(actual2) == 1
    assert len(actual2[0]) == 4
    assert actual2[0][3] == "Auto-completion refresh restarted."


def test_refresh_with_callbacks(refresher):
    """Callbacks must be called.

    :param refresher:

    """
    callbacks = [Mock()]
    sqlexecute_class = Mock()
    sqlexecute = Mock()

    with patch("litecli.completion_refresher.SQLExecute", sqlexecute_class):
        # Set refreshers to 0: we're not testing refresh logic here
        refresher.refreshers = {}
        refresher.refresh(sqlexecute, callbacks)
        time.sleep(1)  # Wait for the thread to work.
        assert callbacks[0].call_count == 1


def test_refresh_with_view_referencing_unavailable_function(refresher, tmp_path):
    """A view that references a function provided by a loadable extension
    must not crash the background completion refresh. All relation names
    and the columns of the introspectable relations must be completed.

    :param refresher:

    """
    from litecli.sqlexecute import SQLExecute, sqlite3

    db_path = str(tmp_path / "completion_refresh.db")
    conn = sqlite3.connect(db_path)
    conn.execute("create table products(product_id integer primary key)")
    conn.create_function("unavailable_ext_func", 1, lambda x: b"")
    conn.execute("create view v_ext_hashed as select hex(unavailable_ext_func(product_id)) from products")
    conn.commit()
    conn.close()

    executor = SQLExecute(db_path)
    refreshed = []
    refresher.refresh(executor, refreshed.append, {})

    deadline = time.time() + 5
    while refresher.is_refreshing() and time.time() < deadline:
        time.sleep(0.05)
    time.sleep(0.1)

    assert refreshed, "the completion refresh did not complete"
    completer = refreshed[0]
    assert "products" in completer.all_completions
    assert "v_ext_hashed" in completer.all_completions
    assert "product_id" in completer.all_completions
