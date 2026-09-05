#!/usr/bin/env python3
"""The build gate.

The only thing permitted to mark a phase done. `BUILD/plan.json` is the source of
truth; `BUILD/PLAN.md` and `BUILD/STATE.md` are rendered from it and must never be
hand-edited, because a hand edit is how a plan and its real state start to disagree.

    python tools/gate.py status
    python tools/gate.py check P07
    python tools/gate.py close P07 [--signoff "Caleb: reviewed 40 items"]
    python tools/gate.py checkpoint C3
    python tools/gate.py extend "reason" --title "..." --block "..." --intent "..." \
        --exit "..." --check "..."
    python tools/gate.py amend P18 "reason" --set-title "..." --add-task "..." --drop-task "..."
    python tools/gate.py ledger "what was tried" --cause "why it failed" --rule "what to do instead"
    python tools/gate.py render
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "BUILD"
PLAN_JSON = BUILD / "plan.json"
PLAN_MD = BUILD / "PLAN.md"
STATE_MD = BUILD / "STATE.md"
LEDGER_MD = BUILD / "LEDGER.md"
AMEND_MD = BUILD / "AMENDMENTS.md"
PHASES_DIR = BUILD / "phases"

OK = "PASS"
NO = "FAIL"

# A checkpoint covers at most this many phases. Small on purpose: a checkpoint that spans
# half a block cannot tell you which phase stopped agreeing with the others, which is the
# only question it exists to answer.
MAX_CHECKPOINT_SPAN = 4


# ---------------------------------------------------------------- plan i/o


def load() -> dict[str, Any]:
    if not PLAN_JSON.exists():
        sys.exit(f"no plan at {PLAN_JSON}. This repo is not bootstrapped.")
    plan: dict[str, Any] = json.loads(PLAN_JSON.read_text(encoding="utf-8"))
    return plan


def save(plan: dict[str, Any]) -> None:
    """Write the plan and regenerate everything derived from it.

    Everything, including the phase files. They were left out once, which meant an amend
    updated PLAN.md and STATE.md and left `BUILD/phases/` describing the plan as it had
    been - and CLAUDE.md sends every session to read exactly those files.
    """
    PLAN_JSON.write_text(json.dumps(plan, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    render(plan)
    render_phase_files(plan)


def today() -> str:
    return dt.date.today().isoformat()


def find_phase(plan: dict[str, Any], pid: str) -> dict[str, Any]:
    pid = pid.upper()
    for p in plan["phases"]:
        if p["id"] == pid:
            found: dict[str, Any] = p
            return found
    sys.exit(f"unknown phase {pid}")


def find_checkpoint(plan: dict[str, Any], cid: str) -> dict[str, Any]:
    cid = cid.upper()
    for c in plan["checkpoints"]:
        if c["id"] == cid:
            found: dict[str, Any] = c
            return found
    sys.exit(f"unknown checkpoint {cid}")


def phases_before(plan: dict[str, Any], cid: str) -> list[dict[str, Any]]:
    """Every phase that must be green before this checkpoint."""
    c = find_checkpoint(plan, cid)
    return [p for p in plan["phases"] if p["id"] <= c["after"]]


# ---------------------------------------------------------------- running


UV_PREFIX = "python -m uv run "


def resolve(cmd: str) -> str:
    """Point `python -m uv run` at an interpreter that has uv.

    The checks are written for a person to type, and typed in a shell they work. Run from
    inside a uv-managed environment - `uv run python tools/gate.py check P28` - PATH
    starts with the project venv, which has no uv, and every check fails with "No module
    named uv". A red phase that is actually green is the worst answer this tool can give,
    so the prefix is resolved rather than trusted.
    """
    if not cmd.startswith(UV_PREFIX):
        return cmd
    exe = shutil.which("uv")
    if exe is None:
        return cmd
    return f'"{exe}" run ' + cmd[len(UV_PREFIX) :]


def run(cmd: str) -> tuple[bool, str]:
    proc = subprocess.run(
        resolve(cmd),
        shell=True,
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    return proc.returncode == 0, out.strip()


def run_checks(checks: list[str], verbose: bool) -> bool:
    allok = True
    for cmd in checks:
        ok, out = run(cmd)
        print(f"  [{OK if ok else NO}] {cmd}")
        if not ok or verbose:
            for line in out.splitlines()[-25:]:
                print(f"         {line}")
        allok = allok and ok
    return allok


# ---------------------------------------------------------------- commands


def cmd_status(plan: dict[str, Any], _args: argparse.Namespace) -> int:
    done = [p for p in plan["phases"] if p["status"] == "done"]
    cur = next((p for p in plan["phases"] if p["status"] != "done"), None)
    last_cp = [c for c in plan["checkpoints"] if c["status"] == "done"]

    print(f"\n  {plan['project']}")
    print(
        f"  {len(done)}/{len(plan['phases'])} phases closed"
        f" | last green checkpoint: {last_cp[-1]['id'] if last_cp else 'none'}"
    )

    if cur is None:
        print("\n  Every phase is closed. Run the final checkpoint.\n")
        return 0

    blocking = blocking_checkpoint(plan, cur["id"])
    print(f"\n  CURRENT   {cur['id']}  {cur['title']}")
    print(f"            block {cur['block']} | gate: {cur['gate']}")
    print(f"            {cur['intent']}")
    if blocking:
        print(f"\n  BLOCKED   {blocking['id']} must pass first: {blocking['title']}")
        print(f"            python tools/gate.py checkpoint {blocking['id']}")
        print()
        return 0

    print(f"\n  NEXT      see BUILD/phases/{cur['id']}.md")
    for t in cur["tasks"][:3]:
        print(f"            - {t}")
    if len(cur["tasks"]) > 3:
        print(f"            ... {len(cur['tasks']) - 3} more in the phase file")
    print(f"\n  VERIFY    python tools/gate.py check {cur['id']}")
    print(f"  CLOSE     python tools/gate.py close {cur['id']}")
    print()
    return 0


def blocking_checkpoint(plan: dict[str, Any], pid: str) -> dict[str, Any] | None:
    """A checkpoint sitting between the last closed phase and this one, still red."""
    for c in plan["checkpoints"]:
        if c["status"] != "done" and c["after"] < pid:
            unmet = [p for p in phases_before(plan, c["id"]) if p["status"] != "done"]
            if not unmet:
                blocking: dict[str, Any] = c
                return blocking
    return None


def cmd_check(plan: dict[str, Any], args: argparse.Namespace) -> int:
    p = find_phase(plan, args.id)
    print(f"\n  {p['id']}  {p['title']}   (gate: {p['gate']})")
    print("  exit criteria:")
    for e in p["exit"]:
        print(f"    - {e}")
    print(f"\n  running {len(p['checks'])} check(s):")
    ok = run_checks(p["checks"], args.verbose)
    print(f"\n  {'PASS' if ok else 'FAIL'} - {p['id']}\n")
    return 0 if ok else 1


def cmd_close(plan: dict[str, Any], args: argparse.Namespace) -> int:
    p = find_phase(plan, args.id)

    if p["status"] == "done":
        print(f"\n  {p['id']} is already closed ({p['closed']}).\n")
        return 0

    earlier = [q for q in plan["phases"] if q["id"] < p["id"] and q["status"] != "done"]
    if earlier:
        print(f"\n  REFUSED - {p['id']} cannot close while {earlier[0]['id']} is open.")
        print("            Phases close in order. That is the point of the order.\n")
        return 1

    blocking = blocking_checkpoint(plan, p["id"])
    if blocking:
        print(f"\n  REFUSED - checkpoint {blocking['id']} has not passed.\n")
        return 1

    print(f"\n  {p['id']}  {p['title']}")
    ok = run_checks(p["checks"], args.verbose)
    if not ok:
        print(f"\n  REFUSED - {p['id']} did not pass its own checks. Nothing was written.\n")
        return 1

    if p["gate"] == "human" and not args.signoff:
        print(f"\n  REFUSED - {p['id']} is a judgment phase. Tests passing is necessary,")
        print('            not sufficient. Re-run with --signoff "who: what you checked".')
        print(f"            What needs a human: {p.get('human_check', 'see the phase file')}\n")
        return 1

    p["status"] = "done"
    p["closed"] = today()
    if args.signoff:
        p["signoff"] = args.signoff
    save(plan)
    print(
        f"\n  CLOSED  {p['id']} on {p['closed']}"
        f"{' - signed off: ' + args.signoff if args.signoff else ''}\n"
    )
    return 0


def cmd_checkpoint(plan: dict[str, Any], args: argparse.Namespace) -> int:
    c = find_checkpoint(plan, args.id)
    covered = phases_before(plan, c["id"])
    unmet = [p["id"] for p in covered if p["status"] != "done"]

    print(f"\n  {c['id']}  {c['title']}")
    print(f"  proves: {c['proves']}")
    print(f"  covers: {covered[0]['id']}..{c['after']}  ({len(covered)} phases)")

    if unmet:
        print(f"\n  REFUSED - these phases are not closed: {', '.join(unmet)}\n")
        return 1

    print("\n  1. every prior phase, re-run together:")
    regression = [f"python -m uv run pytest tests/{p['id'].lower()} -q" for p in covered]
    ok1 = run_checks(regression, args.verbose)

    print("\n  2. the integration test for this checkpoint:")
    ok2 = run_checks(c["checks"], args.verbose)

    ok = ok1 and ok2
    if ok:
        c["status"] = "done"
        c["closed"] = today()
        save(plan)
        print(f"\n  GREEN   {c['id']} - everything built so far still works together.\n")
        return 0

    print(f"\n  RED     {c['id']} - the next phase is blocked until this passes.")
    print("          A red checkpoint after a green phase means the phases disagree")
    print("          with each other, which is the failure this exists to catch.\n")
    return 1


def amend_checkpoint(plan: dict[str, Any], args: argparse.Namespace) -> int:
    """Amend a checkpoint. Same rule as a phase: the reason travels with the change."""
    c = find_checkpoint(plan, args.id)
    changes = []

    if args.set_title:
        changes.append(f"title: {c['title']!r} -> {args.set_title!r}")
        c["title"] = args.set_title
    if args.set_proves:
        changes.append(f"proves: {c['proves']!r} -> {args.set_proves!r}")
        c["proves"] = args.set_proves
    if getattr(args, "set_after", None):
        target = args.set_after.upper()
        if target not in {p["id"] for p in plan["phases"]}:
            sys.exit(f"unknown phase {target}")
        changes.append(f"after: {c['after']} -> {target}")
        c["after"] = target
        plan["checkpoints"].sort(key=lambda x: x["after"])
    if args.add_check:
        for check in args.add_check:
            c["checks"].append(check)
            changes.append(f"check added: {check}")
    if args.reopen:
        changes.append(f"status: {c['status']} -> open")
        c["status"] = "open"
        c.pop("passed", None)

    rejected = [
        f for f in ("add_task", "add_exit", "set_gate", "set_blueprint") if getattr(args, f, None)
    ]
    if rejected:
        sys.exit(f"a checkpoint has no {', '.join(rejected)} - it has proves and checks.")
    if not changes:
        sys.exit("amend needs at least one change flag. See --help.")

    entry = [f"\n## {today()} - {c['id']} {c['title']}", f"\n**Why:** {args.reason}\n"]
    entry += [f"- {ch}" for ch in changes]
    with AMEND_MD.open("a", encoding="utf-8") as f:
        f.write("\n".join(entry) + "\n")

    save(plan)
    print(f"\n  amended {c['id']} - {len(changes)} change(s), reason recorded.\n")
    return 0


def next_phase_id(plan: dict[str, Any]) -> str:
    """The id after the last one. Phases are ordered and close in order, so a new phase
    goes at the end or it is not a phase, it is a rewrite of the sequence."""
    last = max(int(p["id"][1:]) for p in plan["phases"])
    return f"P{last + 1:02d}"


def cmd_extend(plan: dict[str, Any], args: argparse.Namespace) -> int:
    """Add a phase to the end of the plan, recording why.

    Deliberately not a flag on `amend`: amend changes a phase that exists, this makes one.
    """
    if not args.exit:
        sys.exit(
            "a phase needs at least one exit criterion. A phase that can close on "
            "nothing is a phase that means nothing."
        )
    if not args.check:
        sys.exit(
            "a phase needs at least one check. `gate close` runs the checks; with none, "
            "closing would be an assertion rather than a test."
        )

    pid = next_phase_id(plan)
    phase: dict[str, Any] = {
        "id": pid,
        "title": args.title,
        "block": args.block,
        "gate": args.gate,
        "status": "open",
        "intent": args.intent,
        "builds": list(args.builds or []),
        "tasks": list(args.task or []),
        "exit": list(args.exit),
        "checks": list(args.check),
        "notes": args.notes or "",
    }
    if args.gate == "human":
        if not args.human_check:
            sys.exit("a judgment phase says what a person is confirming: --human-check")
        phase["human_check"] = args.human_check
    plan["phases"].append(phase)

    entry = [
        f"\n## {today()} - {pid} {args.title}",
        f"\n**Why:** {args.reason}\n",
        f"- phase added: {pid} {args.title} ({args.block}, gate: {args.gate})",
        *[f"- exit criterion: {e}" for e in args.exit],
    ]
    with AMEND_MD.open("a", encoding="utf-8") as f:
        f.write("\n".join(entry) + "\n")

    save(plan)
    print(f"\n  added {pid}  {args.title}")
    print(f"  block {args.block} | gate: {args.gate} | {len(args.exit)} exit criteria")
    print("  reason recorded in AMENDMENTS.md.")

    # Every block of work ends in a checkpoint: phases that each pass alone can still
    # disagree with each other, which is the whole reason checkpoints exist. Warned
    # rather than refused, because the phases of a block are added one at a time and
    # only the last of them knows it is the last.
    uncovered = phases_after_last_checkpoint(plan)
    if uncovered:
        print(
            f"\n  OWED - {', '.join(uncovered)} sit past the last checkpoint."
            f"\n         Close the block with `gate seal` when it is finished."
        )
    print()
    return 0


def cmd_seal(plan: dict[str, Any], args: argparse.Namespace) -> int:
    """Close the last block with a checkpoint.

    Every block of work ends in one: phases that each pass alone can still disagree with
    each other, and a checkpoint re-runs them together plus an integration test of its
    own. Separate from `extend` because a phase is rarely known to be the last of its
    block at the moment it is added.
    """
    uncovered = phases_after_last_checkpoint(plan)
    if not uncovered:
        sys.exit("every phase is already covered by a checkpoint; there is nothing to seal.")

    after = (args.after or plan["phases"][-1]["id"]).upper()
    if after not in uncovered:
        sys.exit(
            f"{after} is not one of the phases waiting for a checkpoint "
            f"({', '.join(uncovered)}). A checkpoint goes after the last phase of the "
            f"block it covers."
        )
    covered = uncovered[: uncovered.index(after) + 1]
    if len(covered) > MAX_CHECKPOINT_SPAN:
        sys.exit(
            f"that checkpoint would cover {len(covered)} phases ({', '.join(covered)}), "
            f"and a checkpoint covers at most {MAX_CHECKPOINT_SPAN}. One that spans half "
            f"a block cannot tell you which phase stopped agreeing with the others - "
            f"seal the block in two."
        )
    cid = next_checkpoint_id(plan)
    checkpoint = {
        "id": cid,
        "title": args.title,
        "after": after,
        "status": "open",
        "proves": args.proves,
        "checks": [f"python -m uv run pytest tests/checkpoints/c{int(cid[1:]):02d} -q"],
    }
    plan["checkpoints"].append(checkpoint)
    plan["checkpoints"].sort(key=lambda c: c["after"])

    entry = [
        f"\n## {today()} - {cid} {args.title}",
        f"\n**Why:** {args.reason}\n",
        f"- checkpoint added: {cid} after {after}, covering {', '.join(covered)}",
        f"- proves: {args.proves}",
    ]
    with AMEND_MD.open("a", encoding="utf-8") as f:
        f.write("\n".join(entry) + "\n")

    save(plan)
    print(f"\n  added {cid}  {args.title}")
    print(f"  after {after}, covering {', '.join(covered)}")
    print(f"  its integration test goes in {checkpoint['checks'][0].split()[-2]}\n")
    return 0


def next_checkpoint_id(plan: dict[str, Any]) -> str:
    last = max(int(c["id"][1:]) for c in plan["checkpoints"])
    return f"C{last + 1}"


def phases_after_last_checkpoint(plan: dict[str, Any]) -> list[str]:
    """Phases no checkpoint covers. A plan that ends in phases rather than in a
    checkpoint is a plan whose last block was never tested as a whole."""
    covered = {c["after"] for c in plan["checkpoints"]}
    if not covered:
        return [p["id"] for p in plan["phases"]]
    last = max(covered)
    return [p["id"] for p in plan["phases"] if p["id"] > last]


def cmd_amend(plan: dict[str, Any], args: argparse.Namespace) -> int:
    if args.id.startswith("C"):
        return amend_checkpoint(plan, args)
    p = find_phase(plan, args.id)
    changes = []

    if args.set_title:
        changes.append(f"title: {p['title']!r} -> {args.set_title!r}")
        p["title"] = args.set_title
    if args.add_task:
        for t in args.add_task:
            p["tasks"].append(t)
            changes.append(f"task added: {t}")
    if args.drop_task:
        # A task that this phase cannot do has to move, not sit ticked: render marks
        # every task of a closed phase done, so an undoable task left behind becomes a
        # false record the moment the phase closes. The drop is logged with its reason
        # like every other change, so the history of where it went survives.
        for fragment in args.drop_task:
            matched = [t for t in p["tasks"] if fragment.lower() in t.lower()]
            if len(matched) != 1:
                listed = "\n  ".join(p["tasks"])
                sys.exit(
                    f"--drop-task {fragment!r} matched {len(matched)} tasks; "
                    f"it must match exactly one. Tasks are:\n  {listed}"
                )
            p["tasks"].remove(matched[0])
            changes.append(f"task dropped: {matched[0]}")
    if args.add_exit:
        for e in args.add_exit:
            p["exit"].append(e)
            changes.append(f"exit criterion added: {e}")
    if args.drop_exit:
        for fragment in args.drop_exit:
            matched = [e for e in p["exit"] if fragment.lower() in e.lower()]
            if len(matched) != 1:
                listed = "\n  ".join(p["exit"])
                sys.exit(
                    f"--drop-exit {fragment!r} matched {len(matched)} criteria; "
                    f"it must match exactly one. Criteria are:\n  {listed}"
                )
            p["exit"].remove(matched[0])
            changes.append(f"exit criterion dropped: {matched[0]}")
    if args.add_check:
        for c in args.add_check:
            p["checks"].append(c)
            changes.append(f"check added: {c}")
    if args.set_gate:
        changes.append(f"gate: {p['gate']} -> {args.set_gate}")
        p["gate"] = args.set_gate
    if args.set_blueprint:
        # Project-level rather than phase-level, but it goes through amend for the same
        # reason everything else does: the path to the design of record is not a thing
        # that should be able to change without the reason travelling with it.
        changes.append(f"blueprint: {plan['blueprint']!r} -> {args.set_blueprint!r}")
        plan["blueprint"] = args.set_blueprint
    if args.reopen:
        changes.append(f"status: {p['status']} -> open")
        p["status"] = "open"
        p.pop("closed", None)

    if not changes:
        sys.exit("amend needs at least one change flag. See --help.")

    entry = [f"\n## {today()} - {p['id']} {p['title']}", f"\n**Why:** {args.reason}\n"]
    entry += [f"- {c}" for c in changes]
    with AMEND_MD.open("a", encoding="utf-8") as f:
        f.write("\n".join(entry) + "\n")

    save(plan)
    print(f"\n  amended {p['id']} - {len(changes)} change(s), reason recorded.\n")
    return 0


def cmd_ledger(_plan: dict[str, Any], args: argparse.Namespace) -> int:
    entry = [
        f"\n## {today()} - {args.what}",
        f"\n**Phase:** {args.phase or 'not phase-specific'}",
        f"\n**Why it failed:** {args.cause}",
        f"\n**Rule:** {args.rule}\n",
    ]
    with LEDGER_MD.open("a", encoding="utf-8") as f:
        f.write("\n".join(entry) + "\n")
    print("\n  recorded. Read LEDGER.md before anything that looks like a retry.\n")
    return 0


# ---------------------------------------------------------------- render


def render(plan: dict[str, Any]) -> None:
    """PLAN.md and STATE.md are generated. Never edit them by hand."""
    L: list[str] = []
    A = L.append
    A(f"# {plan['project']} - master build plan")
    A("")
    A("*Generated from `BUILD/plan.json` by `tools/gate.py`. Do not edit by hand -")
    A("use `gate amend`, so the reason for every change is captured with the change.*")
    A("")
    done = sum(1 for p in plan["phases"] if p["status"] == "done")
    A(
        f"**{done} of {len(plan['phases'])} phases closed.** "
        f"A phase closes only when `gate close` runs its checks and they pass."
    )
    A("")
    A("Checkpoints re-run every prior phase together plus an integration test of their own.")
    A("A red checkpoint blocks the next phase - it means the phases disagree with each other.")
    A("")

    by_block: dict[str, list[dict[str, Any]]] = {}
    for p in plan["phases"]:
        by_block.setdefault(p["block"], []).append(p)

    cps = {c["after"]: c for c in plan["checkpoints"]}

    for block, items in by_block.items():
        A(f"## {block}")
        A("")
        A("| | Phase | Gate | Closes when | Status |")
        A("|---|---|---|---|---|")
        for p in items:
            mark = "x" if p["status"] == "done" else " "
            crit = p["exit"][0] if p["exit"] else ""
            when = p.get("closed", "")
            A(f"| [{mark}] | **{p['id']}** {p['title']} | {p['gate']} | {crit} | {when} |")
            if p["id"] in cps:
                c = cps[p["id"]]
                cmark = "x" if c["status"] == "done" else " "
                A(
                    f"| [{cmark}] | **{c['id']} - {c['title']}** | integration | {c['proves']} "
                    f"| {c.get('closed', '')} |"
                )
        A("")

    PLAN_MD.write_text("\n".join(L) + "\n", encoding="utf-8")

    # ---- STATE.md : the cursor
    cur = next((p for p in plan["phases"] if p["status"] != "done"), None)
    last_cp = [c for c in plan["checkpoints"] if c["status"] == "done"]
    S: list[str] = []
    B = S.append
    B("# Build state")
    B("")
    B("*Generated. This file is the cursor - read it before doing anything else in this repo.*")
    B(f"*Last written {today()}.*")
    B("")
    B("## Where the build is")
    B("")
    B(f"- **{done} of {len(plan['phases'])} phases closed**")
    B(f"- Last green checkpoint: **{last_cp[-1]['id'] if last_cp else 'none yet'}**")
    if cur:
        B(f"- Current phase: **{cur['id']} - {cur['title']}** (gate: {cur['gate']})")
    else:
        B("- Every phase is closed.")
    B("")

    if cur:
        blocking = blocking_checkpoint(plan, cur["id"])
        B("## The next action")
        B("")
        if blocking:
            B(f"**{blocking['id']} is due and has not passed.** Nothing else starts until it does.")
            B("")
            B(f"    python tools/gate.py checkpoint {blocking['id']}")
        else:
            B(
                f"Work {cur['id']}. Its full definition is in "
                f"[BUILD/phases/{cur['id']}.md](phases/{cur['id']}.md)."
            )
            B("")
            B(f"> {cur['intent']}")
            B("")
            B("Tasks:")
            B("")
            for t in cur["tasks"]:
                B(f"- [ ] {t}")
            B("")
            B("Then:")
            B("")
            B(f"    python tools/gate.py check {cur['id']}")
            B(
                f"    python tools/gate.py close {cur['id']}"
                + ('  --signoff "name: what you checked"' if cur["gate"] == "human" else "")
            )
        B("")

    B("## Before you start")
    B("")
    B("1. Read [LEDGER.md](LEDGER.md) if what you are about to try resembles something")
    B("   that has been tried before. It records dead ends so they are not re-walked.")
    B("2. Read [AMENDMENTS.md](AMENDMENTS.md) if the plan looks wrong. It probably")
    B("   changed for a reason, and the reason is there.")
    B("3. Never hand-edit PLAN.md or this file. Both are generated.")
    B("")
    B("## Closed so far")
    B("")
    for p in plan["phases"]:
        if p["status"] == "done":
            sign = f" - {p['signoff']}" if p.get("signoff") else ""
            B(f"- **{p['id']}** {p['title']} ({p.get('closed', '')}){sign}")
    if done == 0:
        B("*Nothing yet.*")
    B("")

    STATE_MD.write_text("\n".join(S) + "\n", encoding="utf-8")


def render_phase_files(plan: dict[str, Any]) -> None:
    """BUILD/phases/PNN.md, regenerated from plan.json.

    These were written once by the scaffold and then left alone, which made them stale
    copies of the plan the moment anything was amended - and CLAUDE.md sends every
    session to read the current one. Generated now, like PLAN.md and STATE.md, so the
    file a session opens says what the plan actually says.
    """
    cps = {c["after"]: c for c in plan["checkpoints"]}
    for p in plan["phases"]:
        L = [
            f"# {p['id']} - {p['title']}",
            "",
            "*Generated from BUILD/plan.json by `gate render`. Change it with `gate amend`.*",
            "",
            f"**Block.** {p['block']}  ",
            f"**Gate.** `{p['gate']}`"
            + (
                " - tests passing is necessary but not sufficient; a human signs off."
                if p["gate"] == "human"
                else " - closes on green tests alone."
            ),
        ]
        if p["status"] == "done":
            L.append(
                f"  \n**Closed.** {p['closed']}"
                + (f" - signed off: {p['signoff']}" if p.get("signoff") else "")
            )
        L += ["", "## Intent", "", p["intent"], ""]
        if p["builds"]:
            L += [
                "## Blueprint nodes this phase implements",
                "",
                "".join(f"`{b}` " for b in p["builds"]),
                "",
            ]
        L += ["## Tasks", ""]
        mark = "x" if p["status"] == "done" else " "
        L += [f"- [{mark}] {t}" for t in p["tasks"]]
        L += [
            "",
            "## Exit criteria",
            "",
            "*The phase closes when all of these are true and `gate close` says so.*",
            "",
        ]
        L += [f"- {e}" for e in p["exit"]]
        if p["gate"] == "human":
            L += [
                "",
                "## What needs a person",
                "",
                p.get("human_check", ""),
                "",
                f'    python tools/gate.py close {p["id"]} --signoff "name: what you checked"',
            ]
        L += ["", "## Verify", "", "```"]
        L += list(p["checks"])
        L += [f"python tools/gate.py check {p['id']}", "```", ""]
        if p.get("notes"):
            L += ["## Note", "", p["notes"], ""]
        if p["id"] in cps:
            c = cps[p["id"]]
            L += [
                f"## Then: checkpoint {c['id']} - {c['title']}",
                "",
                f"Before {p['id']} can be followed by the next phase, every phase up to here "
                f"is re-run together and this must hold:",
                "",
                f"> {c['proves']}",
                "",
                "```",
                f"python tools/gate.py checkpoint {c['id']}",
                "```",
                "",
                "Write the integration test at the end of this phase, not at the checkpoint - "
                "a test written after the fact tends to test what was built rather than what "
                "was meant.",
                "",
            ]
        (PHASES_DIR / f"{p['id']}.md").write_text("\n".join(L) + "\n", encoding="utf-8")


def cmd_eval(_plan: dict[str, Any], args: argparse.Namespace) -> int:
    """gate eval <skill> | --all | --coverage [--register WHO].

    The Evaluation Harness as a first-class command: the scorecard against the named
    gates, the coverage report with what is not covered, and registration on a pass.
    """
    import shlex

    forwarded = []
    if args.skill:
        forwarded.append(args.skill)
    if args.all:
        forwarded.append("--all")
    if args.coverage:
        forwarded.append("--coverage")
    if args.register:
        forwarded += ["--register", args.register]
    # The gate tool itself imports nothing from the project, so it keeps working when
    # the environment is what is broken. Inside the project environment already (the
    # test runner, or a shell that activated it) the harness runs directly; otherwise
    # under uv, like every phase check.
    import importlib.util

    if importlib.util.find_spec("jsonschema") is not None:
        return subprocess.run([sys.executable, "-m", "evals", *forwarded], cwd=ROOT).returncode
    command = "python -m uv run python -m evals " + shlex.join(forwarded)
    return subprocess.run(command, shell=True, cwd=ROOT).returncode


def cmd_render(plan: dict[str, Any], _args: argparse.Namespace) -> int:
    render(plan)
    render_phase_files(plan)
    print(f"  rendered PLAN.md, STATE.md and {len(plan['phases'])} phase files")
    return 0


# ---------------------------------------------------------------- cli


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("-v", "--verbose", action="store_true", help="show command output on pass too")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status", help="where the build is and what to do next")
    sub.add_parser("render", help="regenerate PLAN.md and STATE.md")

    c = sub.add_parser("check", help="run a phase's exit criteria without closing it")
    c.add_argument("id")

    c = sub.add_parser("close", help="check, then mark done only if it passes")
    c.add_argument("id")
    c.add_argument("--signoff", help='required for judgment phases: "who: what you checked"')

    c = sub.add_parser("checkpoint", help="re-run every prior phase plus an integration test")
    c.add_argument("id")

    c = sub.add_parser("extend", help="add a phase to the end of the plan, recording why")
    c.add_argument("reason", help="why the plan is growing; recorded in AMENDMENTS.md")
    c.add_argument("--title", required=True)
    c.add_argument("--block", required=True)
    c.add_argument("--intent", required=True)
    c.add_argument("--gate", choices=["auto", "human"], default="auto")
    c.add_argument("--human-check", help="what a person confirms; required when gate is human")
    c.add_argument("--task", action="append")
    c.add_argument("--exit", action="append", help="an exit criterion; at least one")
    c.add_argument("--check", action="append", help="a command gate close runs; at least one")
    c.add_argument("--builds", action="append", help="blueprint node ids this phase implements")
    c.add_argument("--notes")

    c = sub.add_parser("seal", help="close the last block with a checkpoint")
    c.add_argument("reason", help="why the block ends here; recorded in AMENDMENTS.md")
    c.add_argument("--title", required=True)
    c.add_argument("--proves", required=True, help="what this checkpoint proves, in one sentence")
    c.add_argument(
        "--after",
        help="the last phase it covers; defaults to the last phase in the plan. "
        "A checkpoint covers at most four.",
    )

    c = sub.add_parser("amend", help="change the plan, recording why")
    c.add_argument("id")
    c.add_argument("reason")
    c.add_argument("--set-title")
    c.add_argument("--set-gate", choices=["auto", "human"])
    c.add_argument("--add-task", action="append")
    c.add_argument(
        "--drop-task",
        action="append",
        help="drop a task by unique text fragment - a task this phase cannot do moves "
        "to one that can, because a closed phase renders every task it lists as done",
    )
    c.add_argument("--add-exit", action="append")
    c.add_argument(
        "--drop-exit",
        action="append",
        help="drop a criterion by unique text fragment - "
        "a criterion that cannot be met must go, not be ignored",
    )
    c.add_argument("--add-check", action="append")
    c.add_argument("--set-blueprint", help="where the design of record lives")
    c.add_argument("--set-proves", help="what a checkpoint proves")
    c.add_argument("--set-after", help="move a checkpoint to cover up to a different phase")
    c.add_argument("--reopen", action="store_true")

    c = sub.add_parser("ledger", help="record a dead end so it is not re-walked")
    c.add_argument("what")
    c.add_argument("--cause", required=True)
    c.add_argument("--rule", required=True)
    c.add_argument("--phase")

    c = sub.add_parser("eval", help="score a skill against its acceptance gates")
    c.add_argument("skill", nargs="?")
    c.add_argument("--all", action="store_true", help="every shipped skill")
    c.add_argument("--coverage", action="store_true", help="what is and is not covered")
    c.add_argument("--register", metavar="WHO", help="register the version on a pass")

    args = ap.parse_args()
    plan = load()
    return {
        "status": cmd_status,
        "check": cmd_check,
        "close": cmd_close,
        "checkpoint": cmd_checkpoint,
        "extend": cmd_extend,
        "seal": cmd_seal,
        "amend": cmd_amend,
        "ledger": cmd_ledger,
        "render": cmd_render,
        "eval": cmd_eval,
    }[args.cmd](plan, args)


if __name__ == "__main__":
    raise SystemExit(main())
