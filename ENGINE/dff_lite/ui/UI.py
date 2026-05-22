# ui/ui.py — Rich terminal UI (progress, tables, panels)
"""Colored status output and match summary tables."""

from __future__ import annotations

import sys
from typing import Dict, List

from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table
from rich.text import Text

from dff_lite.core.Models import MatchResult

if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

console = Console()


def format_size(num_bytes: int) -> str:
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024.0:
            return f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{size:.2f} PB"


def print_welcome_banner() -> None:
    text = Text()
    text.append("DFF Lite Cursor — Filename Intelligence Engine\n", style="bold cyan")
    text.append("Multi-stage heuristic duplicate detection (not hash-based)\n\n", style="italic white")
    text.append("Modular pipeline • YAML weights • SQLite cache • Blocking indexes", style="dim grey70")
    console.print(Panel(text, border_style="cyan", subtitle="[bold magenta]Cursor Edition v1.0[/bold magenta]"))
    console.print()


def print_success(msg: str) -> None:
    console.print(f"[bold green]OK[/bold green] {msg}")


def print_warning(msg: str) -> None:
    console.print(f"[bold yellow]WARN[/bold yellow] {msg}")


def print_error(msg: str) -> None:
    console.print(f"[bold red]ERROR[/bold red] {msg}")


def print_status(msg: str) -> None:
    console.print(f"[bold blue]INFO[/bold blue] {msg}")


def print_match_summary(matches: List[MatchResult]) -> None:
    """Category counts panel."""
    counts: Dict[str, int] = {}
    for m in matches:
        counts[m.category] = counts.get(m.category, 0) + 1
    if not counts:
        return
    lines = [f"  {k}: [cyan]{v}[/cyan]" for k, v in sorted(counts.items(), key=lambda x: -x[1])]
    console.print(Panel("\n".join(lines), title="Match Summary", border_style="green"))


def print_match_table(matches: List[MatchResult]) -> None:
    if not matches:
        print_warning("No matches at or above the configured threshold.")
        return

    table = Table(
        title="[bold cyan]Duplicate / Similarity Report[/bold cyan]",
        border_style="grey37",
        header_style="bold cyan",
    )
    table.add_column("Score", justify="center")
    table.add_column("Category")
    table.add_column("File A", overflow="ellipsis", max_width=40)
    table.add_column("File B", overflow="ellipsis", max_width=40)
    table.add_column("Sizes", justify="right")

    styles = {
        "almost certain duplicate": ("bold green3", "[green3]Almost Certain[/green3]"),
        "highly likely": ("bold spring_green3", "[spring_green3]Highly Likely[/spring_green3]"),
        "potential duplicate": ("bold gold3", "[gold3]Potential[/gold3]"),
        "weak similarity": ("bold deep_sky_blue1", "[deep_sky_blue1]Weak[/deep_sky_blue1]"),
    }

    for m in matches:
        score_style, cat_style = styles.get(m.category, ("white", m.category))
        table.add_row(
            Text(f"{m.confidence_score}%", style=score_style),
            cat_style,
            Text(m.path_a, style="grey70"),
            Text(m.path_b, style="grey70"),
            Text(f"A: {format_size(m.file_a_size)}\nB: {format_size(m.file_b_size)}", style="grey50"),
        )
    console.print(table)
    print_match_summary(matches)
    console.print()


def get_progress_bar() -> Progress:
    return Progress(
        SpinnerColumn(spinner_name="dots", style="cyan"),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(bar_width=40, style="grey37", complete_style="cyan"),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        console=console,
    )

