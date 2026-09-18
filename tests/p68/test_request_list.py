"""P68: the request list, as the schedule documents arrive against.

The firm sends a due diligence request list and the same workbook tracks what came back.
Seven section groupings, stable across engagements; items inside them written per
engagement. Each section is also a folder in Box and ShareFile, and the firm writes item
references - `B.6`, `C.7`, `D.5` - as the names of the tabs carrying supporting data.

So a file's *section* is knowable from its path, which is better evidence than any cue in
its content, and it is a different question from what kind of document it is.

The test that matters most is
`test_a_file_naming_only_a_section_does_not_satisfy_an_item`: the tempting bug is to let
"something from section A turned up" close out "item A.3", which would report a client as
having provided something they have not.
"""

from __future__ import annotations

import pytest

from intake.request_list import (
    SECTIONS,
    Arrived,
    ItemRef,
    RequestItem,
    RequestList,
    Status,
    parse_ref,
    section_of,
)

LIST = RequestList.from_rows(
    [
        ("A.1", "Audited financial statements for the five fiscal years"),
        ("A.2", "Annual internally prepared financial statements for the five fiscal years"),
        ("A.6", "List of compensation paid to each owner for the past five years"),
        ("B.6", "Current shareholder list"),
        ("G.1", "A list of all suits, actions and arbitrations"),
    ]
)


# ------------------------------------------------------------------ the section vocabulary


def test_the_seven_sections_are_named() -> None:
    assert list(SECTIONS) == ["A", "B", "C", "D", "E", "F", "G"]
    assert SECTIONS["A"] == "Financial Records"
    assert SECTIONS["G"] == "Legal Matters"


@pytest.mark.parametrize(
    "path,expected",
    [
        ("Clients/Acme/2026/A. Financial Records/audited FY25.pdf", "A"),
        ("Clients/Acme/2026/B - Corporate Documents/bylaws.pdf", "B"),
        ("Clients/Acme/2026/C_Operational Matters/payor mix.xlsx", "C"),
        (r"Clients\Acme\2026\G. Legal Matters\suits.pdf", "G"),
        ("Clients/Acme/inbox/whatever.pdf", None),
        ("Clients/Acme/2026/Z. Something Else/file.pdf", None),
        ("", None),
    ],
)
def test_the_section_is_read_from_the_folder(path: str, expected: str | None) -> None:
    assert section_of(path) == expected


def test_a_path_naming_no_section_says_so_rather_than_guessing() -> None:
    """None is a real answer. A file dropped outside the lettered folders has no section,
    and saying so beats assigning one - the same reason an unclaimed folder is reported
    rather than bound to an engagement."""
    assert section_of("Clients/Acme/loose file.pdf") is None


def test_the_deeper_folder_wins() -> None:
    """`.../A. Financial Records/B.6/` is a B.6 tab filed under A. The more specific
    statement is the deeper one."""
    assert section_of("Clients/A. Financial Records/B.6/detail.xlsx") == "B"


# ------------------------------------------------------------------ item references


@pytest.mark.parametrize(
    "text,expected",
    [
        ("B.6", ItemRef("B", 6)),
        ("see D.5", ItemRef("D", 5)),
        ("E.1 & E.2", ItemRef("E", 1)),
        ("Tab C.7", ItemRef("C", 7)),
        ("A.16 appraisals", ItemRef("A", 16)),
        ("nothing here", None),
        ("H.1", None),
        ("B.", None),
        ("FY 22,23,YTD 24", None),
    ],
)
def test_an_item_reference_is_parsed_or_refused(text: str, expected: ItemRef | None) -> None:
    assert parse_ref(text) == expected


def test_a_reference_reads_as_the_firm_writes_it() -> None:
    assert str(ItemRef("B", 6)) == "B.6"
    assert ItemRef("A", 1).section_title == "Financial Records"


def test_references_sort_in_the_order_the_list_is_written() -> None:
    refs = sorted([ItemRef("B", 2), ItemRef("A", 10), ItemRef("A", 2)])
    assert [str(r) for r in refs] == ["A.2", "A.10", "B.2"]


# ------------------------------------------------------------------ coverage


def test_a_file_carrying_an_item_reference_provides_it() -> None:
    report = LIST.coverage([Arrived.at("Clients/Acme/A. Financial Records/A.1 audited.pdf")])
    by_ref = {str(c.item.ref): c for c in report}
    assert by_ref["A.1"].status is Status.PROVIDED
    assert by_ref["A.1"].evidence == ("Clients/Acme/A. Financial Records/A.1 audited.pdf",)
    assert by_ref["A.2"].status is Status.OUTSTANDING


def test_a_file_naming_only_a_section_does_not_satisfy_an_item() -> None:
    """The tempting bug. Something from section A turning up is not item A.1 having been
    provided, and reporting it as such tells the analyst a client has sent something they
    have not."""
    landed = Arrived.at("Clients/Acme/A. Financial Records/some statements.pdf")
    assert landed.section == "A"
    assert landed.ref is None
    assert all(c.status is Status.OUTSTANDING for c in LIST.coverage([landed]))


def test_not_applicable_is_its_own_answer() -> None:
    """The tracker's third column. An item nobody will ever provide is not outstanding
    for ever."""
    narrowed = RequestList(LIST.items, not_applicable=[ItemRef("G", 1)])
    by_ref = {str(c.item.ref): c.status for c in narrowed.coverage([])}
    assert by_ref["G.1"] is Status.NOT_APPLICABLE
    assert by_ref["A.1"] is Status.OUTSTANDING


def test_outstanding_is_the_follow_up_list_with_the_essential_first() -> None:
    items = [
        RequestItem(ItemRef("A", 1), "Audited statements", essential=True),
        RequestItem(ItemRef("A", 9), "Aged receivables"),
        RequestItem(ItemRef("B", 2), "Bylaws"),
    ]
    waiting = RequestList(items).outstanding([])
    assert [str(c.item.ref) for c in waiting] == ["A.1", "A.9", "B.2"]
    assert waiting[0].item.essential


def test_coverage_reads_in_the_order_the_list_is_written() -> None:
    assert [str(c.item.ref) for c in LIST.coverage([])] == ["A.1", "A.2", "A.6", "B.6", "G.1"]


def test_a_malformed_reference_is_refused_when_the_list_is_loaded() -> None:
    with pytest.raises(ValueError, match="not a request item reference"):
        RequestList.from_rows([("nonsense", "something")])


# ------------------------------------------------------------------ the two axes stay apart


def test_nothing_here_classifies_a_document_type() -> None:
    """Section and type are different questions and both are kept. If this module ever
    starts answering the second, a file's type would depend on which folder somebody
    dropped it in."""
    source = (__import__("pathlib").Path(__file__).parents[2] / "intake/request_list.py").read_text(
        encoding="utf-8"
    )
    body = source.split('"""', 2)[2]
    for leaked in ("trial_balance", "financial_statements", "document_type", "classify("):
        assert leaked not in body, f"{leaked} is the classifier's business, not this module's"
