"""P94 - A request list when nobody wrote one.

P68 built the sections, the references, the three statuses and the coverage, and left the
items out on purpose: the only real list in hand belonged to a client. That was right about
that list, and it left the machinery unable to start - nothing in the tree could produce a
request list, so nothing could track one.

Two things are being held here. That a new engagement gets a list at all, and that the
list it gets is honest about being a guess: a coverage report against something somebody
invented and one against the firm's own list are different sentences, and only one of them
is worth acting on without checking.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from intake.readers.classify import CLASSES
from intake.request_list import (
    BY_KIND,
    BY_REFERENCE,
    DEFAULT_LISTS,
    SECTIONS,
    STARTING_POINT,
    THE_FIRM_S_OWN,
    Arrived,
    ItemRef,
    RequestItem,
    RequestList,
    Status,
    for_scope,
    load_list,
)
from tests.conftest import needs_a_checkout

ROOT = Path(__file__).resolve().parents[2]
THE_LIST = DEFAULT_LISTS / "valuation-non-esop.yaml"


def rows(report: dict) -> dict[str, dict]:
    return {row["ref"]: row for row in report["items"]}


# ============================================================ a list, at all


def test_the_focus_division_starts_from_a_list() -> None:
    """The state this phase exists for: an engagement with nothing written for it, which
    is every new engagement and is also how the first real test will arrive."""
    found = for_scope("valuation/non-esop")
    assert found is not None
    assert len(found.items) > 30, "a request list of a dozen items is not a request list"


def test_a_division_with_no_list_of_its_own_inherits_its_practice_s(tmp_path: Path) -> None:
    """Shown on a tree built for the purpose rather than by writing into
    `intake/request_lists/` and taking it away again - a test that edits the repo is a
    test that can leave the repo edited, and this project has lost committed records that
    way before."""
    (tmp_path / "valuation.yaml").write_text(
        yaml.safe_dump({"name": "valuation", "items": [{"ref": "A.1", "text": "anything"}]}),
        encoding="utf-8",
    )
    found = for_scope("valuation/esop", tmp_path)
    assert found is not None and found.name == "valuation"
    assert for_scope("tax/compliance", tmp_path) is None, "and it does not fall further"


def test_a_division_nobody_has_written_one_for_gets_nothing() -> None:
    """None is the answer, not another division's list. A request list is what the client
    is asked for, and sending the wrong one is worse than sending none."""
    assert for_scope("tax/compliance") is None


# ============================================================ honest about being a guess


def test_the_default_list_says_it_is_a_starting_point() -> None:
    found = for_scope("valuation/non-esop")
    assert found is not None
    assert found.origin == STARTING_POINT
    assert found.is_a_starting_point


def test_every_report_carries_where_the_list_came_from() -> None:
    """Not left to be remembered. "Nine of twenty provided" reads the same whether the
    list was the firm's or invented, and only one of those is worth acting on unchecked."""
    found = for_scope("valuation/non-esop")
    assert found is not None
    report = found.report([])
    assert report["origin"] == STARTING_POINT
    assert report["is_a_starting_point"] is True


def test_a_registered_list_is_not_marked_as_a_guess(tmp_path: Path) -> None:
    """The firm's own list loads as the firm's own, and the two never silently mix: a
    list is one or the other, and `load_list` has no way to produce a blend."""
    path = tmp_path / "real.yaml"
    path.write_text(
        yaml.safe_dump({"name": "the firm's", "items": [{"ref": "A.1", "text": "statements"}]}),
        encoding="utf-8",
    )
    assert load_list(path).origin == THE_FIRM_S_OWN
    assert not load_list(path).is_a_starting_point


def test_the_file_says_in_its_own_words_that_it_is_not_the_firm_s() -> None:
    """A person opening the YAML is the one who needs to know."""
    document = yaml.safe_load(THE_LIST.read_text(encoding="utf-8"))
    assert "not the firm's own list" in document["provenance"].lower()


# ============================================================ it owes nothing to a client


def test_the_default_list_names_nobody_the_register_knows() -> None:
    """The real reason this list had to be written rather than copied. `interview.py scan`
    polices what leaves `knowledge/`; this asks the same question of a file that ships.
    """
    needs_a_checkout("the identifier register")
    register = ROOT / "knowledge" / "identifiers.txt"
    names = [
        line.strip()
        for line in register.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]
    assert names, "the register is empty, so this test is asking nothing"
    text = THE_LIST.read_text(encoding="utf-8").lower()
    assert not [n for n in names if n.lower() in text]


def test_every_item_is_generic_enough_to_be_asked_of_anybody() -> None:
    """Checked the only way a test can: no digits that would be a year, an amount or an
    account number, which is what a copied item would carry."""
    import re

    found = for_scope("valuation/non-esop")
    assert found is not None
    for item in found.items:
        assert not re.search(r"\b(19|20)\d{2}\b", item.text), item.text
        assert not re.search(r"[$£€]\s?\d", item.text), item.text


# ============================================================ what the list has to say


def test_the_sections_are_the_firm_s_seven_and_nothing_else() -> None:
    found = for_scope("valuation/non-esop")
    assert found is not None
    assert {i.ref.section for i in found.items} == set(SECTIONS)


def test_the_historicals_are_marked_essential() -> None:
    """The analyst's own distinction: they are the gate the whole job waits on, and most
    of the list is not."""
    found = for_scope("valuation/non-esop")
    assert found is not None
    essential = {str(i.ref) for i in found.essential}
    assert {"A.1", "A.2", "A.3"} <= essential
    assert len(essential) < len(found.items) / 3, "if most of it is essential, none of it is"


def test_answered_by_only_names_classes_the_classifier_can_produce() -> None:
    """A typo here would be silent: the item would simply never match, and would sit
    outstanding for ever while the document that answers it was sitting in the folder."""
    found = for_scope("valuation/non-esop")
    assert found is not None
    named = {kind for item in found.items for kind in item.answered_by}
    assert named, "nothing is matched by kind, so a pile of ordinary filenames tracks nothing"
    assert named <= set(CLASSES), sorted(named - set(CLASSES))


def test_nothing_is_answered_by_other() -> None:
    """`other` means the classifier read it and recognised nothing in particular. An item
    that accepted it would be satisfied by any unreadable file in the folder."""
    found = for_scope("valuation/non-esop")
    assert found is not None
    assert not [i for i in found.items if "other" in i.answered_by]


# ============================================================ matching, and how it is said


def list_of(*items: tuple[str, str, tuple[str, ...]]) -> RequestList:
    return RequestList(
        [
            RequestItem(ItemRef(ref[0], int(ref.split(".")[1])), text, answered_by=kinds)
            for ref, text, kinds in items
        ],
        name="test",
    )


def test_a_file_that_carries_a_reference_is_matched_by_it() -> None:
    made = list_of(("B.6", "prior appraisals", ()))
    row = rows(made.report([Arrived.at("inbox/B.6 prior appraisal.pdf")]))["B.6"]
    assert row["status"] == Status.PROVIDED.value
    assert row["matched_by"] == BY_REFERENCE
    assert row["inferred"] is False


def test_a_file_the_classifier_recognised_is_matched_by_kind_and_flagged() -> None:
    """What makes a pile of ordinary filenames trackable. A client sends
    `TB 2025 final.xlsx`, not `A. Financial Records/A.3/`."""
    made = list_of(("A.3", "trial balance", ("trial_balance",)))
    row = rows(made.report([Arrived.at("inbox/TB 2025 final.xlsx", kind="trial_balance")]))["A.3"]
    assert row["status"] == Status.PROVIDED.value
    assert row["matched_by"] == BY_KIND
    assert row["inferred"] is True, "the tool's reading of a document, not somebody's word"


def test_a_reference_wins_over_a_kind() -> None:
    """Somebody filed it there. That is a statement about the file, and this is not the
    place to argue with it."""
    made = list_of(("A.3", "trial balance", ("trial_balance",)))
    landed = [Arrived.at("inbox/A.3 whatever it is.pdf", kind="tax_return")]
    assert rows(made.report(landed))["A.3"]["matched_by"] == BY_REFERENCE


def test_a_file_naming_only_a_section_still_satisfies_nothing() -> None:
    """P68's rule, unchanged: "something from section A turned up" is not "A.3 has been
    provided", and a phase that added kind matching could easily have lost it."""
    made = list_of(("A.3", "trial balance", ("trial_balance",)))
    landed = [Arrived.at("inbox/A. Financial Records/scan.pdf")]
    assert rows(made.report(landed))["A.3"]["status"] == Status.OUTSTANDING.value


def test_a_file_nobody_has_read_matches_nothing_by_kind() -> None:
    """`kind=None` is "nobody looked", which is not "it is nothing". Treating the two the
    same would have an unread folder report as fully outstanding with confidence."""
    made = list_of(("A.3", "trial balance", ("trial_balance",)))
    assert rows(made.report([Arrived.at("inbox/TB.xlsx")]))["A.3"]["status"] == (
        Status.OUTSTANDING.value
    )


def test_one_document_can_answer_two_items_and_both_are_flagged() -> None:
    """A five-year set of financial statements matches both "the last five fiscal years"
    and "interim year to date", and only one of those is true. Marking one arbitrarily
    would be wrong half the time with nothing to show for it; marking both, flagged, puts
    it in front of the person who can settle it."""
    made = list_of(
        ("A.1", "five fiscal years", ("financial_statements",)),
        ("A.2", "interim year to date", ("financial_statements",)),
    )
    report = made.report([Arrived.at("inbox/FS 2021-2025.pdf", kind="financial_statements")])
    assert report["inferred"] == 2
    for ref in ("A.1", "A.2"):
        assert rows(report)[ref]["inferred"] is True


def test_not_applicable_is_never_overridden_by_something_arriving() -> None:
    """A person said this one does not apply. A file turning up in the folder is not an
    argument with that."""
    made = RequestList(
        [RequestItem(ItemRef("D", 5), "collective bargaining agreements")],
        not_applicable=[ItemRef("D", 5)],
        name="test",
    )
    landed = [Arrived.at("inbox/D.5 something.pdf")]
    assert rows(made.report(landed))["D.5"]["status"] == Status.NOT_APPLICABLE.value


# ============================================================ the report itself


def test_the_report_counts_what_is_still_owed_and_flags_the_essential() -> None:
    """The follow-up list. An outstanding item that is essential is a different phone call
    from an outstanding item that is not."""
    found = for_scope("valuation/non-esop")
    assert found is not None
    report = found.report([Arrived.at("inbox/TB.xlsx", kind="trial_balance")])
    assert report["counts"][Status.PROVIDED.value] == 1
    assert "A.3" not in report["essential_outstanding"]
    assert "A.1" in report["essential_outstanding"]


def test_evidence_is_the_path_so_provided_can_be_checked() -> None:
    found = for_scope("valuation/non-esop")
    assert found is not None
    report = found.report([Arrived.at("inbox/TB 2025.xlsx", kind="trial_balance")])
    assert rows(report)["A.3"]["evidence"] == ["inbox/TB 2025.xlsx"]


# ============================================================ what a bad list does


def test_a_list_with_an_unreadable_reference_is_refused(tmp_path: Path) -> None:
    """Not skipped. An item silently dropped is an item nobody chases."""
    path = tmp_path / "bad.yaml"
    path.write_text(
        yaml.safe_dump({"items": [{"ref": "Z.9", "text": "something"}]}), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="request item reference"):
        load_list(path)


def test_a_list_with_no_items_is_refused(tmp_path: Path) -> None:
    """An empty list would report everything as provided, because there is nothing
    outstanding - which is the most flattering possible way to be wrong."""
    path = tmp_path / "empty.yaml"
    path.write_text(yaml.safe_dump({"name": "nothing", "items": []}), encoding="utf-8")
    with pytest.raises(ValueError, match="no request items"):
        load_list(path)
