# -*- coding: utf-8 -*-


import multiprocessing
import os
import signal
import sys
import time
from contextlib import closing

import pytest

try:
    import sqlean as sqlite3
except ImportError:
    import sqlite3

from litecli.main import special

DATABASE = "test.sqlite3"


def db_connection(dbname=":memory:"):
    conn = sqlite3.connect(database=dbname, isolation_level=None)  # type: ignore[attr-defined]
    return conn


try:
    db_connection()
    CAN_CONNECT_TO_DB = True
except Exception:
    CAN_CONNECT_TO_DB = False

dbtest = pytest.mark.skipif(not CAN_CONNECT_TO_DB, reason="Error creating sqlite connection")


def create_db(dbname):
    with closing(db_connection().cursor()) as cur:
        try:
            cur.execute("""DROP DATABASE IF EXISTS _test_db""")
            cur.execute("""CREATE DATABASE _test_db""")
        except Exception:
            pass


def drop_tables(dbname):
    with closing(db_connection().cursor()) as cur:
        try:
            cur.execute("""DROP DATABASE IF EXISTS _test_db""")
        except Exception:
            pass


def run(executor, sql, rows_as_list=True):
    """Return string output for the sql to be run."""
    result = []

    for title, rows, headers, status in executor.run(sql):
        rows = list(rows) if (rows_as_list and rows) else rows
        result.append({"title": title, "rows": rows, "headers": headers, "status": status})

    return result


def set_expanded_output(is_expanded):
    """Pass-through for the tests."""
    return special.set_expanded_output(is_expanded)


def is_expanded_output():
    """Pass-through for the tests."""
    return special.is_expanded_output()


def send_ctrl_c_to_pid(pid, wait_seconds):
    """Sends a Ctrl-C like signal to the given `pid` after `wait_seconds`
    seconds."""
    time.sleep(wait_seconds)
    # ty, is aware of sys.platform and not platform.system. See: https://github.com/astral-sh/ty/issues/2033
    if sys.platform == "win32":
        os.kill(pid, signal.CTRL_C_EVENT)
    else:
        os.kill(pid, signal.SIGINT)


def send_ctrl_c(wait_seconds):
    """Create a process that sends a Ctrl-C like signal to the current process
    after `wait_seconds` seconds.

    Returns the `multiprocessing.Process` created.

    """
    ctrl_c_process = multiprocessing.Process(target=send_ctrl_c_to_pid, args=(os.getpid(), wait_seconds))
    ctrl_c_process.start()
    return ctrl_c_process


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
