#!/usr/bin/env python3
"""The build gate.

The only thing permitted to mark a phase done. `BUILD/plan.json` is the source of
truth; `BUILD/PLAN.md` and `BUILD/STATE.md` are rendered from it and must never be
hand-edited, because a hand edit is how a plan and its real state start to disagree.

    python tools/gate.py status
    python tools/gate.py check P07
    python tools/gate.py close P07 [--signoff "Caleb: reviewed 40 items"]
    python tools/gate.py checkpoint C3
    python tools/gate.py amend P18 "reason" --set-title "..." --add-task "..."
    python tools/gate.py ledger "what was tried" --cause "why it failed" --rule "what to do instead"
    python tools/gate.py render
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "BUILD"
PLAN_JSON = BUILD / "plan.json"
PLAN_MD = BUILD / "PLAN.md"
STATE_MD = BUILD / "STATE.md"
LEDGER_MD = BUILD / "LEDGER.md"
AMEND_MD = BUILD / "AMENDMENTS.md"

OK = "PASS"
NO = "FAIL"


# ---------------------------------------------------------------- plan i/o


def load() -> dict:
    if not PLAN_JSON.exists():
        sys.exit(f"no plan at {PLAN_JSON}. This repo is not bootstrapped.")
    return json.loads(PLAN_JSON.read_text(encoding="utf-8"))


def save(plan: dict) -> None:
    PLAN_JSON.write_text(json.dumps(plan, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    render(plan)


def today() -> str:
    return dt.date.today().isoformat()


def find_phase(plan: dict, pid: str) -> dict:
    pid = pid.upper()
    for p in plan["phases"]:
        if p["id"] == pid:
            return p
    sys.exit(f"unknown phase {pid}")


def find_checkpoint(plan: dict, cid: str) -> dict:
    cid = cid.upper()
    for c in plan["checkpoints"]:
        if c["id"] == cid:
            return c
    sys.exit(f"unknown checkpoint {cid}")


def phases_before(plan: dict, cid: str) -> list[dict]:
    """Every phase that must be green before this checkpoint."""
    c = find_checkpoint(plan, cid)
    return [p for p in plan["phases"] if p["id"] <= c["after"]]


# ---------------------------------------------------------------- running


def run(cmd: str) -> tuple[bool, str]:
    proc = subprocess.run(
        cmd, shell=True, cwd=ROOT, capture_output=True,
        text=True, encoding="utf-8", errors="replace",
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


def cmd_status(plan: dict, _args) -> int:
    done = [p for p in plan["phases"] if p["status"] == "done"]
    cur = next((p for p in plan["phases"] if p["status"] != "done"), None)
    last_cp = [c for c in plan["checkpoints"] if c["status"] == "done"]

    print(f"\n  {plan['project']}")
    print(f"  {len(done)}/{len(plan['phases'])} phases closed"
          f" | last green checkpoint: {last_cp[-1]['id'] if last_cp else 'none'}")

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


def blocking_checkpoint(plan: dict, pid: str) -> dict | None:
    """A checkpoint sitting between the last closed phase and this one, still red."""
    for c in plan["checkpoints"]:
        if c["status"] != "done" and c["after"] < pid:
            unmet = [p for p in phases_before(plan, c["id"]) if p["status"] != "done"]
            if not unmet:
                return c
    return None


def cmd_check(plan: dict, args) -> int:
    p = find_phase(plan, args.id)
    print(f"\n  {p['id']}  {p['title']}   (gate: {p['gate']})")
    print("  exit criteria:")
    for e in p["exit"]:
        print(f"    - {e}")
    print(f"\n  running {len(p['checks'])} check(s):")
    ok = run_checks(p["checks"], args.verbose)
    print(f"\n  {'PASS' if ok else 'FAIL'} - {p['id']}\n")
    return 0 if ok else 1


def cmd_close(plan: dict, args) -> int:
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
        print("            not sufficient. Re-run with --signoff \"who: what you checked\".")
        print(f"            What needs a human: {p.get('human_check', 'see the phase file')}\n")
        return 1

    p["status"] = "done"
    p["closed"] = today()
    if args.signoff:
        p["signoff"] = args.signoff
    save(plan)
    print(f"\n  CLOSED  {p['id']} on {p['closed']}"
          f"{' - signed off: ' + args.signoff if args.signoff else ''}\n")
    return 0


def cmd_checkpoint(plan: dict, args) -> int:
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


def cmd_amend(plan: dict, args) -> int:
    p = find_phase(plan, args.id)
    changes = []

    if args.set_title:
        changes.append(f"title: {p['title']!r} -> {args.set_title!r}")
        p["title"] = args.set_title
    if args.add_task:
        for t in args.add_task:
            p["tasks"].append(t)
            changes.append(f"task added: {t}")
    if args.add_exit:
        for e in args.add_exit:
            p["exit"].append(e)
            changes.append(f"exit criterion added: {e}")
    if args.add_check:
        for c in args.add_check:
            p["checks"].append(c)
            changes.append(f"check added: {c}")
    if args.set_gate:
        changes.append(f"gate: {p['gate']} -> {args.set_gate}")
        p["gate"] = args.set_gate
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


def cmd_ledger(_plan: dict, args) -> int:
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


def render(plan: dict) -> None:
    """PLAN.md and STATE.md are generated. Never edit them by hand."""
    L: list[str] = []
    A = L.append
    A(f"# {plan['project']} - master build plan")
    A("")
    A("*Generated from `BUILD/plan.json` by `tools/gate.py`. Do not edit by hand -")
    A("use `gate amend`, so the reason for every change is captured with the change.*")
    A("")
    done = sum(1 for p in plan["phases"] if p["status"] == "done")
    A(f"**{done} of {len(plan['phases'])} phases closed.** "
      f"A phase closes only when `gate close` runs its checks and they pass.")
    A("")
    A("Checkpoints re-run every prior phase together plus an integration test of their own.")
    A("A red checkpoint blocks the next phase - it means the phases disagree with each other.")
    A("")

    by_block: dict[str, list] = {}
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
                A(f"| [{cmark}] | **{c['id']} - {c['title']}** | integration | {c['proves']} "
                  f"| {c.get('closed', '')} |")
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
            B(f"Work {cur['id']}. Its full definition is in "
              f"[BUILD/phases/{cur['id']}.md](phases/{cur['id']}.md).")
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
            B(f"    python tools/gate.py close {cur['id']}"
              + ('  --signoff "name: what you checked"' if cur["gate"] == "human" else ""))
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


def cmd_render(plan: dict, _args) -> int:
    render(plan)
    print("  rendered PLAN.md and STATE.md")
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

    c = sub.add_parser("amend", help="change the plan, recording why")
    c.add_argument("id")
    c.add_argument("reason")
    c.add_argument("--set-title")
    c.add_argument("--set-gate", choices=["auto", "human"])
    c.add_argument("--add-task", action="append")
    c.add_argument("--add-exit", action="append")
    c.add_argument("--add-check", action="append")
    c.add_argument("--reopen", action="store_true")

    c = sub.add_parser("ledger", help="record a dead end so it is not re-walked")
    c.add_argument("what")
    c.add_argument("--cause", required=True)
    c.add_argument("--rule", required=True)
    c.add_argument("--phase")

    args = ap.parse_args()
    plan = load()
    return {
        "status": cmd_status,
        "check": cmd_check,
        "close": cmd_close,
        "checkpoint": cmd_checkpoint,
        "amend": cmd_amend,
        "ledger": cmd_ledger,
        "render": cmd_render,
    }[args.cmd](plan, args)


if __name__ == "__main__":
    raise SystemExit(main())
