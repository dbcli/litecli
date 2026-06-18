from __future__ import annotations

import logging

import pygments.styles
from prompt_toolkit.styles import Style, merge_styles
from prompt_toolkit.styles.pygments import style_from_pygments_cls
from prompt_toolkit.styles.style import _MergedStyle
from pygments.style import Style as PygmentsStyle
from pygments.token import (
    Comment,
    Error,
    Generic,
    Keyword,
    Name,
    Number,
    Operator,
    String,
    Token,
    _TokenType,
    string_to_tokentype,
)
from pygments.util import ClassNotFound

logger = logging.getLogger(__name__)

# map Pygments tokens (ptk 1.0) to class names (ptk 2.0).
TOKEN_TO_PROMPT_STYLE: dict[_TokenType, str] = {
    Token.Menu.Completions.Completion.Current: "completion-menu.completion.current",
    Token.Menu.Completions.Completion: "completion-menu.completion",
    Token.Menu.Completions.Meta.Current: "completion-menu.meta.completion.current",
    Token.Menu.Completions.Meta: "completion-menu.meta.completion",
    Token.Menu.Completions.MultiColumnMeta: "completion-menu.multi-column-meta",
    Token.Menu.Completions.ProgressButton: "scrollbar.arrow",  # best guess
    Token.Menu.Completions.ProgressBar: "scrollbar",  # best guess
    Token.SelectedText: "selected",
    Token.SearchMatch: "search",
    Token.SearchMatch.Current: "search.current",
    Token.Toolbar: "bottom-toolbar",
    Token.Toolbar.Off: "bottom-toolbar.off",
    Token.Toolbar.On: "bottom-toolbar.on",
    Token.Toolbar.Search: "search-toolbar",
    Token.Toolbar.Search.Text: "search-toolbar.text",
    Token.Toolbar.System: "system-toolbar",
    Token.Toolbar.Arg: "arg-toolbar",
    Token.Toolbar.Arg.Text: "arg-toolbar.text",
    Token.Toolbar.Transaction.Valid: "bottom-toolbar.transaction.valid",
    Token.Toolbar.Transaction.Failed: "bottom-toolbar.transaction.failed",
    Token.Output.Header: "output.header",
    Token.Output.OddRow: "output.odd-row",
    Token.Output.EvenRow: "output.even-row",
    Token.Prompt: "prompt",
    Token.Continuation: "continuation",
}

# reverse dict for cli_helpers, because they still expect Pygments tokens.
PROMPT_STYLE_TO_TOKEN: dict[str, _TokenType] = {v: k for k, v in TOKEN_TO_PROMPT_STYLE.items()}


def _make_solarized_style(colors: dict[str, str]) -> dict[_TokenType, str]:
    return {
        Token: colors["base0"],
        Comment: "italic " + colors["base01"],
        Comment.Hashbang: colors["base01"],
        Comment.Multiline: colors["base01"],
        Comment.Preproc: "noitalic " + colors["magenta"],
        Comment.PreprocFile: "noitalic " + colors["base01"],
        Keyword: colors["green"],
        Keyword.Constant: colors["cyan"],
        Keyword.Declaration: colors["cyan"],
        Keyword.Namespace: colors["orange"],
        Keyword.Type: colors["yellow"],
        Operator: colors["base01"],
        Operator.Word: colors["green"],
        Name.Builtin: colors["blue"],
        Name.Builtin.Pseudo: colors["blue"],
        Name.Class: colors["blue"],
        Name.Constant: colors["blue"],
        Name.Decorator: colors["blue"],
        Name.Entity: colors["blue"],
        Name.Exception: colors["blue"],
        Name.Function: colors["blue"],
        Name.Function.Magic: colors["blue"],
        Name.Label: colors["blue"],
        Name.Namespace: colors["blue"],
        Name.Tag: colors["blue"],
        Name.Variable: colors["blue"],
        Name.Variable.Global: colors["blue"],
        Name.Variable.Magic: colors["blue"],
        String: colors["cyan"],
        String.Doc: colors["base01"],
        String.Regex: colors["orange"],
        Number: colors["cyan"],
        Generic: colors["base0"],
        Generic.Deleted: colors["red"],
        Generic.Emph: "italic",
        Generic.Error: colors["red"],
        Generic.Heading: "bold",
        Generic.Subheading: "underline",
        Generic.Inserted: colors["green"],
        Generic.Output: colors["base0"],
        Generic.Prompt: "bold " + colors["blue"],
        Generic.Strong: "bold",
        Generic.EmphStrong: "bold italic",
        Generic.Traceback: colors["blue"],
        Error: "bg:" + colors["red"],
    }


SOLARIZED_DARK_COLORS = {
    "base03": "#002b36",
    "base02": "#073642",
    "base01": "#586e75",
    "base00": "#657b83",
    "base0": "#839496",
    "base1": "#93a1a1",
    "base2": "#eee8d5",
    "base3": "#fdf6e3",
    "yellow": "#b58900",
    "orange": "#cb4b16",
    "red": "#dc322f",
    "magenta": "#d33682",
    "violet": "#6c71c4",
    "blue": "#268bd2",
    "cyan": "#2aa198",
    "green": "#859900",
}

SOLARIZED_LIGHT_COLORS = {
    "base3": "#002b36",
    "base2": "#073642",
    "base1": "#586e75",
    "base0": "#657b83",
    "base00": "#839496",
    "base01": "#93a1a1",
    "base02": "#eee8d5",
    "base03": "#fdf6e3",
    "yellow": "#b58900",
    "orange": "#cb4b16",
    "red": "#dc322f",
    "magenta": "#d33682",
    "violet": "#6c71c4",
    "blue": "#268bd2",
    "cyan": "#2aa198",
    "green": "#859900",
}


class SolarizedDarkStyle(PygmentsStyle):
    name = "solarized-dark"
    background_color = SOLARIZED_DARK_COLORS["base03"]
    highlight_color = SOLARIZED_DARK_COLORS["base02"]
    line_number_color = SOLARIZED_DARK_COLORS["base01"]
    line_number_background_color = SOLARIZED_DARK_COLORS["base02"]
    styles = _make_solarized_style(SOLARIZED_DARK_COLORS)


class SolarizedLightStyle(PygmentsStyle):
    name = "solarized-light"
    background_color = SOLARIZED_LIGHT_COLORS["base03"]
    highlight_color = SOLARIZED_LIGHT_COLORS["base02"]
    line_number_color = SOLARIZED_LIGHT_COLORS["base01"]
    line_number_background_color = SOLARIZED_LIGHT_COLORS["base02"]
    styles = _make_solarized_style(SOLARIZED_LIGHT_COLORS)


CUSTOM_STYLES: dict[str, type[PygmentsStyle]] = {
    "solarized": SolarizedDarkStyle,
    "solarized-dark": SolarizedDarkStyle,
    "solarized-light": SolarizedLightStyle,
}


def get_style(name: str) -> type[PygmentsStyle]:
    if name in CUSTOM_STYLES:
        return CUSTOM_STYLES[name]

    try:
        return pygments.styles.get_style_by_name(name)
    except ClassNotFound:
        return pygments.styles.get_style_by_name("native")


def parse_pygments_style(
    token_name: str,
    style_object: type[PygmentsStyle] | dict[_TokenType, str],
    style_dict: dict[str, str],
) -> tuple[_TokenType, str]:
    """Parse token type and style string.

    :param token_name: str name of Pygments token. Example: "Token.String"
    :param style_object: pygments.style.Style instance to use as base
    :param style_dict: dict of token names and their styles, customized to this cli

    """
    token_type = string_to_tokentype(token_name)
    style_value = style_dict[token_name]
    if isinstance(style_object, type) and issubclass(style_object, PygmentsStyle) and style_value.startswith("Token."):
        other_token_type = string_to_tokentype(style_value)
        return token_type, style_object.styles[other_token_type]
    else:
        return token_type, style_value


def style_factory(name: str, cli_style: dict[str, str]) -> _MergedStyle:
    style = get_style(name)

    prompt_styles: list[tuple[str, str]] = []
    # prompt-toolkit used pygments tokens for styling before, switched to style
    # names in 2.0. Convert old token types to new style names, for backwards compatibility.
    for token in cli_style:
        if token.startswith("Token."):
            # treat as pygments token (1.0)
            token_type, style_value = parse_pygments_style(token, style, cli_style)
            if token_type in TOKEN_TO_PROMPT_STYLE:
                prompt_style = TOKEN_TO_PROMPT_STYLE[token_type]
                prompt_styles.append((prompt_style, style_value))
            else:
                # we don't want to support tokens anymore
                logger.error("Unhandled style / class name: %s", token)
        else:
            # treat as prompt style name (2.0). See default style names here:
            # https://github.com/jonathanslenders/python-prompt-toolkit/blob/master/prompt_toolkit/styles/defaults.py
            prompt_styles.append((token, cli_style[token]))

    override_style: Style = Style([("bottom-toolbar", "noreverse")])
    return merge_styles([style_from_pygments_cls(style), override_style, Style(prompt_styles)])


def style_factory_output(name: str, cli_style: dict[str, str]) -> type[PygmentsStyle]:
    style_cls = get_style(name)
    style = dict(style_cls.styles)

    for token in cli_style:
        if token.startswith("Token."):
            token_type, style_value = parse_pygments_style(token, style, cli_style)
            style.update({token_type: style_value})
        elif token in PROMPT_STYLE_TO_TOKEN:
            token_type = PROMPT_STYLE_TO_TOKEN[token]
            style.update({token_type: cli_style[token]})
        else:
            # TODO: cli helpers will have to switch to ptk.Style
            logger.error("Unhandled style / class name: %s", token)

    class OutputStyle(PygmentsStyle):
        default_style = ""

    OutputStyle.background_color = style_cls.background_color
    OutputStyle.highlight_color = style_cls.highlight_color
    OutputStyle.line_number_color = style_cls.line_number_color
    OutputStyle.line_number_background_color = style_cls.line_number_background_color
    OutputStyle.styles = style

    return OutputStyle
