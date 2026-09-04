"""Shadow Deployment: a new version runs beside the live one before it replaces it.

Fixtures tell you a skill works on the cases someone thought of. Shadow running tells you
what it does on the cases nobody thought of, at no risk to a client, which is the only
honest way to gain confidence before a version handles work on its own.

**The candidate output has no path to a deliverable.** It is recorded against the run and
in the governance record, and that is all. This module imports nothing from `deliver/` and
nothing from `ports.delivery`; a test walks the imports, because "it never reaches the
client model" is a claim about what the code can do rather than about what it does today.

**Promotion needs the threshold sustained, not one good day.** Three conditions, all of
them: the candidate has been observed on at least the stated number of distinct real runs;
the disagreement rate over every observation is inside the threshold; and the rate over
the most recent window of that size is inside it too. The last one is what "sustained"
buys - a candidate that was fine for eighteen runs and has disagreed on the last four does
not promote on its average.

What is compared is the candidate's output against the registered version's, both of them
masked skill outputs read by reference. Governance sees masked payloads or it sees nothing.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from evals.replay import json_diff
from governance.candidate import Stage
from governance.record import GovernanceRecord
from ops.blobs import ContentStore, put_json
from registries.errors import SHADOW_INSUFFICIENT, DiagnosticError, diagnose

__all__ = ["Observation", "Promotion", "ShadowDeployment", "ShadowRefused"]

NODE = "shadow_run"
STAGE = "shadow_observed"


class ShadowRefused(DiagnosticError):
    """The agreement threshold is not sustained. The candidate keeps shadowing."""


@dataclass(frozen=True)
class Observation:
    """One real run, seen twice: what the registered version produced and what the
    candidate would have."""

    run_id: str
    step_id: str
    skill: str
    version: str
    agreed: bool
    changes: tuple[str, ...] = ()
    candidate_ref: str = ""

    def line(self) -> str:
        return (
            f"{self.run_id}/{self.step_id}: "
            + ("agreed" if self.agreed else f"{len(self.changes)} difference(s)")
        )


@dataclass(frozen=True)
class Promotion:
    """Whether a candidate may be promoted, and the arithmetic behind the answer."""

    skill: str
    version: str
    runs: int
    required_runs: int
    disagreement: float
    recent_disagreement: float
    threshold: float
    promoted: bool = False

    @property
    def sustained(self) -> bool:
        return (
            self.runs >= self.required_runs
            and self.disagreement < self.threshold
            and self.recent_disagreement < self.threshold
        )

    def why_not(self) -> str:
        if self.runs < self.required_runs:
            return (
                f"{self.runs} of the {self.required_runs} real runs the gate asks for; "
                f"a threshold held over fewer runs than that is one good day"
            )
        if self.disagreement >= self.threshold:
            return (
                f"disagreement {self.disagreement:.1%} over {self.runs} runs, against a "
                f"threshold of {self.threshold:.1%}"
            )
        return (
            f"the overall rate holds at {self.disagreement:.1%} but the last "
            f"{self.required_runs} runs disagree at {self.recent_disagreement:.1%}, past "
            f"the {self.threshold:.1%} threshold"
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "skill": self.skill,
            "version": self.version,
            "runs": self.runs,
            "required_runs": self.required_runs,
            "disagreement": round(self.disagreement, 6),
            "recent_disagreement": round(self.recent_disagreement, 6),
            "threshold": self.threshold,
            "sustained": self.sustained,
            "promoted": self.promoted,
        }


class ShadowDeployment:
    def __init__(
        self,
        record: GovernanceRecord,
        blobs: ContentStore,
        *,
        threshold: float,
        required_runs: int,
    ) -> None:
        self.record = record
        self.blobs = blobs
        self.threshold = float(threshold)
        self.required_runs = int(required_runs)

    @classmethod
    def for_gate(cls, record: Any, blobs: Any, gate: Any) -> ShadowDeployment:
        """Built from the published gate, so the threshold and the number of runs are
        the practice's rather than a constant in this file. A gate with no run count is
        not a shadow gate: an offline metric is measured once, not sustained."""
        if not getattr(gate, "runs", 0):
            raise ValueError(
                f"{getattr(gate, 'metric', gate)!r} names no run count, so there is "
                f"nothing for a shadow period to be sustained over"
            )
        return cls(record, blobs, threshold=gate.threshold, required_runs=gate.runs)

    def __repr__(self) -> str:
        return (
            f"ShadowDeployment(threshold={self.threshold:.1%}, runs={self.required_runs})"
        )

    # -- observing

    def observe(
        self,
        candidate_id: str,
        *,
        run_id: str,
        step_id: str,
        skill: str,
        version: str,
        registered_output: Any,
        candidate_output: Any,
    ) -> Observation:
        """One run seen twice. The candidate's output is stored and recorded; it goes
        nowhere else."""
        changes = json_diff(registered_output, candidate_output)
        ref = put_json(self.blobs, candidate_output, name=f"shadow:{candidate_id}:{run_id}")
        observation = Observation(
            run_id=run_id,
            step_id=step_id,
            skill=skill,
            version=version,
            agreed=not changes,
            changes=tuple(c.line() for c in changes[:8]),
            candidate_ref=ref.content_hash,
        )
        self.record.append(
            candidate_id,
            STAGE,
            actor=NODE,
            ref=ref.content_hash,
            detail={
                "node": NODE,
                "run_id": run_id,
                "step_id": step_id,
                "skill": skill,
                "version": version,
                "agreed": observation.agreed,
                "changes": list(observation.changes),
            },
        )
        return observation

    def observations(self, candidate_id: str) -> tuple[Observation, ...]:
        return tuple(
            Observation(
                run_id=str((e.detail or {}).get("run_id", "")),
                step_id=str((e.detail or {}).get("step_id", "")),
                skill=str((e.detail or {}).get("skill", "")),
                version=str((e.detail or {}).get("version", "")),
                agreed=bool((e.detail or {}).get("agreed")),
                changes=tuple((e.detail or {}).get("changes") or ()),
                candidate_ref=e.ref,
            )
            for e in self.record.entries(candidate_id)
            if e.stage == STAGE
        )

    # -- promoting

    def promotion(self, candidate_id: str) -> Promotion:
        """The arithmetic, without deciding anything."""
        seen = self.observations(candidate_id)
        by_run = _last_per_run(seen)
        recent = by_run[-self.required_runs :] if self.required_runs else by_run
        return Promotion(
            skill=seen[0].skill if seen else "",
            version=seen[0].version if seen else "",
            runs=len(by_run),
            required_runs=self.required_runs,
            disagreement=_rate(by_run),
            recent_disagreement=_rate(recent),
            threshold=self.threshold,
        )

    def promote(self, candidate_id: str, *, promoted_by: str = NODE) -> Promotion:
        """Record the promotion, or refuse it. A refusal is not a failure of the
        candidate: it is the shadow period not being over."""
        found = self.promotion(candidate_id)
        if not found.sustained:
            raise ShadowRefused(
                diagnose(
                    SHADOW_INSUFFICIENT,
                    f"{found.skill}@{found.version} cannot be promoted: {found.why_not()}",
                    locator=candidate_id,
                    skill=f"{found.skill}@{found.version}",
                    expected=f"< {self.threshold:.1%} over {self.required_runs} runs",
                    found=f"{found.disagreement:.1%} over {found.runs} runs",
                )
            )
        promoted = Promotion(**{**found.__dict__, "promoted": True})
        self.record.append(
            candidate_id,
            Stage.SHADOWED,
            actor=promoted_by,
            ref=f"{found.disagreement:.4f}",
            detail={"node": NODE, **promoted.as_dict()},
        )
        return promoted


def _last_per_run(observations: Sequence[Observation]) -> tuple[Observation, ...]:
    """One result per real run, the latest. The gate counts runs, not steps: a skill
    invoked three times in one run is one run's worth of evidence."""
    found: dict[str, Observation] = {}
    for observation in observations:
        found[observation.run_id] = observation
    return tuple(found.values())


def _rate(observations: Sequence[Observation]) -> float:
    if not observations:
        return 1.0
    return sum(0 if o.agreed else 1 for o in observations) / len(observations)
