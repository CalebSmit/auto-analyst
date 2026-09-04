"""The board, the shadow run and the registry: who decides, what a promotion costs, and
the one write path into the live tree."""

from __future__ import annotations

import inspect
from pathlib import Path
from typing import Any

import pytest

from evals.registration import RegistrationRefused
from evals.world import EvalWorld
from governance import (
    GovernanceChain,
    ShadowRefused,
    reviewers_for,
)
from governance.candidate import Stage
from ops.drift import DriftReport, Flag
from tests.p27.conftest import (
    LAYER,
    OWNER,
    REQUIRED_RUNS,
    REVIEWER,
    SKILL,
    THRESHOLD,
    definition_of,
    shadow,
    walk,
)


def test_submission_is_an_act_and_the_board_is_routed_by_scope(
    chain: GovernanceChain, root: Path, eval_world: EvalWorld
) -> None:
    """Building and testing a skill never, by itself, ships anything."""
    walked = walk(chain, root, eval_world, stop_before=str(Stage.SUBMITTED))
    cid = walked["candidate_id"]
    assert chain.board.queue() == (), "nothing reached the board on its own"

    submission = chain.submit(
        cid,
        skill=SKILL,
        version="0.2.0",
        layer="valuation/esop/_segment",
        submitted_by=OWNER,
        transcript_ref=walked["transcript"].ref,
        scorecard_key=walked["scorecard"].key,
    )
    assert submission.submitted_by == OWNER
    (queued,) = chain.board.queue()
    assert queued["candidate_id"] == cid and queued["routed_to"] == "valuation/esop"
    assert chain.board.queue("firm") == (), "it went to the ESOP reviewers, not to whoever"

    with pytest.raises(ValueError, match="names the person"):
        chain.board.submit(cid, skill=SKILL, version="0.2.0", layer=LAYER,
                           submitted_by="  ", transcript_ref="")

    assert reviewers_for("_firm") == "firm"
    assert reviewers_for("valuation/_group") == "valuation"
    assert reviewers_for("valuation/esop/repeat") == "valuation/esop/repeat"


def test_a_decision_names_a_reviewer_and_a_reason_and_only_approval_advances(
    chain: GovernanceChain, root: Path, eval_world: EvalWorld
) -> None:
    walked = walk(chain, root, eval_world, stop_before=str(Stage.APPROVED))
    cid = walked["candidate_id"]

    with pytest.raises(ValueError, match="reason"):
        chain.board.decide(cid, decision="approved", reviewer=REVIEWER, reason=" ", layer=LAYER)
    with pytest.raises(ValueError, match="reviewer"):
        chain.board.decide(cid, decision="approved", reviewer="", reason="fine", layer=LAYER)
    with pytest.raises(ValueError, match="not one of"):
        chain.board.decide(cid, decision="looks ok", reviewer=REVIEWER, reason="x", layer=LAYER)

    returned = chain.board.decide(
        cid, decision="returned", reviewer=REVIEWER,
        reason="the escalation rule does not say what happens to the unmatched line",
        layer=LAYER,
    )
    assert not returned.approved
    assert not chain.candidate(cid).has(Stage.APPROVED), "returned is not approved"
    assert chain.board.queue() == (), "a returned submission leaves the queue"

    approved = chain.board.decide(
        cid, decision="approved", reviewer=REVIEWER, reason="reworked and clear", layer=LAYER
    )
    assert approved.approved and chain.candidate(cid).has(Stage.APPROVED)
    stages = [e.stage for e in chain.record.entries(cid)]
    assert "returned" in stages and str(Stage.APPROVED) in stages


def test_promotion_needs_the_threshold_sustained_not_one_good_day(
    chain: GovernanceChain, root: Path, eval_world: EvalWorld
) -> None:
    """The exit criterion. Three conditions and all of them: enough real runs, the rate
    over all of them, and the rate over the most recent window."""
    walked = walk(chain, root, eval_world, stop_before=str(Stage.SHADOWED))
    cid = walked["candidate_id"]

    # Too few runs, however well it did on them.
    shadow(chain, cid, runs=2, agree=2)
    with pytest.raises(ShadowRefused) as refused:
        chain.promote(cid, promoted_by=OWNER)
    d = refused.value.diagnostic
    assert d.code == "SKILL.SHADOW_INSUFFICIENT"
    assert f"2 of the {REQUIRED_RUNS} real runs" in d.detail
    assert "one good day" in d.detail
    assert not chain.candidate(cid).has(Stage.SHADOWED)

    # Enough runs, but it disagrees too often.
    shadow(chain, cid, runs=REQUIRED_RUNS, agree=2)
    promotion = chain.shadow.promotion(cid)
    assert promotion.runs == REQUIRED_RUNS and promotion.disagreement > THRESHOLD
    with pytest.raises(ShadowRefused, match="disagreement"):
        chain.promote(cid, promoted_by=OWNER)

    # Agreeing on every run: promoted, with the arithmetic on the record.
    shadow(chain, cid, runs=REQUIRED_RUNS, agree=REQUIRED_RUNS)
    promoted = chain.promote(cid, promoted_by=OWNER)
    assert promoted.promoted and promoted.sustained
    assert promoted.disagreement == 0.0 and promoted.runs == REQUIRED_RUNS
    entry = [e for e in chain.record.entries(cid) if e.stage == str(Stage.SHADOWED)][-1]
    assert entry.detail["threshold"] == THRESHOLD
    assert entry.detail["required_runs"] == REQUIRED_RUNS


def test_a_good_average_over_a_bad_recent_window_does_not_promote(
    chain: GovernanceChain, root: Path, eval_world: EvalWorld
) -> None:
    """A candidate that was fine for a while and has disagreed since does not promote on
    its average."""
    walked = walk(chain, root, eval_world, stop_before=str(Stage.SHADOWED))
    cid = walked["candidate_id"]

    for n in range(20):
        agreed = n != 19
        registered = {"unmatched": []}
        chain.shadow.observe(
            cid,
            run_id=f"run_{n:03d}",
            step_id="timing",
            skill=SKILL,
            version="0.2.0",
            registered_output=registered,
            candidate_output=registered if agreed else {"unmatched": ["rent"]},
        )
    promotion = chain.shadow.promotion(cid)
    assert promotion.runs == 20
    assert promotion.disagreement == pytest.approx(0.05), "inside the threshold on average"
    assert promotion.recent_disagreement == pytest.approx(0.2), "and outside it lately"
    with pytest.raises(ShadowRefused) as refused:
        chain.promote(cid, promoted_by=OWNER)
    detail = refused.value.diagnostic.detail
    assert "the overall rate holds at 5.0%" in detail
    assert "the last 5 runs disagree at 20.0%" in detail


def test_the_candidate_output_has_no_path_to_a_deliverable(chain: GovernanceChain) -> None:
    """Recorded against the run and in the governance record, and nowhere else."""
    import governance.shadow as module

    imports = [
        line
        for line in inspect.getsource(module).splitlines()
        if line.startswith(("import ", "from "))
    ]
    for banned in ("deliver", "ports.delivery", "release"):
        assert not [line for line in imports if banned in line], banned
    assert not [n for n in dir(chain.shadow) if "deliver" in n or "release" in n]


def test_a_sustained_drift_flag_opens_a_re_review_once(chain: GovernanceChain) -> None:
    """The drift monitor's cross-run loop lands here. It writes nothing itself; this is
    where a flag becomes something a person has to look at."""
    flag = Flag(
        skill=SKILL,
        scope="valuation/esop/repeat",
        metric="override_rate",
        recent=0.31,
        baseline=0.12,
        runs=4,
        direction="up",
    )
    report = DriftReport(series=(), flags=(flag,), recent=5, baseline=10, rise=0.05, sustained=3)

    (opened,) = chain.board.reopen_from_drift(report)
    assert opened.skill == SKILL and opened.metric == "override_rate"
    (row,) = chain.board.re_reviews()
    assert row["loop"] == "drift_re_review"
    assert row["routed_to"] == "valuation/esop/repeat"
    assert row["recent"] == 0.31 and row["baseline"] == 0.12
    assert "override_rate up" in row["detail"]

    # Still true next week is the same episode, not a second review.
    assert chain.board.reopen_from_drift(report) == ()
    assert len(chain.board.re_reviews()) == 1

    other = DriftReport(
        series=(),
        flags=(Flag(SKILL, "valuation/esop/repeat", "guard_failure_rate", 0.2, 0.05, 3, "up"),),
        recent=5, baseline=10, rise=0.05, sustained=3,
    )
    assert len(chain.board.reopen_from_drift(other)) == 1, "a different metric is its own episode"


def test_the_registry_is_the_only_writer_into_the_skills_tree() -> None:
    """The one edge from governance back into the live system, and it carries a
    definition. Every other module that writes a file writes somewhere else."""
    import ast
    from pathlib import Path as P

    root = P(__file__).resolve().parents[2]
    packages = [
        p
        for p in root.iterdir()
        if p.is_dir()
        and (p / "__init__.py").exists()
        and p.name not in {"tests", "skills", ".venv"}
    ]
    writers: list[str] = []
    for package in packages:
        for module in package.rglob("*.py"):
            source = module.read_text(encoding="utf-8")
            if "skills_dir" not in source and "SKILLS_DIR" not in source:
                continue
            for node in ast.walk(ast.parse(source)):
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr in {"write_text", "write_bytes"}
                ):
                    writers.append(str(module.relative_to(root)).replace("\\\\", "/"))
    assert {w.replace("\\", "/") for w in writers} == {"governance/registry.py"}, writers


def test_nothing_reaches_the_tree_without_fixtures_and_a_shadow_run(
    chain: GovernanceChain, root: Path, eval_world: EvalWorld, skills_dir: Path
) -> None:
    """The exit criterion, from the other end: what is in the tree, and what is behind it."""
    walked = walk(chain, root, eval_world)
    published = chain.register(
        walked["candidate_id"],
        walked["scorecard"],
        definition=definition_of(walked),
        layer=LAYER,
        approved_by=OWNER,
    )
    assert chain.registry.unregistered() == (), "every skill in this tree has a row behind it"
    assert published.registered.gates, "the row names the gates it cleared"
    assert published.registered.scorecard_hash.startswith("sha256:")
    assert published.registered.approved_by == OWNER

    # A file put into the tree by hand is visible as unregistered rather than live by
    # virtue of existing.
    folder = skills_dir / LAYER / "smuggled"
    folder.mkdir(parents=True)
    (folder / "SKILL.md").write_text(
        (skills_dir / LAYER / SKILL / "SKILL.md").read_text(encoding="utf-8")
        .replace(f"name: {SKILL}", "name: smuggled"),
        encoding="utf-8",
    )
    assert chain.registry.unregistered() == ("smuggled@0.2.0",)


def test_a_version_below_its_gate_or_already_registered_is_refused(
    chain: GovernanceChain, root: Path, eval_world: EvalWorld
) -> None:
    """Whoever approves it. Approval is a decision; registration is a deployment."""
    walked = walk(chain, root, eval_world)
    cid = walked["candidate_id"]
    scorecard = walked["scorecard"]

    from dataclasses import replace

    failing = replace(
        scorecard,
        metrics=tuple(replace(m, passed=False) if m.value is not None else m
                      for m in scorecard.metrics),
    )
    with pytest.raises(RegistrationRefused) as refused:
        chain.register(cid, failing, definition=definition_of(walked), layer=LAYER,
                       approved_by=OWNER)
    assert refused.value.diagnostic.code == "SKILL.BELOW_GATE"
    assert "do not lower the gate" in refused.value.diagnostic.what_now
    assert chain.registry.registered() == ()

    chain.register(cid, scorecard, definition=definition_of(walked), layer=LAYER,
                   approved_by=OWNER)
    with pytest.raises(RegistrationRefused, match="already registered"):
        chain.register(cid, scorecard, definition=definition_of(walked), layer=LAYER,
                       approved_by=OWNER)
    assert len(chain.registry.registered()) == 1


def test_the_sandbox_tree_is_not_the_live_tree(
    chain: GovernanceChain, root: Path, eval_world: EvalWorld, skills_dir: Path
) -> None:
    """A draft is written where nothing reads it, and it parses as a skill there."""
    walked = walk(chain, root, eval_world, stop_before=str(Stage.EXERCISED))
    path = walked["path"]
    assert path.is_file()
    assert skills_dir not in path.parents, "the sandbox is not the live tree"
    assert "_sandbox" in str(path)
    assert chain.registry.tree().all() == (), "nothing is live yet"

    tree = chain.sandbox.tree()
    assert {s.name for s in tree.all()} == {SKILL}
    tree.self_check()


def test_the_transcript_is_what_a_reviewer_reads(
    chain: GovernanceChain, root: Path, eval_world: EvalWorld, dispatches: Any
) -> None:
    """Every case, what the guards said, what it cost - through the production dispatcher
    rather than a second code path."""
    walked = walk(chain, root, eval_world, stop_before=str(Stage.EVALUATED))
    transcript = walked["transcript"]
    assert transcript.passed and len(transcript.entries) == 3
    assert dispatches.seen == ["annual_drift", "rename", "one_unmatched"]
    assert "annual_drift" in transcript.report()
    assert chain.candidate(walked["candidate_id"]).has(Stage.EXERCISED)


def test_a_case_a_guard_refuses_is_recorded_rather_than_raised(
    chain: GovernanceChain, root: Path, eval_world: EvalWorld, dispatches: Any
) -> None:
    """A harness that stops at the first failure tells a reviewer about one case."""
    from guards import GuardResult
    from guards.schema import SchemaGate  # noqa: F401 - the real gate's result shape

    dispatches.refuse = {"rename": _guard_failed()}
    walked = walk(chain, root, eval_world, stop_before=str(Stage.EVALUATED))
    transcript = walked["transcript"]

    assert not transcript.passed
    assert [e.case for e in transcript.entries] == ["annual_drift", "rename", "one_unmatched"]
    (failed,) = [e for e in transcript.entries if not e.passed]
    assert "provenance" in failed.refusal or "provenance" in " ".join(failed.guards)
    assert isinstance(GuardResult, type)


def _guard_failed() -> Exception:
    from guards import GuardFailed, GuardResult

    return GuardFailed(
        GuardResult(
            guard="provenance",
            passed=False,
            checked=3,
            failed=1,
            code="SKILL.NO_PROVENANCE",
            reasons=("one figure cites no source",),
        ),
        locator="rename",
    )
