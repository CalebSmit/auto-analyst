"""P96 - the documents a valuation engagement really receives.

The first real client folder reached this build on 2026-09-21: thirteen files, redacted by
the firm, from a live non-ESOP valuation. The tracker matched three of them. Nothing in the
tracking was wrong; everything wrong was in the reading.

Three causes, and the third is the one worth remembering.

1. The classifier's vocabulary was the ESOP set. A non-ESOP valuation is sent board
   minutes, an org chart, a customer schedule, a competitor list, a capex history and an
   employee count, and none of those existed as a document type.
2. The client's own folder names - `Board Minutes/`, `Stockholder list/` - were discarded
   before anything looked at them. A client who files a document under `Board Minutes` has
   said what it is in the plainest way available.
3. **Every cue ending in `\\b` silently missed every file whose name carried a suffix.**
   Underscore is a word character, so `minutes\\b` does not match `Minutes_Redacted`. The
   whole table failed at once, on the naming convention every one of the thirteen files
   used, and the failure looked exactly like "no cue matched".

And a fourth, found on the way: the tracker read its confidence off `found.score`, an
attribute `Classification` has never had, behind a `getattr` default. Every confidence it
ever reported was 0.0 - the correct matches as uncertain as the wrong ones.

What this file holds is the reading, not the tracking. The rule underneath it is that **a
wrong match is worse than an unmatched file**: an unmatched file is on a list somebody
reads, and a wrongly matched one is a request that looks answered.
"""

from __future__ import annotations

import ast
from pathlib import Path

import docx
import pytest
import yaml

from intake.readers.classify import CLASSES, FOLDER_WEIGHT, Evidence, classify
from intake.request_list import for_scope
from intake.tracker import Tracker, look_at
from ports.storage.local_folder import LocalFolderStorage

ROOT = Path(__file__).resolve().parents[2]
LIST = ROOT / "intake" / "request_lists" / "valuation-non-esop.yaml"


def a_file(name: str, *folders: str, rows: list[str] | None = None) -> Evidence:
    return Evidence(filename=name, first_rows=rows or [], folders=list(folders))


# ===================================================================== the underscore rule


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("2024 Board Minutes_Redacted.pdf", "board_minutes"),
        ("Org Chart_Redacted.pdf", "org_chart"),
        ("List of Competitors_Redacted.pdf", "competitor_list"),
        ("Capital Expenditures_Redacted.xlsx", "capex_schedule"),
        ("List of Stockholders_Redacted.pdf", "stockholder_list"),
        ("Nonrecurring Income Expenses_Redacted.pdf", "nonrecurring_items"),
        ("Employee Count_Redacted.xlsx", "employee_roster"),
        ("Top 15 Customers 2021 - 2024 YTD_Redacted.xlsx", "customer_detail"),
        # The suffixes a document picks up on its way through a firm, which is the general
        # case the redaction suffix is one instance of.
        ("Org Chart_final.pdf", "org_chart"),
        ("Org Chart_v2_FINAL.pdf", "org_chart"),
        ("Org_Chart.pdf", "org_chart"),
        ("board_minutes_2024.pdf", "board_minutes"),
    ],
)
def test_a_suffix_on_the_name_does_not_hide_the_document(name: str, expected: str) -> None:
    """The defect that cost twelve of thirteen matches. `\\b` between `s` and `_` is not a
    boundary, so a cue that ends in one misses every name with a suffix - and firms suffix
    everything."""
    assert classify(a_file(name)).document_type == expected


def test_the_underscore_rule_reads_a_name_as_words_rather_than_widening_every_cue() -> None:
    """Held on the mechanism, because the alternative fix is the one that rots: widening each
    `\\b` to `(?:\\b|_)` is forty edits today and has to be remembered by whoever adds the
    forty-first."""
    source = (ROOT / "intake" / "readers" / "classify.py").read_text(encoding="utf-8")
    assert "(?:\\b|_)" not in source, "the per-pattern fix is the one that rots"
    assert 'name.replace("_", " ")' in source


# ======================================================================= the folder is evidence


def test_a_folder_name_alone_can_say_what_a_file_is() -> None:
    """`Board Minutes/2023.pdf` is a scan with no text layer and a name that says nothing.
    The client still told us what it is."""
    found = classify(a_file("2023.pdf", "Board Minutes"))
    assert found.document_type == "board_minutes"
    assert any("folder" in reason for reason in found.reasons)


def test_the_tracker_carries_the_folder_to_the_classifier(tmp_path: Path) -> None:
    """`classify` can read a folder only if something hands it one, and until P96 the path
    called `Path(path).name` and threw the rest away. Held separately from the classifier's
    own folder tests because those would all still pass with this wire cut - and did: the
    thirteen real filenames are self-describing enough that the end-to-end run stayed green
    with `folders=[]`, which is exactly how a seam gets left unjoined.
    """
    minutes = tmp_path / "Board Minutes"
    minutes.mkdir()
    (minutes / "2023.pdf").write_bytes(b"%PDF-1.4\n")
    seen = look_at(LocalFolderStorage(tmp_path))
    assert [s.kind for s in seen] == ["board_minutes"]


def test_the_run_path_carries_the_folder_too() -> None:
    """Two places build an `Evidence`, and fixing one is how this build's most repeated
    defect happens. `read_source` is the path a real run takes; the tracker is the path a
    button takes. `IntakeRow` has carried the full path since P12 and `read_source` used
    only the last part of it."""
    from intake.readers import _folders_of

    assert _folders_of("Board Minutes/2023.pdf", "2023.pdf") == ["Board Minutes"]
    assert _folders_of("a/b/c.pdf", "c.pdf") == ["a", "b"]
    # A port that hands back the bare name, which several do.
    assert _folders_of("2023.pdf", "2023.pdf") == []
    assert _folders_of("", "2023.pdf") == []

    source = (ROOT / "intake" / "readers" / "__init__.py").read_text(encoding="utf-8")
    assert "folders=_folders_of(row.path, row.filename)" in source


def test_a_folder_is_worth_less_than_the_name_on_the_file() -> None:
    assert FOLDER_WEIGHT < 1.0
    named = classify(a_file("Org Chart.pdf")).confidence
    filed = classify(a_file("something.pdf", "Org Chart")).confidence
    assert filed < named, "a folder is true of everything in it; a name is about this file"


def test_the_forecast_folder_does_not_turn_its_balance_sheets_into_forecasts() -> None:
    """The real folder is `Historical and Forecasted Financial Statements/` and it holds
    both. Scored at full weight, the word "Forecasted" in the folder would make every file
    in it a forecast - which is P38's own bug arriving by a new road: projected years
    entering the historical table and satisfying a recipe waiting for the real ones.
    """
    for name in (
        "Consolidated Balance Sheets_Redacted.xlsx",
        "Consolidated Income Statements_Redacted.xlsx",
    ):
        found = classify(a_file(name, "Historical and Forecasted Financial Statements"))
        assert found.document_type == "financial_statements", (name, found.scores)
    projections = classify(
        a_file("Projections_Redacted.xlsx", "Historical and Forecasted Financial Statements")
    )
    assert projections.document_type == "forecast", "the file that IS the forecast still is"


def test_p38s_rule_still_holds_when_the_file_itself_is_forward_looking() -> None:
    """The demotion above is narrow on purpose: it fires only when the folder is the sole
    forward-looking cue. A file whose own name or contents say forecast is still a forecast,
    which is the whole of P38."""
    found = classify(
        Evidence("Budget FY26.xlsx", headers=["Income statement", "Revenue", "Net income"])
    )
    assert found.document_type == "forecast"


# ======================================================== the confidence that was always zero


def test_the_tracker_reports_the_classifiers_own_confidence(tmp_path: Path) -> None:
    """`float(getattr(found, "score", 0.0) or 0.0)` - and `Classification` has never had a
    `score`. The default fired every time, so every confidence this tracker ever reported
    was 0.0 and a certain match read exactly like a doubtful one."""
    (tmp_path / "Org Chart.pdf").write_bytes(b"%PDF-1.4\n")
    seen = look_at(LocalFolderStorage(tmp_path))
    assert len(seen) == 1
    assert seen[0].kind == "org_chart"
    assert seen[0].confidence > 0.0, "a confident match must not report as certain as nothing"
    assert seen[0].confidence == classify(a_file("Org Chart.pdf")).confidence


def test_the_confidence_is_not_read_off_an_attribute_that_may_not_exist() -> None:
    """The bug was invisible because `getattr` was given a default. An AttributeError would
    have said so on the first run; the default said 0.0 for twenty phases."""
    source = (ROOT / "intake" / "tracker.py").read_text(encoding="utf-8")
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "getattr":
            assert len(node.args) < 3, (
                "a getattr with a default on the classification is how the last one hid"
            )


def test_an_unreadable_file_still_reports_no_kind_rather_than_a_confident_nothing() -> None:
    """The distinction the confidence fix must not blur: nobody looked, versus looked and
    found nothing in particular. Only the second may ever satisfy a request item."""
    found = classify(a_file("scan0001.pdf"))
    assert found.document_type == "other"
    assert found.confidence == 0.0


# ================================================== what must not be matched to what


def test_the_write_up_is_not_read_as_a_forecast() -> None:
    """The one false positive the real folder produced before P96. The firm's own sources-of
    -information and company-overview section quotes the forecast it relied on, so it scored
    on the forecast cues and was filed as one - which would have satisfied A.6 with a
    narrative and left the actual projections unaccounted for."""
    overview = a_file(
        "Overview and notes.docx",
        rows=[
            "SOURCES OF INFORMATION",
            "Forecast for the fiscal years ending December 31, 2024 through December 31, 2028;",
            "Internal financial statements for the fiscal years ended December 31, 2019",
            "COMPETITIVE POSITION",
            "Management indicated the following:",
        ],
    )
    assert classify(overview).document_type == "business_overview"


def test_a_capex_schedule_does_not_satisfy_the_fixed_asset_register() -> None:
    """Both are plant and equipment and they are not the same request. E.3 is a balance at a
    date; A.13 is what was spent over a period. A person chasing one would not accept the
    other, so a tracker that marked E.3 answered by a capex file would have closed a request
    nobody had answered."""
    items = {i["ref_text"]: i for i in _items()}
    assert "capex_schedule" not in items["E.3"]["answered_by"]
    assert "capex_schedule" in items["A.13"]["answered_by"]


def test_an_employee_roster_is_not_a_plan_census() -> None:
    """`participant_census` is a plan filing's census and carries dates of birth and hours.
    Sharing a class would let a benefit-plan filing mark an operational request answered."""
    assert "employee_roster" in CLASSES and "participant_census" in CLASSES
    roster = classify(a_file("Employee Count.xlsx"))
    assert roster.document_type == "employee_roster"
    census = classify(
        Evidence("census.xlsx", headers=["Participant", "Date of birth", "Hours"])
    )
    assert census.document_type == "participant_census"


def test_a_stockholder_list_is_not_by_itself_a_cap_table() -> None:
    """It answers the holders and their shares and says nothing about options or warrants.
    It satisfies B.3 as far as it goes - which is why both are listed there - but it is a
    class of its own so that what it leaves out stays visible."""
    assert classify(a_file("List of Stockholders.pdf")).document_type == "stockholder_list"
    assert (
        classify(Evidence("owners.xlsx", headers=["Capitalization table", "Shares outstanding"]))
    ).document_type == "cap_table"
    items = {i["ref_text"]: i for i in _items()}
    assert set(items["B.3"]["answered_by"]) == {"cap_table", "stockholder_list"}


# ============================================================== the folder as it really arrived


#: Twelve of the thirteen files of the first real client folder, by name and folder only -
#: no contents, no figures and no client. The names say what kind of document each is and
#: nothing about whose it is, which `tools/interview.py scan` is the standing check on.
THE_REAL_FOLDER = {
    ("Board Minutes", "2023 Board Minutes_Redacted.pdf"): "board_minutes",
    ("Board Minutes", "2024 Board Minutes_Redacted.pdf"): "board_minutes",
    ("", "Capital Expenditures_Redacted.xlsx"): "capex_schedule",
    ("", "Employee Count_Redacted.xlsx"): "employee_roster",
    (
        "Historical and Forecasted Financial Statements",
        "Consolidated Balance Sheets_Redacted.xlsx",
    ): "financial_statements",
    (
        "Historical and Forecasted Financial Statements",
        "Consolidated Income Statements_Redacted.xlsx",
    ): "financial_statements",
    (
        "Historical and Forecasted Financial Statements",
        "Projections_Redacted.xlsx",
    ): "forecast",
    ("", "List of Competitors_Redacted.pdf"): "competitor_list",
    ("", "Nonrecurring Income Expenses_Redacted.pdf"): "nonrecurring_items",
    ("", "Org Chart_Redacted.pdf"): "org_chart",
    ("Stockholder list", "List of Stockholders_Redacted.pdf"): "stockholder_list",
    ("", "Top 15 Customers 2021 - 2024 YTD_Redacted.xlsx"): "customer_detail",
}

#: The thirteenth. `Overview and notes.docx` is not recognisable from its name, and this
#: says so rather than adding a cue for the word "overview" - which would be fitted to one
#: filename and would file every `Overview.docx` in the firm as a company write-up. It is
#: recognised from its section headings, which is what actually distinguishes a write-up
#: from a data file.
THE_WRITE_UP = "Overview and notes.docx"
THE_WRITE_UP_SAYS = [
    "SOURCES OF INFORMATION",
    "The relevant sources of information used in performing the valuation engagement include:",
    "COMPETITIVE POSITION",
    "RECENT DEVELOPMENTS AND OUTLOOK",
    "OTHER NOTES FROM CLIENT MEETINGS",
    "Management indicated the following:",
]


@pytest.mark.parametrize(("where", "expected"), sorted(THE_REAL_FOLDER.items()))
def test_every_file_in_the_real_folder_is_recognised(
    where: tuple[str, str], expected: str
) -> None:
    """From the name and the folder alone - no contents. That is the harder half of the
    problem and the half that was broken: three of these thirteen classified before P96."""
    folder, name = where
    found = classify(a_file(name, *([folder] if folder else [])))
    assert found.document_type == expected, (name, found.scores)


def test_the_write_up_needs_its_contents_and_its_name_is_not_enough() -> None:
    """Stated as a property rather than left as a gap. `Overview and notes.docx` could be
    anything, and a classifier that guessed from that name would be guessing."""
    assert classify(a_file(THE_WRITE_UP)).document_type == "other"
    assert classify(a_file(THE_WRITE_UP, rows=THE_WRITE_UP_SAYS)).document_type == (
        "business_overview"
    )


def test_every_class_the_real_folder_needed_answers_a_request_item() -> None:
    """A document type nothing asks for is a type that classifies a file and then leaves it
    on the unmatched sheet, which is where it started."""
    asked = {cls for item in _items() for cls in item["answered_by"]}
    for expected in {*THE_REAL_FOLDER.values(), "business_overview"}:
        assert expected in asked, f"{expected} is recognised and answers nothing"


# ================================================================ the list itself


def _items() -> list[dict]:
    loaded = yaml.safe_load(LIST.read_text(encoding="utf-8"))
    out = []
    for item in loaded["items"]:
        out.append({**item, "answered_by": item.get("answered_by") or [], "ref_text": item["ref"]})
    return out


def test_the_request_list_has_no_repeated_key() -> None:
    """Written because it happened, inside this phase, to me. A second `answered_by` under
    one item is not an error in YAML - the last one silently wins - so an edit that looked
    applied had been discarded, and the only symptom was one file staying unmatched."""

    class _NoDuplicates(yaml.SafeLoader):
        pass

    def _mapping(loader: yaml.SafeLoader, node: yaml.MappingNode) -> dict:
        seen: set = set()
        for key_node, _ in node.value:
            key = loader.construct_object(key_node)
            assert key not in seen, f"{key!r} appears twice in one item of {LIST.name}"
            seen.add(key)
        return loader.construct_mapping(node)

    _NoDuplicates.add_constructor(
        yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _mapping
    )
    yaml.load(LIST.read_text(encoding="utf-8"), Loader=_NoDuplicates)


def test_every_answered_by_names_a_class_the_classifier_can_produce() -> None:
    for item in _items():
        for cls in item["answered_by"]:
            assert cls in CLASSES, f"{item['ref_text']} expects {cls!r}, which is not a class"


def test_the_new_classes_are_declared_in_the_registry_that_owns_the_vocabulary() -> None:
    """The closed vocabulary is the Contract Registry's, not the classifier's. P17 holds the
    relationship; this says which side P96 had to change, because adding a class without
    declaring it is how the two drift."""
    registry = yaml.safe_load((ROOT / "contracts" / "registry.yaml").read_text(encoding="utf-8"))
    declared = {t["id"] for t in registry["intake_document_types"]}
    for added in (
        "board_minutes",
        "org_chart",
        "employee_roster",
        "customer_detail",
        "competitor_list",
        "capex_schedule",
        "nonrecurring_items",
        "stockholder_list",
        "business_overview",
    ):
        assert added in declared, added
        entry = next(t for t in registry["intake_document_types"] if t["id"] == added)
        assert entry["privacy_class"] == "masked_only", (
            f"{added} names people; nothing here is unmasked by default"
        )


# ================================================================ end to end, on the folder


def test_the_whole_folder_goes_from_three_matches_to_all_thirteen(tmp_path: Path) -> None:
    """The phase's own claim - thirteen of thirteen - run through `look_at` rather than
    `classify`, because the folder has to reach the classifier for any of the above to
    matter, and until P96 the path threw it away at `Path(path).name`."""
    for (folder, name), _ in THE_REAL_FOLDER.items():
        target = tmp_path / folder / name if folder else tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        # Empty but for a byte: the point is that the name and the folder are enough.
        target.write_bytes(b"%PDF-1.4\n" if name.endswith(".pdf") else b"x")

    # The thirteenth is a real .docx, because it is the one file whose name says nothing and
    # whose contents have to be opened for it to be recognised at all.
    document = docx.Document()
    for line in THE_WRITE_UP_SAYS:
        document.add_paragraph(line)
    document.save(tmp_path / THE_WRITE_UP)

    seen = look_at(LocalFolderStorage(tmp_path))
    assert len(seen) == len(THE_REAL_FOLDER) + 1
    by_name = {Path(s.path).name: s for s in seen}
    for (_, name), expected in THE_REAL_FOLDER.items():
        assert by_name[name].kind == expected, name
    assert by_name[THE_WRITE_UP].kind == "business_overview"

    tracker = Tracker(for_scope("valuation/non-esop"), seen, {})
    assert tracker.report()["unmatched_files"] == [], "every file answers something"
    provided = {row.item.ref for row in tracker.report_rows() if row.status.value == "provided"}
    assert len(provided) >= 12, sorted(str(r) for r in provided)
