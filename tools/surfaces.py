"""The public surfaces of this system, collected from the live registries.

A change that alters one of these changes what every future run means. Some of those
changes are intended; the dangerous ones are the accidents - a contract edited in place,
an error code renamed, a tool's cap widened, a skill's review floor lowered, a template
rebound. Each of those passes every unit test in the repo, because each unit test asks
whether the code does what it says rather than whether what it says has changed.

So: collect the surfaces, hash them, and keep the snapshot in the repo. `tests/regression`
compares the live surfaces against `BUILD/surfaces.json` and fails on any difference,
naming it. Accepting a difference is a deliberate act with a reason attached:

    python tools/surfaces.py --check         # what changed, if anything
    python tools/surfaces.py --update        # accept it, after gate amend records why

Nothing here is hand-maintained. Every surface is read from the registry, the tree or the
compiler that owns it, so a surface that gains a member gains it here too - the failure
mode of a hand-written list is that it silently stops covering things, which is exactly
what happened to the import-boundary scan before P28 derived it.

**The plan hashes are the load-bearing entry.** A recipe's compiled `plan_hash` folds in
the graph structure, every skill version, every model pin, every output contract, the
scope resolution, the template binding, the taxonomy and the constraint and contract
registry versions. If any of those move, the hash moves. One line in the snapshot
therefore covers most of the ways a change can quietly alter what a run does.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "BUILD" / "surfaces.json"

# Run as a script from anywhere: `python tools/surfaces.py` puts tools/ on the path, not
# the repo. Every collector imports from the project, so the project has to be importable.
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools._environment import needs  # noqa: E402

# What this tool cannot run without. Called here, before the first project import, because
# that import is where a bare `python tools/surfaces.py` fails - and what it fails with is a
# traceback about somebody else's library rather than the line to type. P58 was written
# about that failure for `serve.py`; six more tools had it, and this is one of them.
needs("yaml", "pydantic", script="tools/surfaces.py")

# The scope and versions the sample plans are compiled against. Fixed here so the hash
# moves when the system moves rather than when the caller does.
SAMPLE_SCOPE = "valuation/esop/repeat"
SAMPLE_TAXONOMY = "coa-taxonomy@1.0.0"
SAMPLE_SNAPSHOT_ID = "surfaces_fixed_snapshot"
SAMPLE_ENGAGEMENT = "SURF-0000-00"


def digest(value: Any) -> str:
    body = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(body).hexdigest()[:32]


# ------------------------------------------------------------------ the surfaces


def contracts_surface() -> dict[str, Any]:
    """Every pinned contract, and a digest of each schema. An edit in place shows up as
    a changed digest under an unchanged id, which is the whole point: a contract is
    versioned, and a change is a new version beside the old one."""
    from registries.contracts import ContractRegistry

    registry = ContractRegistry.load()
    return {
        "version": registry.version,
        "ids": list(registry.ids()),
        "schemas": {key: digest(registry.get(key)) for key in registry.ids()},
    }


def diagnostics_surface() -> dict[str, Any]:
    """Every error code with its owner and whether it is retryable. A renamed code
    breaks every runbook and every saved query that mentions it."""
    from registries.errors import WHAT_NOW

    return {
        "codes": {code: owner for code, (owner, _what_now) in sorted(WHAT_NOW.items())},
        "families": sorted({code.split(".", 1)[0] for code in WHAT_NOW}),
    }


def constraints_surface() -> dict[str, Any]:
    """What the system is allowed to do: the tool namespace with its caps, the declared
    loops with their ceilings, and the four run ceilings."""
    from registries.constraints import ConstraintRegistry

    registry = ConstraintRegistry.load()
    return {
        "version": registry.version,
        "tools": {
            name: {
                "kind": spec.kind,
                "read_only": spec.read_only,
                "caps": dict(sorted(spec.caps.items())),
            }
            for name, spec in sorted(registry.tools.items())
        },
        "loops": {
            spec.name: {"scope": spec.scope, "max_iterations": spec.max_iterations}
            for spec in sorted(registry.loops.values(), key=lambda s: s.name)
        },
        "ceilings": registry.ceilings,
    }


def scopes_surface() -> dict[str, Any]:
    from registries.scopes import ScopeRegistry

    registry = ScopeRegistry.load()
    return {
        "version": registry.version,
        "layer_order": list(registry.layer_order),
        "paths": [str(path) for path in registry.combinations()],
    }


def skills_surface() -> dict[str, Any]:
    """Every skill and the four declarations the dispatcher enforces. A lowered review
    floor or a widened sensitivity class is the change this entry exists to catch."""
    from registries.skills import SkillTree

    tree = SkillTree.load()
    return {
        "skills": {
            skill.key: {
                "layer": skill.layer,
                "tier": skill.tier,
                "status": skill.status,
                "tools": list(skill.tools),
                "hitl": skill.hitl,
                "data_sensitivity": skill.data_sensitivity,
                "output_contract": skill.output_contract,
            }
            for skill in sorted(tree.all(), key=lambda s: s.key)
        },
        "overlays": [
            {"layer": o.layer, "target": o.target, "tightens": sorted(o.tightens)}
            for o in sorted(tree.overlays(), key=lambda o: (o.layer, o.target))
        ],
    }


def recipes_surface() -> dict[str, Any]:
    # `declared_in`, not `load_recipe`: a snapshot of what the recipe files declare is not
    # a request to run one, and asking the registration gate for it made the first step of
    # `verify.py` refuse on any clone that had never run the suite. See `graph.recipes`.
    from graph.recipes import RECIPES_DIR, declared_in, recipe_names

    found: dict[str, Any] = {}
    for name in recipe_names():
        recipe = declared_in(RECIPES_DIR / f"{name}.yaml")
        found[recipe.key] = {
            "steps": [s.id for s in recipe.steps],
            "skills": [s.skill for s in recipe.steps if s.skill],
            "loops": [f"{loop.loop}:{loop.head}<={loop.max_iterations}" for loop in recipe.loops],
            "required_types": list(recipe.required_types),
        }
    return found


def plans_surface() -> dict[str, Any]:
    """The load-bearing entry: each recipe compiled to a plan hash.

    The hash folds in structure, skill versions, model pins, output contracts, the scope
    resolution, the template binding, the taxonomy and both registry versions - so this
    one line moves whenever any of them does, and names which recipe changed.
    """
    from graph.compile import PlanContext, compile_recipe
    from graph.recipes import RECIPES_DIR, declared_in, recipe_names
    from graph.resolve import ScopeResolver

    scope = ScopeResolver().resolve(SAMPLE_SCOPE)
    context = PlanContext(
        engagement_id=SAMPLE_ENGAGEMENT,
        scope=scope,
        taxonomy_version=SAMPLE_TAXONOMY,
        precedent_snapshot=SAMPLE_SNAPSHOT_ID,
    )
    found: dict[str, Any] = {
        "scope": SAMPLE_SCOPE,
        "resolution_hash": scope.resolution_hash,
        "template": None
        if scope.template is None
        else f"{scope.template.file}@{scope.template.template_version}",
        "skills_resolved": list(scope.names),
    }
    for name in recipe_names():
        plan = compile_recipe(declared_in(RECIPES_DIR / f"{name}.yaml"), context)
        found[name] = {
            "plan_hash": plan.plan_hash,
            "order": list(plan.order),
            "loops": [region.id for region in plan.loops],
        }
    return found


def ports_surface() -> dict[str, Any]:
    import ports

    return {
        name: {
            "env_var": spec.env_var,
            "default": spec.default,
            "adapters": sorted(spec.adapters),
            "contracts": sorted(spec.contracts),
        }
        for name, spec in sorted(ports.PORTS.items())
    }


def record_surface() -> dict[str, Any]:
    """The run's own vocabulary: states, legal transitions, outcomes, step statuses, and
    the event types the console's trace reducer understands."""
    from ops.console.trace import EXPLICIT, PREFIX, SUFFIX
    from ops.models import OUTCOMES_FOR, TRANSITIONS, Outcome, RunState, StepStatus

    return {
        "run_states": [str(s) for s in RunState],
        "transitions": {
            str(state): sorted(str(t) for t in targets) for state, targets in TRANSITIONS.items()
        },
        "outcomes": [str(o) for o in Outcome],
        "outcomes_for": {
            str(state): sorted(str(o) for o in allowed)
            for state, allowed in OUTCOMES_FOR.items()
        },
        "step_statuses": [str(s) for s in StepStatus],
        "event_types": sorted(EXPLICIT),
        "event_suffixes": sorted(SUFFIX),
        "event_prefixes": sorted(PREFIX),
    }


def graph_surface() -> dict[str, Any]:
    from graph.architecture_assertions import ALL, load_graph

    graph = load_graph()
    return {
        "nodes": len(graph),
        "node_ids": sorted(graph[node]["id"] for node in graph.nodes_where()),
        "invariants": [f"{i.number}. {i.name}" for i in ALL],
    }


def evals_surface() -> dict[str, Any]:
    from evals.harness import EvalHarness

    harness = EvalHarness()
    return {
        skill: [
            {
                "metric": gate.metric,
                "op": gate.op,
                "threshold": gate.threshold,
                "runs": gate.runs,
                "measured_by": gate.measured_by,
            }
            for gate in harness.gates_for(skill)
        ]
        for skill in sorted(harness.spec["skills"])
    }


def criteria_surface() -> dict[str, Any]:
    from ops.scorecard import CURRENT_CRITERIA, load_criteria

    loaded = load_criteria(CURRENT_CRITERIA)
    return {
        "version": loaded.key,
        "verdicts": sorted(loaded.verdicts),
        "criteria": {
            criterion.id: {
                "bar": criterion.bar,
                "guards": sorted(criterion.guards),
                "resolved_by": sorted(criterion.resolved_by),
                "max_failed": criterion.max_failed,
            }
            for criterion in sorted(loaded.criteria, key=lambda c: c.id)
        },
    }


def foundations_surface(register: Any = None) -> dict[str, Any]:
    """What every prompt carries, by layer: the filenames and one digest over them.

    Not the content - a snapshot is a diff somebody reads, and a methodology file pasted
    into it would be unreadable and would put the firm\'s standards in two places. The
    digest is over the layer as a whole, in the order the Context Builder attaches it, so
    an edit, an addition, a deletion and a reorder each move exactly one line.
    """
    import hashlib

    from registries.methodology import MethodologyRegister, body_of

    register = register or MethodologyRegister()
    out: dict[str, Any] = {}
    for layer in register.layers():
        files = sorted((register.root / layer).glob("*.md"))
        files = [f for f in files if f.name.lower() != "readme.md"]
        rolling = hashlib.sha256()
        for path in files:
            rolling.update(path.name.encode("utf-8"))
            rolling.update(body_of(path))
        out[layer] = {
            "files": [f.name for f in files],
            "bytes": sum(len(body_of(f)) for f in files),
            "digest": f"sha256:{rolling.hexdigest()}",
        }
    return out


def governance_surface() -> dict[str, Any]:
    from governance.candidate import NODE_FOR, STAGES

    return {
        "stages": [str(s) for s in STAGES],
        "nodes": {str(stage): node for stage, node in NODE_FOR.items()},
    }


COLLECTORS = {
    "contracts": contracts_surface,
    "diagnostics": diagnostics_surface,
    "constraints": constraints_surface,
    "scopes": scopes_surface,
    "skills": skills_surface,
    "recipes": recipes_surface,
    "plans": plans_surface,
    "ports": ports_surface,
    "record": record_surface,
    "graph": graph_surface,
    "evals": evals_surface,
    "criteria": criteria_surface,
    "governance": governance_surface,
    "foundations": foundations_surface,
}


def collect() -> dict[str, Any]:
    """Every surface, as they are right now."""
    return {name: collector() for name, collector in COLLECTORS.items()}


def load() -> dict[str, Any]:
    if not SNAPSHOT.is_file():
        return {}
    return json.loads(SNAPSHOT.read_text(encoding="utf-8"))  # type: ignore[no-any-return]


def save(surfaces: dict[str, Any]) -> None:
    SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
    SNAPSHOT.write_text(json.dumps(surfaces, indent=1, sort_keys=True) + "\n", encoding="utf-8")


# ------------------------------------------------------------------ the diff


def differences(before: dict[str, Any], after: dict[str, Any], path: str = "") -> list[str]:
    """Every leaf that differs, named by its path. Readable rather than a JSON dump: the
    point of the snapshot is that somebody can see what changed at a glance and say
    whether they meant it."""
    found: list[str] = []
    if isinstance(before, dict) and isinstance(after, dict):
        for key in sorted(set(before) | set(after)):
            here = f"{path}.{key}" if path else key
            if key not in before:
                found.append(f"+ {here} = {_short(after[key])}")
            elif key not in after:
                found.append(f"- {here} (was {_short(before[key])})")
            else:
                found += differences(before[key], after[key], here)
    elif isinstance(before, list) and isinstance(after, list) and before != after:
        gained = [x for x in after if x not in before]
        lost = [x for x in before if x not in after]
        for item in gained:
            found.append(f"+ {path}: {_short(item)}")
        for item in lost:
            found.append(f"- {path}: {_short(item)}")
        if not gained and not lost:
            found.append(f"~ {path}: reordered")
    elif before != after:
        found.append(f"~ {path}: {_short(before)} -> {_short(after)}")
    return found


def _short(value: Any) -> str:
    text = json.dumps(value, sort_keys=True) if not isinstance(value, str) else value
    return text if len(text) <= 90 else text[:87] + "..."


def report(changes: list[str]) -> str:
    if not changes:
        return "  no public surface changed."
    lines = [f"  {len(changes)} surface change(s):"] + [f"    {c}" for c in changes[:60]]
    if len(changes) > 60:
        lines.append(f"    ... and {len(changes) - 60} more")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="report differences, change nothing")
    parser.add_argument("--update", action="store_true", help="accept the current surfaces")
    parser.add_argument("--print", action="store_true", help="print the surfaces as JSON")
    args = parser.parse_args(argv)

    current = collect()
    if args.print:
        print(json.dumps(current, indent=1, sort_keys=True))
        return 0

    recorded = load()
    changes = differences(recorded, current) if recorded else ["+ the snapshot does not exist yet"]

    if args.update:
        save(current)
        print(f"\n  surfaces recorded in {SNAPSHOT.relative_to(ROOT).as_posix()}")
        print(report(changes) if recorded else "  first snapshot.")
        print(
            "\n  This is a deliberate act. If any of the above was not intended, revert it;"
            "\n  if it was, `gate amend` is where the reason belongs.\n"
        )
        return 0

    print(f"\n  surfaces: {len(current)} groups against {SNAPSHOT.relative_to(ROOT).as_posix()}")
    print(report(changes))
    if changes:
        print(
            "\n  Accept them with `python tools/surfaces.py --update`, after recording why"
            "\n  with `gate amend`. A surface change nobody decided on is the thing this"
            "\n  snapshot exists to catch.\n"
        )
        return 1
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
