"""The Evaluation Harness: golden fixtures and acceptance thresholds. A skill passes, or
it does not ship.

`evaluate(skill)` runs the skill's metrics over its fixtures and scores each named gate
in `gates.yaml`. `coverage()` reports which skills and which guards have fixtures and,
just as loudly, which do not: fixtures only cover cases somebody thought of, and a
coverage report that hid the gaps would be the cheapest way to forget them.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from evals.metrics import METRICS
from evals.world import EvalWorld
from registries.skills import SkillTree

__all__ = ["Coverage", "EvalHarness", "GATES_FILE", "Gate", "Metric", "Scorecard"]

ROOT = Path(__file__).resolve().parents[1]
GATES_FILE = ROOT / "evals" / "gates.yaml"
GUARD_FIXTURES = ROOT / "fixtures" / "guards" / "fixtures.yaml"
GRAPH = ROOT / "graph" / "architecture.json"

# The fixture table names guards by their short key; the map names nodes.
GUARD_NODES = {
    "payload_scan": "payload_scan",
    "unmask_verify": "unmask_verify",
    "tieout": "tieout_gate",
    "numeric_lock": "numeric_lock",
    "provenance": "provenance_gate",
    "budget_governor": "budget_governor",
    "loop_controller": "loop_controller",
    "engagement_lock": "engagement_lock",
    "untrusted_boundary": "untrusted_boundary",
    "deliverable_qc": "deliverable_qc",
}


@dataclass(frozen=True)
class Gate:
    metric: str
    op: str
    threshold: float
    blueprint: str = ""
    measured_by: str = "eval_harness"
    note: str = ""

    def holds(self, value: float) -> bool:
        return {
            ">=": value >= self.threshold,
            "<=": value <= self.threshold,
            ">": value > self.threshold,
            "<": value < self.threshold,
            "==": value == self.threshold,
        }[self.op]


@dataclass(frozen=True)
class Metric:
    gate: Gate
    value: float | None
    passed: bool | None
    """None when the offline harness cannot measure it: owed, not failed and not passed."""

    def line(self) -> str:
        if self.value is None:
            return f"{self.gate.metric}: owed to {self.gate.measured_by} ({self.gate.note})"
        mark = "PASS" if self.passed else "FAIL"
        return f"{self.gate.metric}: {self.value:g} {self.gate.op} {self.gate.threshold:g}  {mark}"


@dataclass(frozen=True)
class Scorecard:
    skill: str
    version: str
    status: str
    fixtures: str
    metrics: tuple[Metric, ...]
    extras: dict[str, float] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        """Every measurable gate holds. An owed gate neither passes nor fails a skill
        here; the coverage report and the registration record both say it is owed."""
        return self.status == "shipped" and all(
            m.passed for m in self.metrics if m.passed is not None
        )

    @property
    def owed(self) -> tuple[Gate, ...]:
        return tuple(m.gate for m in self.metrics if m.value is None)

    @property
    def key(self) -> str:
        return f"{self.skill}@{self.version}"

    def as_dict(self) -> dict[str, Any]:
        return {
            "skill": self.skill,
            "version": self.version,
            "status": self.status,
            "fixtures": self.fixtures,
            "passed": self.passed,
            "metrics": [
                {
                    "metric": m.gate.metric,
                    "op": m.gate.op,
                    "threshold": m.gate.threshold,
                    "value": m.value,
                    "passed": m.passed,
                    "measured_by": m.gate.measured_by,
                }
                for m in self.metrics
            ],
            "extras": dict(self.extras),
        }

    def report(self) -> str:
        lines = [f"{self.key}  {'PASS' if self.passed else 'FAIL'}  fixtures: {self.fixtures}"]
        lines += [f"  {m.line()}" for m in self.metrics]
        if self.extras:
            lines.append("  " + ", ".join(f"{k}={v:g}" for k, v in sorted(self.extras.items())))
        return "\n".join(lines)


@dataclass(frozen=True)
class Coverage:
    skills_covered: tuple[str, ...]
    skills_not_covered: tuple[str, ...]
    """Skills in the tree with no fixtures: skeletons, and anything shipped without."""
    guards_covered: tuple[str, ...]
    guards_not_covered: tuple[str, ...]
    """Guard nodes on the map with no adversarial fixture aimed at them."""
    gates_owed: tuple[str, ...]
    """`skill: metric` pairs a gate declares but the offline harness cannot measure."""

    def report(self) -> str:
        def block(title: str, names: tuple[str, ...]) -> str:
            body = "\n".join(f"    {n}" for n in names) if names else "    (none)"
            return f"  {title} ({len(names)})\n{body}"

        return "\n".join(
            [
                "fixture coverage",
                block("skills with fixtures and a gate", self.skills_covered),
                block("skills NOT covered", self.skills_not_covered),
                block("guards with an adversarial fixture", self.guards_covered),
                block("guards NOT covered", self.guards_not_covered),
                block("gates owed to a later control", self.gates_owed),
            ]
        )


class EvalHarness:
    def __init__(self, gates_file: Path = GATES_FILE, tree: SkillTree | None = None) -> None:
        self.gates_file = gates_file
        self.spec = yaml.safe_load(gates_file.read_text(encoding="utf-8"))
        self.tree = tree or SkillTree.load()

    def gates_for(self, skill: str) -> tuple[Gate, ...]:
        entry = self.spec["skills"].get(skill) or {}
        return tuple(
            Gate(
                metric=str(g["metric"]),
                op=str(g["op"]),
                threshold=float(g["threshold"]),
                blueprint=str(g.get("blueprint", "")),
                measured_by=str(g.get("measured_by", "eval_harness")),
                note=str(g.get("note", "")),
            )
            for g in entry.get("gates", [])
        )

    def evaluate(self, skill: str, world: EvalWorld | None = None) -> Scorecard:
        """Run the skill's metrics over its fixtures and score every gate."""
        entry = self.spec["skills"].get(skill)
        if entry is None:
            raise KeyError(f"{skill!r} has no entry in {self.gates_file.name}")
        version = next((s.version for s in self.tree.all() if s.name == skill), "0.0.0")
        if entry.get("status") != "shipped" or skill not in METRICS:
            return Scorecard(
                skill=skill,
                version=version,
                status=str(entry.get("status", "not_shipped")),
                fixtures="",
                metrics=(),
            )
        own = world is None
        world = world or EvalWorld()
        try:
            values = METRICS[skill](world)
        finally:
            if own:
                world.close()
        metrics = []
        for gate in self.gates_for(skill):
            if gate.measured_by != "eval_harness":
                metrics.append(Metric(gate, None, None))
                continue
            value = values.get(gate.metric)
            if value is None:
                raise KeyError(f"{skill}: metrics report no {gate.metric!r}")
            metrics.append(Metric(gate, value, gate.holds(value)))
        named = {g.metric for g in self.gates_for(skill)}
        return Scorecard(
            skill=skill,
            version=version,
            status="shipped",
            fixtures=str(entry.get("fixtures", "")),
            metrics=tuple(metrics),
            extras={k: v for k, v in values.items() if k not in named},
        )

    def shipped(self) -> tuple[str, ...]:
        return tuple(
            name for name, entry in self.spec["skills"].items() if entry.get("status") == "shipped"
        )

    def coverage(self) -> Coverage:
        skills = tuple(sorted(s.name for s in self.tree.all()))
        covered = tuple(
            s
            for s in skills
            if s in self.shipped() and (ROOT / str(self.spec["skills"][s]["fixtures"])).is_dir()
        )
        guard_rows = yaml.safe_load(GUARD_FIXTURES.read_text(encoding="utf-8"))["fixtures"]
        fixture_guards = {GUARD_NODES.get(r["guard"], r["guard"]) for r in guard_rows}
        graph = json.loads(GRAPH.read_text(encoding="utf-8"))
        nodes = graph["nodes"] if isinstance(graph, dict) else graph
        guard_nodes = tuple(sorted(n["id"] for n in nodes if n.get("isGuard")))
        owed = tuple(
            f"{s}: {g.metric} ({g.measured_by})"
            for s in self.shipped()
            for g in self.gates_for(s)
            if g.measured_by != "eval_harness"
        )
        # The fixture table also aims at two controls the map draws outside the guard
        # band - the loop controller and the engagement lock. They count as covered;
        # what is reported as not covered is every guard node with no fixture at all.
        return Coverage(
            skills_covered=covered,
            skills_not_covered=tuple(s for s in skills if s not in covered),
            guards_covered=tuple(sorted(fixture_guards)),
            guards_not_covered=tuple(g for g in guard_nodes if g not in fixture_guards),
            gates_owed=owed,
        )
