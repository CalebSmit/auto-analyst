"""P104 - which documents a skill is even asked about.

P103 let twelve of the real client's thirteen files into a run, and the run then stalled.
`timing-normalization` is handed every source, so it was asked to find periods in board
minutes, an org chart and a competitor list. It reported each ambiguous - correctly, there
are none - a person answered, the step re-ran and reported them again. **Thirty passes,
thirty review items, no progress.**

Before P103 only three files entered and all three were financial, so nothing found it. One
fix made the next defect reachable, which is the ordinary way this happens.

A document of a kind that carries no periods is not an ambiguity for somebody to resolve.
It is a question the skill should never have been asked.

**Where the answer lives.** In the Contract Registry, beside the type it describes, and
required rather than defaulted. A list in the harness would go stale the first time a type
was added and nobody remembered; a default would let a type arrive with no answer and read
as "no", which is the silence the field exists to prevent.

**And it is narrower than "has dates in it"** - a distinction that cost a wrong answer
before it was written down. A capital-expenditure schedule is transactions by date and a
customer schedule is sales by year; both carry dates, neither is a statement the timing
skill can align.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from registries.contracts import ContractRegistry
from registries.errors import RegistryError

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "contracts" / "registry.yaml"


class Source:
    """The shape `build_inputs` reads: a parsed source with a document type."""

    def __init__(self, filename: str, document_type: str) -> None:
        self.filename = filename
        self.document_type = document_type


def facts_with(*sources: Source) -> Any:
    from harness.inputs import RunFacts

    class Policy:
        auto_accept_confidence = 0.9
        always_review_categories: frozenset[str] = frozenset()

    return RunFacts(
        profile={},
        policy=Policy(),
        taxonomy_version="coa-taxonomy@1.0.0",
        sources=tuple(sources),
        blocks={},
    )


# ============================================================ what the registry declares


def test_every_intake_type_declares_whether_it_carries_periods() -> None:
    for declared in ContractRegistry.load().intake_document_types():
        assert isinstance(declared.carries_periods, bool), declared.id


def test_a_type_that_does_not_declare_it_is_refused(tmp_path: Path) -> None:
    """Required rather than defaulted. `row.get(field, False)` would let a type arrive with
    no answer and read as "no" - and a type that carries periods and says nothing would be
    silently withheld from the one skill that can read it."""
    # The whole contracts folder, because the index is checked against the schema files
    # beside it - a registry alone in a temp directory fails for an unrelated reason first.
    import shutil

    shutil.copytree(ROOT / "contracts", tmp_path / "contracts")
    broken = tmp_path / "contracts" / "registry.yaml"
    loaded = yaml.safe_load(broken.read_text(encoding="utf-8"))
    for row in loaded["intake_document_types"]:
        if row["id"] == "financial_statements":
            del row["carries_periods"]
    broken.write_text(yaml.safe_dump(loaded), encoding="utf-8")

    with pytest.raises(RegistryError) as refused:
        ContractRegistry.load(broken)
    assert "carries_periods" in str(refused.value)
    assert "no sensible default" in str(refused.value)


def test_it_is_the_statements_and_not_everything_with_a_date_in_it() -> None:
    """The distinction that cost a wrong answer. A capex schedule is transactions by date
    and a customer schedule is sales by year; neither is a statement to align."""
    carries = {
        t.id for t in ContractRegistry.load().intake_document_types() if t.carries_periods
    }
    assert carries == {"financial_statements", "trial_balance", "tax_return", "forecast"}
    for dated_but_not_a_statement in ("capex_schedule", "customer_detail", "nonrecurring_items"):
        assert dated_but_not_a_statement not in carries


def test_the_documents_a_valuation_reads_for_other_reasons_carry_none() -> None:
    """They matter and they have no fiscal year. Being excluded here is not being excluded
    from the run - they are bound, on the record, and they answer request-list items."""
    by_id = {t.id: t for t in ContractRegistry.load().intake_document_types()}
    for narrative in ("board_minutes", "org_chart", "competitor_list", "stockholder_list",
                      "business_overview", "employee_roster"):
        assert by_id[narrative].carries_periods is False, narrative


# ============================================================ what the skill is handed


def test_the_timing_skill_sees_only_the_statements() -> None:
    from harness.inputs import build_inputs

    built = build_inputs(
        "timing-normalization",
        "timing",
        {},
        facts_with(
            Source("Consolidated Income Statements.xlsx", "financial_statements"),
            Source("2023 Board Minutes.pdf", "board_minutes"),
            Source("Org Chart.pdf", "org_chart"),
            Source("TB_FY25.xlsx", "trial_balance"),
        ),
        blobs=None,
    )
    assert [f.filename for f in built.files] == [
        "Consolidated Income Statements.xlsx", "TB_FY25.xlsx"
    ]


def test_a_folder_of_nothing_but_narrative_says_so_rather_than_handing_over_an_empty_list() -> None:
    """The distinction between "no documents" and "no documents of a kind this skill reads".
    An empty list would make the skill report nothing was found, which is true and useless;
    this names the types that did arrive so a person can see what the folder actually holds.
    """
    from harness.inputs import InputsUnavailable, build_inputs

    with pytest.raises(InputsUnavailable) as refused:
        build_inputs(
            "timing-normalization",
            "timing",
            {},
            facts_with(
                Source("2023 Board Minutes.pdf", "board_minutes"),
                Source("Org Chart.pdf", "org_chart"),
            ),
            blobs=None,
        )
    said = str(refused.value)
    assert "board_minutes" in said and "org_chart" in said
    assert "carries figures over periods" in said


def test_a_run_with_no_sources_at_all_still_says_that_instead() -> None:
    """Two different problems and two different sentences: nothing arrived, versus nothing
    of the right kind arrived."""
    from harness.inputs import InputsUnavailable, build_inputs

    with pytest.raises(InputsUnavailable) as refused:
        build_inputs("timing-normalization", "timing", {}, facts_with(), blobs=None)
    assert "no parsed source documents" in str(refused.value)


def test_the_filter_asks_the_registry_rather_than_carrying_a_list() -> None:
    """A list in the harness is the roll-call failure this repo has six of. Adding a type
    must force an answer where the type is declared, not silently miss one here."""
    source = (ROOT / "harness" / "inputs.py").read_text(encoding="utf-8")
    body = source[source.index("def _with_periods") : source.index("def build_inputs")]
    assert "ContractRegistry.load()" in body
    assert "carries_periods" in body
    for hard_coded in ('"financial_statements"', '"trial_balance"', '"forecast"'):
        assert hard_coded not in body, "the set is declared, not listed here"


def test_the_excluded_files_are_not_dropped_from_the_run() -> None:
    """They are bound, recorded and answer request-list items; they are simply not shown to
    a skill that reads fiscal calendars. Held on the docstring because the distinction is
    the whole point and the code cannot state it."""
    source = (ROOT / "harness" / "inputs.py").read_text(encoding="utf-8")
    body = source[source.index("def _with_periods") : source.index("def build_inputs")]
    assert "not dropped from the run" in body
