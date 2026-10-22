from __future__ import annotations

import logging
import shutil
import time
from pathlib import Path

from .classifier import FileClassifier
from .models import AppConfig, DuplicatePolicy, OrganizationResult, ResultStatus

logger = logging.getLogger(__name__)


class FileOrganizer:
    def __init__(self, config: AppConfig, *, directory: Path | None = None) -> None:
        self.config = config
        self.directory = (directory or config.general.directory).expanduser()
        self.classifier = FileClassifier(config.categories)

    def organize_all(self, *, dry_run: bool = False) -> list[OrganizationResult]:
        if not self.directory.is_dir():
            raise NotADirectoryError(f"Directory not found: {self.directory}")
        results: list[OrganizationResult] = []
        for path in sorted(self.directory.iterdir(), key=lambda item: item.name.lower()):
            if path.is_file():
                results.append(self.organize(path, dry_run=dry_run))
        return results

    def organize(self, path: Path, *, dry_run: bool = False) -> OrganizationResult:
        path = path.expanduser()
        if not path.exists():
            return OrganizationResult(path, None, None, ResultStatus.SKIPPED, "File no longer exists")
        if not path.is_file():
            return OrganizationResult(path, None, None, ResultStatus.SKIPPED, "Directories are ignored")
        if path.parent.resolve() != self.directory.resolve():
            return OrganizationResult(path, None, None, ResultStatus.SKIPPED, "File is outside the watched directory")
        if self.classifier.is_temporary(path):
            return OrganizationResult(path, None, None, ResultStatus.SKIPPED, "Incomplete download")

        rule = self.classifier.classify(path)
        category = rule.name if rule else "others"
        relative_destination = rule.destination if rule else self.config.general.unknown_destination
        destination_dir = self.directory / relative_destination
        target = destination_dir / path.name

        try:
            target = self._resolve_duplicate(target)
        except FileExistsError as exc:
            return OrganizationResult(path, target, category, ResultStatus.SKIPPED, str(exc))

        if dry_run:
            return OrganizationResult(path, target, category, ResultStatus.WOULD_MOVE)

        try:
            if not destination_dir.exists():
                if not self.config.general.create_directories:
                    return OrganizationResult(
                        path,
                        target,
                        category,
                        ResultStatus.ERROR,
                        f"Destination does not exist: {destination_dir}",
                    )
                destination_dir.mkdir(parents=True, exist_ok=True)

            if self.config.general.handle_duplicates is DuplicatePolicy.OVERWRITE and target.exists():
                if target.is_file():
                    target.unlink()
                else:
                    return OrganizationResult(
                        path, target, category, ResultStatus.ERROR, "Refusing to overwrite a directory"
                    )

            shutil.move(str(path), str(target))
            logger.info("Moved %s -> %s", path, target)
            return OrganizationResult(path, target, category, ResultStatus.MOVED)
        except OSError as exc:
            logger.exception("Could not move %s", path)
            return OrganizationResult(path, target, category, ResultStatus.ERROR, str(exc))

    def _resolve_duplicate(self, target: Path) -> Path:
        if not target.exists():
            return target

        policy = self.config.general.handle_duplicates
        if policy is DuplicatePolicy.SKIP:
            raise FileExistsError("Destination already exists")
        if policy is DuplicatePolicy.OVERWRITE:
            return target

        counter = 1
        stem = target.stem
        suffix = target.suffix
        while True:
            candidate = target.with_name(f"{stem}_{counter}{suffix}")
            if not candidate.exists():
                return candidate
            counter += 1


def is_file_stable(path: Path, *, checks: int = 3, interval: float = 0.4) -> bool:
    """Return True after size and mtime stay unchanged for consecutive checks."""
    if checks < 2:
        raise ValueError("checks must be at least 2")

    previous: tuple[int, int] | None = None
    stable_samples = 0
    for _ in range(checks + 2):
        try:
            stat = path.stat()
        except OSError:
            return False
        current = (stat.st_size, stat.st_mtime_ns)
        if current == previous:
            stable_samples += 1
            if stable_samples >= checks - 1:
                return True
        else:
            stable_samples = 0
        previous = current
        time.sleep(interval)
    return False
