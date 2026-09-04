"""The chain end to end, and the claim that holds it up: remove any one gate and the path
from the drop folder to the live tree breaks."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from evals.world import EvalWorld
from governance import GateSkipped, GovernanceChain, GovernanceRecord, RecordBroken
from governance.candidate import MEANS, NODE_FOR, STAGES, Stage
from tests.p27.conftest import (
    DROPPER,
    LAYER,
    OWNER,
    ROUGH_DRAFT,
    SKILL,
    definition_of,
    drop_draft,
    walk,
)

# Every gate between the drop and the tree. The drop itself is not one: a candidate that
# was never dropped has no id to register.
GATES = tuple(s for s in STAGES if s not in (Stage.DROPPED, Stage.REGISTERED))


def test_a_rough_draft_becomes_a_registered_skill(
    chain: GovernanceChain, root: Path, eval_world: EvalWorld, skills_dir: Path
) -> None:
    """A draft with no frontmatter, no scope and no fixtures goes in; a registered version
    comes out, having passed every gate, with the whole path on the record."""
    walked = walk(chain, root, eval_world)
    cid = walked["candidate_id"]

    published = chain.register(
        cid,
        walked["scorecard"],
        definition=definition_of(walked),
        layer=LAYER,
        approved_by=OWNER,
    )
    assert published.registered.skill == SKILL
    assert published.path.is_file() and published.path.parent.parent.name == LAYER
    assert chain.registry.is_registered(SKILL, published.registered.version)

    # The tree the Scope Resolver reads now holds it, and it parses as a skill.
    tree = chain.registry.tree()
    assert SKILL in {s.name for s in tree.all()}
    tree.self_check()

    # Every stage, in order, once. The record holds more than stages - the shadow
    # observations are in there too - so this reads the stage entries out of it.
    names = {str(s) for s in STAGES}
    stages = [e.stage for e in chain.record.entries(cid) if e.stage in names]
    assert stages == [str(s) for s in STAGES], stages
    assert [e.stage for e in chain.record.entries(cid)].count("shadow_observed") == 5
    assert chain.stage_of(cid) is Stage.REGISTERED
    chain.record.verify()

    # And each entry names the node that did it and who or what did it.
    for entry in chain.record.entries(cid):
        assert entry.actor
        if entry.stage in names:
            assert (entry.detail or {}).get("node") == NODE_FOR[Stage(entry.stage)]


@pytest.mark.parametrize("gate", GATES, ids=[str(g) for g in GATES])
def test_remove_any_one_gate_and_the_path_breaks(
    chain: GovernanceChain, root: Path, eval_world: EvalWorld, gate: Stage
) -> None:
    """The exit criterion, one gate at a time. Everything else happens; the chain is asked
    to register anyway, and refuses naming exactly what is missing."""
    walked = walk(chain, root, eval_world, stop_before=str(gate))
    cid = walked["candidate_id"]

    # The next stage that needs it refuses on the spot, naming the gate and what it
    # would have meant: the path breaks where the gate was, not at the end. The shadow
    # run is the last gate before the registry, so for that one there is no later stage
    # to notice and the registry below is what refuses.
    stopped = walked["refused"]
    if gate is not Stage.SHADOWED:
        assert stopped is not None, f"the chain carried on without {gate}"
        assert stopped.diagnostic.code == "SKILL.GATE_SKIPPED"
        assert str(gate) in stopped.diagnostic.detail
        assert MEANS[gate] in stopped.diagnostic.detail

    # And asking the registry directly, skipping everything after the gap, is refused
    # the same way and writes nothing.
    with pytest.raises(GateSkipped) as refused:
        chain.register(
            cid,
            walked.get("scorecard") or _any_scorecard(chain, eval_world),
            definition="---\nname: x\n---\n",
            layer=LAYER,
            approved_by=OWNER,
        )
    d = refused.value.diagnostic
    assert d.code == "SKILL.GATE_SKIPPED"
    assert str(gate) in d.detail
    assert d.owner == "process" and d.what_now
    assert not (chain.registry.skills_dir / LAYER / SKILL).exists(), "nothing was written"
    assert chain.registry.registered() == ()


def test_the_stages_are_the_blueprints_nodes(chain: GovernanceChain) -> None:
    """The chain's stages and the graph's governance nodes are the same eleven things,
    in the same order - so a stage cannot quietly stop implementing its node."""
    from graph.architecture_assertions import load_graph

    graph = load_graph()
    for stage, node in NODE_FOR.items():
        assert node in graph, node
        assert graph[node]["group"] == "gov", node
        assert MEANS[stage]
    ordered = [NODE_FOR[s] for s in STAGES]
    assert ordered == [
        "skill_drop", "skill_conformance", "skill_adapt", "skill_sandbox", "sandbox_test",
        "eval_harness", "replay_harness", "skill_submit", "skill_board", "shadow_run",
        "skill_registry",
    ]
    # Every edge in that chain exists in the graph, in that direction.
    edges = {(e.src, e.dst) for e in graph.kind("flow", "guard")}
    for src, dst in zip(ordered, ordered[1:], strict=False):
        assert (src, dst) in edges, f"{src} -> {dst} is not an edge in the blueprint"


def test_the_drop_folder_takes_a_copy_and_leaves_the_original(
    chain: GovernanceChain, root: Path
) -> None:
    """Nobody loses work by contributing, and nothing is demanded of the draft."""
    path = drop_draft(root, ROUGH_DRAFT)
    before = path.read_bytes()
    dropped = chain.take(path, DROPPER)

    assert path.is_file() and path.read_bytes() == before, "the contributor keeps their file"
    assert dropped.path != path and dropped.path.read_bytes() == before
    assert dropped.source_hash.startswith("sha256:")
    assert dropped.text().startswith("# Period alignment")

    # No frontmatter, no scope, no fixtures - and it was still taken.
    assert "---" not in dropped.text().split("\n")[0]
    (entry,) = chain.record.entries(dropped.candidate_id)
    assert entry.stage == str(Stage.DROPPED) and entry.actor == DROPPER

    # The same bytes are the same candidate; both drops are on the record.
    again = chain.take(path, "someone else")
    assert again.candidate_id == dropped.candidate_id
    assert len(chain.record.entries(dropped.candidate_id)) == 2


def test_the_record_is_append_only_and_says_when_it_was_edited(
    chain: GovernanceChain, root: Path, record: GovernanceRecord
) -> None:
    """A file in a governance scope cannot have database triggers, so the chain of hashes
    is what makes the guarantee survive a text editor."""
    dropped = chain.take(drop_draft(root), DROPPER)
    chain.scan(dropped, "skill_conformance")
    record.verify()

    assert not [m for m in dir(record) if "delete" in m or "update" in m or "edit" in m]

    lines = record.path.read_text(encoding="utf-8").splitlines()
    edited = lines[0].replace(DROPPER, "somebody else")
    record.path.write_text("\n".join([edited, *lines[1:]]) + "\n", encoding="utf-8")
    with pytest.raises(RecordBroken, match="edited after it was written"):
        record.verify()

    record.path.write_text("\n".join(lines[1:]) + "\n", encoding="utf-8")
    with pytest.raises(RecordBroken):
        record.verify()


def test_a_candidates_position_is_read_from_the_record_not_from_an_object(
    chain: GovernanceChain, root: Path, record: GovernanceRecord
) -> None:
    """Nothing advances because an object in memory said it had. A second reader of the
    same file sees exactly the same stage."""
    dropped = chain.take(drop_draft(root), DROPPER)
    chain.scan(dropped, "skill_conformance")

    fresh = GovernanceRecord(record.root)
    candidate = fresh.candidate(dropped.candidate_id)
    assert candidate is not None
    assert candidate.stage is Stage.SCANNED
    assert candidate.has(Stage.DROPPED) and not candidate.has(Stage.ADAPTED)
    assert candidate.missing(Stage.SUBMITTED) == (
        Stage.ADAPTED, Stage.DRAFTED, Stage.EXERCISED, Stage.EVALUATED, Stage.REPLAYED,
    )
    assert candidate.source_hash == dropped.source_hash


def test_there_is_no_method_that_marks_a_stage_done(chain: GovernanceChain) -> None:
    """No force, no skip, no override. A stage's evidence comes from doing the stage."""
    for holder in (chain, chain.registry, chain.board, chain.shadow, chain.conformance):
        names = [n for n in dir(holder) if not n.startswith("_")]
        assert not [
            n for n in names if any(w in n.lower() for w in ("force", "skip", "override", "bypass"))
        ], holder


def _any_scorecard(chain: GovernanceChain, world: EvalWorld) -> Any:
    """A passing scorecard, for the cases where the eval stage is the one removed: the
    refusal must come from the missing gate rather than from a missing scorecard."""
    return chain.evals.evaluate(SKILL, world)
