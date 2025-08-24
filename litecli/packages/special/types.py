from __future__ import annotations

from typing import Any, Protocol, Sequence


class DBCursor(Protocol):
    """Minimal DB-API cursor protocol used by special modules."""

    description: Sequence[Sequence[Any]] | None

    # Optional attribute on many DB-API cursors
    connection: Any

    def execute(self, sql: str, params: Any = ...) -> Any: ...

    def fetchall(self) -> list[tuple[Any, ...]]: ...

    def fetchone(self) -> tuple[Any, ...] | None: ...
