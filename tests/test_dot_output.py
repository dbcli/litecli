from litecli.packages.dot_output import format_dot_output


def test_dot_output_formats_edges():
    rows = [("orders", "customers"), ("line_items", "orders")]
    headers = ["child", "parent"]

    assert list(format_dot_output(rows, headers)) == [
        "digraph result {",
        "  // Columns: child, parent",
        '  "orders" -> "customers";',
        '  "line_items" -> "orders";',
        "}",
    ]


def test_dot_output_formats_nodes_and_escapes_values():
    rows = [('a"b',), ("line\nbreak",), (None,)]

    assert list(format_dot_output(rows, ["name"])) == [
        "digraph result {",
        "  // Columns: name",
        '  "a\\"b";',
        '  "line\\nbreak";',
        '  "NULL";',
        "}",
    ]


def test_dot_output_uses_extra_columns_as_edge_label():
    rows = [("a", "b", "foreign key")]
    headers = ["source", "target", "relation"]

    assert list(format_dot_output(rows, headers)) == [
        "digraph result {",
        "  // Columns: source, target, relation",
        '  "a" -> "b" [label="relation=foreign key"];',
        "}",
    ]
