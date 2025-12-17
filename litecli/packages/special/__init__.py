# ruff: noqa

from __future__ import annotations
from types import FunctionType

from typing import Callable, Any

__all__: list[str] = []


def export(defn: Callable[..., Any]) -> Callable[..., Any]:
    """Decorator to explicitly mark functions that are exposed in a lib."""
    if isinstance(defn, FunctionType):
        globals()[defn.__name__] = defn
        __all__.append(defn.__name__)
    return defn


from . import dbcommands
from . import iocommands
from . import llm
