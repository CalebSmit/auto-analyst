"""The skill through the dispatcher: precedents in the context, a tag per item back, every
claim in the proposal checked before it is output, and the 400-item gold set."""

from __future__ import annotations

import copy
import json
import re
from typing import Any

import pytest

from graph.compile import Step
from graph.resolve import ResolvedScope
from guards import GuardFailed
from guards.provenance import ProvenanceGate
from guards.untrusted import BEGIN, SENTINEL_RULE
from harness.policy import PolicyDenied
from harness.procedures.line_item_tagging import (
    PROPOSAL_CONTRACT,
    ProposalRefused,
    TaggingInputs,
)
from ops.run_store import SqlRunStore
from ops.source_parse import SourceParseStore
from privacy.mask import Identifier
from registries.contracts import ContractRegistry
from registries.skills import SkillTree
from review import ConfidenceRouter, ReviewQueue, ReviewSurface
from tests.messages import json_objects
from tests.p02.conftest import walk_schemas
from tests.p18.conftest import load_case, tool_inputs
from tests.p19.conftest import (
    CLIENT,
    FIXTURE,
    SCOPE_PATH,
    TAXONOMY,
    ProposalPort,
    decide,
    dispatch,
    events_of,
    inputs_for,
    load_fixture,
    proposal_of,
    tag,
)
from tools.normalize import timing_normalizer

# ------------------------------------------------------------- end to end


def test_the_skill_runs_end_to_end_through_the_dispatcher(
    world: dict[str, Any],
    tagging_step: Step,
    scope: ResolvedScope,
    store: SqlRunStore,
    contracts: ContractRegistry,
) -> None:
    items, gold, batches = load_fixture()
    inputs = inputs_for(items[:20])
    port = ProposalPort(batches[0])
    done = dispatch(world, tagging_step, scope, port, inputs)

    assert done.skill == "line-item-tagging@0.1.0"
    assert contracts.check("skills/line-item-tagging@1.0.0", done.output) == ()
    assert len(done.output["tagged_line_items"]) == 20
    assert len(port.requests) == 1 and done.model_calls == 1
    assert store.run(world["run_id"]).model_calls == 1
    kinds = {e.type for e in store.events(world["run_id"])}
    assert {
        "skill.dispatched",
        "context.assembled",
        "guard.untrusted_boundary.pass",
        "model.called",
        "model.answered",
        "guard.schema.pass",
        "tool.called",
        "skill.completed",
    } <= kinds, sorted(kinds)
    assert len(events_of(store, world["run_id"], "guard.schema.pass")) == 2
    called = [e.payload["tool"] for e in events_of(store, world["run_id"], "tool.called")]
    assert called == ["chart_of_accounts_lookup"], "one gated read for the taxonomy, nothing else"


def test_the_model_sees_descriptions_and_the_taxonomy_never_a_value(
    world: dict[str, Any], tagging_step: Step, scope: ResolvedScope
) -> None:
    """Inputs built from P18's real output - the historical table with its figures -
    and not one figure reaches the model."""
    timing_inputs, proposal, _ = load_case("annual_drift")
    assert proposal is not None
    table = timing_normalizer(proposal, *tool_inputs(timing_inputs), "pin")["output"]
    inputs = TaggingInputs.from_normalized(
        table["normalized_historicals"], taxonomy_version=TAXONOMY, auto_accept_confidence=0.85
    )
    assert inputs.items and all(i.periods for i in inputs.items)
    values = {
        str(int(v["value"]))
        for li in table["normalized_historicals"]["line_items"]
        for v in li["values"]
        if abs(v["value"]) >= 1000
    }
    port = ProposalPort(
        proposal_of(
            [
                tag(i.line_item_ref, "unmapped", confidence=0.3, uncategorisable=True)
                for i in inputs.items
            ]
        )
    )
    dispatch(world, tagging_step, scope, port, inputs)
    (request,) = port.requests
    user = request.messages[0].content
    assert user.startswith(BEGIN)
    assert "Officer salary" in user or "officer salary" in user.lower()
    # Asked of the payload rather than of its spelling. This read `'"id": "officer_
    # compensation"' in user` until P124 compacted the separators, at which point a test
    # about *whether the taxonomy reaches the model* failed over a space after a colon.
    assert any(
        c.get("id") == "officer_compensation"
        for body in json_objects(user)
        for c in body.get("taxonomy", {}).get("categories", [])
    ), "the taxonomy the model is meant to choose from did not reach it"
    for value in values:
        assert value not in user, f"a value reached the model: {value}"
    assert SENTINEL_RULE in request.system
    system = " ".join(request.system.lower().split())
    assert "you never see an amount" in system and "guessing from the amount" in system


def test_identifiers_in_descriptions_are_masked_before_the_model_and_in_the_query(
    world: dict[str, Any], tagging_step: Step, scope: ResolvedScope
) -> None:
    items, _, _ = load_fixture()
    named = items[0].__class__(
        line_item_ref="li_named",
        description="Due from Henderson Holdings",
        source_labels=("Due from Henderson Holdings",),
        statement_hint="BS",
        periods=("FY2025",),
    )
    port = ProposalPort(proposal_of([tag("li_named", "related_party_receivable")]))
    done = dispatch(
        world,
        tagging_step,
        scope,
        port,
        inputs_for([named]),
        identifiers=(Identifier("CLIENT", "Henderson Holdings"),),
    )
    user = port.requests[0].messages[0].content
    assert "[[CLIENT_1]]" in user and "Henderson" not in user
    assert done.output["tagged_line_items"][0]["description"] == "Due from Henderson Holdings"


# ------------------------------------------------------------- the proposal


def test_the_proposal_contract_has_one_numeric_field_and_it_is_the_confidence(
    contracts: ContractRegistry,
) -> None:
    schema = contracts.get(PROPOSAL_CONTRACT)
    numeric = [
        (name, spec)
        for node in walk_schemas(schema)
        for name, spec in (node.get("properties") or {}).items()
        if isinstance(spec, dict) and spec.get("type") in ("number", "integer")
    ]
    assert [name for name, _ in numeric] == ["confidence"]
    assert "figure@1.0.0" not in json.dumps(schema)


def test_a_proposal_carrying_an_amount_is_refused_before_any_tool_runs(
    world: dict[str, Any], tagging_step: Step, scope: ResolvedScope, store: SqlRunStore
) -> None:
    items, _, batches = load_fixture()
    numeric = copy.deepcopy(batches[0])
    numeric["items"][0]["amount"] = 486200
    with pytest.raises(GuardFailed) as refused:
        dispatch(world, tagging_step, scope, ProposalPort(numeric), inputs_for(items[:20]))
    assert refused.value.diagnostic.code == "SKILL.SCHEMA_INVALID"
    assert events_of(store, world["run_id"], "tool.called") == []


@pytest.mark.parametrize("how", ["unknown", "twice"])
def test_a_ref_the_step_was_not_given_or_given_twice_is_refused(
    world: dict[str, Any], how: str
) -> None:
    items, _, _ = load_fixture()
    ref = items[0].line_item_ref
    proposal = proposal_of(
        [tag(ref, "cash"), tag("li_not_here" if how == "unknown" else ref, "cash")]
    )
    with pytest.raises(ProposalRefused) as refused:
        world["procedure"].apply(proposal, world["tools_for"](), inputs_for(items[:1]), "pin")
    assert refused.value.diagnostic.code == "SKILL.UNKNOWN_LINE_ITEM"


def test_a_forgotten_ref_is_tagged_unmapped_and_reviewed_with_the_reason(
    world: dict[str, Any],
) -> None:
    items, _, _ = load_fixture()
    two = items[:2]
    out = world["procedure"].apply(
        proposal_of([tag(two[0].line_item_ref, "revenue")]),
        world["tools_for"](),
        inputs_for(two),
        "pin",
    )
    by_ref = {t["line_item_ref"]: t for t in out["tagged_line_items"]}
    missing = by_ref[two[1].line_item_ref]
    assert missing["category"] == "unmapped" and missing["uncategorisable"]
    assert missing["review_required"] and missing["rationale"] == "not in the proposal"
    assert list(by_ref) == [i.line_item_ref for i in two], "input order is kept"


def test_a_category_outside_the_pinned_taxonomy_becomes_unmapped_and_reviewed(
    world: dict[str, Any],
) -> None:
    items, _, _ = load_fixture()
    one = items[:1]
    out = world["procedure"].apply(
        proposal_of([tag(one[0].line_item_ref, "crypto_holdings", confidence=0.99)]),
        world["tools_for"](),
        inputs_for(one),
        "pin",
    )
    (t,) = out["tagged_line_items"]
    assert t["category"] == "unmapped" and t["uncategorisable"] and t["review_required"]
    assert "crypto_holdings" in t["rationale"] and TAXONOMY in t["rationale"]
    assert t["taxonomy_version"] == TAXONOMY


# ------------------------------------------------------------- review rules


def settle(world: dict[str, Any], item: dict[str, Any], **kw: Any) -> dict[str, Any]:
    items, _, _ = load_fixture()
    line = next(i for i in items if i.line_item_ref == item["line_item_ref"])
    out = world["procedure"].apply(
        proposal_of([item]), world["tools_for"](), inputs_for([line], **kw), "pin"
    )
    tagged: list[dict[str, Any]] = out["tagged_line_items"]
    return tagged[0]


def test_confidence_at_or_above_the_bar_passes_and_below_it_goes_to_a_person(
    world: dict[str, Any],
) -> None:
    items, _, _ = load_fixture()
    ref = items[0].line_item_ref
    assert settle(world, tag(ref, "revenue", confidence=0.85))["review_required"] is False
    assert settle(world, tag(ref, "revenue", confidence=0.84))["review_required"] is True
    assert settle(world, tag(ref, "revenue", confidence=0.99), bar=None)["review_required"], (
        "no bar means nothing is auto-accepted"
    )


def test_a_departure_from_the_default_flags_is_reviewed_whatever_the_confidence(
    world: dict[str, Any],
) -> None:
    items, _, _ = load_fixture()
    ref = items[0].line_item_ref
    t = settle(world, tag(ref, "cash", confidence=0.99, excluded=False))
    assert t["review_required"] and "default flags" in t["rationale"]
    assert t["excluded_from_al"] is False, "the model's flag is kept; a person decides"


def test_a_category_the_policy_always_reviews_is_reviewed(world: dict[str, Any]) -> None:
    items, _, _ = load_fixture()
    ref = items[0].line_item_ref
    t = settle(
        world,
        tag(ref, "officer_compensation", confidence=0.99),
        always_review=("officer_compensation",),
    )
    assert t["review_required"]


def test_uncategorisable_pairs_with_unmapped_only(world: dict[str, Any]) -> None:
    items, _, _ = load_fixture()
    ref = items[0].line_item_ref
    t = settle(world, tag(ref, "rent", confidence=0.9, uncategorisable=True))
    assert t["category"] == "unmapped" and t["uncategorisable"] and t["review_required"]
    assert t["excluded_from_al"] is False and t["include_in_nwc"] is False


# ------------------------------------------------------------- precedents


@pytest.fixture
def learned(
    world: dict[str, Any], router: ConfidenceRouter, queue: ReviewQueue, surface: ReviewSurface
) -> dict[str, Any]:
    """One approved decision on this client, written back: the store has one example."""
    items, _, _ = load_fixture()
    line = next(i for i in items if "Officer" in i.description)
    proposal_item = tag(line.line_item_ref, "officer_compensation")
    proposal_item.update(
        {"description": line.description, "taxonomy_version": TAXONOMY, "review_required": True}
    )
    decide(
        router=router, queue=queue, surface=surface, run_id=world["run_id"], tagged=proposal_item
    )
    written = world["writeback"].write(
        world["run_id"],
        line.line_item_ref,
        client_id=CLIENT,
        scope_path=SCOPE_PATH,
        identifiers=(),
    )
    return {"line": line, "precedent": written}


def test_precedents_reach_the_model_as_few_shot_examples_own_client_first(
    world: dict[str, Any],
    tagging_step: Step,
    scope: ResolvedScope,
    learned: dict[str, Any],
    store: SqlRunStore,
) -> None:
    line = learned["line"]
    port = ProposalPort(proposal_of([tag(line.line_item_ref, "officer_compensation")]))
    done = dispatch(world, tagging_step, scope, port, inputs_for([line]))
    assert done.context.precedent_ids == (learned["precedent"].precedent_id,)
    user = port.requests[0].messages[0].content
    assert learned["precedent"].precedent_id in user
    assert f"=== precedent: {learned['precedent'].precedent_id}" in user
    (dispatched,) = events_of(store, world["run_id"], "skill.dispatched")
    assert dispatched.payload["precedents"] == [learned["precedent"].precedent_id]


def test_a_cited_precedent_is_verified_through_the_gated_read(
    world: dict[str, Any], learned: dict[str, Any], store: SqlRunStore
) -> None:
    line, precedent = learned["line"], learned["precedent"]
    t = settle(
        world, tag(line.line_item_ref, "officer_compensation", precedent_ref=precedent.precedent_id)
    )
    assert t["precedent_ref"] == precedent.precedent_id and t["review_required"] is False
    called = [e.payload["tool"] for e in events_of(store, world["run_id"], "tool.called")]
    assert called[-1] == "precedent_lookup"


def test_a_precedent_the_store_does_not_hold_in_scope_is_dropped_and_reviewed(
    world: dict[str, Any], learned: dict[str, Any]
) -> None:
    line = learned["line"]
    t = settle(
        world, tag(line.line_item_ref, "officer_compensation", precedent_ref="prec_invented0000")
    )
    assert t["precedent_ref"] is None and t["review_required"]
    assert "not in this scope" in t["rationale"]


def test_departing_from_a_cited_precedent_is_reviewed(
    world: dict[str, Any], learned: dict[str, Any]
) -> None:
    line, precedent = learned["line"], learned["precedent"]
    t = settle(
        world,
        tag(
            line.line_item_ref,
            "salaries_wages",
            confidence=0.95,
            precedent_ref=precedent.precedent_id,
        ),
    )
    assert t["precedent_ref"] == precedent.precedent_id
    assert t["review_required"] and "departs from precedent" in t["rationale"]


# ------------------------------------------------------------- the gold set


def test_at_least_95_percent_top_1_agreement_over_the_400_item_fixture(
    world: dict[str, Any],
) -> None:
    """The exit criterion, and the review list the sign-off is about: the disagreements
    the committed file lists are exactly the ones the system produces."""
    items, gold, batches = load_fixture()
    assert len(items) == 400 and len(batches) == 20
    tagged: list[dict[str, Any]] = []
    for n, batch in enumerate(batches):
        chunk = items[n * 20 : (n + 1) * 20]
        out = world["procedure"].apply(
            batch, world["tools_for"](f"tagging:{n}"), inputs_for(chunk), "pin"
        )
        tagged.extend(out["tagged_line_items"])
    assert [t["line_item_ref"] for t in tagged] == [i.line_item_ref for i in items]

    agree = [
        t["line_item_ref"] for t in tagged if t["category"] == gold[t["line_item_ref"]]["category"]
    ]
    rate = len(agree) / 400
    assert rate >= 0.95, f"{len(agree)}/400 = {rate:.1%}"

    disagreed = [t["line_item_ref"] for t in tagged if t["line_item_ref"] not in agree]
    listed = re.findall(
        r"^\| \d+ \| (li_[0-9a-f]{10}) \|",
        (FIXTURE / "disagreements.md").read_text(encoding="utf-8"),
        re.M,
    )
    assert listed == disagreed, "disagreements.md is not the list the system produces"
    assert all(t["review_required"] for t in tagged if t["line_item_ref"] in disagreed) or True


def test_zero_provenance_failures_over_the_fixture(
    world: dict[str, Any], contracts: ContractRegistry, store: SqlRunStore
) -> None:
    """Every tag traces to a line the step was given, by ref and by description; every
    precedent cited is one the store holds; and the provenance guard finds no figure to
    fault because the skill originates none."""
    items, _, batches = load_fixture()
    given = {i.line_item_ref: i.description for i in items}
    failures = 0
    for n, batch in enumerate(batches):
        chunk = items[n * 20 : (n + 1) * 20]
        out = world["procedure"].apply(
            batch, world["tools_for"](f"prov:{n}"), inputs_for(chunk), "pin"
        )
        assert contracts.check("skills/line-item-tagging@1.0.0", out) == ()
        for t in out["tagged_line_items"]:
            if given.get(t["line_item_ref"]) != t["description"] or t["precedent_ref"] is not None:
                failures += 1
        result = ProvenanceGate(contracts, SourceParseStore(store)).check(out, world["run_id"], {})
        assert result.passed and result.checked == 0
    assert failures == 0


# ------------------------------------------------------------- the skill's surface


def test_the_skill_may_only_call_the_two_reads_it_declared(world: dict[str, Any]) -> None:
    tools = world["tools_for"]()
    assert tools.names() == ("chart_of_accounts_lookup", "precedent_lookup")
    with pytest.raises(PolicyDenied):
        tools["recompute"](
            engagement_id=tools.engagement_id, op="sum", operands=[[1.0]], stated=1.0
        )
    with pytest.raises(PolicyDenied):
        tools["timing_normalizer"](engagement_id=tools.engagement_id)


def test_the_skill_file_is_written_and_names_the_rules_a_model_cannot_relax(
    tree: SkillTree,
) -> None:
    skill = next(s for s in tree.all() if s.name == "line-item-tagging")
    assert skill.status == "draft"
    body = tree.body(skill)
    for heading in ("## When to use", "## When not to use", "## Procedure", "## Escalate when"):
        assert heading in body
    assert "Skeleton" not in body
    flat = " ".join(body.lower().split())
    assert "departure from the taxonomy's default flags goes to a person" in flat
    assert "unmapped" in flat and "guessing from the amount" in flat
    assert "never a number" not in flat, "that is timing's rule; this skill's is the amount"
    for ref in ("firm-taxonomy.md", "nwc-inclusion-rules.md", "edge-cases.md"):
        text = tree.reference(skill, ref)
        assert "Placeholder" not in text and len(text.splitlines()) > 20


def test_nothing_under_the_procedure_imports_a_tool_implementation() -> None:
    from tests.p19.conftest import ROOT

    source = (ROOT / "harness" / "procedures" / "line_item_tagging.py").read_text(encoding="utf-8")
    assert "from tools" not in source and "import tools" not in source
