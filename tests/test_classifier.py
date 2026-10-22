from pathlib import Path

from adf.classifier import FileClassifier
from adf.config import default_config


def test_classifies_extension_case_insensitively() -> None:
    classifier = FileClassifier(default_config().categories)
    assert classifier.classify(Path("PHOTO.JPEG")).name == "images"


def test_pdf_has_specific_rule() -> None:
    classifier = FileClassifier(default_config().categories)
    rule = classifier.classify(Path("invoice.pdf"))
    assert rule is not None
    assert rule.name == "pdf"
    assert rule.destination == Path("Documents/PDF")


def test_unknown_extension_returns_none() -> None:
    classifier = FileClassifier(default_config().categories)
    assert classifier.classify(Path("mystery.xyzabc")) is None


def test_temporary_extension_is_ignored() -> None:
    classifier = FileClassifier(default_config().categories)
    assert classifier.is_temporary(Path("video.mp4.crdownload"))
