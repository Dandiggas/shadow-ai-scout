from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from scout.agentic import run_agentic_scan
from scout.approvals import DecisionStore
from scout.errors import ScoutAPIError
from scout.pipeline import run_cached_scan
from scout.review import review_approved_products

app = typer.Typer(help="Shadow AI Scout: policy-evidence scanner for AI vendor review")
console = Console()


@app.callback()
def main():
    """Run Shadow AI Scout commands."""


def _print_result(result):
    table = Table(title="Shadow AI Scout Verdicts")
    table.add_column("Tool")
    table.add_column("Verdict")
    table.add_column("Score", justify="right")
    table.add_column("Failed policy")
    for verdict in result.verdicts:
        table.add_row(verdict.tool_name, verdict.verdict, str(verdict.risk_score), ", ".join(verdict.failed_policy) or "None")
    console.print(table)
    console.print(f"Evidence JSON: {result.evidence_json}")
    console.print(f"Markdown report: {result.markdown_report}")
    console.print(f"ClickHouse inserts: {result.clickhouse_sql}")


@app.command()
def demo(
    tools: str = typer.Option("Cursor,Granola,Rewind AI", help="Comma-separated tool names"),
    company_context: str = typer.Option("Security-sensitive company handling source code, customer data, and internal meetings."),
    output_dir: Path = typer.Option(Path("reports/demo_run_cached")),
):
    """Run the cached zero-key demo."""
    result = run_cached_scan([t.strip() for t in tools.split(",") if t.strip()], company_context, output_dir)
    _print_result(result)


@app.command()
def scan(
    tools: str = typer.Option("Cursor,Granola,Rewind AI", help="Comma-separated tool names"),
    company_context: str = typer.Option("Security-sensitive company handling source code, customer data, and internal meetings."),
    output_dir: Path = typer.Option(Path("reports/live_run")),
    max_iterations: int = typer.Option(3, help="Plan-act-observe loops per tool"),
):
    """Run the live agentic scan. Requires TAVILY_API_KEY and GEMINI_API_KEY/GOOGLE_API_KEY."""
    try:
        result = run_agentic_scan([t.strip() for t in tools.split(",") if t.strip()], company_context, output_dir, max_iterations=max_iterations)
    except ScoutAPIError as exc:
        console.print(f"[red]{exc.provider} setup error[/red]: {exc.user_message}")
        if exc.detail:
            console.print(f"[dim]{exc.detail}[/dim]")
        raise typer.Exit(code=1) from exc
    _print_result(result)
    trace_path = output_dir / "agent_trace.json"
    console.print(f"Agent trace: {trace_path}")


@app.command("review-approved")
def review_approved(
    company_context: str = typer.Option("Security-sensitive company handling source code, customer data, and internal meetings."),
    decisions_path: Path = typer.Option(Path("reports/decisions.json"), help="Saved approval decisions JSON"),
    output_dir: Path = typer.Option(Path("reports/weekly_review")),
    live: bool = typer.Option(False, "--live/--cached", help="Use live Tavily/Gemini scan instead of cached demo fixtures"),
    max_iterations: int = typer.Option(1, help="Plan-act-observe loops per approved tool in live mode"),
):
    """Rescan approved/conditionally approved products for weekly compliance review."""
    store = DecisionStore(decisions_path)

    def scan_func(tools: list[str], context: str, out: Path):
        if live:
            return run_agentic_scan(tools, context, out, max_iterations=max_iterations)
        return run_cached_scan(tools, context, out)

    try:
        result = review_approved_products(store, company_context, output_dir, scan_func=scan_func)
    except ScoutAPIError as exc:
        console.print(f"[red]{exc.provider} setup error[/red]: {exc.user_message}")
        if exc.detail:
            console.print(f"[dim]{exc.detail}[/dim]")
        raise typer.Exit(code=1) from exc
    except ValueError as exc:
        console.print(f"[yellow]{exc}[/yellow]")
        raise typer.Exit(code=0) from exc

    _print_result(result)
    console.print(f"Weekly summary: {output_dir / 'weekly_review_summary.md'}")


if __name__ == "__main__":
    app()
