"""The Precedent Store: scope-built retrieval, own client first, exactly one writer."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError, OperationalError

from graph.compile import CompiledGraph
from graph.resolve import ResolvedScope, ScopeResolver
from harness.context import ContextBuilder, PrecedentQuery
from harness.policy import PolicyDenied
from ops.models import AppendOnlyViolation, DecisionKind, PrecedentRow
from ops.run_store import SqlRunStore
from precedent import PrecedentRecord, PrecedentStore
from precedent.store import PrecedentRefused, similarity
from tests.p19.conftest import (
    CLIENT,
    ENGAGEMENT,
    ROOT,
    SKILL,
    TAXONOMY,
    compile_for,
    start,
)

OTHER_CLIENT = "client_okafor"
OTHER_ENGAGEMENT = "OKAF-2026-02"
CF_CLIENT = "client_brandt"
CF_ENGAGEMENT = "BRAN-2026-07"


def approved(
    store: SqlRunStore,
    world: dict[str, Any],
    *,
    run_id: str,
    engagement_id: str,
    client_id: str,
    scope_path: str,
    item_id: str,
    description: str,
    category: str,
    decision: DecisionKind = DecisionKind.ACCEPTED,
    decided_by: str = "Dana Whitfield",
) -> PrecedentRecord:
    """A decision recorded the way the surface records one, then written back."""
    store.open_review_item(
        run_id,
        item_id,
        "confidence",
        f"{description}: {category}?",
        detail={"skill": SKILL, "proposal": {"description": description, "category": category}},
    )
    store.record_decision(
        run_id,
        item_id,
        decided_by=decided_by,
        decision=decision,
        rationale="reviewed",
        writes_precedent=decision in (DecisionKind.ACCEPTED, DecisionKind.CORRECTED),
        proposal={
            "description": description,
            "category": category,
            "excluded_from_al": False,
            "include_in_nwc": False,
            "rationale": "the description says so",
        },
        skill=SKILL,
    )
    written: PrecedentRecord = world["writeback"].write(
        run_id, item_id, client_id=client_id, scope_path=scope_path, identifiers=()
    )
    return written


@pytest.fixture
def populated(
    world: dict[str, Any], store: SqlRunStore, plan: CompiledGraph
) -> dict[str, list[PrecedentRecord]]:
    """Three engagements, two practices: the repeat ESOP client (this run), another
    valuation client, and a corporate-finance client whose rows must never appear."""
    start(store, plan, "run_other", OTHER_ENGAGEMENT)
    start(store, plan, "run_cf", CF_ENGAGEMENT)
    own = [
        approved(
            store,
            world,
            run_id=world["run_id"],
            engagement_id=ENGAGEMENT,
            client_id=CLIENT,
            scope_path="valuation/esop/repeat",
            item_id=f"own_{n}",
            description=d,
            category=c,
        )
        for n, (d, c) in enumerate(
            [("Officer salaries", "officer_compensation"), ("Rent - shop", "rent")]
        )
    ]
    other = [
        approved(
            store,
            world,
            run_id="run_other",
            engagement_id=OTHER_ENGAGEMENT,
            client_id=OTHER_CLIENT,
            scope_path="valuation/non-esop/non-repeat",
            item_id=f"oth_{n}",
            description=d,
            category=c,
        )
        for n, (d, c) in enumerate(
            [("Officer compensation", "officer_compensation"), ("Utilities", "utilities")]
        )
    ]
    cf = [
        approved(
            store,
            world,
            run_id="run_cf",
            engagement_id=CF_ENGAGEMENT,
            client_id=CF_CLIENT,
            scope_path="corporate-finance/tbd/non-repeat",
            item_id="cf_0",
            description="Officer salaries",
            category="officer_compensation",
        )
    ]
    return {"own": own, "other": other, "cf": cf}


def query(scope: ResolvedScope, **overrides: Any) -> PrecedentQuery:
    fields: dict[str, Any] = {
        "engagement_id": ENGAGEMENT,
        "client_id": CLIENT,
        "practice": scope.scope.practice,
        "segment": scope.scope.segment,
        "disposition": scope.scope.disposition,
        "precedent_scope": scope.precedent_scope,
        "skill": SKILL,
    }
    fields.update(overrides)
    return PrecedentQuery(**fields)


# ------------------------------------------------------------ scope-built


def test_retrieval_never_crosses_a_practice_boundary(
    populated: dict[str, list[PrecedentRecord]], precedents: PrecedentStore, scope: ResolvedScope
) -> None:
    """The exit criterion. The corporate-finance row exists, matches the term exactly,
    and is not in the result - it was never in the query."""
    assert precedents.count(practice="corporate-finance") == 1
    got = precedents.retrieve(query(scope, terms=("Officer salaries",), limit=50))
    assert got, "the scope's own rows were retrieved"
    assert {p.practice for p in got} == {"valuation"}
    assert populated["cf"][0].precedent_id not in {p.precedent_id for p in got}


def test_a_query_has_no_free_text_scope_and_the_builder_derives_it_from_the_resolved_scope(
    scope: ResolvedScope,
) -> None:
    """Proven by shape, not by convention: every scope field of the query is a plain
    value the builder fills from a ResolvedScope; `terms` ranks and cannot widen."""
    names = set(PrecedentQuery.__dataclass_fields__)
    assert names == {
        "engagement_id",
        "client_id",
        "practice",
        "segment",
        "disposition",
        "precedent_scope",
        "skill",
        "limit",
        "terms",
    }
    builder_source = (ROOT / "harness" / "context.py").read_text(encoding="utf-8")
    assert "practice=scope.practice" in builder_source
    assert "precedent_scope=resolved.precedent_scope or request.scope.precedent_scope" in (
        builder_source
    )


def test_the_where_clause_is_built_from_the_query_not_filtered_afterwards() -> None:
    source = (ROOT / "precedent" / "store.py").read_text(encoding="utf-8")
    assert "PrecedentRow.practice == query.practice" in source
    assert "PrecedentRow.practice == practice" in source
    # No method takes the whole table and filters it by practice in Python.
    assert not re.search(r"if\s+\w+\.practice\s*!=", source)


def test_a_repeat_client_sees_its_own_prior_decisions_first(
    populated: dict[str, list[PrecedentRecord]], precedents: PrecedentStore, scope: ResolvedScope
) -> None:
    assert scope.precedent_scope == "client_first"
    got = precedents.retrieve(query(scope, terms=("Officer compensation",), limit=50))
    ids = [p.precedent_id for p in got]
    own = {r.precedent_id for r in populated["own"]}
    other = {r.precedent_id for r in populated["other"]}
    assert ids[0] in own, "the other client's exact match came before the client's own"
    assert max(i for i, p in enumerate(ids) if p in own) < min(
        i for i, p in enumerate(ids) if p in other
    )


def test_a_new_client_sees_the_scope_not_a_client(
    populated: dict[str, list[PrecedentRecord]], precedents: PrecedentStore
) -> None:
    new = ScopeResolver().resolve("valuation/non-esop/non-repeat")
    assert new.precedent_scope == "scope_only"
    got = precedents.retrieve(
        query(new, client_id="client_nobody", terms=("Officer compensation",), limit=50)
    )
    assert got[0].example["description"] == "Officer compensation"
    assert {p.practice for p in got} == {"valuation"}


def test_ranking_is_by_the_terms_and_is_deterministic(
    populated: dict[str, list[PrecedentRecord]], precedents: PrecedentStore, scope: ResolvedScope
) -> None:
    first = precedents.retrieve(query(scope, terms=("Rent expense",), limit=3))
    again = precedents.retrieve(query(scope, terms=("Rent expense",), limit=3))
    assert first == again
    assert first[0].example["category"] == "rent"
    assert similarity("Rent - shop", "Rent expense") > similarity("Utilities", "Rent expense")
    assert 0 < similarity("Repairs and Maintenance", "Repairs & Maint") < 1
    assert similarity("Rent expense", "rent - expense") == 1.0


def test_the_context_builder_receives_the_stores_examples_masked_and_in_scope(
    populated: dict[str, list[PrecedentRecord]], precedents: PrecedentStore
) -> None:
    """P09's checks run over what this store returns: every precedent is masked and
    inside the practice, so the builder's refusal path is never reached."""
    from harness.context import ContextBuilder as CB  # noqa: F401

    got = precedents.retrieve(
        PrecedentQuery(
            engagement_id=ENGAGEMENT,
            client_id=CLIENT,
            practice="valuation",
            segment="esop",
            disposition="repeat",
            precedent_scope="client_first",
            skill=SKILL,
        )
    )
    assert got and all(p.masked for p in got)
    assert all(p.practice == "valuation" for p in got)
    checked = ContextBuilder._checked(  # noqa: SLF001 - P09's refusal path, exercised
        ContextBuilder.__new__(ContextBuilder),
        got,
        query(ScopeResolver().resolve("valuation/esop/repeat")),
    )
    assert checked


# ------------------------------------------------------------ the gated read


def test_the_lookup_tool_cannot_declare_another_practice(
    populated: dict[str, list[PrecedentRecord]], world: dict[str, Any], store: SqlRunStore
) -> None:
    tools = world["tools_for"]()
    before = len([e for e in store.events(world["run_id"]) if e.type == "tool.called"])
    with pytest.raises(PolicyDenied) as denied:
        tools["precedent_lookup"](
            engagement_id=tools.engagement_id,
            scope="corporate-finance/tbd/non-repeat",
            ids=[populated["cf"][0].precedent_id],
        )
    assert denied.value.decision.predicate == "precedent_scope_declared"
    assert len([e for e in store.events(world["run_id"]) if e.type == "tool.called"]) == before


def test_the_lookup_tool_answers_ids_within_the_runs_scope_only(
    populated: dict[str, list[PrecedentRecord]], world: dict[str, Any]
) -> None:
    tools = world["tools_for"]()
    wanted = [populated["own"][0].precedent_id, populated["cf"][0].precedent_id]
    result = tools["precedent_lookup"](
        engagement_id=tools.engagement_id, scope=tools.scope_path, ids=wanted
    )
    assert [r["precedent_id"] for r in result.value["rows"]] == [wanted[0]]
    assert "client" not in " ".join(result.value["rows"][0]).lower()
    ranked = tools["precedent_lookup"](
        engagement_id=tools.engagement_id, scope=tools.scope_path, terms=["Utilities"], limit=2
    )
    assert ranked.rows == 2 and ranked.value["rows"][0]["category"] == "utilities"


# ------------------------------------------------------------ the snapshot


def test_the_snapshot_id_changes_when_the_store_does_and_so_does_the_plan_hash(
    world: dict[str, Any], precedents: PrecedentStore, store: SqlRunStore, scope: ResolvedScope
) -> None:
    before = precedents.snapshot_id()
    assert before == "precedent_snapshot_empty"
    approved(
        store,
        world,
        run_id=world["run_id"],
        engagement_id=ENGAGEMENT,
        client_id=CLIENT,
        scope_path="valuation/esop/repeat",
        item_id="snap_0",
        description="Rent",
        category="rent",
    )
    after = precedents.snapshot_id()
    assert after != before and after.startswith("precedent_snapshot_")
    assert compile_for(scope, before).plan_hash != compile_for(scope, after).plan_hash


# ------------------------------------------------------------ one writer, three ways


def test_the_api_has_exactly_one_writer_and_it_is_the_writeback() -> None:
    """Level one. `admit` is called from precedent/writeback.py and nowhere else;
    `PrecedentRow(` is constructed in precedent/store.py and nowhere else."""
    admits: list[str] = []
    rows: list[str] = []
    for path in ROOT.rglob("*.py"):
        rel = path.relative_to(ROOT).as_posix()
        if rel.startswith((".venv/", "tests/")):
            continue
        source = path.read_text(encoding="utf-8")
        touches_store = "from precedent" in source or "import precedent" in source
        if touches_store and ".admit(" in source and "def admit(" not in source:
            admits.append(rel)
        if "PrecedentRow(" in source and "class PrecedentRow(" not in source:
            rows.append(rel)
    assert admits == ["precedent/writeback.py"], admits
    assert rows == ["precedent/store.py"], rows


def test_the_store_refuses_a_record_whose_decision_does_not_qualify(
    world: dict[str, Any], store: SqlRunStore, precedents: PrecedentStore
) -> None:
    """Level two. A record naming no decision, or a rejection, is refused by the store
    itself - it re-reads the decision rather than trusting the caller."""

    def record(item_id: str) -> PrecedentRecord:
        return PrecedentRecord(
            precedent_id=f"prec_{item_id}",
            decision_run_id=world["run_id"],
            decision_item_id=item_id,
            engagement_id=ENGAGEMENT,
            client_id=CLIENT,
            practice="valuation",
            segment="esop",
            disposition="repeat",
            skill="line-item-tagging",
            taxonomy_version=TAXONOMY,
            decided_by="Dana Whitfield",
            decided_at="2026-09-03T00:00:00Z",
            decision="accepted",
            description="Rent",
            example={"category": "rent"},
        )

    with pytest.raises(PrecedentRefused) as refused:
        precedents.admit(record("nobody_decided_this"))
    assert refused.value.diagnostic.code == "PROCESS.PRECEDENT_NO_DECISION"

    store.open_review_item(world["run_id"], "rejected_1", "confidence", "Rent?", detail={})
    store.record_decision(
        world["run_id"],
        "rejected_1",
        decided_by="Dana Whitfield",
        decision=DecisionKind.REJECTED,
        rationale="wrong",
        writes_precedent=False,
    )
    with pytest.raises(PrecedentRefused) as refused:
        precedents.admit(record("rejected_1"))
    assert "rejected" in refused.value.diagnostic.found
    assert precedents.count() == 0


def test_the_database_refuses_a_raw_insert_without_a_qualifying_decision(
    world: dict[str, Any], store: SqlRunStore, precedents: PrecedentStore
) -> None:
    """Level three. Bypass the API and the store entirely: a session that inserts a row
    for a rejected decision hits the BEFORE INSERT trigger; one for no decision hits the
    foreign key. Either way nothing is written."""
    store.open_review_item(world["run_id"], "rejected_2", "confidence", "Rent?", detail={})
    store.record_decision(
        world["run_id"],
        "rejected_2",
        decided_by="Dana Whitfield",
        decision=DecisionKind.REJECTED,
        rationale="wrong",
        writes_precedent=False,
    )

    def raw(item_id: str) -> None:
        with precedents._session() as session:  # noqa: SLF001 - the bypass is the point
            session.add(
                PrecedentRow(
                    precedent_id=f"raw_{item_id}",
                    decision_run_id=world["run_id"],
                    decision_item_id=item_id,
                    engagement_id=ENGAGEMENT,
                    client_id=CLIENT,
                    practice="valuation",
                    segment="esop",
                    disposition="repeat",
                    skill="line-item-tagging",
                    taxonomy_version=TAXONOMY,
                    decided_by="Dana Whitfield",
                    decided_at="2026-09-03T00:00:00Z",
                    decision="accepted",
                    masked=True,
                    description="Rent",
                    example={},
                )
            )
            session.flush()

    with pytest.raises((IntegrityError, OperationalError)) as trigger:
        raw("rejected_2")
    assert "PRECEDENT_NO_DECISION" in str(trigger.value)
    with pytest.raises((IntegrityError, OperationalError)):
        raw("never_decided")
    assert precedents.count() == 0


def test_the_store_is_append_only_like_the_log_it_hangs_off(
    populated: dict[str, list[PrecedentRecord]], precedents: PrecedentStore
) -> None:
    target = populated["own"][0].precedent_id
    with pytest.raises(AppendOnlyViolation), precedents._session() as session:  # noqa: SLF001
        row = session.scalars(select(PrecedentRow).where(PrecedentRow.precedent_id == target)).one()
        row.description = "edited"
        session.flush()
    with (
        pytest.raises((IntegrityError, OperationalError)) as refused,
        precedents._session() as session,  # noqa: SLF001
    ):
        session.execute(text("DELETE FROM precedent WHERE precedent_id = :p"), {"p": target})
    assert "APPEND_ONLY_VIOLATION" in str(refused.value)


def test_a_decision_writes_one_precedent_once(
    world: dict[str, Any], store: SqlRunStore, precedents: PrecedentStore
) -> None:
    first = approved(
        store,
        world,
        run_id=world["run_id"],
        engagement_id=ENGAGEMENT,
        client_id=CLIENT,
        scope_path="valuation/esop/repeat",
        item_id="once",
        description="Rent",
        category="rent",
    )
    again = world["writeback"].write(
        world["run_id"],
        "once",
        client_id=CLIENT,
        scope_path="valuation/esop/repeat",
        identifiers=(),
    )
    assert again.precedent_id == first.precedent_id
    assert precedents.count() == 1
    assert Path(ROOT / "precedent" / "store.py").is_file()
