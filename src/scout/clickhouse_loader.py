"""Load Shadow AI Scout evidence into a live ClickHouse instance.

The pipeline writes a portable ``clickhouse_inserts.sql`` next to every report so
evidence stays auditable offline. This module takes the next step: it connects to a
running ClickHouse over the official ``clickhouse-connect`` client, ensures the
MergeTree schema exists (``sql/schema.sql``), executes the report's inserts, and
returns row counts so the load is verified, not assumed.

    from scout.clickhouse_loader import load_report
    counts = load_report(Path("reports/demo_run_cached"), host="localhost", port=8124)
    # -> {"runs": 1, "sources": 12, "risk_claims": 9, "verdicts": 3}

A local ClickHouse is one command away via the bundled docker-compose:

    docker compose up -d clickhouse
    shadow-scout load-clickhouse reports/demo_run_cached
"""

from __future__ import annotations

from pathlib import Path

SCHEMA_PATH = Path(__file__).resolve().parents[2] / "sql" / "schema.sql"
TABLES = ("runs", "sources", "risk_claims", "verdicts")


def _statements(sql_text: str) -> list[str]:
    """Split a .sql file into statements, treating ';' as a separator only when
    it is OUTSIDE a single-quoted string. Values may legitimately contain ';'
    (e.g. an escaped '&amp;'), so a naive split on ';' corrupts them.

    Escaping matches the generator: backslash-escaped quotes ("\\'") and
    backslashes ("\\\\") inside single-quoted strings.
    """
    body = "\n".join(
        line for line in sql_text.splitlines() if not line.lstrip().startswith("--")
    )
    stmts: list[str] = []
    buf: list[str] = []
    in_str = False
    i = 0
    while i < len(body):
        ch = body[i]
        if in_str:
            buf.append(ch)
            if ch == "\\" and i + 1 < len(body):
                buf.append(body[i + 1])
                i += 2
                continue
            if ch == "'":
                in_str = False
        elif ch == "'":
            in_str = True
            buf.append(ch)
        elif ch == ";":
            stmt = "".join(buf).strip()
            if stmt:
                stmts.append(stmt)
            buf = []
        else:
            buf.append(ch)
        i += 1
    tail = "".join(buf).strip()
    if tail:
        stmts.append(tail)
    return stmts


def load_report(
    report_dir: Path,
    *,
    host: str = "localhost",
    port: int = 8123,
    database: str = "scout",
    username: str = "default",
    password: str = "",
    inserts_file: str = "clickhouse_inserts.sql",
) -> dict[str, int]:
    """Ensure the schema, load one report's inserts, and return per-table row counts.

    Raises FileNotFoundError if the report has no inserts file, and lets
    clickhouse-connect surface connection errors directly.
    """
    try:
        import clickhouse_connect
    except ModuleNotFoundError as exc:  # pragma: no cover - import guard
        raise ModuleNotFoundError(
            "clickhouse-connect is required for live loading. "
            "Install with: pip install 'shadow-ai-scout[clickhouse]' or pip install clickhouse-connect"
        ) from exc

    inserts_path = report_dir / inserts_file
    if not inserts_path.is_file():
        raise FileNotFoundError(f"no {inserts_file} in {report_dir}")

    admin = clickhouse_connect.get_client(host=host, port=port, username=username, password=password)
    admin.command(f"CREATE DATABASE IF NOT EXISTS {database}")

    client = clickhouse_connect.get_client(
        host=host, port=port, username=username, password=password, database=database
    )
    for stmt in _statements(SCHEMA_PATH.read_text(encoding="utf-8")):
        client.command(stmt)
    for stmt in _statements(inserts_path.read_text(encoding="utf-8")):
        client.command(stmt)

    return {t: int(client.command(f"SELECT count() FROM {t}")) for t in TABLES}
