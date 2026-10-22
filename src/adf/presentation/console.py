from __future__ import annotations

from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.theme import Theme

from ..models import OrganizationResult, ResultStatus

THEME = Theme(
    {
        "adf.accent": "bold cyan",
        "adf.title": "bold white",
        "adf.muted": "dim",
        "adf.success": "green",
        "adf.warning": "yellow",
        "adf.error": "bold red",
        "adf.path": "cyan",
        "adf.file": "white",
    }
)

console = Console(theme=THEME)
error_console = Console(stderr=True, theme=THEME)


def banner() -> None:
    title = Text.assemble(("ADF", "adf.accent"), "\n", ("Automate Download Files", "adf.title"))
    console.print(Panel.fit(title, border_style="adf.accent", padding=(0, 8)))


def header(name: str) -> None:
    console.print(Text.assemble(("ADF", "adf.accent"), " · ", (name, "adf.title")))
    console.print("─" * max(12, len(name) + 6), style="adf.muted")


def key_values(rows: list[tuple[str, str]]) -> None:
    table = Table.grid(padding=(0, 3))
    table.add_column(style="adf.muted")
    table.add_column(style="adf.title")
    for key, value in rows:
        table.add_row(key, value)
    console.print(table)


def format_path(path: Path, root: Path | None = None) -> str:
    if root is not None:
        try:
            return str(path.relative_to(root))
        except ValueError:
            pass
    home = Path.home()
    try:
        return f"~/{path.relative_to(home)}"
    except ValueError:
        return str(path)


def print_result(result: OrganizationResult, root: Path) -> None:
    source = result.source.name
    destination = format_path(result.destination, root) if result.destination else "—"

    if result.status is ResultStatus.MOVED:
        console.print(f"[adf.success]✓[/] [adf.file]{source}[/]  →  [adf.path]{destination}[/]")
    elif result.status is ResultStatus.WOULD_MOVE:
        console.print(f"[adf.muted]→[/] [adf.file]{source}[/]  →  [adf.path]{destination}[/]")
    elif result.status is ResultStatus.SKIPPED:
        console.print(f"[adf.warning]![/] [adf.file]{source}[/]  {result.message}")
    else:
        console.print(f"[adf.error]×[/] [adf.file]{source}[/]  {result.message}")
