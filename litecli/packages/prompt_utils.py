from __future__ import annotations

import sys

import click

from .parseutils import is_destructive
from typing import Any


class ConfirmBoolParamType(click.ParamType):
    name = "confirmation"

    def convert(self, value: bool | str, param: click.Parameter | None, ctx: click.Context | None) -> bool:
        if isinstance(value, bool):
            return value
        value = value.lower()
        if value in ("yes", "y"):
            return True
        if value in ("no", "n"):
            return False
        self.fail(f"{value} is not a valid boolean", param, ctx)

    def __repr__(self) -> str:
        return "BOOL"


BOOLEAN_TYPE = ConfirmBoolParamType()


def confirm_destructive_query(queries: str) -> bool | None:
    """Check if the query is destructive and prompt to confirm.

    Returns:
    - None: non-destructive or cannot prompt (non-tty).
    - True: destructive and user consents.
    - False: destructive and user declines.
    """
    prompt_text = "You're about to run a destructive command.\nDo you want to proceed? (y/n)"
    if is_destructive(queries) and sys.stdin.isatty():
        return bool(prompt(prompt_text, type=BOOLEAN_TYPE))
    return None


def confirm(*args: Any, **kwargs: Any) -> bool:
    """Prompt for confirmation (yes/no) and handle aborts."""
    try:
        return click.confirm(*args, **kwargs)
    except click.Abort:
        return False


def prompt(*args: Any, **kwargs: Any) -> Any:
    """Prompt the user for input and handle aborts. Returns the value from click.prompt."""
    try:
        return click.prompt(*args, **kwargs)
    except click.Abort:
        return False
