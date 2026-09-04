"""The Deliverable QC Gate: opens the file and checks it before anyone else does.

openpyxl round-trip plus pattern checks. It loads; no `#REF!`, `#VALUE!`, `#DIV/0!`,
`#NAME?` or `#N/A` in any cell or formula; every formula's sheets and names resolve; no
external link, broken or otherwise; no residual mask token; the template version is
stamped; and every named range the mapping wrote holds the value it was given, so every
figure in the workbook is traceable to the mapping that put it there.

Fails closed. A failure stops the run and routes to the Fixed Notice, never to a
partially valid deliverable. The last chance to catch a file that is technically
produced but practically broken - which, with generated spreadsheets, is a common
enough outcome to deserve its own gate.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from io import BytesIO
from typing import Any

from openpyxl import load_workbook
from openpyxl.formula import Tokenizer

from guards import GuardResult, report
from ops.events import EventBus
from privacy.payload_scan import TOKEN_PATTERN
from registries.errors import QC_FAILED
from tools.write_template import cell_for

__all__ = ["DeliverableQC", "ERROR_VALUES"]

ERROR_VALUES = ("#REF!", "#VALUE!", "#DIV/0!", "#NAME?", "#N/A", "#NUM!", "#NULL!")
EXTERNAL_REF = re.compile(r"\[[^\]]+\]")
SHEET_REF = re.compile(r"^'?(.+?)'?!")


class DeliverableQC:
    def __init__(self, bus: EventBus | None = None) -> None:
        self.bus = bus

    def check(
        self,
        data: bytes,
        *,
        template_version: str | None = None,
        expected: Mapping[str, Any] | None = None,
    ) -> GuardResult:
        """The pure half. Bytes in, verdict out."""
        reasons: list[str] = []
        checked = 0
        try:
            wb = load_workbook(BytesIO(data))
        except Exception as exc:  # noqa: BLE001 - "does not open" is the finding
            return GuardResult(
                guard="deliverable_qc",
                passed=False,
                checked=1,
                failed=1,
                code=QC_FAILED,
                reasons=(f"the workbook does not open: {exc}",),
                detail={},
            )

        sheets = {ws.title for ws in wb.worksheets}
        names = set(wb.defined_names.keys())
        for ws in wb.worksheets:
            names |= set(ws.defined_names.keys())

        if getattr(wb, "_external_links", None):
            reasons.append(f"{len(wb._external_links)} external link(s) in the workbook")  # noqa: SLF001

        for ws in wb.worksheets:
            for row in ws.iter_rows():
                for cell in row:
                    value = cell.value
                    if value is None:
                        continue
                    checked += 1
                    text = str(value)
                    where = f"{ws.title}!{cell.coordinate}"
                    if any(err in text for err in ERROR_VALUES):
                        reasons.append(f"{where} holds {text!r}")
                    if TOKEN_PATTERN.search(text):
                        reasons.append(f"{where} carries a residual mask token")
                    if isinstance(value, str) and value.startswith("="):
                        reasons.extend(_formula_problems(value, where, sheets, names))

        if template_version is not None:
            try:
                sheet, ref = cell_for(wb, "Template_Version")
                stamped = wb[sheet][ref].value
                checked += 1
                if str(stamped) != str(template_version):
                    reasons.append(
                        f"template version stamped {stamped!r}, expected {template_version!r}"
                    )
            except Exception as exc:  # noqa: BLE001 - a missing stamp is a finding
                reasons.append(f"no Template_Version stamp: {exc}")

        for name, want in (expected or {}).items():
            checked += 1
            try:
                sheet, ref = cell_for(wb, name)
            except Exception as exc:  # noqa: BLE001
                reasons.append(f"{name}: {exc}")
                continue
            have = wb[sheet][ref].value
            if not _same(have, want):
                reasons.append(f"{name} holds {have!r}, the mapping wrote {want!r}")

        return GuardResult(
            guard="deliverable_qc",
            passed=not reasons,
            checked=checked,
            failed=len(reasons),
            code=QC_FAILED if reasons else None,
            reasons=tuple(reasons),
            detail={"sheets": sorted(sheets), "names": len(names)},
        )

    def run(
        self,
        data: bytes,
        run_id: str,
        engagement_id: str,
        step_id: str | None = None,
        *,
        template_version: str | None = None,
        expected: Mapping[str, Any] | None = None,
    ) -> GuardResult:
        result = self.check(data, template_version=template_version, expected=expected)
        return report(self.bus, result, "deliverable_qc", run_id, engagement_id, step_id)


def _formula_problems(formula: str, where: str, sheets: set[str], names: set[str]) -> list[str]:
    problems = []
    if EXTERNAL_REF.search(formula):
        problems.append(f"{where} references an external workbook: {formula}")
    try:
        tokens = Tokenizer(formula).items
    except Exception:  # noqa: BLE001 - an unparseable formula is a finding
        return [*problems, f"{where} has a formula that does not parse: {formula}"]
    for token in tokens:
        if token.type != "OPERAND" or token.subtype != "RANGE":
            continue
        ref = token.value
        sheet = SHEET_REF.match(ref)
        if sheet:
            if sheet.group(1) not in sheets:
                problems.append(
                    f"{where} references sheet {sheet.group(1)!r}, which does not exist"
                )
            continue
        if re.match(r"^\$?[A-Za-z]{1,3}\$?\d+(?::\$?[A-Za-z]{1,3}\$?\d+)?$", ref):
            continue  # a plain cell reference on the same sheet
        if ref not in names:
            problems.append(f"{where} references {ref!r}, which is not a defined name")
    return problems


def _same(have: Any, want: Any) -> bool:
    if isinstance(want, int | float) and isinstance(have, int | float):
        return abs(float(have) - float(want)) < 1e-9
    return str(have) == str(want)
