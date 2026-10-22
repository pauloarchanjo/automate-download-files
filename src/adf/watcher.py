from __future__ import annotations

import logging
import time
from collections.abc import Callable
from pathlib import Path
from threading import Lock

from watchdog.events import FileMovedEvent, FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from .models import OrganizationResult, ResultStatus
from .organizer import FileOrganizer, is_file_stable

logger = logging.getLogger(__name__)


class _RecentEvents:
    def __init__(self, window_seconds: float = 2.0) -> None:
        self.window_seconds = window_seconds
        self._seen: dict[Path, float] = {}
        self._lock = Lock()

    def should_process(self, path: Path) -> bool:
        now = time.monotonic()
        with self._lock:
            previous = self._seen.get(path)
            self._seen[path] = now
            cutoff = now - self.window_seconds
            self._seen = {item: stamp for item, stamp in self._seen.items() if stamp >= cutoff}
        return previous is None or (now - previous) >= self.window_seconds


class ADFEventHandler(FileSystemEventHandler):
    def __init__(
        self,
        organizer: FileOrganizer,
        on_result: Callable[[OrganizationResult], None],
        *,
        dry_run: bool = False,
    ) -> None:
        self.organizer = organizer
        self.on_result = on_result
        self.dry_run = dry_run
        self._recent = _RecentEvents()

    def on_created(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self._handle(Path(event.src_path))

    def on_moved(self, event: FileMovedEvent) -> None:
        if not event.is_directory:
            self._handle(Path(event.dest_path))

    def on_modified(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self._handle(Path(event.src_path))

    def _handle(self, path: Path) -> None:
        if path.parent.resolve() != self.organizer.directory.resolve():
            return
        if not self._recent.should_process(path):
            return
        if self.organizer.classifier.is_temporary(path):
            return
        if not path.exists() or not path.is_file():
            return
        if not is_file_stable(path):
            logger.debug("File did not become stable in time: %s", path)
            return

        result = self.organizer.organize(path, dry_run=self.dry_run)
        if result.status is not ResultStatus.SKIPPED or result.message != "File no longer exists":
            self.on_result(result)


class DownloadWatcher:
    def __init__(
        self,
        organizer: FileOrganizer,
        on_result: Callable[[OrganizationResult], None],
        *,
        dry_run: bool = False,
    ) -> None:
        self.organizer = organizer
        self.handler = ADFEventHandler(organizer, on_result, dry_run=dry_run)
        self.observer = Observer()

    def start(self) -> None:
        self.observer.schedule(self.handler, str(self.organizer.directory), recursive=False)
        self.observer.start()

    def stop(self) -> None:
        self.observer.stop()
        self.observer.join()
