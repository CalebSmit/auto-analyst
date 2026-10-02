"""One-shot scaffolder for P01. Generates per-phase files, package markers and
directory READMEs from BUILD/plan.json. Re-runnable: it never overwrites a
README that has been edited beyond its generated stub.
"""

from __future__ import annotations

import json
import sys
import textwrap
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from tools._environment import needs  # noqa: E402

# What this tool cannot run without. Called here, before the first project import, because
# that import is where a bare `python tools/bootstrap_scaffold.py` fails - and what it
# fails with is a traceback about somebody else's library rather than the line to
# type. P58 was written about that failure for `serve.py`; six more tools had it, and
# this is one of them.
needs("yaml", script="tools/bootstrap_scaffold.py")

import gate  # noqa: E402  - after the path insert, deliberately

ROOT = Path(__file__).resolve().parents[1]
PLAN = json.loads((ROOT / "BUILD" / "plan.json").read_text(encoding="utf-8"))

# directory -> (what belongs here, what does not)
DIRS = {
    "contracts": (
        "JSON Schemas for every shape the system passes around: the figure envelope, "
        "one output schema per skill, events, the run manifest, and engagement_profile. "
        "Each carries a version in its id.",
        "No Python. A schema that needs code to be understood is not a contract.",
    ),
    "constraints": (
        "constraints.yaml - the predicates the Policy Gate evaluates before an action runs.",
        "Not guard logic. Constraints decide whether an act is permitted; guards check a result.",
    ),
    "scope": (
        "scopes.yaml - practice groups, segments and dispositions, and nothing else.",
        "No skill content. The tree of scopes is separate from what resolves into it.",
    ),
    "skills": (
        "One directory per scope layer, each holding SKILL.md files and their reference "
        "documents. Deeper layers shadow shallower ones and may only tighten.",
        "Nothing writes here except the Skill Registry. A hand-edited skill has not been "
        "through fixtures, review or a shadow run.",
    ),
    "harness": (
        "What wraps a single step: context.py, policy.py, runtime.py, loops.py. "
        "This is the harness - there is no agent framework underneath it.",
        "No orchestration across steps. That is the graph's job.",
    ),
    "graph": (
        "The run as data: resolve.py, compile.py, execute.py, assertions.py. "
        "The compiler produces a typed DAG and a plan_hash; nothing executes uncompiled.",
        "No domain knowledge. The graph does not know what EBITDA is.",
    ),
    "privacy": (
        "mask.py, vault.py, unmask.py, payload_scan.py. All deterministic Python.",
        "No model call, ever. Re-identification is the one step where a plausible mistake "
        "is indistinguishable from correctness.",
    ),
    "tools": (
        "The deterministic tools a skill may propose calling, plus gate.py. "
        "All arithmetic in the system happens here.",
        "No model calls, and nothing importable from skills/ - tools are reached through "
        "the Guarded Tool Runtime by name, never by import.",
    ),
    "guards": (
        "Assertions about a result: schema, provenance, tieout, reconcile, unmask, "
        "numeric_lock. Every one emits on pass as well as on failure.",
        "No repair logic. A guard reports; the loop controller decides what happens next.",
    ),
    "ports": (
        "Six interfaces and their adapters: storage, delivery, secrets, queue, llm. "
        "Each port has a Protocol and a conformance suite every adapter must pass.",
        "Nothing outside this package imports a concrete adapter.",
    ),
    "ops": (
        "The record and the surfaces over it: events.py, run_store.py, manifest.py, console/.",
        "No business logic. If the console computes something, the scorecard should own it.",
    ),
    "fixtures": (
        "Golden fixtures per skill and per scope, plus one adversarial fixture per guard - "
        "built specifically to defeat the guard it targets.",
        "No client data, ever. Fixtures are masked, synthetic, or public - see fixtures/public/.",
    ),
    "tests": (
        "One directory per phase, plus checkpoints/. The gate runs tests/pNN for a phase "
        "and every prior directory again at a checkpoint.",
        "Nothing that needs network or a real API key outside an opt-in marker.",
    ),
    "BUILD": (
        "The build state system. plan.json is truth; PLAN.md and STATE.md are generated "
        "from it; LEDGER.md and AMENDMENTS.md are append-only.",
        "Never hand-edit PLAN.md or STATE.md. Use tools/gate.py.",
    ),
}

PKG = [
    "harness",
    "graph",
    "privacy",
    "tools",
    "guards",
    "ports",
    "ops",
    "ports/storage",
    "ports/delivery",
    "ports/secrets",
    "ports/queue",
    "ports/llm",
    "ops/console",
]


def write_if_absent(path: Path, text: str) -> bool:
    if path.exists():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return True


def main() -> None:
    made = 0

    # package markers
    for pkg in PKG:
        made += write_if_absent(ROOT / pkg / "__init__.py", '"""Automated Analyst."""\n')

    # directory READMEs
    for d, (yes, no) in DIRS.items():
        made += write_if_absent(
            ROOT / d / "README.md",
            f"# {d}/\n\n**What belongs here.** {yes}\n\n**What does not.** {no}\n",
        )

    # test directories
    for p in PLAN["phases"]:
        d = ROOT / "tests" / p["id"].lower()
        d.mkdir(parents=True, exist_ok=True)
        made += write_if_absent(d / "__init__.py", "")
    for c in PLAN["checkpoints"]:
        cp = ROOT / "tests" / "checkpoints" / f"c{int(c['id'][1:]):02d}"
        proves = chr(10).join(textwrap.wrap(c["proves"], 88))
        cp.mkdir(parents=True, exist_ok=True)
        made += write_if_absent(cp / "__init__.py", "")
        made += write_if_absent(
            cp / f"test_{c['id'].lower()}_integration.py",
            f'''"""{c["id"]} - {c["title"]}

Proves:
{proves}

This checkpoint is not written yet. It is written at the end of {c["after"]},
before that phase closes, so the integration test exists before it is needed.
"""

import pytest


@pytest.mark.skip(reason="written at the end of {c["after"]}")
def test_{c["id"].lower()}_integration():
    raise NotImplementedError
''',
        )
    made += write_if_absent(ROOT / "tests" / "__init__.py", "")
    made += write_if_absent(ROOT / "tests" / "checkpoints" / "__init__.py", "")

    # Per-phase files are generated by the gate, not here. They used to be written
    # once by this scaffolder and never again, which made them stale copies of the plan
    # the moment anything was amended - and CLAUDE.md sends every session to read one.
    gate.render_phase_files(PLAN)
    made += len(PLAN["phases"])

    print(f"scaffold: {made} files created")


if __name__ == "__main__":
    main()
