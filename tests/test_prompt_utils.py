# -*- coding: utf-8 -*-
# mypy: ignore-errors

import click

from litecli.packages.prompt_utils import confirm_destructive_query


def test_confirm_destructive_query_notty():
    stdin = click.get_text_stream("stdin")
    assert stdin.isatty() is False

    sql = "drop database foo;"
    assert confirm_destructive_query(sql) is None
