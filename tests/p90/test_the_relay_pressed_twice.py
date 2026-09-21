"""P90 - The relay, which may be pressed twice.

Power Automate does this automatically and stays outside the boundary. The button is the
backup, which means both will sometimes act on the same files - so nearly every test here
is about converging with the other copier rather than about copying.

Most of them run folder-to-folder. That is not a shortcut: the relay is written against
two protocols and neither of them is Box, so the behaviour that matters is exercisable
with no network anywhere in it. The tests that need Box's own semantics - its sha1, its
folder creation, its 409 - say Box, and say what they do not prove.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

import pytest

from intake.relay import FAILED, Moved, RelayReport, relay
from ports.storage import COPIED, RESENT, SKIPPED, Deposit, ReceivingStorage
from ports.storage.local_folder import LocalFolderStorage
from ports.storage.sharefile import ShareFileStorage
from registries.errors import UNREADABLE_FILE, RegistryError, diagnose
from tests.fake_sharefile import FakeShareFile

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def source(tmp_path: Path) -> LocalFolderStorage:
    out = tmp_path / "from"
    (out / "statements").mkdir(parents=True)
    (out / "TB_FY25.xlsx").write_bytes(b"trial balance")
    (out / "statements" / "BS.pdf").write_bytes(b"balance sheet")
    return LocalFolderStorage(out)


@pytest.fixture
def destination(tmp_path: Path) -> LocalFolderStorage:
    out = tmp_path / "to"
    out.mkdir()
    return LocalFolderStorage(out)


def outcomes(report: RelayReport) -> dict[str, str]:
    return {m.path: m.outcome for m in report.moves}


# ============================================================ pressed twice


def test_the_first_press_copies_everything(source: Any, destination: Any) -> None:
    report = relay(source, destination)
    assert outcomes(report) == {"TB_FY25.xlsx": COPIED, "statements/BS.pdf": COPIED}
    assert report.complete
    assert (destination.root / "statements" / "BS.pdf").read_bytes() == b"balance sheet"


def test_the_second_press_copies_nothing_and_says_so(source: Any, destination: Any) -> None:
    """The case that actually happens: he presses Update, then presses it again because
    he is not sure the first one did anything."""
    relay(source, destination)
    again = relay(source, destination)
    assert set(outcomes(again).values()) == {SKIPPED}
    assert again.counts[COPIED] == 0
    assert again.arrived == (), "nothing arrived, because it was all already there"


def test_a_file_power_automate_already_moved_is_left_alone(
    source: Any, destination: Any
) -> None:
    """The whole design in one test. The other copier got there first with the same bytes;
    the relay must not produce a second copy under a mangled name."""
    (destination.root / "TB_FY25.xlsx").write_bytes(b"trial balance")
    report = relay(source, destination)
    assert outcomes(report)["TB_FY25.xlsx"] == SKIPPED
    assert sorted(p.name for p in destination.root.iterdir()) == ["TB_FY25.xlsx", "statements"]


def test_skipped_is_not_counted_as_arrived(source: Any, destination: Any) -> None:
    """`arrived` is what the request-list tracker reads. Counting a skip would tell it
    something turned up today that turned up last week."""
    relay(source, destination)
    assert relay(source, destination).arrived == ()


# ============================================================ a re-send


def test_different_bytes_under_the_same_name_are_reported_not_overwritten(
    source: Any, destination: Any
) -> None:
    """A client sending a second version is information, not a collision to resolve
    silently. The person has to see it, and the first copy has to survive."""
    relay(source, destination)
    (source.root / "TB_FY25.xlsx").write_bytes(b"trial balance, corrected")
    again = relay(source, destination)

    assert outcomes(again)["TB_FY25.xlsx"] == RESENT
    assert (destination.root / "TB_FY25.xlsx").read_bytes() == b"trial balance, corrected"
    kept = [p.name for p in destination.root.iterdir() if p.name.startswith("TB_FY25.v")]
    assert kept, "the version that was there is kept, not written over"


def test_a_resend_counts_as_arrived(source: Any, destination: Any) -> None:
    relay(source, destination)
    (source.root / "TB_FY25.xlsx").write_bytes(b"corrected")
    assert relay(source, destination).arrived == ("TB_FY25.xlsx",)


# ============================================================ nothing is ever removed


def test_the_source_is_untouched(source: Any, destination: Any) -> None:
    before = {p.name: p.read_bytes() for p in source.root.rglob("*") if p.is_file()}
    relay(source, destination)
    after = {p.name: p.read_bytes() for p in source.root.rglob("*") if p.is_file()}
    assert before == after


def test_a_sharefile_adapter_cannot_be_a_destination_at_all(source: Any) -> None:
    """Not a rule somebody has to keep - a method that does not exist.

    `ShareFileStorage` does not implement `ReceivingStorage`, so "nothing is deleted from
    ShareFile" is structural rather than careful. A relay pointed the wrong way round
    refuses before it copies anything, rather than failing partway through.
    """
    # Given a transport it will never use, because C54 holds a blanket rule that no test
    # in this block constructs a network adapter without one. The rule is worth more than
    # the exception: "this one is safe because it never makes a call" is exactly the
    # reasoning that stops being true when somebody edits the test.
    never_used = FakeShareFile(source.root).transport()
    sharefile = ShareFileStorage(transport=never_used)
    assert not isinstance(sharefile, ReceivingStorage)
    assert not hasattr(sharefile, "deposit")
    with pytest.raises(TypeError, match="ReceivingStorage"):
        relay(source, sharefile)


def test_a_destination_that_cannot_receive_is_refused_before_anything_moves(
    source: Any, tmp_path: Path
) -> None:
    """A half-finished relay is the worst outcome available: some files across, the rest
    not, and a traceback instead of a report saying which."""

    class Useless:
        name = "useless"

    with pytest.raises(TypeError):
        relay(source, Useless())


# ============================================================ partial failure


def test_one_file_failing_does_not_stop_the_others(source: Any, destination: Any) -> None:
    """Nine of twelve is nine of twelve. Stopping at the first failure leaves somebody
    guessing which files made it."""

    class Awkward:
        name = "awkward"

        def __init__(self, real: Any) -> None:
            self.real = real

        def deposit(self, path: str, data: bytes) -> Deposit:
            if path.endswith("BS.pdf"):
                raise RegistryError(
                    diagnose(UNREADABLE_FILE, "the destination refused this one", locator=path)
                )
            return self.real.deposit(path, data)

    report = relay(source, Awkward(destination))
    assert outcomes(report) == {"TB_FY25.xlsx": COPIED, "statements/BS.pdf": FAILED}
    assert not report.complete
    assert [m.path for m in report.failures] == ["statements/BS.pdf"]
    assert "refused this one" in report.failures[0].detail


def test_a_failure_is_named_rather_than_summarised(source: Any, destination: Any) -> None:
    """'An error occurred' would be worse than doing nothing: it tells somebody there is
    a problem and nothing about where."""

    class Broken:
        name = "broken"

        def deposit(self, path: str, data: bytes) -> Deposit:
            raise RegistryError(diagnose(UNREADABLE_FILE, "no", locator=path))

    report = relay(source, Broken())
    assert {m.path for m in report.failures} == {"TB_FY25.xlsx", "statements/BS.pdf"}


def test_a_source_that_cannot_be_listed_is_one_failure_not_an_empty_pass(
    destination: Any,
) -> None:
    """The dangerous shape: a folder that could not be read reported as a folder with
    nothing in it. Somebody would conclude the client had sent nothing."""

    class Unreachable:
        name = "unreachable"

        def list(self, prefix: str = "") -> tuple[Any, ...]:
            raise RegistryError(
                diagnose(UNREADABLE_FILE, "ShareFile is not answering", locator="/")
            )

    report = relay(Unreachable(), destination)
    assert not report.complete
    assert report.counts[FAILED] == 1
    assert report.arrived == ()


def test_a_file_that_cannot_be_read_from_the_source_is_a_failure_not_a_skip(
    source: Any, destination: Any
) -> None:
    class HalfBlind:
        name = "half-blind"

        def __init__(self, real: Any) -> None:
            self.real = real

        def list(self, prefix: str = "") -> Any:
            return self.real.list(prefix)

        def read(self, ref: Any) -> bytes:
            if ref.path.endswith("BS.pdf"):
                raise RegistryError(diagnose(UNREADABLE_FILE, "gone", locator=ref.path))
            data: bytes = self.real.read(ref)
            return data

    report = relay(HalfBlind(source), destination)
    assert outcomes(report)["statements/BS.pdf"] == FAILED
    assert not (destination.root / "statements" / "BS.pdf").exists()


# ============================================================ it is not a run


def test_nothing_in_a_compiled_graph_can_reach_the_relay() -> None:
    """The moment a graph step could move a client's files, everything the graph
    guarantees would have a hole in it - the relay writes no run record, takes no
    engagement, and passes through no policy gate, because it is an operator action.

    Checked by walking imports rather than by remembering.
    """
    forbidden = "intake.relay"
    for package in ("graph", "skills", "harness", "guards", "deliver", "review"):
        folder = ROOT / package
        if not folder.is_dir():
            continue
        for path in folder.rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            named: set[str] = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    named.update(a.name for a in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    named.add(node.module)
            assert forbidden not in named, f"{path} imports the relay"


def test_the_relay_imports_none_of_the_machinery_a_run_is_made_of() -> None:
    """The other direction from the test above: not only can a run not reach the relay,
    the relay cannot reach a run.

    Checked on imports rather than on the text of the file - a first attempt at this
    scanned for words and passed or failed on the docstring, which is the shape of test
    this repo keeps having to delete.
    """
    tree = ast.parse((ROOT / "intake" / "relay.py").read_text(encoding="utf-8"))
    named: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            named.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            named.add(node.module)
    assert named, "nothing was scanned, so nothing is proved"
    for machinery in ("ops.run_store", "graph", "harness", "deliver", "policy", "skills"):
        assert not any(n == machinery or n.startswith(machinery + ".") for n in named), machinery


def test_the_report_says_what_a_skip_means(source: Any, destination: Any) -> None:
    """A screen showing '12 skipped' and nothing else invites the reading that something
    went wrong."""
    relay(source, destination)
    shown = relay(source, destination).as_dict()
    assert "nothing was deleted from the source" in shown["means"]
    assert "Power Automate" in shown["means"]


def test_the_button_reaches_an_action_that_exists() -> None:
    from admin.page import PAGE

    assert 'data-act="updateFromShareFile"' in PAGE
    assert "ACTIONS.updateFromShareFile" in PAGE


# ============================================================ Box's own semantics


def test_box_skips_on_its_own_sha1_without_downloading_anything(tmp_path: Path) -> None:
    """The one place a sha1 is good enough.

    This adapter refuses to let a sha1 stand in for the sha256 a figure cites, because two
    sources must not share an id. "Are these the exact bytes I already uploaded" is a
    different question, and answering it with Box's own hash is what stops every press of
    Update downloading the whole destination.

    Replayed, not real: this proves the adapter's use of the API, not a Box tenant.
    """
    from ports.storage.box import BoxStorage
    from tests.fake_box import ROOT_ID, Credentials, FakeBox

    already = tmp_path / "box"
    already.mkdir()
    (already / "TB_FY25.xlsx").write_bytes(b"trial balance")
    fake = FakeBox(already)
    box = BoxStorage(ROOT_ID, secrets=Credentials(), transport=fake.transport())

    landed = box.deposit("TB_FY25.xlsx", b"trial balance")
    assert landed.outcome == SKIPPED
    assert not [c for c in fake.calls if "upload" in c or c.endswith("/content")]


def test_a_moved_carries_its_own_words() -> None:
    """The report is read by a person, not only by the page."""
    assert "copied" in Moved("a/b.pdf", COPIED, 3).line()
    assert Moved("a/b.pdf", COPIED, 3).arrived
    assert not Moved("a/b.pdf", SKIPPED, 3).arrived
