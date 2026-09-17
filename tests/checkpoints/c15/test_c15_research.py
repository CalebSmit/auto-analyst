"""Checkpoint C15 - what the research changed.

Proves: on a system started the way a person starts it, a client forecast cannot pass for
historical statements at any of the three places a file is judged - the filename, the
contents, the step that builds the historical table - and the model checks read the same
taxonomy the tagging skill writes.

P38 touched three phases' code at once: the binder's conventions (P16, through the admin
initialiser of P24), the classifier (P17) and the timing procedure (P18). Each fix alone
leaves a gap the others close: a filename can say "Income Statement", contents can say
"Balance Sheet", and a model can align what it is shown. This is where they meet.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from harness.procedures.timing_normalization import SourceFile, TimingInputs, TimingNormalization
from intake.bind import bind_document_type
from intake.readers.classify import Evidence, classify
from registries.taxonomy import load_taxonomy
from tools.serve import build
from tools.statement_checks import DIRECTION, Line, Stated, readiness, run_checks

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def served(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    monkeypatch.setenv("AA_DB_URL", f"sqlite:///{(tmp_path / 'c15.db').as_posix()}")
    monkeypatch.setenv("AA_INBOX_ROOT", str(tmp_path / "inbox"))
    monkeypatch.setenv("AA_OUTBOX_ROOT", str(tmp_path / "outbox"))
    (tmp_path / "inbox").mkdir()
    (tmp_path / "outbox").mkdir()

    import ports

    ports.reset()
    system = build()
    TestClient(system.app).post(
        "/api/admin/initialise", json={"who": "C. Smit", "reason": "C15: a first setup"}
    )
    yield system
    system.close()
    ports.reset()


def test_a_forecast_named_like_a_statement_is_held_at_the_door(served: Any) -> None:
    conventions = served.config.conventions()
    assert "forecast" in conventions, "the first setup a person runs knows what a forecast is"
    assert bind_document_type("Income Statement Forecast.xlsx", conventions) is None
    assert bind_document_type("Forecast 2026-2030.xlsx", conventions) == "forecast"
    assert bind_document_type("FY2025 Income Statement.pdf", conventions) == (
        "financial_statements"
    )


def test_a_forecast_that_gets_past_its_name_is_caught_by_its_contents_and_kept_out() -> None:
    """A file called "Mgmt model.xlsx" binds to nothing by name; suppose a person binds it
    by hand. Its contents classify it as a forecast, and the timing step leaves it out."""
    found = classify(
        Evidence("Mgmt model.xlsx", headers=["Income statement", "2026E"], sheet_names=["P&L"])
    )
    assert found.document_type == "forecast"

    def as_source(name: str, document_type: str) -> SourceFile:
        return SourceFile(
            source_id=f"sha256:{name}",
            filename=name,
            document_type=document_type,
            blocks={"IS!B2:B2": [{"label": "Revenue", "value": 1.0, "raw": "1", "ordinal": 2}]},
            scale=1,
            currency="USD",
            period_type="annual",
            period_ends=("2025-12-31",),
        )

    inputs = TimingInputs(
        (
            as_source("FY25.xlsx", "financial_statements"),
            as_source("Mgmt model.xlsx", found.document_type),
        )
    )
    shown = json.loads(TimingNormalization().payload(inputs))
    assert [f["filename"] for f in shown["files"]] == ["FY25.xlsx"]


def test_the_model_checks_read_the_taxonomy_the_tagging_skill_writes() -> None:
    """Every category a tag can carry has a direction, and a table built from the tagging
    gold set's own categories is something the checks can total."""
    gold = json.loads(
        (ROOT / "fixtures/skills/line-item-tagging/gold.json").read_text(encoding="utf-8")
    )
    categories = {str(entry["category"]) for entry in gold.values()}
    assert categories, "the gold set carries categories"
    taxonomy = load_taxonomy("coa-taxonomy@1.0.0")
    unknown = {c for c in categories if c != "unmapped" and c not in DIRECTION}
    assert unknown == set(), f"tagged categories the checks cannot place: {unknown}"

    lines = [
        Line("revenue", {"2025-12-31": 500.0}, "IS!B2"),
        Line("rent", {"2025-12-31": 80.0}, "IS!B3"),
    ]
    findings = run_checks(
        lines, taxonomy, tolerance=0.0, stated_net_income={"2025-12-31": Stated(420.0, "IS!B9")}
    )
    assert findings[0]["result"] == "pass"
    assert readiness(findings) == "no_automated_issues_found"
