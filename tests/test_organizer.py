from pathlib import Path

from adf.config import default_config
from adf.models import ResultStatus
from adf.organizer import FileOrganizer


def make_organizer(tmp_path: Path) -> FileOrganizer:
    return FileOrganizer(default_config(tmp_path), directory=tmp_path)


def test_generates_expected_destination(tmp_path: Path) -> None:
    source = tmp_path / "photo.jpg"
    source.write_bytes(b"x")
    result = make_organizer(tmp_path).organize(source, dry_run=True)
    assert result.status is ResultStatus.WOULD_MOVE
    assert result.destination == tmp_path / "Images" / "photo.jpg"


def test_unknown_files_go_to_others(tmp_path: Path) -> None:
    source = tmp_path / "archive.unknown"
    source.write_bytes(b"x")
    result = make_organizer(tmp_path).organize(source, dry_run=True)
    assert result.destination == tmp_path / "Others" / "archive.unknown"
    assert result.category == "others"


def test_dry_run_does_not_move_file(tmp_path: Path) -> None:
    source = tmp_path / "notes.txt"
    source.write_text("hello", encoding="utf-8")
    result = make_organizer(tmp_path).organize(source, dry_run=True)
    assert result.status is ResultStatus.WOULD_MOVE
    assert source.exists()
    assert not (tmp_path / "Documents" / "notes.txt").exists()


def test_move_creates_destination(tmp_path: Path) -> None:
    source = tmp_path / "notes.txt"
    source.write_text("hello", encoding="utf-8")
    result = make_organizer(tmp_path).organize(source)
    assert result.status is ResultStatus.MOVED
    assert not source.exists()
    assert (tmp_path / "Documents" / "notes.txt").exists()


def test_duplicate_renames_incoming_file(tmp_path: Path) -> None:
    destination = tmp_path / "Images"
    destination.mkdir()
    original = destination / "photo.jpg"
    original.write_text("old", encoding="utf-8")
    incoming = tmp_path / "photo.jpg"
    incoming.write_text("new", encoding="utf-8")

    result = make_organizer(tmp_path).organize(incoming)

    assert result.destination == destination / "photo_1.jpg"
    assert original.read_text(encoding="utf-8") == "old"
    assert (destination / "photo_1.jpg").read_text(encoding="utf-8") == "new"


def test_temporary_download_is_skipped(tmp_path: Path) -> None:
    source = tmp_path / "movie.mp4.part"
    source.write_bytes(b"partial")
    result = make_organizer(tmp_path).organize(source)
    assert result.status is ResultStatus.SKIPPED
    assert result.message == "Incomplete download"


def test_directories_are_not_moved(tmp_path: Path) -> None:
    folder = tmp_path / "folder.jpg"
    folder.mkdir()
    result = make_organizer(tmp_path).organize(folder)
    assert result.status is ResultStatus.SKIPPED
    assert folder.is_dir()
