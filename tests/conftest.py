from __future__ import print_function

import os
import pytest
from utils import create_db, db_connection, drop_tables
import litecli.sqlexecute


@pytest.yield_fixture(scope="function")
def connection():
    create_db("_test_db")
    connection = db_connection("_test_db")
    yield connection

    drop_tables(connection)
    connection.close()
    os.remove("_test_db")


@pytest.fixture
def cursor(connection):
    with connection.cursor() as cur:
        return cur


@pytest.fixture
def executor(connection):
    return litecli.sqlexecute.SQLExecute(database="_test_db")


@pytest.fixture
def exception_formatter():
    return lambda e: str(e)


@pytest.fixture(scope="session", autouse=True)
def temp_config(tmpdir_factory):
    # this function runs on start of test session.
    # use temporary directory for config home so user config will not be used
    os.environ["XDG_CONFIG_HOME"] = str(tmpdir_factory.mktemp("data"))
