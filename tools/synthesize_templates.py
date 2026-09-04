"""Build the synthetic model templates under templates/ from their input schemas.

The firm's real templates are Chartwell's and arrive at the P24 pilot. Until then the
registry, the writer and the QC gate need workbooks with the declared shape: an Inputs
sheet with one named range per declared input, a Historicals sheet of formulas over
those names, a DCF sheet with more formulas, and the two stamp cells. No client data,
no values - a template is empty by definition.

    python tools/synthesize_templates.py            # writes both templates
    python tools/synthesize_templates.py --check    # exit 1 if either differs from disk

Deterministic: the same schema produces the same workbook.
"""

from __future__ import annotations

import sys
from io import BytesIO
from pathlib import Path

import yaml
from openpyxl import Workbook
from openpyxl.workbook.defined_name import DefinedName

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "templates"
INPUTS = TEMPLATES / "inputs"

LINES = [
    ("Revenue", "Revenue"),
    ("COGS", "Cost of sales"),
    ("Officer_Comp", "Officer compensation"),
    ("Wages", "Wages"),
    ("Payroll_Taxes", "Payroll taxes"),
    ("Rent", "Rent"),
    ("Repairs", "Repairs and maintenance"),
    ("Utilities", "Utilities"),
    ("Insurance", "Insurance"),
    ("Professional_Fees", "Professional fees"),
    ("Depreciation", "Depreciation"),
    ("Travel", "Travel"),
    ("Office", "Office supplies"),
    ("Other_Opex", "Other operating expense"),
]


def build(schema: dict) -> bytes:  # type: ignore[type-arg]
    wb = Workbook()
    inputs = wb.active
    inputs.title = "Inputs"
    inputs["A1"] = "Input"
    inputs["B1"] = "Value"
    inputs["A2"] = "Template version"
    inputs["A3"] = "Run id"
    wb.defined_names["Template_Version"] = DefinedName("Template_Version", attr_text="Inputs!$B$2")
    wb.defined_names["Run_Id"] = DefinedName("Run_Id", attr_text="Inputs!$B$3")

    row = 5
    for entry in [*schema["required"], *schema["optional"]]:
        inputs.cell(row=row, column=1, value=f"{entry['line']} ({entry['period']})")
        wb.defined_names[entry["name"]] = DefinedName(entry["name"], attr_text=f"Inputs!$B${row}")
        row += 1

    hist = wb.create_sheet("Historicals")
    hist["A1"] = "Line"
    for n, fy in enumerate(("FY1", "FY2", "FY3"), start=2):
        hist.cell(row=1, column=n, value=fy)
    r = 2
    for key, label in LINES:
        hist.cell(row=r, column=1, value=label)
        for n, fy in enumerate(("FY1", "FY2", "FY3"), start=2):
            hist.cell(row=r, column=n, value=f"={key}_{fy}")
        r += 1
    hist.cell(row=r, column=1, value="Gross profit")
    for n, fy in enumerate(("FY1", "FY2", "FY3"), start=2):
        hist.cell(row=r, column=n, value=f"=Revenue_{fy}-COGS_{fy}")
    gross = r
    r += 1
    hist.cell(row=r, column=1, value="Operating expenses")
    for n, fy in enumerate(("FY1", "FY2", "FY3"), start=2):
        names = "+".join(f"{key}_{fy}" for key, _ in LINES[2:])
        hist.cell(row=r, column=n, value=f"={names}")
    opex = r
    r += 1
    hist.cell(row=r, column=1, value="EBITDA (reported)")
    for n, _ in enumerate(("FY1", "FY2", "FY3"), start=2):
        col = hist.cell(row=1, column=n).column_letter
        hist.cell(row=r, column=n, value=f"={col}{gross}-{col}{opex}+{col}{2 + 10}")
    r += 1
    hist.cell(row=r, column=1, value="Officer comp over benchmark")
    for n, fy in enumerate(("FY1", "FY2", "FY3"), start=2):
        hist.cell(row=r, column=n, value=f"=Officer_Comp_{fy}-Owner_Comp_Benchmark")

    dcf = wb.create_sheet("DCF")
    dcf["A1"] = "Terminal WACC"
    dcf["B1"] = "=WACC_Terminal"
    dcf["A2"] = "Target NWC"
    dcf["B2"] = "=NWC_Target"
    dcf["A3"] = "Selected multiple"
    dcf["B3"] = "=EV_EBITDA_Multiple"
    dcf["A4"] = "Template"
    dcf["B4"] = "=Template_Version"

    out = BytesIO()
    wb.save(out)
    return out.getvalue()


def main(argv: list[str]) -> int:
    check = "--check" in argv
    status = 0
    for schema_path in sorted(INPUTS.glob("*.yaml")):
        schema = yaml.safe_load(schema_path.read_text(encoding="utf-8"))
        target = TEMPLATES / schema["template"]
        data = build(schema)
        if check:
            if not target.is_file() or _cells(target.read_bytes()) != _cells(data):
                print(f"differs: {target.name}")
                status = 1
            continue
        target.write_bytes(data)
        print(f"wrote {target.name}: {len(schema['required'])} required inputs")
    return status


def _cells(data: bytes) -> list[tuple[str, str, object]]:
    from openpyxl import load_workbook

    wb = load_workbook(BytesIO(data))
    found = []
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for cell in row:
                if cell.value is not None:
                    found.append((ws.title, cell.coordinate, cell.value))
    found.append(("names", "", sorted(wb.defined_names.keys())))
    return found


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
