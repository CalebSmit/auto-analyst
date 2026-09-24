"""C57 - what a folder of real documents is allowed to be read as.

P96 was the first phase driven by a client's own files rather than by files this build
generated for itself, and generated files behave. Thirteen real ones matched three request
items; the causes were all in the reading, and the fixes touched two separate paths and
three separate vocabularies.

A checkpoint is owed because of the shape of that, not the size of it. There are **two
readers** - `look_at`, which a button calls, and `read_source`, which a run calls - and
each builds its own `Evidence`. P96 fixed the folder seam in the first and left it broken
in the second, which is this build's most repeated defect committed inside the phase that
was correcting an instance of it. And there are **three places that name a document type**:
the classifier, the Contract Registry and the request list. Any two of them can agree while
the third drifts, and the symptom is a button that appears to do nothing.

So this asks three things no single phase can:

1. The two readers say the same thing about the same file, folder included.
2. The three vocabularies close over each other.
3. Widening what can be recognised did not widen what can be recognised **wrongly**. That
   is the one worth the most: nine new classes and a rule that reads folders are nine new
   ways to be confidently wrong, and a wrongly matched file is a request that looks
   answered.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from guards.untrusted import UntrustedBoundary
from intake.readers import read_source
from intake.readers.classify import CLASSES, Evidence, classify
from intake.request_list import for_scope
from intake.store import IntakeRow
from intake.tracker import Tracker, look_at
from ops.events import EventBus
from ops.run_store import open_store
from ops.source_parse import SourceParseStore
from ports.storage.local_folder import LocalFolderStorage
from registries.contracts import ContractRegistry
from tests.p17.conftest import build_xlsx

ROOT = Path(__file__).resolve().parents[3]

#: One file, filed the way the real client filed it: a name that says what it is, inside a
#: folder that says the same thing, inside a folder whose name would mislead a reader that
#: weighted it equally.
FOLDER = "Historical and Forecasted Financial Statements"
NAME = "Consolidated Balance Sheets_Redacted.xlsx"

SHEET = [
    ["", "Consolidated Balance Sheet", ""],
    ["", "December 31, 2023", ""],
    ["Account", "2023", "%"],
    ["Cash", 1_250_000, 0.11],
    ["Total assets", 11_000_000, 1.0],
]


def through_a_run(path: str, filename: str, data: bytes) -> str:
    """Classify one file the way a run does, rather than the way a button does."""
    store = open_store("sqlite:///:memory:")
    bus = EventBus(store, contracts=ContractRegistry.load())
    store.start_run(
        run_id="r1",
        engagement_id="E",
        plan_hash="sha256:" + "0" * 64,
        versions={
            "model_pin": "x", "skills": [], "contracts": "1", "constraints": "1", "taxonomy": "t",
        },
    )
    row = IntakeRow(
        engagement_id="E", source_id="sha256:" + "1" * 64, filename=filename, path=path,
        watch_id="w", document_type=None, kind="spreadsheet", mime="x", bytes=len(data),
        source_version=1, received_at="2026-01-01T00:00:00Z", state="pending",
    )
    report = read_source(
        "r1", "E", row, data,
        store=store,
        parse_store=SourceParseStore(store),
        boundary=UntrustedBoundary(bus),
        bus=bus,
    )
    assert report.classification is not None
    return report.classification.document_type


# ================================================== 1. the two readers agree


def test_the_button_and_the_run_read_the_same_file_the_same_way(tmp_path: Path) -> None:
    """The seam P96 fixed twice, because the first fix left the second path broken.

    Held on a file **only the folder can identify**. A balance sheet in a forecast folder
    would have been the obvious case and is the wrong one: its name says what it is, so both
    readers get it right whether or not either can see a folder, and the test passes without
    asking anything. `2023.xlsx` says nothing at all. If either reader drops the folder, that
    reader says `other` and the two disagree.
    """
    data = build_xlsx({"Sheet1": [["", 1, 2], ["", 3, 4]]})
    (tmp_path / "Trial Balance").mkdir()
    (tmp_path / "Trial Balance" / "2023.xlsx").write_bytes(data)

    by_button = look_at(LocalFolderStorage(tmp_path))
    assert len(by_button) == 1
    by_run = through_a_run("Trial Balance/2023.xlsx", "2023.xlsx", data)

    assert by_button[0].kind == by_run == "trial_balance"


def test_neither_reader_lets_the_folder_outvote_the_file(tmp_path: Path) -> None:
    """A file whose name and folder say different things, so that one of them has to lose.

    The client's real folder was the gentler version of this - `Forecasted` in a folder over
    `Balance Sheets` in a name - and this is the same question asked where the two cannot
    both be satisfied. The file wins: a folder is true of everything in it and a name is
    about this file.
    """
    data = build_xlsx({"Sheet1": [["", 1], ["", 2]]})
    (tmp_path / "Board Minutes").mkdir()
    (tmp_path / "Board Minutes" / "Trial Balance 2023.xlsx").write_bytes(data)

    by_button = look_at(LocalFolderStorage(tmp_path))
    by_run = through_a_run(
        "Board Minutes/Trial Balance 2023.xlsx", "Trial Balance 2023.xlsx", data
    )
    assert by_button[0].kind == by_run == "trial_balance"


def test_both_readers_take_the_folder_from_the_same_place_in_the_path(tmp_path: Path) -> None:
    """A run's path and a button's path are built by different code. The failure this rules
    out is subtle and would look like nothing: one reader counting the watched root as a
    folder, so that every file in a watch called `Financial Statements` classifies as one."""
    data = build_xlsx({"S": [["Account", "Debit", "Credit"], ["Cash", 1, 0]]})
    deep = tmp_path / "Board Minutes"
    deep.mkdir()
    (deep / "2023.pdf").write_bytes(b"%PDF-1.4\n")

    assert look_at(LocalFolderStorage(tmp_path))[0].kind == "board_minutes"
    # The run path, given only a bare filename by a port that does not expose folders.
    assert through_a_run("TB.xlsx", "TB.xlsx", data) == "trial_balance"


# ================================================== 2. the three vocabularies close


def _list_items() -> list[dict]:
    loaded = yaml.safe_load(
        (ROOT / "intake" / "request_lists" / "valuation-non-esop.yaml").read_text(encoding="utf-8")
    )
    return loaded["items"]


def test_the_classifier_the_registry_and_the_request_list_close_over_each_other() -> None:
    """Three files can drift pairwise and each pair looks fine. The registry owns the
    vocabulary; the classifier may not produce a type it does not declare, and the list may
    not wait for one nothing produces."""
    registry = yaml.safe_load((ROOT / "contracts" / "registry.yaml").read_text(encoding="utf-8"))
    declared = {t["id"] for t in registry["intake_document_types"]}

    assert declared <= set(CLASSES), sorted(declared - set(CLASSES))
    asked_for = {cls for item in _list_items() for cls in (item.get("answered_by") or [])}
    assert asked_for <= set(CLASSES), sorted(asked_for - set(CLASSES))

    # Everything the registry declares is either asked for by the list or belongs to a
    # division this list is not for. Named rather than waved at, so that adding a type and
    # forgetting the list is a failure rather than a silence.
    for a_plan_types_only in ("participant_census", "plan_document"):
        assert a_plan_types_only in declared
    unasked = declared - asked_for - {"participant_census", "plan_document", "ddr_response",
                                      "request_schedule"}
    assert not unasked, f"declared and nothing asks for them: {sorted(unasked)}"


def test_every_class_a_valuation_receives_is_masked_by_default() -> None:
    """The nine types P96 added have the highest concentration of names per page in the
    registry - minutes name directors, a stockholder list is names against holdings, a
    roster names employees - and they arrived together, which is how a default gets set
    once and inherited nine times."""
    registry = yaml.safe_load((ROOT / "contracts" / "registry.yaml").read_text(encoding="utf-8"))
    for entry in registry["intake_document_types"]:
        assert entry["privacy_class"] == "masked_only", entry["id"]


# ================================================== 3. wider, not looser


@pytest.mark.parametrize(
    "name",
    [
        "scan0001.pdf",
        "IMG_20240317.jpg",
        "holiday photos.zip",
        "Document1.docx",
        "Copy of Copy of untitled.xlsx",
        "notes.txt",
        # The near misses. Each contains a word a cue uses and is not the document.
        "Minutes of the safety committee_Redacted.pdf",
        "Customer service training manual.pdf",
    ],
)
def test_a_file_that_says_nothing_still_says_nothing(name: str) -> None:
    """Nine new classes and a folder rule are nine new ways to be confidently wrong. The
    answer "other" is a first-class outcome here and routes to a person; what must not
    happen is a file acquiring a type because the vocabulary got bigger.

    `Minutes of the safety committee` is the one to watch: it carries "minutes" and is not
    board minutes, and it is exactly the sort of thing a firm has a folder of.
    """
    found = classify(Evidence(filename=name))
    assert found.document_type == "other", (name, found.scores)


def test_a_folder_alone_satisfies_a_request_only_as_an_inference(tmp_path: Path) -> None:
    """A folder is the weakest evidence the classifier accepts, and A.3 is an essential item
    somebody is relying on being chased.

    The first version of this test wrapped its assertions in `if status == "provided"`, so a
    folder that stopped matching altogether would have passed it silently - the defect this
    repo is named for. It asserts the match now, and then asserts the two things that make
    the match safe: it is marked an inference rather than a filed reference, and it names the
    file it came from so a person can check it in one click.
    """
    (tmp_path / "Trial Balance").mkdir()
    (tmp_path / "Trial Balance" / "2023.xlsx").write_bytes(build_xlsx({"S": [["", 1]]}))
    tracker = Tracker(for_scope("valuation/non-esop"), look_at(LocalFolderStorage(tmp_path)), {})
    rows = {str(row.item.ref): row for row in tracker.report_rows()}

    a3 = rows["A.3"]
    assert a3.item.essential
    assert a3.status.value == "provided"
    assert a3.inferred, "a folder is an inference and must not read as a filed reference"
    assert any("2023.xlsx" in e for e in a3.evidence), "provided with nothing to check it by"


def test_one_document_does_not_answer_half_the_request_list(tmp_path: Path) -> None:
    """The shape a generous classifier would produce, asked of one file rather than eight.

    Eight files answering eight items cannot distinguish a good classifier from a loose one,
    because the file count caps the answer either way. One file can: if a single set of board
    minutes marks four items provided, the widening has gone wrong, and a tracker reporting a
    nearly-complete engagement on a nearly-empty folder is worse than no tracker.
    """
    (tmp_path / "2024 Board Minutes_Redacted.pdf").write_bytes(b"%PDF-1.4\n")
    tracker = Tracker(for_scope("valuation/non-esop"), look_at(LocalFolderStorage(tmp_path)), {})
    counts = tracker.report()["counts"]
    assert counts["provided"] == 1, tracker.report()
    provided = [str(r.item.ref) for r in tracker.report_rows() if r.status.value == "provided"]
    assert provided == ["B.5"], provided


def test_the_whole_real_folder_still_leaves_most_of_the_list_outstanding(tmp_path: Path) -> None:
    """Thirteen documents answer twelve of forty-six items. The rest of the list is the
    point: a folder missing every tax return, the general ledger, every contract and every
    legal matter must read as an engagement that has barely started."""
    for folder, name in [
        ("Board Minutes", "2024 Board Minutes_Redacted.pdf"),
        ("", "Org Chart_Redacted.pdf"),
        ("", "List of Competitors_Redacted.pdf"),
        ("Stockholder list", "List of Stockholders_Redacted.pdf"),
        ("", "Top 15 Customers 2021 - 2024 YTD_Redacted.xlsx"),
        ("", "Capital Expenditures_Redacted.xlsx"),
        ("", "Employee Count_Redacted.xlsx"),
        ("", "Nonrecurring Income Expenses_Redacted.pdf"),
    ]:
        target = tmp_path / folder / name if folder else tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"%PDF-1.4\n" if name.endswith(".pdf") else b"x")

    tracker = Tracker(for_scope("valuation/non-esop"), look_at(LocalFolderStorage(tmp_path)), {})
    counts = tracker.report()["counts"]
    assert counts["provided"] == 8, counts
    assert counts["outstanding"] > 30, counts

    outstanding = {
        str(row.item.ref) for row in tracker.report_rows() if row.status.value == "outstanding"
    }
    # Nothing in that folder is a tax return, a ledger, a loan agreement or a lawsuit.
    for nobody_sent in ("A.5", "A.4", "F.3", "G.1"):
        assert nobody_sent in outstanding, nobody_sent
