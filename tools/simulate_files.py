"""Twenty-one ways a file can arrive wrong, against the real server.

    python tools/simulate_files.py             # start the real server, drop every case, report

Each case is its own engagement with its own folder, so one bad file cannot hide behind
another: a zero-byte workbook, a text file named .xlsx, a CSV, a PDF, formulas with no
cached values, merged cells and a chart, five thousand account rows, thirty-six monthly
columns, German labels, apostrophes and em-dashes in names, Excel's own lock file, a
macro-enabled copy, files two folders deep, byte-identical duplicates, an empty folder,
an encrypted workbook, numbers written as text with parentheses, real dates as headers,
an incomplete set, everything in one workbook, a file still being written, and a file
changed after it settled.

The bar is the same for every case: the server does not crash, nothing is left half-done,
and whatever happened is on the record with a code a person can read. This is the battery
that found files held in silence, a non-workbook crashing a worker, "December 31" read as
the year 2031, and every halted run failing at its own manifest. Nothing here is a real
client. It stops at the model door unless `AA_LLM_ADAPTER` reaches one.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

Rows = list[list[Any]]

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

from tools._environment import needs  # noqa: E402

# What this tool cannot run without. Called here, before the first project import, because
# that import is where a bare `python tools/simulate_files.py` fails - and what it fails with is a
# traceback about somebody else's library rather than the line to type. P58 was written
# about that failure for `serve.py`; six more tools had it, and this is one of them.
needs("cryptography", "fastapi", "openpyxl", script="tools/simulate_files.py")

import simulate_firm as sim  # noqa: E402 - beside this file, on the path just added
from openpyxl import Workbook  # noqa: E402
from openpyxl.chart import BarChart, Reference  # noqa: E402

IS_ROWS: Rows = [
    ["Case Co", None, None],
    ["Statement of Income", None, None],
    ["($000s)", None, None],
    [],
    ["Account", "FY2024", "FY2025"],
    ["Revenue", 4200.0, 4650.0],
    ["Cost of sales", -2100.0, -2310.0],
    ["Officer compensation", -420.0, -455.0],
    ["Rent", -120.0, -124.0],
    ["Depreciation", -80.0, -85.0],
]
BS_ROWS: Rows = [
    ["Case Co", None, None],
    ["Balance Sheet", None, None],
    ["($000s)", None, None],
    [],
    ["Account", "FY2024", "FY2025"],
    ["Cash", 310.0, 402.0],
    ["Accounts receivable", 520.0, 566.0],
    ["Inventory", 610.0, 640.0],
    ["Accounts payable", -280.0, -301.0],
    ["Long-term debt", -900.0, -820.0],
    ["Equity", -260.0, -487.0],
]
TB_ROWS: Rows = [
    ["Case Co - Trial Balance"],
    ["As of December 31, 2025"],
    ["Actual dollars"],
    [],
    ["Account #", "Account name", "Debit", "Credit"],
    [1000, "Cash", 402_000, None],
    [1200, "Accounts receivable", 566_000, None],
    [4000, "Revenue", None, 4_650_000],
    [6000, "Officer compensation", 455_000, None],
]

ENDED = ("delivered", "halted", "quarantined", "superseded", "waiting")


def xlsx(path: Path, sheets: dict[str, Rows], **kw: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    sim.write_xlsx(path, sheets, **kw)


def normal_set(folder: Path, prefix: str = "Case") -> None:
    xlsx(folder / f"{prefix} Income Statement FY2025.xlsx", {"IS": IS_ROWS})
    xlsx(folder / f"{prefix} Balance Sheet FY2025.xlsx", {"BS": BS_ROWS})
    xlsx(folder / "TB_FY25.xlsx", {"TB": TB_ROWS})


# ---------------------------------------------------------------- the cases


def c_zero_byte(f: Path) -> None:
    normal_set(f)
    (f / "Extra TB.xlsx").write_bytes(b"")


def c_not_a_workbook(f: Path) -> None:
    normal_set(f)
    (f / "Financials.xlsx").write_bytes(b"hello, this is not a workbook")


def c_csv(f: Path) -> None:
    f.mkdir(parents=True, exist_ok=True)
    (f / "TB.csv").write_text("Account,Debit,Credit\nCash,402000,\nRevenue,,4650000\n")
    xlsx(f / "IS.xlsx", {"IS": IS_ROWS})
    xlsx(f / "BS.xlsx", {"BS": BS_ROWS})


def c_pdf(f: Path) -> None:
    normal_set(f)
    (f / "Statements.pdf").write_bytes(b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF")


def c_formulas_only(f: Path) -> None:
    f.mkdir(parents=True, exist_ok=True)
    wb = Workbook()
    ws = wb.active
    ws.title = "IS"
    ws.append(["Case Co"])
    ws.append(["($000s)"])
    ws.append([])
    ws.append(["Account", "FY2024", "FY2025"])
    ws.append(["Revenue", 4200, 4650])
    ws.append(["Cost of sales", "=-B5*0.5", "=-C5*0.5"])
    ws.append(["Gross profit", "=B5+B6", "=C5+C6"])
    wb.save(f / "IS formulas.xlsx")
    xlsx(f / "BS.xlsx", {"BS": BS_ROWS})
    xlsx(f / "TB.xlsx", {"TB": TB_ROWS})


def c_merged_and_chart(f: Path) -> None:
    f.mkdir(parents=True, exist_ok=True)
    wb = Workbook()
    ws = wb.active
    ws.title = "IS"
    for row in IS_ROWS:
        ws.append(row)
    ws.merge_cells("A1:C1")
    ws.merge_cells("A2:C2")
    chart = BarChart()
    chart.add_data(Reference(ws, min_col=2, min_row=5, max_row=10), titles_from_data=True)
    ws.add_chart(chart, "E2")
    wb.save(f / "IS with chart.xlsx")
    xlsx(f / "BS.xlsx", {"BS": BS_ROWS})
    xlsx(f / "TB.xlsx", {"TB": TB_ROWS})


def c_huge_tb(f: Path) -> None:
    rows: Rows = list(TB_ROWS[:5])
    for i in range(5000):
        kind = "expense" if i % 2 else "asset"
        rows.append([1000 + i, f"Account {i} {kind}", 1000 + i, None])
    xlsx(f / "TB huge.xlsx", {"TB": rows})
    xlsx(f / "IS.xlsx", {"IS": IS_ROWS})
    xlsx(f / "BS.xlsx", {"BS": BS_ROWS})


def c_wide_monthly(f: Path) -> None:
    months = [datetime(2023 + i // 12, i % 12 + 1, 28).strftime("%b-%y") for i in range(36)]
    rows: Rows = [
        ["Case Co"],
        ["Monthly Income Statement"],
        ["Actual dollars"],
        [],
        ["Account", *months],
        ["Revenue", *[350_000 + i * 1000 for i in range(36)]],
        ["Cost of sales", *[-(175_000 + i * 500) for i in range(36)]],
        ["Officer compensation", *[-38_000] * 36],
    ]
    xlsx(f / "Monthly IS.xlsx", {"IS": rows})
    xlsx(f / "BS.xlsx", {"BS": BS_ROWS})
    xlsx(f / "TB.xlsx", {"TB": TB_ROWS})


def c_unicode(f: Path) -> None:
    rows: Rows = [
        ["Müller & Söhne GmbH"],
        ["Gewinn- und Verlustrechnung"],
        ["(in Tsd. €)"],
        [],
        ["Konto", "GJ2024", "GJ2025"],
        ["Umsatzerlöse", 4200.0, 4650.0],
        ["Materialaufwand", -2100.0, -2310.0],
        ["Geschäftsführergehalt", -420.0, -455.0],
    ]
    xlsx(f / "GuV 2025 – Müller.xlsx", {"GuV": rows})
    xlsx(f / "Bilanz.xlsx", {"BS": BS_ROWS})
    xlsx(f / "SuSa.xlsx", {"TB": TB_ROWS})


def c_odd_names(f: Path) -> None:
    xlsx(f / "Bob's TB (final) v2 — Dec'25.xlsx", {"TB": TB_ROWS})
    xlsx(f / "IS [draft] #3.xlsx", {"IS": IS_ROWS})
    xlsx(f / "BS.xlsx", {"BS": BS_ROWS})
    (f / "~$TB.xlsx").write_bytes(b"\x00" * 165)  # Excel's own lock file


def c_xlsm(f: Path) -> None:
    normal_set(f)
    shutil.copy(f / "TB_FY25.xlsx", f / "TB macros.xlsm")


def c_nested(f: Path) -> None:
    normal_set(f / "2025" / "Q4")


def c_duplicate_bytes(f: Path) -> None:
    normal_set(f)
    shutil.copy(f / "TB_FY25.xlsx", f / "TB_FY25 (copy).xlsx")


def c_empty_folder(f: Path) -> None:
    f.mkdir(parents=True, exist_ok=True)


def c_password(f: Path) -> None:
    normal_set(f)
    # an OLE compound file header: what an encrypted .xlsx actually is on disk
    (f / "Protected TB.xlsx").write_bytes(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 504)


def c_parens_and_dashes(f: Path) -> None:
    rows: Rows = [
        ["Case Co"],
        ["Statement of Income"],
        ["($000s)"],
        [],
        ["Account", "FY2024", "FY2025"],
        ["Revenue", "4,200", "4,650"],
        ["Cost of sales", "(2,100)", "(2,310)"],
        ["Officer compensation", "(420)", "(455)"],
        ["Bad debt", "-", "—"],
        ["Gross margin %", "50%", "50.3%"],
        ["Note: see schedule 4", None, None],
    ]
    xlsx(f / "IS text numbers.xlsx", {"IS": rows})
    xlsx(f / "BS.xlsx", {"BS": BS_ROWS})
    xlsx(f / "TB.xlsx", {"TB": TB_ROWS})


def c_dates_as_headers(f: Path) -> None:
    rows: Rows = [
        ["Case Co"],
        ["Statement of Income"],
        ["($000s)"],
        [],
        ["Account", datetime(2024, 12, 31), datetime(2025, 12, 31)],
        ["Revenue", 4200.0, 4650.0],
        ["Cost of sales", -2100.0, -2310.0],
        ["Officer compensation", -420.0, -455.0],
    ]
    xlsx(f / "IS dated.xlsx", {"IS": rows})
    xlsx(f / "BS.xlsx", {"BS": BS_ROWS})
    xlsx(f / "TB.xlsx", {"TB": TB_ROWS})


def c_only_tb(f: Path) -> None:
    xlsx(f / "TB.xlsx", {"TB": TB_ROWS})  # an incomplete set: waits, then says so


def c_many_sheets(f: Path) -> None:
    sheets: dict[str, Rows] = {
        "Cover": [["Case Co"], ["Prepared for management"]],
        "IS": IS_ROWS,
        "BS": BS_ROWS,
        "TB": TB_ROWS,
        "Notes": [["Note 1"], ["The company is an S corporation."]],
        "Schedule": [["Item", "Amount"], ["Life insurance - owner", 12_000]],
    }
    xlsx(f / "Everything in one workbook.xlsx", sheets, hidden=("Notes",))


CASES = {
    "zero-byte": c_zero_byte,
    "not-a-workbook": c_not_a_workbook,
    "csv": c_csv,
    "pdf": c_pdf,
    "formulas-only": c_formulas_only,
    "merged-and-chart": c_merged_and_chart,
    "huge-tb": c_huge_tb,
    "wide-monthly": c_wide_monthly,
    "unicode": c_unicode,
    "odd-names": c_odd_names,
    "xlsm": c_xlsm,
    "nested": c_nested,
    "duplicate-bytes": c_duplicate_bytes,
    "empty-folder": c_empty_folder,
    "password": c_password,
    "parens-and-dashes": c_parens_and_dashes,
    "dates-as-headers": c_dates_as_headers,
    "only-tb": c_only_tb,
    "many-sheets": c_many_sheets,
}

# What each case is expected to do. "run" means a run launched and ended somewhere on the
# record; "none" means no run is right - an incomplete set waits, an empty folder is
# nothing, a workbook no convention claims is held and preflight says so.
EXPECTED_NO_RUN = {"empty-folder", "only-tb", "many-sheets"}


def register(api: Any, out: Any, name: str, who: str) -> str:
    eid = "BAT-" + name.upper().replace("-", "")[:8]
    code, r = api.post(
        "/api/admin/engagements",
        {
            "reason": "battery",
            "engagement_id": eid,
            "client": f"{name.title()} Case Co",
            "scope_path": "valuation/non-esop/non-repeat",
            "watch_id": "w-clients",
            "destination_id": "d-out",
            "folder": f"Battery/{name}",
        },
    )
    if code != 200:
        out.finding(f"register {eid}: {code} {str(r)[:160]}")
        return eid
    _, t = api.get(f"/api/admin/engagements/{eid}/profile/template")
    prof = t["profile"]
    prof["industry_classification"] = {
        "system": "NAICS",
        "code": "332710",
        "description": "Machine shops",
    }
    prof["size_band"] = {"metric": "revenue", "band": "1-10M", "as_of": "2025-12-31"}
    prof["owner_compensation_baseline"] = {
        "amount": 265000,
        "currency": "USD",
        "basis": "survey_median",
        "source": "ERI 2025",
        "as_of": "2025-06-30",
    }
    prof["checkpoint_policy"]["owner"] = "reviewer@chartwell.invalid"
    prof["recorded_by"] = who
    prof["recorded_at"] = "2026-09-08T09:00:00Z"
    api.post(f"/api/admin/engagements/{eid}/profile", {"reason": "profile", "profile": prof})
    api.post(
        f"/api/admin/engagements/{eid}/intake",
        {"reason": "battery", "quiet_period_minutes": 0.05},
    )
    code, r = api.post(f"/api/admin/engagements/{eid}/activate", {"reason": "go"})
    if code != 200:
        out.finding(f"activate {eid}: {code} {str(r)[:160]}")
    return eid


def main() -> int:
    from cryptography.fernet import Fernet

    home = ROOT / "runs" / "_battery"
    if home.exists():
        shutil.rmtree(home)
    inbox, outbox, runs = home / "inbox", home / "outbox", home / "runs"
    for d in (inbox / "Clients", outbox, runs):
        d.mkdir(parents=True)
    env = {
        **os.environ,
        "AA_DB_URL": f"sqlite:///{(runs / 'battery.db').as_posix()}",
        "AA_INBOX_ROOT": str(inbox),
        "AA_OUTBOX_ROOT": str(outbox),
        "AA_VAULT_KEY": Fernet.generate_key().decode(),
        "ANTHROPIC_API_KEY": os.environ.get("ANTHROPIC_API_KEY", "not-a-real-key"),
        "AA_LLM_ADAPTER": os.environ.get("AA_LLM_ADAPTER", "fake"),
        "AA_IDENTITY_NAME": "battery",
        "PYTHONIOENCODING": "utf-8",
    }
    port = sim.free_port()
    out = sim.Report()
    out.say(f"=== starting the real server on 127.0.0.1:{port}")
    server = subprocess.Popen(  # noqa: S603 - our own interpreter, our own script
        [
            sys.executable,
            str(ROOT / "tools" / "serve.py"),
            "--port",
            str(port),
            "--sweep-seconds",
            "2",
        ],
        cwd=ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    api = sim.Api(f"http://127.0.0.1:{port}")
    try:
        sim.wait_for(api)
        sim.set_up(api, out)
        _, me = api.get("/api/admin/whoami")
        out.say("\n=== one engagement per case")
        eids = {name: register(api, out, name, str(me.get("name"))) for name in CASES}
        out.say("\n=== the files land")
        for name, land in CASES.items():
            land(inbox / "Clients" / "Battery" / name)
        # a file still being written when the sweep sees it
        partial = inbox / "Clients" / "Battery" / "partial"
        eids["partial"] = register(api, out, "partial", str(me.get("name")))
        partial.mkdir(parents=True, exist_ok=True)
        xlsx(partial / "IS.xlsx", {"IS": IS_ROWS})
        xlsx(partial / "BS.xlsx", {"BS": BS_ROWS})
        with (partial / "TB slow.xlsx").open("wb") as fh:
            fh.write(b"PK\x03\x04")
            fh.flush()
            time.sleep(5)
        xlsx(partial / "TB real.xlsx", {"TB": TB_ROWS})
        # a file changed after it settled
        changed = inbox / "Clients" / "Battery" / "changed-after"
        eids["changed-after"] = register(api, out, "changed-after", str(me.get("name")))
        normal_set(changed)
        time.sleep(9)
        rows2: Rows = [r[:] for r in TB_ROWS]
        rows2[-1] = [6000, "Officer compensation", 999_000, None]
        xlsx(changed / "TB_FY25.xlsx", {"TB": rows2})

        out.say("\n=== waiting for the sweeps")
        time.sleep(30)
        _, all_runs = api.get("/api/runs")
        by_eid: dict[str, list[dict[str, Any]]] = {}
        for r in all_runs:
            by_eid.setdefault(r["engagement_id"], []).append(r)
        _, inbox_items = api.get("/api/review")
        pre: Any = api.get("/api/admin/preflight")[1]
        out.say("\n=== what happened, per case")
        for name, eid in eids.items():
            runs_ = by_eid.get(eid, [])
            summary = ", ".join(f"{r['run_id']} {r['state']}" for r in runs_) or "no run"
            out.say(f"  {name:18} {eid:13} {summary}")
            if not runs_ and name not in EXPECTED_NO_RUN:
                out.finding(f"{name}: nothing launched and nothing said why")
            for r in runs_:
                _, ev = api.get(f"/api/runs/{r['run_id']}/events")
                for e in ev or []:
                    if e.get("level") == "error" or "Traceback" in str(e.get("message")):
                        out.say(f"        x {e['type']}: {str(e.get('message'))[:150]}")
                if r["state"] not in ENDED:
                    out.finding(f"{name}: {r['run_id']} left {r['state']}")
                failed = [e for e in ev or [] if e["type"] == "worker.failed"]
                if failed:
                    out.finding(f"{name}: worker.failed - {str(failed[0].get('message'))[:160]}")
            for i in inbox_items:
                if any(i["run_id"] == r["run_id"] for r in runs_):
                    out.say(f"        review: {i['item_id']} {i['subject'][:100]}")
        held = next((c for c in pre["checks"] if c["id"] == "held_files"), None)
        if held:
            out.say(f"\n=== preflight on held files: {held['status']} - {held['detail']}")
    finally:
        server.terminate()
        try:
            log, _ = server.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()
            log, _ = server.communicate()
    if "Traceback" in log:
        out.finding("a traceback in the server log")
        lines = [ln for ln in log.splitlines() if "Traceback" in ln or "Error" in ln]
        out.say("\n".join(lines)[:2000])
    out.say("\n=== findings")
    for f in out.findings or ["none. Every wrong-shaped file ended on the record."]:
        out.say(f"  - {f}")
    return 1 if out.findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
