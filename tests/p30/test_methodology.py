"""P30: methodology is cleared once by a person, and checked by a hash on every run.

`foundations/` is the one input that reaches every model call for every client and is
never checked against the engagement it is read for. The outbound payload scan knows only
the current engagement's identifiers, so a worked example from a real deal, pasted into a
methodology file, would travel to every prompt and trip nothing.

The four claims, in the order they matter:

1. Something shaped like client data cannot be cleared at all.
2. An edit loses its clearance for free, because the digest changes.
3. The Context Builder refuses an uncleared file, and says which one.
4. The run-time check is a set lookup, so it cannot fail on a false positive - which is
   what makes clearing once, rather than scanning every run, a safe trade.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from admin.preflight import CHECKS, Preflight
from harness.context import ContextBuilder
from registries.errors import RegistryError
from registries.methodology import (
    CLEARED_FILE,
    ClearanceRefused,
    MethodologyRegister,
    body_of,
    digest_of,
)
from tests.conftest import needs_a_checkout
from tests.p30.conftest import WITH_AN_INSTRUCTION, WITH_CLIENT_DATA

ROOT = Path(__file__).resolve().parents[2]


# ------------------------------------------------------------------ clearing


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        (WITH_CLIENT_DATA, "engagement id"),
        (WITH_AN_INSTRUCTION, "instruction"),
    ],
)
def test_a_file_carrying_client_data_or_an_instruction_cannot_be_cleared(
    register: MethodologyRegister, foundations: Path, content: str, expected: str
) -> None:
    """The first exit criterion, and the reason the whole module exists.

    Two scanners, the same two a dropped skill draft goes through. Methodology is the more
    dangerous document of the two: a skill draft is read by one step of one run, and this
    is read by every step of every run, for every client.
    """
    path = foundations / "_firm" / "qc-conventions.md"
    path.write_text(content, encoding="utf-8")

    with pytest.raises(ClearanceRefused) as refused:
        register.clear(path, cleared_by="C. Smit")

    diagnostic = refused.value.diagnostic
    assert diagnostic.code == "CONFIG.METHODOLOGY_UNSAFE"
    assert diagnostic.owner == "config"
    assert "_firm/qc-conventions.md" in diagnostic.detail
    assert diagnostic.what_now, "a refusal that says nothing is a refusal nobody can act on"
    assert register.cleared() == (), "nothing is written when a clearance is refused"

    # The refusal says what it found, not just that it found something.
    reasons = register.scan(body_of(path), path.name)
    assert reasons and any(expected in r.lower() for r in reasons), reasons


def test_a_clearance_names_a_person(register: MethodologyRegister, foundations: Path) -> None:
    """"Cleared by nobody" is the state this register exists to make impossible, so there
    is no default and a blank is refused rather than recorded."""
    path = foundations / "_firm" / "qc-conventions.md"
    for blank in ("", "   "):
        with pytest.raises(ValueError, match="names the person"):
            register.clear(path, cleared_by=blank)
    assert register.cleared() == ()


def test_what_is_recorded_is_who_when_and_which_bytes(
    register: MethodologyRegister, foundations: Path
) -> None:
    path = foundations / "_firm" / "qc-conventions.md"
    record = register.clear(path, cleared_by="  C. Smit  ")

    assert record.cleared_by == "C. Smit", "whitespace is not part of anybody's name"
    assert record.digest == digest_of(body_of(path))
    assert record.size_bytes == len(body_of(path))
    assert record.cleared_at.endswith("Z")
    assert register.is_cleared(record.digest)

    # Written where a person can read it, and read back as the same thing.
    written = yaml.safe_load(register.path.read_text(encoding="utf-8"))
    assert written["cleared"] == [
        {
            "name": "_firm/qc-conventions.md",
            "digest": record.digest,
            "cleared_at": record.cleared_at,
            "cleared_by": "C. Smit",
            "size_bytes": record.size_bytes,
        }
    ]
    assert "Append-only" in register.path.read_text(encoding="utf-8")


def test_clearing_the_same_content_twice_records_it_once(
    register: MethodologyRegister, foundations: Path
) -> None:
    """Idempotent by digest. Two people clearing the same bytes is one fact, and a second
    row would make the register look like a log of attempts rather than a record of what
    is cleared."""
    path = foundations / "_firm" / "qc-conventions.md"
    first = register.clear(path, cleared_by="C. Smit")
    again = register.clear(path, cleared_by="Somebody Else")
    assert again == first
    assert len(register.cleared()) == 1


# ------------------------------------------------------------------ editing


def test_an_edited_file_loses_its_clearance(
    cleared: MethodologyRegister, foundations: Path
) -> None:
    """The second exit criterion. Nobody has to notice, remember or revoke anything: the
    bytes changed, so the digest changed, so the lookup misses."""
    path = foundations / "_firm" / "qc-conventions.md"
    before = {found.name: found.state for found in cleared.review()}
    assert before == {
        "_firm/qc-conventions.md": "cleared",
        "_firm/valuation-standards.md": "cleared",
    }

    path.write_text(path.read_text(encoding="utf-8") + "\nOne more sentence.\n", encoding="utf-8")

    after = {found.name: found.state for found in cleared.review()}
    assert after["_firm/qc-conventions.md"] == "edited"
    assert after["_firm/valuation-standards.md"] == "cleared", "one file changing is not two"
    assert not cleared.is_cleared(digest_of(body_of(path)))

    # The old clearance is still on the record - it happened - it just no longer matches
    # anything on disk. Nothing is edited or removed to make this work.
    assert len(cleared.cleared()) == 2


def test_the_readme_is_not_methodology(cleared: MethodologyRegister, foundations: Path) -> None:
    """The folder's README describes the folder. Clearing it would be recording a decision
    nobody made, and attaching it would put the filing convention in every prompt."""
    assert "README.md" not in [p.name for p in cleared.files()]
    assert "README.md" not in [found.name for found in cleared.review()]


# ------------------------------------------------------------- the run itself


def test_the_context_builder_refuses_an_uncleared_file_and_names_it(
    builder: ContextBuilder, request_for: Any, foundations: Path
) -> None:
    """The third exit criterion. It refuses rather than skipping the file: a run quietly
    missing half its methodology answers a different question from the one asked."""
    with pytest.raises(RegistryError) as refused:
        builder.build(request_for("ebitda"))

    diagnostic = refused.value.diagnostic
    assert diagnostic.code == "CONFIG.METHODOLOGY_UNCLEARED"
    assert diagnostic.owner == "config"
    assert diagnostic.locator in {"_firm/qc-conventions.md", "_firm/valuation-standards.md"}
    assert diagnostic.locator in diagnostic.detail, "the refusal names the file"
    assert diagnostic.found.startswith("sha256:")


def test_an_edited_file_stops_the_run_and_says_it_was_edited(
    cleared: MethodologyRegister, builder: ContextBuilder, request_for: Any, foundations: Path
) -> None:
    """The case the whole design is for: cleared once, changed afterwards, still on disk
    and looking exactly as legitimate as it did before."""
    assert builder.build(request_for("ebitda")).sections, "cleared methodology attaches"

    path = foundations / "_firm" / "qc-conventions.md"
    path.write_text(WITH_CLIENT_DATA, encoding="utf-8")

    with pytest.raises(RegistryError) as refused:
        builder.build(request_for("ebitda"))
    assert "cleared once, but not this version" in refused.value.diagnostic.detail


def test_cleared_methodology_is_attached_in_full(
    cleared: MethodologyRegister, builder: ContextBuilder, request_for: Any, foundations: Path
) -> None:
    """Refusing is only half of it. What is cleared reaches the model, framed with the
    same digest the register holds, so the context manifest and the register agree."""
    assembled = builder.build(request_for("ebitda"))
    attached = assembled.section("foundations")

    assert [s.name for s in attached] == [
        "_firm/qc-conventions.md",
        "_firm/valuation-standards.md",
    ]
    for section in attached:
        assert cleared.is_cleared(section.content_hash)
        assert section.content_hash == digest_of(body_of(foundations / section.name))
    assert b"Every engagement gets a scope memo" in builder.blobs.get(assembled.ref)


def test_the_run_time_check_is_a_lookup_and_never_a_scan(
    cleared: MethodologyRegister,
    builder: ContextBuilder,
    request_for: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The fourth exit criterion, and the trade that makes clearing once safe.

    A regex over methodology at run time would mean one broad pattern takes a practice
    group offline in the middle of the working day. Proved by making the scanner raise:
    if the hot path ever reached for it, this test would fail rather than quietly getting
    slower and more fragile.
    """

    def explode(*_: Any, **__: Any) -> None:
        raise AssertionError("the run-time path scanned methodology; it must only look up")

    monkeypatch.setattr(MethodologyRegister, "scan", explode)
    monkeypatch.setattr(
        "governance.conformance.find_client_data",
        lambda *_, **__: (_ for _ in ()).throw(AssertionError("scanned at run time")),
    )

    assembled = builder.build(request_for("ebitda"))
    assert len(assembled.section("foundations")) == 2


# -------------------------------------------------------------------- setup


def test_preflight_reports_uncleared_methodology_before_a_run_finds_it(
    preflight: Preflight, henderson: Any
) -> None:
    """The fourth task. An uncleared file stops every run, so it is reported as an
    environment failure rather than against one engagement."""
    report = preflight.run(HEND := "HEND-2026-04")
    check = next(c for c in report.checks if c.id == "methodology_cleared")

    assert check.status == "fail"
    assert check.detail == "0 of 2 methodology files cleared"
    assert {f.diagnostic.locator for f in check.failures} == {
        "_firm/qc-conventions.md",
        "_firm/valuation-standards.md",
    }
    assert all(f.blocks_everything for f in check.failures), "this is not one engagement's problem"
    assert "has never been cleared" in check.failures[0].diagnostic.detail
    assert not report.passed and report.blocking(HEND), "it blocks activation"


def test_preflight_reports_an_edited_file_as_edited(
    cleared: MethodologyRegister, preflight: Preflight, henderson: Any, foundations: Path
) -> None:
    assert preflight.run().checks[-1].status == "pass"

    (foundations / "_firm" / "qc-conventions.md").write_text("# Changed\n", encoding="utf-8")
    check = next(c for c in preflight.run().checks if c.id == "methodology_cleared")

    assert check.status == "fail"
    assert check.detail == "1 of 2 methodology files cleared"
    assert "edited it after it was read" in check.failures[0].diagnostic.detail


def test_the_check_joins_the_table_and_the_blueprint_agrees(
    cleared: MethodologyRegister, preflight: Preflight, henderson: Any
) -> None:
    """How many checks there are is asserted here and nowhere else.

    A check that exists in code and not in the design of record is the drift this build
    is built to catch, so the count is compared against the blueprint rather than against
    a number somebody typed in a test.
    """
    ids = [c[0] for c in CHECKS]
    assert ids[-2:] == ["methodology_cleared", "methodology_size"], (
        "they read last; everything above them is per-engagement"
    )
    assert [c.id for c in preflight.run().checks] == ids

    written = {10: "Ten", 11: "Eleven", 12: "Twelve", 13: "Thirteen"}
    blueprint = (ROOT / "docs" / "architecture.html").read_text(encoding="utf-8")
    assert len(CHECKS) == 13
    assert f"{written[len(CHECKS)]} checks over a proposed or live configuration" in blueprint
    assert f"{written[len(CHECKS)].lower()} checks, then what an admin may" in blueprint
    assert "every methodology file cleared, and the version that was cleared" in blueprint


# ------------------------------------------------------------------- the door


def test_a_person_clears_a_file_through_the_admin_surface(console: Any, foundations: Path) -> None:
    """A register nobody can write to stays empty. This is the act, and it takes a name."""
    before = console.methodology()
    assert [f["state"] for f in before["files"]] == ["uncleared", "uncleared"]

    record = console.clear_methodology("_firm/qc-conventions.md", who="C. Smit")
    assert record["cleared_by"] == "C. Smit"

    after = {f["name"]: f for f in console.methodology()["files"]}
    assert after["_firm/qc-conventions.md"]["state"] == "cleared"
    assert after["_firm/qc-conventions.md"]["cleared_by"] == "C. Smit"
    assert after["_firm/qc-conventions.md"]["layer"] == "_firm"
    assert after["_firm/valuation-standards.md"]["state"] == "uncleared"

    with pytest.raises(KeyError):
        console.clear_methodology("not-a-file.md", who="C. Smit")


def test_the_surface_refuses_over_http_with_a_diagnostic(
    console: Any, foundations: Path
) -> None:
    """A refusal a dashboard can render, not a stack trace."""
    from fastapi.testclient import TestClient

    from admin.app import create_admin_app

    (foundations / "_firm" / "qc-conventions.md").write_text(WITH_CLIENT_DATA, encoding="utf-8")
    client = TestClient(create_admin_app(console))

    listed = client.get("/api/admin/methodology")
    assert listed.status_code == 200
    assert [f["state"] for f in listed.json()["files"]] == ["uncleared", "uncleared"]

    refused = client.post(
        "/api/admin/methodology/_firm/qc-conventions.md/clear", json={"who": "C. Smit"}
    )
    assert refused.status_code == 422
    diagnostic = refused.json()["detail"]["refused"][0]
    assert diagnostic["code"] == "CONFIG.METHODOLOGY_UNSAFE"
    assert diagnostic["what_now"]

    ok = client.post(
        "/api/admin/methodology/_firm/valuation-standards.md/clear",
        json={"who": "C. Smit"},
    )
    assert ok.status_code == 200 and ok.json()["cleared_by"] == "C. Smit"


# ------------------------------------------------------ what a clone starts with


def test_a_clone_has_nothing_cleared() -> None:
    """The register is not committed, and that is the point.

    A clearance is a record of somebody at the firm having read a file. Shipping one in
    the repo would be recording a decision nobody made - so a clone starts with nothing
    cleared, preflight says so, and the first run cannot happen until a person has read
    the firm's own methodology.
    """
    needs_a_checkout("what a clone starts with")
    import subprocess

    tracked = subprocess.run(  # noqa: S603
        ["git", "ls-files", "foundations/"],
        cwd=ROOT, capture_output=True, text=True, check=True,
    ).stdout.split()
    assert tracked, "the methodology itself is tracked"
    assert "foundations/cleared.yaml" not in tracked, "a clearance is not something to ship"

    ignored = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "foundations/cleared.yaml" in ignored
    assert "foundations/cleared.yaml" in (ROOT / ".dockerignore").read_text(encoding="utf-8")
    assert CLEARED_FILE.name == "cleared.yaml"


def test_the_repos_own_methodology_scans_clean() -> None:
    """Whatever is in `foundations/` has to be clearable, or the suite could not run.

    Asserted rather than assumed: this is what fails if somebody adds a worked example
    with a real engagement id in it, and it fails here, at the file, rather than in
    whichever test happened to build a context first.
    """
    register = MethodologyRegister()
    assert register.files(), "the firm ships methodology"
    for path in register.files():
        assert register.scan(body_of(path), path.name) == (), path.name


def test_the_error_codes_are_in_the_catalogue_with_what_to_do() -> None:
    """Both codes are things a person has to act on, so both say how."""
    from registries.errors import (
        METHODOLOGY_UNCLEARED,
        METHODOLOGY_UNSAFE,
        WHAT_NOW,
        diagnose,
    )

    for code in (METHODOLOGY_UNCLEARED, METHODOLOGY_UNSAFE):
        assert code in WHAT_NOW
        owner, text = WHAT_NOW[code]
        assert owner == "config"
        assert len(text) > 200, "a code with a one-line entry is a code nobody can act on"
        assert json.loads(json.dumps(diagnose(code, "x", locator="y").as_dict()))["what_now"]
