"""The blueprint publishes one way: repo to mirror.

The direction is the whole point. When the authoritative copy lived outside the repo,
correcting the blueprint meant editing there and then syncing here, and forgetting the
first step reverted the second silently - which is the failure mode this project's
whole build-state system exists to avoid.

The one case that needs care is somebody editing the OneDrive copy out of old habit.
Publishing would discard it, so the tool records what it last published and refuses when
the mirror no longer matches that.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tools import sync_blueprint

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def staged(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    source = tmp_path / "docs" / "architecture.html"
    source.parent.mkdir()
    source.write_text("<html>the design</html>", encoding="utf-8")
    mirror = tmp_path / "onedrive" / "Architecture.html"
    mirror.parent.mkdir()
    record = tmp_path / "docs" / ".blueprint-mirror"

    monkeypatch.setattr(sync_blueprint, "ROOT", tmp_path)
    monkeypatch.setattr(sync_blueprint, "SOURCE", source)
    monkeypatch.setattr(sync_blueprint, "MIRROR", mirror)
    monkeypatch.setattr(sync_blueprint, "RECORD", record)
    return {"source": source, "mirror": mirror, "record": record}


def test_the_repo_copy_is_the_one_that_exists(staged: dict[str, Path]) -> None:
    """The real one, not the fixture: it travels with the repo and the tests read it."""
    assert (ROOT / "docs" / "architecture.html").is_file()


def test_publishing_creates_a_missing_mirror(staged: dict[str, Path]) -> None:
    assert sync_blueprint.main([]) == 0
    assert staged["mirror"].read_text(encoding="utf-8") == "<html>the design</html>"


def test_publishing_overwrites_a_stale_mirror(staged: dict[str, Path]) -> None:
    sync_blueprint.main([])
    staged["source"].write_text("<html>the design, corrected</html>", encoding="utf-8")
    assert sync_blueprint.main([]) == 0
    assert staged["mirror"].read_text(encoding="utf-8") == "<html>the design, corrected</html>"


def test_an_edited_mirror_is_not_silently_discarded(staged: dict[str, Path]) -> None:
    """The one way this arrangement could lose work, so it fails closed."""
    sync_blueprint.main([])
    staged["mirror"].write_text("<html>edited over there</html>", encoding="utf-8")
    staged["source"].write_text("<html>edited over here</html>", encoding="utf-8")

    assert sync_blueprint.main([]) == 1, "publishing over an edited mirror must be refused"
    assert staged["mirror"].read_text(encoding="utf-8") == "<html>edited over there</html>"


def test_force_publishes_over_an_edited_mirror(staged: dict[str, Path]) -> None:
    sync_blueprint.main([])
    staged["mirror"].write_text("<html>edited over there</html>", encoding="utf-8")
    staged["source"].write_text("<html>edited over here</html>", encoding="utf-8")

    assert sync_blueprint.main(["--force"]) == 0
    assert staged["mirror"].read_text(encoding="utf-8") == "<html>edited over here</html>"


def test_pull_takes_an_edit_made_in_the_mirror(staged: dict[str, Path]) -> None:
    """The escape hatch, for when somebody did edit the OneDrive copy on purpose. It
    lands in the repo, where it gets committed with a reason like any other change."""
    sync_blueprint.main([])
    staged["mirror"].write_text("<html>edited over there</html>", encoding="utf-8")

    assert sync_blueprint.main(["--pull"]) == 0
    assert staged["source"].read_text(encoding="utf-8") == "<html>edited over there</html>"


def test_check_changes_nothing(staged: dict[str, Path]) -> None:
    sync_blueprint.main([])
    staged["source"].write_text("<html>the design, corrected</html>", encoding="utf-8")

    assert sync_blueprint.main(["--check"]) == 1, "drift should report non-zero"
    assert staged["mirror"].read_text(encoding="utf-8") == "<html>the design</html>"


def test_a_missing_mirror_is_not_an_error_on_a_machine_without_onedrive(
    staged: dict[str, Path],
) -> None:
    """The work machine has the repo and no OneDrive path. Nothing should fail there."""
    assert sync_blueprint.main(["--check"]) == 0
    assert sync_blueprint.main(["--pull"]) == 0
    assert staged["source"].read_text(encoding="utf-8") == "<html>the design</html>"


def test_publishing_does_not_conjure_a_onedrive_tree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The work machine has the repo and no OneDrive folder at all. Creating one there
    would be a tool inventing a location nobody asked for."""
    source = tmp_path / "docs" / "architecture.html"
    source.parent.mkdir()
    source.write_text("<html>the design</html>", encoding="utf-8")
    absent = tmp_path / "no-such-onedrive" / "Architecture.html"

    monkeypatch.setattr(sync_blueprint, "SOURCE", source)
    monkeypatch.setattr(sync_blueprint, "MIRROR", absent)
    monkeypatch.setattr(sync_blueprint, "RECORD", tmp_path / "docs" / ".blueprint-mirror")

    assert sync_blueprint.main([]) == 0
    assert not absent.parent.exists(), "publishing created a folder tree that did not exist"
