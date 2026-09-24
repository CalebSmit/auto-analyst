"""P109 - a contract version registered, and nothing pointing at it.

P106 added `statements_arrive_in`, cut `engagement_profile@1.1.0` to declare it, registered
it, and left `intake/config.py` validating every profile against @1.0.0 - whose
`additionalProperties` is false. So the one field the scale settlement reads was the one
field a person was refused for sending. The first real client folder hit it at the profile
POST, came back 422 SKILL.SCHEMA_INVALID, and the engagement never activated.

It is this build's most repeated defect - something built and wired to nothing - and it got
past both reachability scans, because it is a version string in YAML rather than a public
function nobody calls. So the last test here is the scan that would have caught it.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest
import yaml

from intake.config import PROFILE_CONTRACT, PROFILES_SUPPORTED

ROOT = Path(__file__).resolve().parents[2]
CONTRACTS = ROOT / "contracts"
REGISTRY = CONTRACTS / "registry.yaml"

# Where a contract version may be named, other than the registry that lists it. Tests are
# excluded on purpose: a version only the tests know about is the defect, not the proof.
PRODUCTION = ("*.py", "*.yaml", "*.yml", "*.json", "*.md")
NOT_PRODUCTION = (".venv", "tests", "BUILD", "runs", "inbox", "knowledge", "__pycache__")


def registered() -> list[dict[str, Any]]:
    return list(yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))["contracts"])


def newest_of_each() -> dict[str, str]:
    """contract id -> the highest version registered for it."""
    best: dict[str, tuple[tuple[int, ...], str]] = {}
    for entry in registered():
        cid, version = str(entry["id"]), str(entry["version"])
        order = tuple(int(part) for part in version.split("."))
        if cid not in best or order > best[cid][0]:
            best[cid] = (order, version)
    return {cid: version for cid, (_, version) in best.items()}


def production_files() -> list[Path]:
    out: list[Path] = []
    for pattern in PRODUCTION:
        for path in ROOT.rglob(pattern):
            rel = path.relative_to(ROOT).parts
            if any(part in NOT_PRODUCTION for part in rel) or path == REGISTRY:
                continue
            out.append(path)
    return out


# ============================================================ the seam itself


def test_the_store_validates_the_newest_profile_version() -> None:
    assert f"engagement_profile@{newest_of_each()['engagement_profile']}" == PROFILE_CONTRACT


def test_an_older_profile_is_still_read_rather_than_migrated() -> None:
    """Same reasoning as the configuration document: a profile recorded last year says
    what it always said, and rewriting it on read is a migration nobody asked for and
    nobody can see."""
    assert "engagement_profile@1.0.0" in PROFILES_SUPPORTED
    assert PROFILES_SUPPORTED[0] == PROFILE_CONTRACT, "newest first"


def test_a_profile_is_validated_against_the_version_it_declares() -> None:
    source = (ROOT / "intake" / "config.py").read_text(encoding="utf-8")
    body = source[source.index("def _check_profiles") : source.index("def _check_conventions")]
    assert "self._contracts.validate(declared, profile)" in body
    assert "PROFILES_SUPPORTED" in body


def test_a_profile_declaring_an_unsupported_version_is_refused_by_name() -> None:
    """Not silently validated against whatever the current one happens to be. A profile
    that names a version this store does not have is a question, and the refusal says
    which versions it does have."""
    source = (ROOT / "intake" / "config.py").read_text(encoding="utf-8")
    body = source[source.index("def _check_profiles") : source.index("def _check_conventions")]
    assert "which this store does not validate" in body


# ============================================================ half a version bump


@pytest.mark.parametrize(
    "path",
    sorted(p for p in CONTRACTS.glob("*.schema.json")),
    ids=lambda p: p.name,
)
def test_a_schema_names_its_own_version_the_same_way_everywhere(path: Path) -> None:
    """@1.1.0 was cut with its `$id` bumped and its `schema_version` const left at
    @1.0.0, so a profile declaring the new version failed the new version's own check.
    The `$id` was checked because the registry checks the `$id`; the const says the same
    fact a second time and nothing compared them. Two statements of one fact drift."""
    doc = json.loads(path.read_text(encoding="utf-8"))
    said = re.search(r"([^/]+)$", str(doc.get("$id", "")))
    assert said, f"{path.name} has no $id"
    declared = (doc.get("properties") or {}).get("schema_version") or {}
    if "const" in declared:
        assert declared["const"] == said.group(1), (
            f"{path.name}: $id says {said.group(1)} and schema_version says {declared['const']}"
        )


# ============================================================ the scan


def test_the_newest_version_of_every_contract_is_named_somewhere() -> None:
    """The defect class, not the instance.

    An old version may sit in the registry for as long as a recorded run cites it - that
    is what the registry is for. The newest may not: something registered a version and
    then did not use it, which means the change it carries reaches nobody. That is exactly
    what happened to the arrival scale, and neither `tests/p71` nor `tests/p73` could see
    it, because it is a string in a YAML file rather than a function.
    """
    text = "\n".join(
        path.read_text(encoding="utf-8", errors="ignore") for path in production_files()
    )
    orphans = [
        f"{cid}@{version}"
        for cid, version in sorted(newest_of_each().items())
        if f"{cid}@{version}" not in text
    ]
    assert not orphans, (
        "registered and pointed at by nothing: "
        + ", ".join(orphans)
        + " - a contract version nothing validates against is a change that reaches nobody"
    )


def test_the_scan_can_see_an_orphan() -> None:
    """The scan above is a needle in a haystack of files, and a haystack search that
    always says "clean" is worse than none. Put a version in the registry's shape that
    nothing names, and check the same rule reports it."""
    newest = dict(newest_of_each())
    newest["a_contract_nobody_wrote"] = "9.9.9"
    text = "\n".join(
        path.read_text(encoding="utf-8", errors="ignore") for path in production_files()
    )
    orphans = [f"{c}@{v}" for c, v in newest.items() if f"{c}@{v}" not in text]
    assert orphans == ["a_contract_nobody_wrote@9.9.9"]


# ============================================================ what a person is asked


def test_the_skeleton_offers_the_version_the_store_validates() -> None:
    """A Setup page handing somebody a skeleton stamped with a version the store refuses
    is the same defect wearing a different hat."""
    console = (ROOT / "admin" / "console.py").read_text(encoding="utf-8")
    assert '"schema_version": PROFILE_CONTRACT,' in console
    assert '"schema_version": "engagement_profile@1.0.0"' not in console


def test_the_skeleton_offers_the_arrival_scale_at_all() -> None:
    console = (ROOT / "admin" / "console.py").read_text(encoding="utf-8")
    assert '"statements_arrive_in": None,' in console


def test_the_two_scale_questions_are_told_apart() -> None:
    """They sit next to each other on one form and they are different questions:
    `scale_convention` is how the firm presents its own work, `statements_arrive_in` is
    what the client sent. A form labelling both "figures are stated in units of" is a form
    that gets one of them wrong."""
    page = (ROOT / "admin" / "page.py").read_text(encoding="utf-8")
    assert "Our working papers are kept in" in page
    assert "The client's statements arrive in" in page
    assert "Figures are stated in units of" not in page


def test_the_arrival_scale_can_be_left_blank_and_the_convention_cannot() -> None:
    """There is no default for what arrived - a silence is settled by a cue on the page,
    and a form that made somebody pick one would be a form that invents the fact the
    settlement was built to avoid inventing. The firm, by contrast, always has a
    convention."""
    page = (ROOT / "admin" / "page.py").read_text(encoding="utf-8")
    block = page[page.index("const SCALE_FIELDS") : page.index("function profileField")]
    assert "scale_convention: {{blank: null" in block
    assert "statements_arrive_in: {{blank: 'not stated" in block


# ============================================================ blank means not stated


def test_a_blank_optional_field_is_dropped_rather_than_sent_as_null() -> None:
    """The form turns an empty number box into `null`, and an optional integer has no
    reading of null that means "not stated". Without this, a person who simply did not
    know what the client sent was refused for a field they had left alone."""
    console = (ROOT / "admin" / "console.py").read_text(encoding="utf-8")
    body = console[console.index("def set_profile") : console.index("def set_intake_override")]
    assert "without_blank_profile_options" in body


def test_a_required_field_left_blank_is_still_refused() -> None:
    """Dropping it would turn a question a person can answer into one they cannot see."""
    from intake.config import ConfigStore

    class Contracts:
        def get(self, key: str) -> dict[str, Any]:
            return {"required": ["schema_version", "engagement_id", "scale_convention"]}

    store = ConfigStore.__new__(ConfigStore)
    store._contracts = Contracts()  # type: ignore[attr-defined]  # noqa: SLF001
    kept = store.without_blank_profile_options(
        {
            "schema_version": PROFILE_CONTRACT,
            "engagement_id": "E-1",
            "scale_convention": None,
            "statements_arrive_in": None,
            "size_band": {"metric": "revenue"},
        }
    )
    assert "statements_arrive_in" not in kept, "optional and blank"
    assert kept["scale_convention"] is None, "required and blank - still a refusal"
    assert kept["size_band"] == {"metric": "revenue"}


def test_a_stated_arrival_scale_is_kept() -> None:
    from intake.config import ConfigStore

    class Contracts:
        def get(self, key: str) -> dict[str, Any]:
            return {"required": ["schema_version"]}

    store = ConfigStore.__new__(ConfigStore)
    store._contracts = Contracts()  # type: ignore[attr-defined]  # noqa: SLF001
    kept = store.without_blank_profile_options(
        {"schema_version": PROFILE_CONTRACT, "statements_arrive_in": 1000}
    )
    assert kept["statements_arrive_in"] == 1000
