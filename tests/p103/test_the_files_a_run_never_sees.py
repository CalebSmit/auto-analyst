"""P103 - the files a run never sees.

Running the real client folder end to end showed ten of its thirteen files never entering a
run at all. The binder reads a document type from filename tokens in
`document_type_conventions` - a table carrying three types - and holds anything no token
claims. P96 taught the classifier to recognise all thirteen, and the binder had never asked
it: the classifier served the DD tracker and the in-run read, and both of those happen
*after* a file is already in.

So the analyst's goal - put all the data into a structured output - failed at the first
step, with ten documents held and nothing wrong with any of them.

**The rule it narrows.** The binder's docstring said a type was "never guessed", and that
was right about guessing and too strict about what counts as one. A convention is a
decision the firm wrote down; a classification is evidence with a confidence and stated
reasons. Evidence does not overrule a decision - but holding a board minute because nobody
had typed `minutes` into a config file is not caution, it is a list somebody works through
by hand every Monday.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from intake.bind import CLASSIFICATION, CONVENTION, bind_document_type, document_type_for

ROOT = Path(__file__).resolve().parents[2]

#: The three types the shipped convention table carries, as `config_document` writes them.
CONVENTIONS: dict[str, tuple[str, ...]] = {
    "trial_balance": ("tb_", "trial balance"),
    "financial_statements": ("income statement", "balance sheet", "financials"),
    "forecast": ("forecast", "projection", "projected", "budget"),
}

#: The client's own folder name for the statements, long enough to wrap every line it
#: appears on.
STATEMENTS = "Historical and Forecasted Financial Statements"

#: The real client folder, by name and folder only - the same thirteen P96 records, and no
#: client in any of them.
THE_REAL_FOLDER: tuple[tuple[str, tuple[str, ...], str, str], ...] = (
    ("2023 Board Minutes_Redacted.pdf", ("Board Minutes",), "board_minutes", CLASSIFICATION),
    ("2024 Board Minutes_Redacted.pdf", ("Board Minutes",), "board_minutes", CLASSIFICATION),  # noqa: E501
    ("Capital Expenditures_Redacted.xlsx", (), "capex_schedule", CLASSIFICATION),
    ("Employee Count_Redacted.xlsx", (), "employee_roster", CLASSIFICATION),
    ("Consolidated Balance Sheets_Redacted.xlsx", (STATEMENTS,), "financial_statements",
     CONVENTION),
    ("Consolidated Income Statements_Redacted.xlsx", (STATEMENTS,), "financial_statements",
     CONVENTION),
    ("Projections_Redacted.xlsx", (STATEMENTS,), "forecast", CONVENTION),
    ("List of Competitors_Redacted.pdf", (), "competitor_list", CLASSIFICATION),
    ("Nonrecurring Income Expenses_Redacted.pdf", (), "nonrecurring_items", CLASSIFICATION),
    ("Org Chart_Redacted.pdf", (), "org_chart", CLASSIFICATION),
    ("List of Stockholders_Redacted.pdf", ("Stockholder list",), "stockholder_list",
     CLASSIFICATION),
    ("Top 15 Customers 2021 - 2024 YTD_Redacted.xlsx", (), "customer_detail",
     CLASSIFICATION),
)


# ============================================================ the folder gets in


@pytest.mark.parametrize(("name", "folders", "expected", "how"), THE_REAL_FOLDER)
def test_every_file_the_classifier_knows_now_binds(
    name: str, folders: tuple[str, ...], expected: str, how: str
) -> None:
    found, by = document_type_for(name, CONVENTIONS, folders=folders)
    assert found == expected, name
    assert by == how, name


def test_three_bound_before_and_twelve_bind_now() -> None:
    """The measurement that justified the phase, as arithmetic rather than a claim."""
    before = sum(1 for n, _, _, _ in THE_REAL_FOLDER if bind_document_type(n, CONVENTIONS))
    after = sum(
        1 for n, f, _, _ in THE_REAL_FOLDER if document_type_for(n, CONVENTIONS, folders=f)[0]
    )
    assert before == 3
    assert after == 12


def test_the_write_up_is_still_held_because_its_name_says_nothing() -> None:
    """`Overview and notes.docx` is the thirteenth, and holding it is correct. P98 already
    established that it needs its contents; the binder sees only a name and a folder, so it
    must not pretend otherwise."""
    assert document_type_for("Overview and notes.docx", CONVENTIONS) == (None, "")


# ============================================================ what may not bind


def test_a_convention_beats_a_classification() -> None:
    """The firm declaring a token is a decision. A classification is evidence, and evidence
    does not overrule a decision - so a filename a token claims keeps that type even where
    the classifier is confident about something else."""
    claimed = {"trial_balance": ("board minutes",)}
    found, how = document_type_for("2024 Board Minutes.pdf", claimed)
    assert (found, how) == ("trial_balance", CONVENTION)


def test_an_unconfident_classification_is_held_rather_than_bound() -> None:
    """The bar is the classifier's own `review_required` - the same one that decides whether
    a read goes to a person - so a binding is never more confident than the read after it."""
    assert document_type_for("scan0001.pdf", CONVENTIONS) == (None, "")
    assert document_type_for("Copy of Copy of untitled.xlsx", CONVENTIONS) == (None, "")


def test_a_type_the_registry_does_not_declare_never_binds() -> None:
    """`gl_detail` and `cap_table` are classes the classifier can produce and the Contract
    Registry does not declare. A binding is a claim about a document's *type*, and the
    vocabulary for that is the registry's."""
    from registries.contracts import ContractRegistry

    declared = {t.id for t in ContractRegistry.load().intake_document_types()}
    assert "gl_detail" not in declared and "cap_table" not in declared

    found, _ = document_type_for("General ledger detail FY25.xlsx", CONVENTIONS)
    assert found != "gl_detail"
    found, _ = document_type_for("Capitalization table.xlsx", CONVENTIONS)
    assert found != "cap_table"


def test_held_is_still_a_real_answer() -> None:
    """Emptying the held list was never the goal. A file nothing recognises is a question
    for a person, and the page that lists them is how it gets asked."""
    for name in ("holiday photos.zip", "IMG_20240317.jpg", "Document1.docx"):
        assert document_type_for(name, CONVENTIONS) == (None, ""), name


# ============================================================ the record says which


def test_the_binding_says_which_of_the_two_found_it() -> None:
    """An inferred type must be visible as one everywhere it travels. A person reading the
    intake record should not have to re-run the classifier to tell a declaration from a
    confident guess."""
    from intake.bind import Bound
    from ports.storage import FileRef

    ref = FileRef(path="Clients/X/2026/Org Chart.pdf")
    held = Bound(ref=ref, engagement_id="E", watch_id="w", document_type=None)
    assert held.bound_by == "", "held carries no method, because nothing found it"

    inferred = Bound(
        ref=ref, engagement_id="E", watch_id="w",
        document_type="org_chart", bound_by=CLASSIFICATION,
    )
    assert inferred.bound_by == CLASSIFICATION


def test_the_docstring_no_longer_claims_a_type_is_never_guessed() -> None:
    """The rule changed, so the sentence describing it had to. A docstring asserting
    "never guessed" over code that classifies is worse than no docstring - it is the next
    person's evidence for something that is not true."""
    said = (ROOT / "intake" / "bind.py").read_text(encoding="utf-8")
    header = said[: said.index('"""', 3)]
    assert "never guessed" not in header
    assert "convention always wins" in header


def test_the_engagement_folder_is_stripped_before_the_classifier_sees_the_path() -> None:
    """Every file under an engagement shares those segments, so they say nothing about any
    one document - and one of them is the client's name, which has no business reaching a
    cue table."""
    from intake.bind import _folders_under
    from intake.sweep import SweepTarget

    target = SweepTarget(
        engagement_id="E", watch_id="w", location="Clients/Henderson Manufacturing/2026",
        recipe="r",
    )
    assert _folders_under(
        "Clients/Henderson Manufacturing/2026/Board Minutes/2023.pdf", target
    ) == ("Board Minutes",)
