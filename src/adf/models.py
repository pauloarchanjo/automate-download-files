from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class DuplicatePolicy(StrEnum):
    RENAME = "rename"
    SKIP = "skip"
    OVERWRITE = "overwrite"


class ResultStatus(StrEnum):
    MOVED = "moved"
    WOULD_MOVE = "would_move"
    SKIPPED = "skipped"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class CategoryRule:
    name: str
    destination: Path
    extensions: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class GeneralConfig:
    directory: Path
    create_directories: bool = True
    handle_duplicates: DuplicatePolicy = DuplicatePolicy.RENAME
    unknown_destination: Path = Path("Others")


@dataclass(frozen=True, slots=True)
class AppConfig:
    general: GeneralConfig
    categories: tuple[CategoryRule, ...]


@dataclass(frozen=True, slots=True)
class OrganizationResult:
    source: Path
    destination: Path | None
    category: str | None
    status: ResultStatus
    message: str = ""
