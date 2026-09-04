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
from pathlib import Path

import pytest

import ports
from tests.p28.test_portability import (
    ENV_PATTERN,
    MANAGED_SERVICE_IMPORTS,
    SHIPPED,
    shipped_files,
)

ROOT = Path(__file__).resolve().parents[3]


def test_a_clean_clone_plus_env_is_the_whole_setup() -> None:
    """What a colleague gets, and what they have to add: two values in .env."""
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
    assert set(ports.PORTS) == {"storage", "delivery", "secrets", "queue", "llm", "compute"}
    for port in ports.PORTS:
        assert ports.ready(port), port

    sources = [p.read_text(encoding="utf-8") for p in shipped_files()]
    for vendor in MANAGED_SERVICE_IMPORTS:
        assert not [s for s in sources if f"import {vendor}" in s], vendor

    # The firm's two connectors are declared and refuse. Selecting one before it is wired
    # is a refusal somebody can read, never a silent fallback to the local folder.
    from registries.errors import RegistryError

    for port, adapter in (("storage", "sharefile"), ("delivery", "box")):
        assert adapter in ports.adapters(port) and adapter not in ports.ready(port)
        with pytest.raises(RegistryError) as refused:
            ports.get_port(port, adapter)
        assert refused.value.diagnostic.owner == "config"


def test_the_build_state_says_this_is_v1() -> None:
    """The record, not anybody's memory: every phase closed, every checkpoint green, and
    what is still owed named as owed rather than quietly dropped."""
    plan = json.loads((ROOT / "BUILD" / "plan.json").read_text(encoding="utf-8"))
    phases = plan["phases"]
    assert len(phases) == 28
    open_phases = [p["id"] for p in phases if p["status"] != "done"]
    assert open_phases in ([], ["P28"]), open_phases

    checkpoints = plan["checkpoints"]
    assert len(checkpoints) == 10
    red = [c["id"] for c in checkpoints if c["status"] != "done" and c["id"] != "C10"]
    assert red == [], red

    # The four things that need the work machine are tasks on P28, not silence.
    p28 = next(p for p in phases if p["id"] == "P28")
    assert len([t for t in p28["tasks"] if t.startswith("On the work machine")]) == 4
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
    assert run.returncode == 0, run.stdout[-8000:] + run.stderr[-4000:]
    assert "passed" in run.stdout or "passed" in run.stderr
