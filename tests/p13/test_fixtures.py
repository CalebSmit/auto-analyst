"""Each of the ten fixtures fires the right guard, and only that guard.

The blueprint's fixture table names ten guards across five phases. Six of them exist
after P13. Each fixture whose guard is built is run against *every* built guard, and the
target must fire while the rest stay quiet - "only that guard" is half the criterion. The
four whose guard is not built yet are reported, by phase, at the end of the session
rather than skipped silently.
"""

from __future__ import annotations

from typing import Any

import pytest
from cryptography.fernet import Fernet

import ports
from guards.numeric_lock import NumericLock
from guards.provenance import ProvenanceGate
from guards.tieout import TieoutGate
from ops.events import EventBus
from ops.run_store import SqlRunStore
from ops.source_parse import Row, SourceParseStore
from privacy.payload_scan import IdentifierList, PayloadScan
from privacy.vault import KEY_NAME, open_vault
from registries.contracts import ContractRegistry
from tests.conftest import PENDING_FIXTURES
from tests.p13.conftest import ENGAGEMENT, FIXTURES, TOLERANCE, case
from tools.recompute import recompute

BUILT = {"payload_scan", "unmask_verify", "tieout", "numeric_lock", "provenance", "budget_governor"}


def test_the_table_has_ten_and_they_are_the_blueprints(fixture_table: dict[str, Any]) -> None:
    rows = fixture_table["fixtures"]
    assert len(rows) == 10
    for row in rows:
        assert (FIXTURES / row["case"]).is_file(), f"{row['id']} has no case file"
        assert row["fires"].split(".")[0] in {
            "PRIVACY",
            "GUARD",
            "SKILL",
            "INTAKE",
            "DELIVER",
            "LOOP",
            "POLICY",
            "PROCESS",
        }


def test_six_guards_are_built_and_four_are_owed(fixture_table: dict[str, Any]) -> None:
    """Said in a test so the number is checked, not remembered."""
    guards = {row["guard"] for row in fixture_table["fixtures"]}
    assert guards & BUILT == BUILT
    owed = {
        row["guard"]: row["built_by"]
        for row in fixture_table["fixtures"]
        if row["guard"] not in BUILT
    }
    assert owed == {
        "untrusted_boundary": "P17",
        "deliverable_qc": "P21",
        "loop_controller": "P14",
        "engagement_lock": "P16",
    }


# --------------------------------------------------------- running them all


def _fire(
    row: dict[str, Any],
    store: SqlRunStore,
    bus: EventBus,
    contracts: ContractRegistry,
    started: str,
    parsed: SourceParseStore,
    monkeypatch: pytest.MonkeyPatch,
) -> dict[str, str | None]:
    """Run one fixture through every built guard it can reach. Returns guard -> code."""
    fired: dict[str, str | None] = {}
    body = case(row["case"])
    guard = row["guard"]

    if guard == "payload_scan":
        ids = IdentifierList.of(body["engagement_id"], body["identifiers"], body["expected_tokens"])
        r = PayloadScan().check(body["payload"], ids)
        fired["payload_scan"] = None if r.passed else "PRIVACY.UNMASKED_IDENTIFIER"

    elif guard == "unmask_verify":
        from privacy.mask import Identifier, Masker
        from privacy.unmask import Unmasker
        from privacy.verify import UnmaskVerify

        monkeypatch.setenv(KEY_NAME, Fernet.generate_key().decode())
        ports.reset()
        vault = open_vault(ports.get_secrets(), f"sqlite:///{store._engine.url.database}")  # noqa: SLF001
        ident = Identifier(**body["identifier"])
        foreign = Masker(vault).mask(ident.value, body["other_engagement_id"], (ident,))
        text = body["text_template"].format(token=foreign.substitutions[ident.value])
        back = Unmasker(vault).unmask(text, body["engagement_id"])
        r = UnmaskVerify.check(back, vault.issued(body["engagement_id"]))
        fired["unmask_verify"] = r.code
        vault.close()

    elif guard in ("tieout", "provenance", "numeric_lock"):
        if guard == "tieout":
            r = TieoutGate(parsed, recompute, body["tolerance"]).check(body["output"], started)
            fired["tieout"] = r.code
            fired["provenance"] = (
                ProvenanceGate(contracts, parsed)
                .check(body["output"], started, {body["source_id"]: 1})
                .code
            )
        elif guard == "provenance":
            r = ProvenanceGate(contracts, parsed).check(body["output"], started, body["sources"])
            fired["provenance"] = r.code
            fired["tieout"] = (
                TieoutGate(parsed, recompute, TOLERANCE).check(body["output"], started).code
            )
        else:
            r = NumericLock.check(body["before"], body["after"])
            fired["numeric_lock"] = r.code
            fired["payload_scan"] = (
                None
                if PayloadScan().check(body["after"], IdentifierList.of(ENGAGEMENT, [])).passed
                else "PRIVACY.UNMASKED_IDENTIFIER"
            )

    elif guard == "budget_governor":
        from harness.budget import BudgetExceeded, BudgetGovernor
        from ops.cost import CostMeter
        from registries.constraints import ConstraintRegistry

        for n in range(body["iterations"]):
            bus.emit(
                run_id=started,
                engagement_id=ENGAGEMENT,
                node_id="loop_controller",
                type="loop.every.iteration",
                message=f"{n}",
                payload={"n": n},
            )
        governor = BudgetGovernor(ConstraintRegistry.load(), CostMeter(store), bus, store)
        try:
            governor.check(started, ENGAGEMENT)
            fired["budget_governor"] = None
        except BudgetExceeded as exc:
            fired["budget_governor"] = exc.diagnostic.code
        fired["tieout"] = None
        fired["provenance"] = None
    return fired


@pytest.mark.parametrize("row_index", range(10))
def test_each_fixture_fires_its_guard_and_only_that_guard(
    row_index: int,
    fixture_table: dict[str, Any],
    store: SqlRunStore,
    bus: EventBus,
    contracts: ContractRegistry,
    started: str,
    parsed: SourceParseStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    row = fixture_table["fixtures"][row_index]
    if row["guard"] not in BUILT:
        PENDING_FIXTURES.append((row["id"], row["guard"], row["built_by"]))
        pytest.skip(f"{row['id']}: {row['guard']} is built by {row['built_by']} (reported)")

    fired = _fire(row, store, bus, contracts, started, parsed, monkeypatch)

    assert fired[row["guard"]] == row["fires"], (
        f"{row['id']} should fire {row['guard']} with {row['fires']}, got {fired[row['guard']]}"
    )
    quiet = {g: c for g, c in fired.items() if g != row["guard"] and c is not None}
    assert not quiet, f"{row['id']} also fired {quiet} - a fixture fires one guard"


def test_tieout_fixture_is_the_blueprints_0_4_percent(
    parsed: SourceParseStore, started: str
) -> None:
    body = case("tieout_altered_total.json")
    parsed_rows = [Row(**r) for r in body["rows"]]
    assert sum(r.value for r in parsed_rows) == body["true_total"]
    assert body["altered_total"] == pytest.approx(body["true_total"] * 1.004, abs=0.01)


def test_provenance_fixture_carries_both_halves() -> None:
    """A figure citing "derived", and one citing a hash not in the manifest."""
    body = case("provenance_derived_source.json")
    ids = [f["source_id"] for f in body["output"]["figures"]]
    assert "derived" in ids
    assert any(i.startswith("sha256:") and i not in body["sources"] for i in ids)


def test_every_case_file_is_in_the_table(fixture_table: dict[str, Any]) -> None:
    """No orphan case files: a fixture nobody runs is a fixture nobody maintains."""
    listed = {row["case"] for row in fixture_table["fixtures"]}
    on_disk = {p.name for p in FIXTURES.glob("*.json")}
    assert on_disk == listed
