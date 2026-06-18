from __future__ import annotations

from typing import Any, Iterable


def _dot_value(value: Any) -> str:
    if value is None:
        return "NULL"
    return str(value)


def _dot_quote(value: Any) -> str:
    text = _dot_value(value)
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "\\r") + '"'


def format_dot_output(rows: Iterable[Iterable[Any]], headers: Iterable[str]) -> Iterable[str]:
    """Format one-column results as nodes and multi-column results as edges."""
    header_names = list(headers)

    yield "digraph result {"

    if header_names:
        yield "  // Columns: {}".format(", ".join(header_names))

    for row in rows:
        row_values = list(row)
        if not row_values:
            continue

        if len(row_values) == 1:
            yield "  {};".format(_dot_quote(row_values[0]))
            continue

        label = ""
        if len(row_values) > 2:
            label_values = []
            for index, value in enumerate(row_values[2:], start=2):
                column_name = header_names[index] if index < len(header_names) else "column{}".format(index + 1)
                label_values.append("{}={}".format(column_name, _dot_value(value)))
            label = " [label={}]".format(_dot_quote(", ".join(label_values)))

        yield "  {} -> {}{};".format(_dot_quote(row_values[0]), _dot_quote(row_values[1]), label)

    yield "}"
