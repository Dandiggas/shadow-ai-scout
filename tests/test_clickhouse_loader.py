from scout.clickhouse_loader import _statements


def test_splitter_ignores_semicolons_inside_strings():
    # '&amp;' contains a ';' that must NOT split the statement.
    sql = (
        "-- header comment\n"
        "INSERT INTO sources VALUES ('risks &amp; vulnerabilities');\n"
        "INSERT INTO verdicts VALUES ('ok');\n"
    )
    stmts = _statements(sql)
    assert len(stmts) == 2
    assert "&amp;" in stmts[0]
    assert stmts[0].startswith("INSERT INTO sources")
    assert stmts[1].startswith("INSERT INTO verdicts")


def test_splitter_handles_escaped_quotes():
    sql = r"INSERT INTO t VALUES ('it\'s; fine');" + "\nINSERT INTO t VALUES ('b');\n"
    stmts = _statements(sql)
    assert len(stmts) == 2
    assert r"it\'s; fine" in stmts[0]


def test_splitter_drops_comments_and_blanks():
    assert _statements("-- only a comment\n\n") == []
