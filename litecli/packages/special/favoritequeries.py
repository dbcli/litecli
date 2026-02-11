# -*- coding: utf-8 -*-
from __future__ import annotations

import builtins
from typing import Any, cast


class FavoriteQueries(object):
    section_name: str = "favorite_queries"

    usage = """
Favorite Queries are a way to save frequently used queries
with a short name.
Examples:

    # Save a new favorite query.
    > \\fs simple select * from abc where a is not Null;

    # List all favorite queries.
    > \\f
    ╒════════╤═══════════════════════════════════════╕
    │ Name   │ Query                                 │
    ╞════════╪═══════════════════════════════════════╡
    │ simple │ SELECT * FROM abc where a is not NULL │
    ╘════════╧═══════════════════════════════════════╛

    # Run a favorite query.
    > \\f simple
    ╒════════╤════════╕
    │ a      │ b      │
    ╞════════╪════════╡
    │ 日本語 │ 日本語 │
    ╘════════╧════════╛

    # Delete a favorite query.
    > \\fd simple
    simple: Deleted
"""

    def __init__(self, config: Any) -> None:
        self.config = config

    def list(self) -> builtins.list[str]:
        section = cast(dict[str, str], self.config.get(self.section_name, {}))
        return list(section.keys())

    def get(self, name: str) -> str | None:
        section = cast(dict[str, str], self.config.get(self.section_name, {}))
        return section.get(name)

    def save(self, name: str, query: str) -> None:
        if self.section_name not in self.config:
            self.config[self.section_name] = {}
        self.config[self.section_name][name] = query
        self.config.write()

    def delete(self, name: str) -> str:
        try:
            del self.config[self.section_name][name]
        except KeyError:
            return "%s: Not Found." % name
        self.config.write()
        return "%s: Deleted" % name
