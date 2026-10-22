from pathlib import Path

from adf.config import load_config, render_config, write_config
from adf.models import DuplicatePolicy


def test_config_round_trip(tmp_path: Path) -> None:
    from adf.config import default_config

    config = default_config(tmp_path / "Downloads")
    path = tmp_path / "config.toml"
    write_config(config, path)
    loaded = load_config(path)

    assert loaded.general.directory == tmp_path / "Downloads"
    assert loaded.general.handle_duplicates is DuplicatePolicy.RENAME
    assert loaded.categories == config.categories


def test_render_config_contains_general_and_categories(tmp_path: Path) -> None:
    from adf.config import default_config

    rendered = render_config(default_config(tmp_path))
    assert "[general]" in rendered
    assert "[categories.images]" in rendered
