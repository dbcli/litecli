# -*- coding: utf-8 -*-

"""Test the litecli.clistyle module."""

import pytest
from pygments.style import Style
from pygments.token import Keyword, String, Token

from litecli.clistyle import SolarizedDarkStyle, SolarizedLightStyle, style_factory, style_factory_output


@pytest.mark.skip(reason="incompatible with new prompt toolkit")
def test_style_factory():
    """Test that a Pygments Style class is created."""
    header = "bold underline #ansired"
    cli_style = {"Token.Output.Header": header}
    style = style_factory("default", cli_style)

    assert isinstance(style, Style)
    assert Token.Output.Header in style.styles
    assert header == style.styles[Token.Output.Header]


@pytest.mark.skip(reason="incompatible with new prompt toolkit")
def test_style_factory_unknown_name():
    """Test that an unrecognized name will not throw an error."""
    style = style_factory("foobar", {})

    assert isinstance(style, Style)


@pytest.mark.parametrize(
    ("name", "style", "background"),
    [
        ("solarized", SolarizedDarkStyle, "#002b36"),
        ("solarized-dark", SolarizedDarkStyle, "#002b36"),
        ("solarized-light", SolarizedLightStyle, "#fdf6e3"),
    ],
)
def test_style_factory_output_solarized(name, style, background):
    output_style = style_factory_output(name, {})

    assert output_style.styles[Keyword] == style.styles[Keyword]
    assert output_style.styles[String] == style.styles[String]
    assert output_style.background_color == background
