"""The public surfaces have not moved without somebody deciding they should.

Every other test in this repo asks whether the code does what it says. This one asks
whether what it says has changed - which is a different question, and the one that goes
unasked until a change three months from now quietly alters what a run means.

A failure here is not necessarily a bug. It is a change to something other work depends
on: a contract, an error code, a tool's cap, a skill's review floor, a loop ceiling, a
plan hash. The right response is to read the diff, decide whether it was intended, and
then either revert it or accept it deliberately:

    python tools/surfaces.py --check      # what moved
    gate amend P<nn> "why it moved"       # the reason, on the record
    python tools/surfaces.py --update     # accept it

That order matters. The snapshot is not the authority on what is correct - the reason
recorded beside it is.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.conftest import needs_a_checkout
from tools.surfaces import COLLECTORS, SNAPSHOT, collect, differences, load, report

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def recorded() -> dict:
    assert SNAPSHOT.is_file(), (
        f"{SNAPSHOT.relative_to(ROOT)} does not exist. Take the first snapshot with "
        f"`python tools/surfaces.py --update`."
    )
    return load()


@pytest.fixture(scope="module")
def current() -> dict:
    return collect()


def test_no_public_surface_changed_without_being_recorded(
    recorded: dict, current: dict
) -> None:
    """The whole point, in one assertion."""
    changes = differences(recorded, current)
    assert not changes, (
        "the public surfaces have moved:\n"
        + report(changes)
        + "\n\n  Read the diff. If it was intended, record why with `gate amend` and "
        "accept it with\n  `python tools/surfaces.py --update`. If it was not, this is "
        "the bug."
    )


def test_the_snapshot_covers_every_surface_that_is_collected(recorded: dict) -> None:
    """A collector added without re-snapshotting would report nothing forever, which is
    how a safety net stops covering the thing it was added for."""
    assert set(recorded) == set(COLLECTORS), {
        "in the snapshot only": sorted(set(recorded) - set(COLLECTORS)),
        "collected but not recorded": sorted(set(COLLECTORS) - set(recorded)),
    }


def test_the_snapshot_is_committed_and_readable(recorded: dict) -> None:
    """It is evidence, so it lives in the repo rather than in a cache, and it is JSON a
    person can read in a diff rather than a pickle nobody can review."""
    needs_a_checkout("the tracked-file check")
    import subprocess

    tracked = subprocess.run(  # noqa: S603
        ["git", "ls-files", "BUILD/surfaces.json"],
        cwd=ROOT, capture_output=True, text=True, check=True,
    ).stdout.strip()
    assert tracked == "BUILD/surfaces.json", "the snapshot is not tracked by git"
    text = SNAPSHOT.read_text(encoding="utf-8")
    assert json.loads(text) == recorded
    assert text.count("\n") > 100, "it should be readable as a diff, one thing per line"


def test_the_load_bearing_surfaces_are_all_there(recorded: dict) -> None:
    """A snapshot that quietly lost a group would pass the comparison above forever.

    These are the counts the rest of the build asserts against elsewhere, named here so
    that a group emptying itself - a registry failing to load, a tree finding no skills -
    fails loudly rather than being recorded as the new truth.
    """
    assert len(recorded["contracts"]["ids"]) >= 31
    assert len(recorded["diagnostics"]["codes"]) >= 80
    assert len(recorded["diagnostics"]["families"]) == 10
    assert len(recorded["graph"]["invariants"]) == 25
    assert recorded["graph"]["nodes"] == 118
    assert len(recorded["skills"]["skills"]) >= 13
    assert len(recorded["ports"]) == 6
    assert len(recorded["governance"]["stages"]) == 11
    assert len(recorded["record"]["run_states"]) == 7
    assert set(recorded["recipes"]) == {"monthly-refresh@v3", "full-ddr-intake@v1"}
    for name in ("monthly-refresh", "full-ddr-intake"):
        assert recorded["plans"][name]["plan_hash"].startswith("sha256:")


def test_a_changed_surface_is_reported_in_words(recorded: dict) -> None:
    """The diff has to be readable, or nobody will read it and everybody will just
    re-snapshot. Checked against a deliberately altered copy rather than trusted."""
    altered = json.loads(json.dumps(recorded))
    altered["constraints"]["tools"]["recompute"]["caps"]["max_rows"] = 999_999
    altered["diagnostics"]["codes"].pop("SKILL.BELOW_GATE", None)

    changes = differences(recorded, altered)
    text = report(changes)
    assert "constraints.tools.recompute.caps.max_rows" in text
    assert "999999" in text.replace(",", "")
    assert "SKILL.BELOW_GATE" in text
    assert text.count("\n") >= 2


def test_a_plan_hash_change_names_the_recipe(recorded: dict) -> None:
    """The load-bearing entry. Anything that alters a skill version, a model pin, an
    output contract, the scope resolution or the template binding moves a plan hash, and
    the diff says which recipe moved rather than leaving somebody to find out."""
    altered = json.loads(json.dumps(recorded))
    altered["plans"]["monthly-refresh"]["plan_hash"] = "sha256:" + "00" * 32
    changes = differences(recorded, altered)
    assert len(changes) == 1
    assert changes[0].startswith("~ plans.monthly-refresh.plan_hash")
