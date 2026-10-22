from __future__ import annotations

from pathlib import Path

from .config import TEMPORARY_EXTENSIONS
from .models import CategoryRule


class FileClassifier:
    def __init__(self, rules: tuple[CategoryRule, ...]) -> None:
        self._rules = rules

    @staticmethod
    def is_temporary(path: Path) -> bool:
        name = path.name.lower()
        return any(name.endswith(extension) for extension in TEMPORARY_EXTENSIONS)

    def classify(self, path: Path) -> CategoryRule | None:
        name = path.name.lower()
        for rule in self._rules:
            if any(name.endswith(extension) for extension in rule.extensions):
                return rule
        return None
