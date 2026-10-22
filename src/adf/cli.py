from __future__ import annotations

import importlib.util
import logging
import os
import shlex
import shutil
import subprocess
from pathlib import Path
from typing import Optional

import typer
from rich.table import Table
from . import __version__
from .config import get_config_path, load_config, write_config
from .downloads import detect_downloads_directory
from .exceptions import ConfigError
from .models import AppConfig, ResultStatus
from .organizer import FileOrganizer
from .presentation.console import banner, console, error_console, format_path, header, key_values, print_result

app = typer.Typer(
    name="adf",
    help="ADF · Automate Download Files — keep your Downloads directory organized.",
    no_args_is_help=False,
    add_completion=False,
    rich_markup_mode="rich",
    context_settings={"help_option_names": ["-h", "--help"]},
)
config_app = typer.Typer(help="Manage ADF configuration.", add_completion=False)
app.add_typer(config_app, name="config")


def _configure_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.WARNING,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        force=True,
    )


def _load_or_exit() -> AppConfig:
    try:
        return load_config()
    except ConfigError as exc:
        error_console.print(f"[adf.error]×[/] {exc}")
        raise typer.Exit(2) from exc


def _effective_directory(config: AppConfig, directory: Optional[Path]) -> Path:
    return (directory or config.general.directory).expanduser()


def _root_overview() -> None:
    config = _load_or_exit()
    banner()
    console.print("Automated organization for your Downloads.\n", style="adf.muted")
    key_values(
        [
            ("Directory", format_path(config.general.directory)),
            ("Rules", str(len(config.categories))),
            ("Status", "ready"),
        ]
    )
    console.print("\nUse [adf.accent]adf --help[/] to see available commands.")


@app.callback(invoke_without_command=True)
def root(
    ctx: typer.Context,
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable technical debug logging."),
    version: bool = typer.Option(False, "--version", help="Show version and exit."),
) -> None:
    """ADF — Automate Download Files."""
    _configure_logging(verbose)
    if version:
        console.print(f"[adf.accent]ADF {__version__}[/]\nAutomate Download Files")
        raise typer.Exit()
    if ctx.invoked_subcommand is None:
        _root_overview()


@app.command()
def organize(
    directory: Optional[Path] = typer.Option(None, "--directory", "-d", help="Directory to organize."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview changes without moving files."),
) -> None:
    """Organize existing files immediately."""
    config = _load_or_exit()
    target = _effective_directory(config, directory)
    organizer = FileOrganizer(config, directory=target)

    header("Dry Run" if dry_run else "Organize")
    console.print(f"Scanning [adf.path]{format_path(target)}[/]\n")
    try:
        results = organizer.organize_all(dry_run=dry_run)
    except NotADirectoryError as exc:
        error_console.print(f"[adf.error]×[/] {exc}")
        raise typer.Exit(2) from exc

    changed = 0
    for result in results:
        print_result(result, target)
        if result.status in {ResultStatus.MOVED, ResultStatus.WOULD_MOVE}:
            changed += 1

    if dry_run:
        console.print(f"\n{changed} file(s) would be organized. No files were modified.")
    else:
        console.print(f"\n{changed} file(s) organized.")


@app.command()
def watch(
    directory: Optional[Path] = typer.Option(None, "--directory", "-d", help="Directory to watch."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Report moves without changing files."),
    verbose: bool = typer.Option(False, "--verbose", help="Enable technical debug logging for this run."),
) -> None:
    """Monitor the directory continuously and organize new files."""
    if verbose:
        _configure_logging(True)
    config = _load_or_exit()
    target = _effective_directory(config, directory)
    if not target.is_dir():
        error_console.print(f"[adf.error]×[/] Directory not found: {target}")
        raise typer.Exit(2)

    organizer = FileOrganizer(config, directory=target)
    try:
        from .watcher import DownloadWatcher
    except ImportError as exc:
        error_console.print("[adf.error]×[/] watchdog is unavailable. Reinstall ADF with its dependencies.")
        raise typer.Exit(2) from exc
    watcher = DownloadWatcher(organizer, lambda result: print_result(result, target), dry_run=dry_run)

    banner()
    console.print("[adf.success]●[/] Watcher active\n")
    key_values(
        [
            ("Directory", format_path(target)),
            ("Rules", f"{len(config.categories)} loaded"),
            ("Mode", "dry-run" if dry_run else "automatic"),
        ]
    )
    console.print("\nWatching for new files...\n")
    console.print("Ctrl+C to stop", style="adf.muted")

    try:
        watcher.start()
        while True:
            watcher.observer.join(timeout=1.0)
    except KeyboardInterrupt:
        console.print("\n[adf.muted]Watcher stopped.[/]")
    finally:
        if watcher.observer.is_alive():
            watcher.stop()


@app.command()
def status() -> None:
    """Show the current ADF configuration and runtime status."""
    config = _load_or_exit()
    header("Status")
    key_values(
        [
            ("Directory", format_path(config.general.directory)),
            ("Configuration", format_path(get_config_path())),
            ("Rules", str(len(config.categories))),
            ("Watcher", "inactive"),
            ("Version", __version__),
        ]
    )


@app.command()
def rules(
    category: Optional[str] = typer.Option(None, "--category", "-c", help="Filter by category name."),
) -> None:
    """List active organization rules."""
    config = _load_or_exit()
    selected = config.categories
    if category:
        selected = tuple(rule for rule in selected if rule.name.lower() == category.lower())
        if not selected:
            error_console.print(f"[adf.error]×[/] Unknown category: {category}")
            raise typer.Exit(2)

    header("Rules")
    table = Table(show_header=True, header_style="adf.accent", box=None, pad_edge=False)
    table.add_column("Category")
    table.add_column("Extensions")
    table.add_column("Destination", style="adf.path")
    for rule in selected:
        table.add_row(rule.name.title(), " ".join(ext.lstrip(".") for ext in rule.extensions), rule.destination.as_posix())
    console.print(table)


@app.command("init")
def init_command(
    directory: Optional[Path] = typer.Option(None, "--directory", "-d", help="Downloads directory to configure."),
    force: bool = typer.Option(False, "--force", help="Replace an existing ADF configuration."),
) -> None:
    """Create the initial ADF configuration."""
    from .config import default_config

    target = (directory or detect_downloads_directory()).expanduser()
    config = default_config(target)
    banner()
    console.print("Setting up ADF...\n")
    try:
        path = write_config(config, overwrite=force)
    except ConfigError as exc:
        error_console.print(f"[adf.error]×[/] {exc}")
        raise typer.Exit(2) from exc

    console.print(f"[adf.success]✓[/] Configuration created  [adf.path]{format_path(path)}[/]")
    if target.exists():
        console.print(f"[adf.success]✓[/] Downloads directory detected  [adf.path]{format_path(target)}[/]")
    else:
        console.print(f"[adf.warning]![/] Directory does not exist yet  [adf.path]{format_path(target)}[/]")
    console.print(f"[adf.success]✓[/] {len(config.categories)} default rules loaded")
    console.print("\nADF is ready.\n\nRun:\n\n  [adf.accent]adf watch[/]")


@app.command()
def doctor() -> None:
    """Diagnose configuration, filesystem access, and essential dependencies."""
    header("Doctor")
    checks: list[tuple[str, bool, str]] = []

    try:
        config = load_config()
        checks.append(("Configuration is valid", True, ""))
    except ConfigError as exc:
        checks.append(("Configuration is valid", False, str(exc)))
        config = None

    target = config.general.directory if config else detect_downloads_directory()
    exists = target.is_dir()
    checks.append(("Downloads directory exists", exists, str(target) if not exists else ""))
    checks.append(("Directory is readable", exists and os.access(target, os.R_OK), ""))
    checks.append(("Directory is writable", exists and os.access(target, os.W_OK), ""))
    checks.append(("Rules loaded", bool(config and config.categories), ""))

    dependencies = all(importlib.util.find_spec(name) is not None for name in ("watchdog", "rich", "typer"))
    checks.append(("Essential dependencies available", dependencies, ""))

    watcher_ok = False
    if exists and dependencies:
        try:
            from watchdog.events import FileSystemEventHandler
            from watchdog.observers import Observer

            observer = Observer()
            observer.schedule(FileSystemEventHandler(), str(target), recursive=False)
            observer.unschedule_all()
            watcher_ok = True
        except Exception as exc:  # watchdog can raise platform-specific exceptions
            logging.getLogger(__name__).debug("Watcher diagnostic failed", exc_info=exc)
    checks.append(("Watcher can be initialized", watcher_ok, ""))

    issues = 0
    for label, ok, detail in checks:
        if ok:
            console.print(f"[adf.success]✓[/] {label}")
        else:
            issues += 1
            suffix = f" — {detail}" if detail else ""
            console.print(f"[adf.error]×[/] {label}{suffix}")

    if issues:
        console.print(f"\n{issues} issue(s) detected.")
        raise typer.Exit(1)
    console.print("\nSystem healthy.")


@app.command()
def version() -> None:
    """Show the installed ADF version."""
    console.print(f"[adf.accent]ADF {__version__}[/]\nAutomate Download Files")


@config_app.command("show")
def config_show() -> None:
    """Show the active configuration."""
    config = _load_or_exit()
    header("Config")
    key_values(
        [
            ("Path", format_path(get_config_path())),
            ("Directory", format_path(config.general.directory)),
            ("Duplicate policy", config.general.handle_duplicates.value),
            ("Unknown files", config.general.unknown_destination.as_posix()),
        ]
    )


@config_app.command("path")
def config_path() -> None:
    """Print the configuration file path."""
    console.print(str(get_config_path()))


@config_app.command("edit")
def config_edit() -> None:
    """Open the configuration in the system editor."""
    path = get_config_path()
    if not path.exists():
        error_console.print("[adf.error]×[/] Configuration not found. Run `adf init` first.")
        raise typer.Exit(2)

    editor = os.environ.get("EDITOR") or os.environ.get("VISUAL")
    if editor:
        command = shlex.split(editor, posix=os.name != "nt")
        subprocess.run([*command, str(path)], check=False)
        return

    if os.name == "nt":
        os.startfile(path)  # type: ignore[attr-defined]
        return

    candidate = shutil.which("xdg-open") or shutil.which("open")
    if candidate:
        subprocess.run([candidate, str(path)], check=False)
        return

    error_console.print(f"[adf.warning]![/] No editor detected. Configuration: {path}")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
