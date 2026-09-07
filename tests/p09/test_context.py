"""The Context Builder: one place, one hash, and nothing loaded that was not selected.

Four exit criteria. The first is the one everything else in the system will lean on:
`context_ref` reproduces the exact bytes a model was shown, so any call can be
reconstructed later - which is what a workfile has to be able to do.
"""

from __future__ import annotations

import dataclasses
import inspect
from typing import Any

import pytest

from graph.compile import CompiledGraph
from graph.execute import step_key
from harness.context import ContextBuilder, ContextRequest, NoPrecedents, PrecedentQuery
from ops.blobs import ContentRef, LocalContentStore
from ops.run_store import SqlRunStore
from registries.errors import RegistryError
from registries.skills import SkillTree
from tests.p09.conftest import CLIENT, ENGAGEMENT, Sourced, precedent

# ------------------------------------------------- the bytes are the bytes


def test_context_ref_reproduces_the_exact_bytes(
    builder: ContextBuilder, request_for: Any, blobs: LocalContentStore
) -> None:
    """The exit criterion. The ref resolves to the assembled whole, byte for byte, and
    the hash of those bytes is the ref."""
    built = builder.build(request_for())
    shown = blobs.get(built.ref)
    assert built.context_ref == built.ref.content_hash
    assert blobs.put(shown).content_hash == built.context_ref


def test_the_same_inputs_assemble_to_the_same_ref(
    builder: ContextBuilder, request_for: Any
) -> None:
    """Deterministic, or the key it feeds would be noise."""
    assert builder.build(request_for()).context_ref == builder.build(request_for()).context_ref


def test_the_assembled_context_contains_every_section_in_order(
    builder: ContextBuilder, request_for: Any, blobs: LocalContentStore
) -> None:
    """The order is fixed because the hash is an identity. Two contexts differing only in
    section order would be two keys for one question."""
    built = builder.build(request_for())
    kinds = [s.kind for s in built.sections]
    assert kinds[0] == "skill"
    assert kinds[-2:] == ["engagement_profile", "payload"]
    assert "foundations" in kinds and "precedent" in kinds and "reference" in kinds
    first = kinds.index("foundations")
    assert all(k == "reference" for k in kinds[1:first])

    shown = blobs.get(built.ref).decode("utf-8")
    positions = [shown.index(f"=== {s.kind}: {s.name}") for s in built.sections]
    assert positions == sorted(positions)


def test_the_manifest_agrees_with_the_bytes(
    builder: ContextBuilder, request_for: Any, blobs: LocalContentStore
) -> None:
    """Each section's hash appears in the frame around it, so the manifest and the bytes
    cannot disagree by construction."""
    built = builder.build(request_for())
    shown = blobs.get(built.ref).decode("utf-8")
    manifest = blobs.get_json(built.manifest_ref)
    assert manifest["context_ref"] == built.context_ref
    for section in manifest["sections"]:
        assert section["content_hash"] in shown


# -------------------------------------------- precedents move the key


def test_changing_a_retrieved_precedent_changes_context_ref_and_step_key(
    tree: SkillTree, blobs: LocalContentStore, bus: Any, store: SqlRunStore,
    request_for: Any, plan: CompiledGraph,
) -> None:
    """The exit criterion, and the correction the phase note records: without context_ref
    in the key, a resumed run could return a cached result the current context would no
    longer produce."""
    request = request_for()
    inputs = {"tagging": ContentRef("sha256:" + "a" * 64, name="tagging")}

    before = ContextBuilder(
        tree, blobs, bus, store, precedents=Sourced(precedent("p1", category="rent"))
    ).build(request)
    after = ContextBuilder(
        tree, blobs, bus, store, precedents=Sourced(precedent("p1", category="owner_comp"))
    ).build(request)

    assert before.context_ref != after.context_ref
    assert step_key(plan.step("ebitda"), inputs, before.context_ref) != step_key(
        plan.step("ebitda"), inputs, after.context_ref
    )


def test_no_precedents_is_a_different_context_from_some(
    tree: SkillTree, blobs: LocalContentStore, bus: Any, store: SqlRunStore, request_for: Any
) -> None:
    none = ContextBuilder(tree, blobs, bus, store, precedents=NoPrecedents()).build(request_for())
    some = ContextBuilder(
        tree, blobs, bus, store, precedents=Sourced(precedent("p1"))
    ).build(request_for())
    assert none.context_ref != some.context_ref
    assert none.precedent_ids == ()
    assert some.precedent_ids == ("p1",)


def test_repair_feedback_is_a_different_context(
    builder: ContextBuilder, request_for: Any, blobs: LocalContentStore
) -> None:
    """A repair pass has to change the input, or it is not an iteration - and the
    changed input has to change the key, or the ledger would hand back the result the
    guard just rejected."""
    plain = builder.build(request_for())
    feedback = blobs.put_json({"guard": "schema", "failed": ["addback_schedule[2].source_id"]})
    repaired = builder.build(request_for(repair_feedback=feedback))
    assert plain.context_ref != repaired.context_ref
    assert repaired.section("repair_feedback")


# ------------------------------------------------ progressive disclosure


class Watched(SkillTree):
    """A tree that records which bodies and references it was asked for."""

    def __init__(self, real: SkillTree) -> None:
        super().__init__(real.all(), real.overlays())
        self.bodies: list[str] = []
        self.references: list[tuple[str, str]] = []

    def body(self, skill):  # noqa: ANN001, ANN201 - a test double
        self.bodies.append(skill.name)
        return super().body(skill)

    def reference(self, skill, name, declared=None, layers=()):  # noqa: ANN001, ANN201
        self.references.append((skill.name, name))
        return super().reference(skill, name, declared=declared, layers=layers)


def test_a_skill_body_is_never_loaded_for_a_skill_the_plan_did_not_select(
    tree: SkillTree, blobs: LocalContentStore, bus: Any, store: SqlRunStore, request_for: Any
) -> None:
    """The exit criterion. Twelve skills resolved into this scope; one body was read."""
    watched = Watched(tree)
    ContextBuilder(watched, blobs, bus, store).build(request_for("ebitda"))
    assert watched.bodies == ["ebitda-normalization"]
    assert {s for s, _ in watched.references} == {"ebitda-normalization"}


def test_only_the_selected_skills_references_are_loaded(
    tree: SkillTree, blobs: LocalContentStore, bus: Any, store: SqlRunStore, request_for: Any
) -> None:
    watched = Watched(tree)
    built = ContextBuilder(watched, blobs, bus, store).build(request_for("timing"))
    assert watched.bodies == ["timing-normalization"]
    loaded = {name for _, name in watched.references}
    assert loaded == {s.name for s in built.section("reference")}
    assert loaded == {"line-item-matching.md", "period-conventions.md"}


def test_an_overlay_added_reference_is_loaded_from_the_overlays_layer(
    builder: ContextBuilder, request_for: Any, blobs: LocalContentStore
) -> None:
    """ebitda-normalization lives at valuation/_group; the ESOP overlay adds
    dol-adequate-consideration.md, which lives beside the overlay at
    valuation/esop/_segment. The builder finds it there."""
    built = builder.build(request_for("ebitda"))
    names = {s.name for s in built.section("reference")}
    assert "addback-taxonomy.md" in names
    assert "dol-adequate-consideration.md" in names
    assert "ESOP-layer reference" in blobs.get(built.ref).decode("utf-8")


def test_a_non_skill_step_has_no_context(builder: ContextBuilder, request_for: Any) -> None:
    with pytest.raises(RegistryError, match="only a skill step"):
        builder.build(request_for("intake"))


# ------------------------------------------------------- foundations


def test_foundations_are_attached_to_every_call(builder: ContextBuilder, request_for: Any) -> None:
    """Unconditionally. Not something the next skill\'s author can leave out.

    The firm layer is the floor of every scope walk, which is what makes it unconditional
    without a second mechanism saying so. A file is named by its layer because two
    practice groups can write the same filename and mean different documents; what a
    group adds on top of this is P31.
    """
    for step_id in ("timing", "ebitda", "qc"):
        names = {s.name for s in builder.build(request_for(step_id)).section("foundations")}
        assert names == {
            "_firm/qc-conventions.md",
            "_firm/tagging-policy.md",
            "_firm/valuation-standards.md",
        }


def test_the_foundations_readme_is_not_context(builder: ContextBuilder, request_for: Any) -> None:
    """The README explains the folder to a person; it is not a firm standard."""
    names = {s.name for s in builder.build(request_for()).section("foundations")}
    assert "README.md" not in names


# ---------------------------------------------- scope-built retrieval


def test_the_precedent_query_is_built_from_the_resolved_scope(
    builder: ContextBuilder, request_for: Any, source: Sourced
) -> None:
    """The exit criterion, first half. Every field of the query comes from the scope the
    engagement resolved to; there is nothing a caller could widen it through."""
    builder.build(request_for("ebitda"))
    query = source.queries[-1]
    assert query == PrecedentQuery(
        engagement_id=ENGAGEMENT,
        client_id=CLIENT,
        practice="valuation",
        segment="esop",
        disposition="repeat",
        precedent_scope="client_first",
        skill="ebitda-normalization@0.1.0",
    )


def test_the_query_cannot_be_widened(builder: ContextBuilder) -> None:
    """A request carries the resolved scope object, not a scope string. The query is
    derived, and there is no parameter on `build` that could change what it derives."""
    params = set(inspect.signature(builder.build).parameters)
    assert params == {"request"}
    fields = {f.name for f in dataclasses.fields(ContextRequest)}
    assert "precedent_scope" not in fields
    assert "practice" not in fields


def test_a_precedent_from_another_practice_group_refuses_the_batch(
    tree: SkillTree, blobs: LocalContentStore, bus: Any, store: SqlRunStore, request_for: Any
) -> None:
    """The exit criterion, second half. A Corporate Finance decision is never available
    to an ESOP valuation - and a source that offered one is broken, so the whole batch
    is refused rather than the one item filtered."""
    leaky = Sourced(precedent("ok"), precedent("cf1", scope="corporate-finance/tbd/repeat"))
    with pytest.raises(RegistryError) as raised:
        ContextBuilder(tree, blobs, bus, store, precedents=leaky).build(request_for())
    assert raised.value.diagnostic.code == "SCOPE.PRECEDENT_OUT_OF_SCOPE"
    assert "corporate-finance" in str(raised.value)


def test_an_unmasked_precedent_refuses_the_batch(
    tree: SkillTree, blobs: LocalContentStore, bus: Any, store: SqlRunStore, request_for: Any
) -> None:
    """Nothing unmasked reaches a model through the precedent path."""
    leaky = Sourced(precedent("raw", masked=False))
    with pytest.raises(RegistryError) as raised:
        ContextBuilder(tree, blobs, bus, store, precedents=leaky).build(request_for())
    assert raised.value.diagnostic.code == "PRIVACY.UNMASKED_PRECEDENT"


def test_a_repeat_client_sees_its_own_decisions_first(
    builder: ContextBuilder, request_for: Any
) -> None:
    """The source returned p1, p2, p3 with p2 belonging to this client. Under
    client_first, p2 leads; the rest keep the store's own order."""
    built = builder.build(request_for("ebitda"))
    assert built.precedent_ids == ("p2", "p1", "p3")


def test_a_new_client_gets_the_stores_order(
    tree: SkillTree, blobs: LocalContentStore, bus: Any, store: SqlRunStore,
    request_for: Any, profile: ContentRef, payload: ContentRef,
) -> None:
    from graph.resolve import ScopeResolver

    new_scope = ScopeResolver().resolve("valuation/esop/non-repeat")
    source = Sourced(precedent("p1"), precedent("p2", client_id=CLIENT), precedent("p3"))
    built = ContextBuilder(tree, blobs, bus, store, precedents=source).build(
        request_for("ebitda", scope=new_scope)
    )
    assert source.queries[-1].precedent_scope == "scope_only"
    assert built.precedent_ids == ("p1", "p2", "p3")


# ------------------------------------------------------------- the record


def test_the_context_is_recorded_against_the_run(
    builder: ContextBuilder, request_for: Any, store: SqlRunStore, started: str
) -> None:
    """Written to the event bus and recorded as an artifact, so it reaches the run
    manifest. "What was in context" is then a lookup, not archaeology."""
    built = builder.build(request_for("ebitda"))
    events = [e for e in store.events(started) if e.type == "context.assembled"]
    assert len(events) == 1
    assert events[0].node_id == "context_builder"
    assert events[0].payload["context_ref"] == built.context_ref
    assert events[0].payload["precedents"] == 3

    artifacts = {a.name: a for a in store.artifacts(started)}
    assert artifacts["context/ebitda"].content_hash == built.context_ref


def test_the_record_does_not_hold_the_bytes(
    builder: ContextBuilder, request_for: Any, store: SqlRunStore, started: str
) -> None:
    """The event carries hashes and names. The bytes live in the content store, once."""
    built = builder.build(request_for())
    event = next(e for e in store.events(started) if e.type == "context.assembled")
    assert len(str(event.payload)) < 2000
    assert built.ref.size_bytes > 2000
