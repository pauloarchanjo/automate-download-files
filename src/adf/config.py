from __future__ import annotations

import tomllib
from pathlib import Path

from platformdirs import user_config_path

from .downloads import detect_downloads_directory
from .exceptions import ConfigError
from .models import AppConfig, CategoryRule, DuplicatePolicy, GeneralConfig

TEMPORARY_EXTENSIONS = frozenset({".crdownload", ".part", ".tmp", ".download"})

DEFAULT_CATEGORIES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    (
        "images",
        "Images",
        (
            ".jpg", ".jpeg", ".jpe", ".jif", ".jfif", ".jfi", ".png", ".gif", ".webp",
            ".tiff", ".tif", ".psd", ".raw", ".arw", ".cr2", ".nrw", ".k25", ".bmp",
            ".dib", ".heif", ".heic", ".ind", ".indd", ".indt", ".jp2", ".j2k", ".jpf",
            ".jpx", ".jpm", ".mj2", ".svg", ".svgz", ".ai", ".eps", ".ico",
        ),
    ),
    (
        "video",
        "Videos",
        (
            ".webm", ".mpg", ".mp2", ".mpeg", ".mpe", ".mpv", ".ogv", ".mp4", ".mp4v",
            ".m4v", ".avi", ".wmv", ".mov", ".qt", ".flv", ".swf", ".avchd", ".mkv",
        ),
    ),
    ("audio", "Audio", (".m4a", ".flac", ".mp3", ".wav", ".wma", ".aac", ".ogg", ".oga", ".opus")),
    ("pdf", "Documents/PDF", (".pdf",)),
    (
        "documents",
        "Documents",
        (".doc", ".docx", ".md", ".odt", ".xls", ".xlsx", ".ppt", ".pptx", ".csv", ".txt"),
    ),
    ("archives", "Archives", (".gz", ".zip", ".rar", ".7z", ".sitx", ".tar", ".tar.gz")),
    ("installers", "Installers", (".exe", ".msi", ".apk", ".bat", ".cmd", ".vbs", ".deb", ".rpm", ".dmg", ".pkg")),
    (
        "development",
        "Development",
        (".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".c", ".cpp", ".h", ".hpp", ".go", ".rs", ".php", ".rb", ".sh", ".ps1", ".sql", ".json", ".yaml", ".yml", ".toml", ".xml", ".html", ".css", ".scss"),
    ),
)


def get_config_path() -> Path:
    return user_config_path("adf", appauthor=False) / "config.toml"


def _normalize_extension(extension: str) -> str:
    value = extension.strip().lower()
    if not value:
        raise ConfigError("Category extensions cannot be empty.")
    return value if value.startswith(".") else f".{value}"


def default_config(directory: Path | None = None) -> AppConfig:
    rules = tuple(
        CategoryRule(
            name=name,
            destination=Path(destination),
            extensions=tuple(_normalize_extension(ext) for ext in extensions),
        )
        for name, destination, extensions in DEFAULT_CATEGORIES
    )
    general = GeneralConfig(directory=(directory or detect_downloads_directory()).expanduser())
    return AppConfig(general=general, categories=rules)


def _parse_general(raw: dict[str, object], fallback_directory: Path) -> GeneralConfig:
    directory = Path(str(raw.get("directory", fallback_directory))).expanduser()
    create_directories = bool(raw.get("create_directories", True))
    unknown_destination = Path(str(raw.get("unknown_destination", "Others")))
    try:
        duplicate_policy = DuplicatePolicy(str(raw.get("handle_duplicates", "rename")))
    except ValueError as exc:
        raise ConfigError("handle_duplicates must be rename, skip, or overwrite.") from exc

    if unknown_destination.is_absolute():
        raise ConfigError("unknown_destination must be relative to the organized directory.")

    return GeneralConfig(
        directory=directory,
        create_directories=create_directories,
        handle_duplicates=duplicate_policy,
        unknown_destination=unknown_destination,
    )


def _parse_categories(raw: dict[str, object]) -> tuple[CategoryRule, ...]:
    rules: list[CategoryRule] = []
    for name, value in raw.items():
        if not isinstance(value, dict):
            raise ConfigError(f"Category '{name}' must be a TOML table.")
        destination = Path(str(value.get("destination", name.title())))
        if destination.is_absolute():
            raise ConfigError(f"Category '{name}' destination must be relative.")
        extensions_raw = value.get("extensions", [])
        if not isinstance(extensions_raw, list):
            raise ConfigError(f"Category '{name}' extensions must be a list.")
        extensions = tuple(_normalize_extension(str(ext)) for ext in extensions_raw)
        if not extensions:
            raise ConfigError(f"Category '{name}' must contain at least one extension.")
        rules.append(CategoryRule(name=name, destination=destination, extensions=extensions))
    return tuple(rules)


def load_config(path: Path | None = None) -> AppConfig:
    config_path = path or get_config_path()
    if not config_path.exists():
        return default_config()

    try:
        with config_path.open("rb") as stream:
            raw = tomllib.load(stream)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ConfigError(f"Could not read configuration: {exc}") from exc

    general_raw = raw.get("general", {})
    categories_raw = raw.get("categories", {})
    if not isinstance(general_raw, dict) or not isinstance(categories_raw, dict):
        raise ConfigError("Configuration must contain [general] and [categories] tables.")

    general = _parse_general(general_raw, detect_downloads_directory())
    categories = _parse_categories(categories_raw)
    if not categories:
        raise ConfigError("At least one category must be configured.")
    return AppConfig(general=general, categories=categories)


def _toml_quote(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def render_config(config: AppConfig) -> str:
    lines = [
        "[general]",
        f"directory = {_toml_quote(str(config.general.directory))}",
        f"create_directories = {str(config.general.create_directories).lower()}",
        f"handle_duplicates = {_toml_quote(config.general.handle_duplicates.value)}",
        f"unknown_destination = {_toml_quote(config.general.unknown_destination.as_posix())}",
        "",
    ]
    for rule in config.categories:
        lines.extend(
            [
                f"[categories.{rule.name}]",
                f"destination = {_toml_quote(rule.destination.as_posix())}",
                "extensions = ["
                + ", ".join(_toml_quote(ext) for ext in rule.extensions)
                + "]",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def write_config(config: AppConfig, path: Path | None = None, *, overwrite: bool = False) -> Path:
    config_path = path or get_config_path()
    if config_path.exists() and not overwrite:
        raise ConfigError(f"Configuration already exists: {config_path}")
    try:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(render_config(config), encoding="utf-8")
    except OSError as exc:
        raise ConfigError(f"Could not write configuration: {exc}") from exc
    return config_path
