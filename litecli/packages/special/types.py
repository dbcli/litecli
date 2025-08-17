from __future__ import annotations

from typing import Any, List, Optional, Protocol, Sequence, Tuple


class DBCursor(Protocol):
    """Minimal DB-API cursor protocol used by special modules."""

    description: Optional[Sequence[Sequence[Any]]]

    def execute(self, sql: str, params: Any = ...) -> Any: ...

    def fetchall(self) -> List[Tuple[Any, ...]]: ...

    def fetchone(self) -> Optional[Tuple[Any, ...]]: ...
