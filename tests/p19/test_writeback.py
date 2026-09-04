"""Precedent Write-back: a decision id in, a masked example out, or nothing at all."""

from __future__ import annotations

import inspect
from typing import Any

import pytest

from ops.models import DecisionKind
from ops.run_store import SqlRunStore
from precedent import PrecedentStore, PrecedentWriteback, WritebackRefused
from privacy.mask import Identifier, Masked, Masker
from privacy.payload_scan import IdentifierList, PayloadScan
from review import ConfidenceRouter, DecisionLog, ReviewQueue, ReviewSurface
from tests.p19.conftest import CLIENT, ENGAGEMENT, SCOPE_PATH, TAXONOMY, decide, events_of, tag

HENDERSON = Identifier("CLIENT", "Henderson Holdings")


def tagged(ref: str, description: str, category: str, **extra: Any) -> dict[str, Any]:
    body = tag(ref, category, **extra)
    body.update({"description": description, "review_required": True, "taxonomy_version": TAXONOMY})
    return body


def test_an_accepted_decision_becomes_a_masked_example(
    world: dict[str, Any],
    router: ConfidenceRouter,
    queue: ReviewQueue,
    surface: ReviewSurface,
    precedents: PrecedentStore,
    store: SqlRunStore,
) -> None:
    item = tagged("li_1", "Due from Henderson Holdings", "related_party_receivable")
    decide(router=router, queue=queue, surface=surface, run_id=world["run_id"], tagged=item)

    written = world["writeback"].write(
        world["run_id"], "li_1", client_id=CLIENT, scope_path=SCOPE_PATH, identifiers=(HENDERSON,)
    )
    assert written.decision == "accepted" and written.decided_by == "Dana Whitfield"
    assert written.taxonomy_version == TAXONOMY
    assert written.example["category"] == "related_party_receivable"
    assert "[[CLIENT_1]]" in written.example["description"]
    assert "henderson" not in written.example["description"].lower()
    assert precedents.count() == 1
    (event,) = events_of(store, world["run_id"], "precedent.written")
    assert event.payload["precedent_id"] == written.precedent_id
    assert event.payload["decided_by"] == "Dana Whitfield"


def test_a_correction_teaches_the_corrected_value_not_the_proposal(
    world: dict[str, Any], router: ConfidenceRouter, queue: ReviewQueue, surface: ReviewSurface
) -> None:
    item = tagged("li_2", "Accrued interest", "accrued_liabilities")
    decide(
        router=router,
        queue=queue,
        surface=surface,
        run_id=world["run_id"],
        tagged=item,
        decision=DecisionKind.CORRECTED,
        answer={"excluded_from_al": True, "include_in_nwc": False},
        rationale="a financing accrual: excluded from A/L, never NWC",
    )
    written = world["writeback"].write(
        world["run_id"], "li_2", client_id=CLIENT, scope_path=SCOPE_PATH, identifiers=()
    )
    assert written.decision == "corrected"
    assert written.example["category"] == "accrued_liabilities"
    assert written.example["excluded_from_al"] is True
    assert written.example["include_in_nwc"] is False
    assert written.example["rationale"].startswith("a financing accrual")


@pytest.mark.parametrize("decision", [DecisionKind.REJECTED, DecisionKind.ESCALATED])
def test_a_rejection_or_an_escalation_teaches_nothing(
    world: dict[str, Any],
    router: ConfidenceRouter,
    queue: ReviewQueue,
    surface: ReviewSurface,
    precedents: PrecedentStore,
    decision: DecisionKind,
) -> None:
    item = tagged("li_3", "Misc", "other_operating_expense")
    decide(
        router=router,
        queue=queue,
        surface=surface,
        run_id=world["run_id"],
        tagged=item,
        decision=decision,
        rationale="not this",
    )
    with pytest.raises(WritebackRefused) as refused:
        world["writeback"].write(
            world["run_id"], "li_3", client_id=CLIENT, scope_path=SCOPE_PATH, identifiers=()
        )
    assert refused.value.diagnostic.code == "PROCESS.PRECEDENT_NO_DECISION"
    assert precedents.count() == 0


def test_no_decision_no_precedent(world: dict[str, Any], precedents: PrecedentStore) -> None:
    with pytest.raises(WritebackRefused) as refused:
        world["writeback"].write(
            world["run_id"],
            "never_queued",
            client_id=CLIENT,
            scope_path=SCOPE_PATH,
            identifiers=(),
        )
    assert refused.value.diagnostic.code == "PROCESS.PRECEDENT_NO_DECISION"
    assert refused.value.diagnostic.found == "no decision"
    assert precedents.count() == 0


def test_the_writeback_cannot_be_handed_an_example() -> None:
    """Gated on a decision id, structurally: the only way in takes a run and an item,
    and nothing that looks like a category, a description or an example."""
    params = set(inspect.signature(PrecedentWriteback.write).parameters) - {"self"}
    assert params == {"run_id", "item_id", "client_id", "scope_path", "identifiers"}


class NoOpMasker(Masker):
    """P13's adversary: a masker that substitutes nothing and says nothing."""

    def mask(
        self, text: str, engagement_id: str, identifiers: Any, run_id: str | None = None
    ) -> Masked:
        declared = list(identifiers)
        return Masked(
            text=text,
            engagement_id=engagement_id,
            substitutions={},
            identifiers=IdentifierList.of(engagement_id, [i.value for i in declared], ()),
        )


def test_an_example_the_masker_could_not_clear_is_not_written(
    world: dict[str, Any],
    router: ConfidenceRouter,
    queue: ReviewQueue,
    surface: ReviewSurface,
    precedents: PrecedentStore,
    store: SqlRunStore,
    bus: Any,
) -> None:
    """Blueprint failure mode 2414: a name that reached a model should have been a
    token, so write-back for that item is suppressed until it is corrected."""
    item = tagged("li_4", "Due from Henderson Holdings", "related_party_receivable")
    decide(router=router, queue=queue, surface=surface, run_id=world["run_id"], tagged=item)
    broken = PrecedentWriteback(
        store, precedents, NoOpMasker(world["vault"]), PayloadScan(bus), bus
    )
    with pytest.raises(WritebackRefused) as refused:
        broken.write(
            world["run_id"],
            "li_4",
            client_id=CLIENT,
            scope_path=SCOPE_PATH,
            identifiers=(HENDERSON,),
        )
    assert refused.value.diagnostic.code == "PRIVACY.UNMASKED_PRECEDENT"
    assert precedents.count() == 0
    (event,) = events_of(store, world["run_id"], "precedent.writeback.refused")
    assert event.diagnostic_code == "PRIVACY.UNMASKED_PRECEDENT"
    assert "Henderson" not in event.message and "Henderson" not in str(event.payload)


def test_a_sweep_writes_every_candidate_the_log_names_and_only_those(
    world: dict[str, Any],
    router: ConfidenceRouter,
    queue: ReviewQueue,
    surface: ReviewSurface,
    precedents: PrecedentStore,
    store: SqlRunStore,
) -> None:
    run_id = world["run_id"]
    decide(
        router=router,
        queue=queue,
        surface=surface,
        run_id=run_id,
        tagged=tagged("s_1", "Rent", "rent"),
    )
    decide(
        router=router,
        queue=queue,
        surface=surface,
        run_id=run_id,
        tagged=tagged("s_2", "Misc", "other_operating_expense"),
        decision=DecisionKind.REJECTED,
        rationale="sparse",
    )
    decide(
        router=router,
        queue=queue,
        surface=surface,
        run_id=run_id,
        tagged=tagged("s_3", "Utilities", "utilities"),
        decision=DecisionKind.CORRECTED,
        answer={"category": "utilities"},
        rationale="ok",
    )

    candidates = DecisionLog(store).precedent_candidates(run_id)
    assert [c.item_id for c in candidates] == ["s_1", "s_3"]
    written = world["writeback"].sweep(
        run_id, client_id=CLIENT, scope_path=SCOPE_PATH, identifiers=()
    )
    assert [w.decision_item_id for w in written] == ["s_1", "s_3"]
    assert precedents.count() == 2
    assert (
        world["writeback"].sweep(run_id, client_id=CLIENT, scope_path=SCOPE_PATH, identifiers=())
        == written
    )


def test_the_example_carries_the_pattern_and_not_the_client(
    world: dict[str, Any], router: ConfidenceRouter, queue: ReviewQueue, surface: ReviewSurface
) -> None:
    item = tagged("li_5", "Loan to Henderson Holdings", "related_party_receivable")
    decide(router=router, queue=queue, surface=surface, run_id=world["run_id"], tagged=item)
    written = world["writeback"].write(
        world["run_id"], "li_5", client_id=CLIENT, scope_path=SCOPE_PATH, identifiers=(HENDERSON,)
    )
    row = written.as_row()
    assert set(row) >= {"precedent_id", "scope", "description", "category", "rationale"}
    assert "client_id" not in row and "engagement_id" not in row
    assert written.engagement_id == ENGAGEMENT
    assert written.as_precedent().masked is True
