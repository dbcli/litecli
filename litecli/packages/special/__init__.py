# ruff: noqa

from __future__ import annotations
from types import FunctionType

from typing import Callable, Any

__all__: list[str] = []


def export(defn: Callable[..., Any]) -> Callable[..., Any]:
    """Decorator to explicitly mark functions that are exposed in a lib."""
    # ty, requires explict check for callable of tyep | function type to access __name__
    if isinstance(defn, (type, FunctionType)):
        globals()[defn.__name__] = defn
        __all__.append(defn.__name__)
    return defn


from . import dbcommands
from . import iocommands
from . import llm
from . import utils
from .main import CommandNotFound, register_special_command, execute
from .iocommands import (
    set_favorite_queries,
    editor_command,
    get_filename,
    get_editor_query,
    open_external_editor,
    is_expanded_output,
    set_expanded_output,
    write_tee,
    unset_once_if_written,
    unset_pipe_once_if_written,
    disable_pager,
    set_pager,
    is_pager_enabled,
    write_once,
    write_pipe_once,
    close_tee,
)
from .llm import is_llm_command, handle_llm, FinishIteration
