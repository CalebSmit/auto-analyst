"""The Decision Log: append-only, in the manifest, and the source of the override rate."""

from __future__ import annotations

import pytest
from sqlalchemy import select, text

from ops.manifest import assemble
from ops.models import AppendOnlyViolation, Decision, DecisionKind
from ops.run_store import SqlRunStore
from review import ConfidenceRouter, DecisionLog, Money, ReviewQueue, ReviewSurface
from tests.p15.conftest import DECLARED, EBITDA, ENGAGEMENT, TAGGING, item


@pytest.fixture
def decided(
    queue: ReviewQueue, router: ConfidenceRouter, surface: ReviewSurface, started: str
) -> str:
    """Four decisions: two tagging accepts, one tagging correction, one EBITDA rejection."""
    for n, (skill, decision, extra) in enumerate(
        [
            (TAGGING, DecisionKind.ACCEPTED, {}),
            (TAGGING, DecisionKind.ACCEPTED, {}),
            (
                TAGGING,
                DecisionKind.CORRECTED,
                {"rationale": "recurs", "answer": {"category": "recurring"}},
            ),
            (EBITDA, DecisionKind.REJECTED, {"rationale": "not an add-back"}),
        ]
    ):
        it = item(
            f"i_{n}", skill, confidence=0.5, amount=Money(50000, "USD") if skill == EBITDA else None
        )
        queue.enqueue(started, ENGAGEMENT, it, router.route(it, DECLARED[skill]))
        surface.decide(
            started,
            it.item_id,
            decided_by="Dana Whitfield",
            decision=decision,
            expected_version=1,
            **extra,
        )
    return started


def test_every_entry_carries_the_proposal_and_the_answer(store: SqlRunStore, decided: str) -> None:
    log = DecisionLog(store)
    entries = log.entries(decided)
    assert len(entries) == 4
    assert all(e.proposal["category"] == "non_recurring" for e in entries)
    corrected = log.for_item(decided, "i_2")
    assert corrected is not None and corrected.answer == {"category": "recurring"}
    assert corrected.rationale == "recurs" and corrected.decided_by == "Dana Whitfield"


def test_the_override_rate_per_skill(store: SqlRunStore, decided: str) -> None:
    log = DecisionLog(store)
    tagging = log.override_rate(decided, TAGGING)
    assert (tagging.decided, tagging.overridden) == (3, 1) and tagging.rate == pytest.approx(1 / 3)
    assert log.override_rate(decided, EBITDA).rate == 1.0
    assert log.override_rate(decided).decided == 4
    assert log.override_rate(decided, "nothing").rate == 0.0


def test_only_a_persons_accept_or_correction_may_reach_precedent(
    store: SqlRunStore, decided: str
) -> None:
    candidates = DecisionLog(store).precedent_candidates(decided)
    assert {c.item_id for c in candidates} == {"i_0", "i_1", "i_2"}
    assert all(c.decided_by for c in candidates)


def test_the_log_is_append_only_at_the_orm(store: SqlRunStore, decided: str) -> None:
    with pytest.raises(AppendOnlyViolation), store._session() as session:  # noqa: SLF001
        row = session.scalars(select(Decision).where(Decision.run_id == decided)).first()
        assert row is not None
        row.rationale = "rewritten"
    assert DecisionLog(store).for_item(decided, "i_2").rationale == "recurs"  # type: ignore[union-attr]


def test_the_log_is_append_only_at_the_database(store: SqlRunStore, decided: str) -> None:
    """A trigger, so a raw UPDATE through a prompt or a migration fails too."""
    with pytest.raises(Exception, match="append-only"), store._engine.begin() as connection:  # noqa: SLF001
        connection.execute(text("UPDATE decision SET rationale = 'rewritten'"))
    with pytest.raises(Exception, match="append-only"), store._engine.begin() as connection:  # noqa: SLF001
        connection.execute(text("DELETE FROM decision"))
    assert len(DecisionLog(store).entries(decided)) == 4


def test_the_manifest_carries_every_decision(store: SqlRunStore, decided: str, bus) -> None:
    manifest = assemble(store, decided, bus=bus)
    logged = manifest["human_decisions"]
    assert len(logged) == 4
    assert {d["decision"] for d in logged} == {"accepted", "corrected", "rejected"}
    assert all(d["decided_by"] == "Dana Whitfield" for d in logged)
