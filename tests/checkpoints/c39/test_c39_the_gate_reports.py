"""C39 - The gate reports a failure rather than becoming one.

P70 came from `gate.py` crashing while printing a failing check's output. A checkpoint
asks the whole path rather than the one function: a real check, really run, whose output
carries a character the console cannot encode, reported to a console that cannot encode it.

This matters more than its size suggests. `gate close` is the only thing permitted to mark
a phase done, and the moment it is most needed is the moment a check has failed. A gate
that dies there refuses correctly and explains nothing, and the traceback it leaves reads
as the gate being broken rather than the check having failed - which is the one wrong
conclusion that would send somebody looking in the wrong place.
"""

from __future__ import annotations

import io
import subprocess
import sys
from pathlib import Path

from tools import gate

ROOT = Path(__file__).resolve().parents[3]

# An em dash: valid UTF-8, and not in cp1252's repertoire.
CANNOT = "—"


def cp1252() -> io.TextIOWrapper:
    return io.TextIOWrapper(io.BytesIO(), encoding="cp1252", newline="")


def read(stream: io.TextIOWrapper) -> str:
    stream.flush()
    raw: io.BytesIO = stream.buffer  # type: ignore[assignment]
    return raw.getvalue().decode("cp1252")


def test_a_real_failing_check_is_reported_to_a_console_that_cannot_encode_it(
    monkeypatch, capsys
) -> None:
    """The whole path: `run` decodes the child's output, `run_checks` reports it, `say`
    puts it on a stream that cannot hold it."""
    stream = cp1252()
    monkeypatch.setattr(sys, "stdout", stream)
    monkeypatch.delenv(gate.REENTRY, raising=False)

    failing = (
        f'{sys.executable} -c "import sys; '
        f"sys.stdout.reconfigure(encoding=\'utf-8\'); "
        f'print(\'a finding {CANNOT} with an em dash\'); sys.exit(1)"'
    )
    ok = gate.run_checks([failing], verbose=False)

    assert ok is False, "a failing check must still be reported as failing"
    said = read(stream)
    assert "FAIL" in said
    assert "a finding" in said and "with an em dash" in said, said


def test_the_gate_survives_it_as_a_process(tmp_path: Path) -> None:
    """Not monkeypatched: a real interpreter, with the console encoding the crash happened
    on, running the gate's own status command."""
    env = {
        **dict(__import__("os").environ),
        "PYTHONIOENCODING": "cp1252",
        "PYTHONUTF8": "0",
    }
    proc = subprocess.run(  # noqa: S603
        [sys.executable, str(ROOT / "tools" / "gate.py"), "status"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="cp1252",
        errors="replace",
        env=env,
        timeout=120,
    )
    assert proc.returncode == 0, proc.stderr
    assert "Traceback" not in proc.stderr
    assert "UnicodeEncodeError" not in proc.stderr


def test_a_passing_check_is_unaffected(monkeypatch) -> None:
    """The reporting change must not have altered what a green run looks like."""
    stream = cp1252()
    monkeypatch.setattr(sys, "stdout", stream)
    monkeypatch.delenv(gate.REENTRY, raising=False)

    ok = gate.run_checks([f'{sys.executable} -c "pass"'], verbose=False)
    assert ok is True
    assert "PASS" in read(stream)


def test_every_phase_is_still_covered_by_a_checkpoint() -> None:
    """P01's structural rule, asked here because P70 is the phase this checkpoint covers
    and a phase past the last checkpoint is a phase nothing re-runs."""
    import json

    plan = json.loads((ROOT / "BUILD" / "plan.json").read_text(encoding="utf-8"))
    ids = [p["id"] for p in plan["phases"]]
    last = plan["checkpoints"][-1]
    assert last["after"] == ids[-1], "the newest phase sits past the last checkpoint"
