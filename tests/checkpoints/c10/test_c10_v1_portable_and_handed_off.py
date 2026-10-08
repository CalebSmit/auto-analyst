"""Checkpoint C10 - v1: portable and handed off.

Proves: everything above, green, inside a container, from a clean clone plus .env.

The other nine checkpoints proved the system does what it says. This one proves it does
it somewhere else. Three claims, in the order somebody moving the repo meets them:

1. **A clean clone plus .env is the whole setup.** Every file the packet tells a newcomer
   to use is tracked, nothing that holds a credential or a client file is, and every
   environment variable the code reads is documented.
2. **Nothing is a fact about one machine.** No managed-service primitive anywhere, every
   deployment choice behind a port, and the two adapters that are contracts for the firm's
   connectors refuse in words rather than falling back to something local.
3. **The image builds and the suite passes inside it.** That last one needs a machine with
   an OCI runtime. On one without, this checkpoint says so rather than passing quietly -
   `pytest --container` runs it, and the session summary reports which way it went.

The regression half - every phase re-run together - is `gate checkpoint C10`, not this
file. This is the integration test that sits beside it.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

import ports
from tests.conftest import needs_a_checkout, what_failed_inside
from tests.p28.test_portability import (
    ENV_PATTERN,
    MANAGED_SERVICE_IMPORTS,
    SHIPPED,
    owed_on_the_work_machine,
    shipped_files,
)

ROOT = Path(__file__).resolve().parents[3]

sys.path.insert(0, str(ROOT))
from tools.gate import number_of  # noqa: E402


def test_a_clean_clone_plus_env_is_the_whole_setup() -> None:
    """What a colleague gets, and what they have to add: two values in .env."""
    needs_a_checkout("what a colleague gets")
    tracked = set(
        subprocess.run(  # noqa: S603
            ["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True
        ).stdout.split()
    )
    for needed in ("pyproject.toml", "uv.lock", ".env.example", "HANDOFF.md", "Dockerfile",
                   "compose.yaml", "tools/gate.py", "BUILD/plan.json"):
        assert needed in tracked, needed
    assert ".env" not in tracked
    assert not [p for p in tracked if p.startswith(("runs/", "vault/", "inbox/", "outbox/"))]

    # The two values that change on the work machine, and nothing else.
    example = (ROOT / ".env.example").read_text(encoding="utf-8")
    handoff = (ROOT / "HANDOFF.md").read_text(encoding="utf-8")
    assert "ANTHROPIC_API_KEY" in example and "AA_VAULT_KEY" in example
    assert "**`.env` changes, and nothing else.**" in handoff

    # Every variable the code reads is in the example, so there is no step nobody wrote
    # down. Derived from the source rather than trusted.
    read = {
        name
        for path in shipped_files()
        for name in ENV_PATTERN.findall(path.read_text(encoding="utf-8"))
    }
    assert read and not {name for name in read if name not in example}


def test_nothing_in_the_build_is_a_fact_about_one_machine() -> None:
    """Six ports, no vendor SDK, and the deployment target is an environment."""
    assert set(ports.PORTS) == {
        "storage", "delivery", "secrets", "queue", "llm", "compute", "identity", "ocr",
    }
    for port in ports.PORTS:
        assert ports.ready(port), port

    sources = [p.read_text(encoding="utf-8") for p in shipped_files()]
    for vendor in MANAGED_SERVICE_IMPORTS:
        assert not [s for s in sources if f"import {vendor}" in s], vendor

    # A connector that is declared and refuses: selecting one before it is wired is a
    # refusal somebody can read, never a silent fallback to the local folder.
    #
    # There used to be two. ShareFile stopped being one in P89 and Box on the storage side
    # in P87 - both are written now, though neither has reached a real service, which is
    # what P93 is for. Delivery's Box adapter is still a contract because nothing writes a
    # deliverable to Box yet, and the arrangement has to keep working for the one that is
    # left or it proves nothing about the ones that were.
    from registries.errors import RegistryError

    assert ports.contracts("delivery") == ("box",)
    assert ports.contracts("storage") == (), "both storage adapters are implemented now"
    for port, adapter in (("delivery", "box"),):
        assert adapter in ports.adapters(port) and adapter not in ports.ready(port)
        with pytest.raises(RegistryError) as refused:
            ports.get_port(port, adapter)
        assert refused.value.diagnostic.owner == "config"


def test_the_build_state_says_this_is_v1() -> None:
    """The record, not anybody's memory: every phase v1 covers is closed, every
    checkpoint up to this one is green, and what is still owed is named as owed.

    Scoped to what C10 covers rather than to the whole plan. v1 is a milestone, not the
    end of the plan - work agreed afterwards is added past P28 through `gate extend`, and
    a checkpoint that asserted the plan had exactly 28 phases would fail the first time
    the firm asked for something, which is not a thing going wrong.
    """
    plan = json.loads((ROOT / "BUILD" / "plan.json").read_text(encoding="utf-8"))
    # By number. `"P100" <= "P28"` is True, so from the hundredth phase on every
    # three-digit phase up to P299 silently counted as part of v1 - found by `verify.py`
    # the day P100 landed, and the seventh instance of the same comparison in this repo.
    covered = [p for p in plan["phases"] if number_of(p["id"]) <= 28]
    assert len(covered) == 28, "v1 is the first 28 phases"

    open_phases = [p["id"] for p in covered if p["status"] != "done"]
    assert open_phases in ([], ["P28"]), open_phases

    up_to_here = [c for c in plan["checkpoints"] if number_of(c["after"]) <= 28]
    assert len(up_to_here) == 10
    red = [c["id"] for c in up_to_here if c["status"] != "done" and c["id"] != "C10"]
    assert red == [], red

    # Anything past v1 is a later block, and does not make v1 unfinished.
    later = [p for p in plan["phases"] if number_of(p["id"]) > 28]
    assert all(p["block"] != covered[-1]["block"] for p in later), (
        "work added after v1 belongs to a block of its own"
    )

    # What needs the work machine is a task on P28 and a row in the register, not silence.
    p28 = next(p for p in covered if p["id"] == "P28")
    owed, rows = owed_on_the_work_machine()
    assert owed and len(owed) == len(rows), {"plan": owed, "register": rows}
    assert p28["gate"] == "human", "the last word is a person's"


def test_every_package_that_ships_is_covered_by_the_boundary_test() -> None:
    """The portability guarantee is worth what it scans."""
    from tests.p03.test_boundary import SCANNED

    assert sorted(set(SHIPPED) - {"ports"}) == sorted(SCANNED)


def test_the_image_builds_and_the_whole_suite_passes_inside_it(
    container_runtime: str, tmp_path: Path
) -> None:
    """The claim this checkpoint exists for, on a machine that can make it.

    The image is built from the clone rather than from the working tree, so what runs is
    what a colleague would get - and the suite runs on the image's own interpreter, with
    no host Python involved.
    """
    clone = tmp_path / "clone"
    subprocess.run(  # noqa: S603
        ["git", "clone", "--quiet", str(ROOT), str(clone)],
        capture_output=True, text=True, check=True,
    )
    build = subprocess.run(  # noqa: S603
        [container_runtime, "build", "-t", "automated-analyst:c10", "."],
        cwd=clone, capture_output=True, text=True, timeout=2400, check=False,
    )
    assert build.returncode == 0, build.stderr[-4000:]

    run = subprocess.run(  # noqa: S603
        [container_runtime, "run", "--rm", "automated-analyst:c10"],
        cwd=clone, capture_output=True, text=True, timeout=5400, check=False,
    )
    assert run.returncode == 0, what_failed_inside(run.stdout, run.stderr)
    assert "passed" in run.stdout or "passed" in run.stderr
