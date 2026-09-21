"""C54 - What a button is allowed to claim.

P87 to P90 put three network surfaces on the dashboard: read Box, sign in to ShareFile,
copy one to the other. Each phase passed its own tests. A checkpoint asks the thing a unit
test cannot, which here is mostly about **claims** - what a green result is allowed to be
read as, and what the code makes structurally impossible rather than merely checks.

The four claims worth holding together:

1. Nothing in this block has spoken to a real tenant, and the code says so in the places a
   person looks.
2. The relay cannot be reached from a run, and the run machinery cannot be reached from
   the relay.
3. Delivery still has two inbound edges. The relay needed a write side and did not take
   delivery's.
4. No credential reaches a repr, a report or a page.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

import ports
from ports.storage import ReceivingStorage

ROOT = Path(__file__).resolve().parents[3]


# ============================================================ what a green test means


def test_every_network_adapter_says_it_has_never_run() -> None:
    """A person reading the module is the one who needs to know, and a module docstring is
    where they will look. Held here rather than only in each phase, because the sentence
    is the same promise in three files and it is the promise P93 discharges."""
    for module, phrase in (
        ("ports/storage/box.py", "has spoken to a real Box tenant"),
        ("ports/storage/sharefile.py", "has spoken to real ShareFile"),
    ):
        assert phrase in (ROOT / module).read_text(encoding="utf-8"), module


def test_the_phase_that_would_prove_it_is_open_and_belongs_to_a_person() -> None:
    """The whole point of this block's honesty: it is not finished. If P93 ever closes on
    a machine with no credentials, something has gone wrong with the gate rather than with
    the connection."""
    import json

    plan = json.loads((ROOT / "BUILD" / "plan.json").read_text(encoding="utf-8"))
    p93 = next((p for p in plan["phases"] if p["id"] == "P93"), None)
    assert p93 is not None, "the phase that proves the connection is not in the plan"
    assert p93["gate"] == "human", "a person signs this one; a test cannot"


def test_no_test_in_this_block_can_reach_the_network() -> None:
    """Every adapter built in these phases' tests carries a replayed transport.

    Without this, a test would pass on the one machine that has credentials, fail on every
    other, and be read as evidence the connection works - which is the single most
    expensive wrong conclusion available here.
    """
    for folder, name in (
        ("tests/p87", "BoxStorage"),
        ("tests/p89", "ShareFileStorage"),
        ("tests/p90", "ShareFileStorage"),
    ):
        for path in (ROOT / folder).rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id == name
                ):
                    assert any(k.arg == "transport" for k in node.keywords), (
                        f"{path.name}:{node.lineno} builds {name} with no replayed "
                        f"transport - that test would reach the real service"
                    )


# ============================================================ the relay is not a run


def test_no_production_module_on_the_run_path_imports_the_relay() -> None:
    """The moment a graph step could move a client's files, every guarantee the graph
    makes would have a hole in it: the relay passes no policy gate, writes no run record
    and takes no engagement, because it is an operator action."""
    for package in ("graph", "skills", "harness", "guards", "deliver", "review", "workers"):
        folder = ROOT / package
        if not folder.is_dir():
            continue
        for path in folder.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            assert "intake.relay" not in text, f"{path} names the relay"


def test_the_relay_cannot_reach_the_run_machinery_either() -> None:
    tree = ast.parse((ROOT / "intake" / "relay.py").read_text(encoding="utf-8"))
    named = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            named.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            named.add(node.module)
    assert named
    for machinery in ("ops.run_store", "graph", "harness", "deliver", "skills"):
        assert not any(n == machinery or n.startswith(machinery + ".") for n in named)


# ============================================================ the fences that held


def test_delivery_still_has_two_inbound_edges() -> None:
    """The relay needed a write side. It did not take delivery's, because delivery's
    contract is released artifacts and the run manifest - and a client's trial balance on
    its way *into* intake is neither."""
    contract = (ROOT / "ports" / "delivery" / "__init__.py").read_text(encoding="utf-8")
    assert "Two inbound edges only" in contract
    assert "deposit" not in contract, "the receiving side is on storage, not delivery"


def test_the_source_of_the_relay_cannot_be_written_to() -> None:
    """Not a rule somebody has to keep: a method that does not exist.

    `ShareFileStorage` does not implement `ReceivingStorage`, so "nothing is deleted from
    ShareFile" and "nothing is written back to ShareFile" are both structural.
    """
    from ports.storage.sharefile import ShareFileStorage

    assert not isinstance(ShareFileStorage(), ReceivingStorage)
    assert not hasattr(ShareFileStorage(), "deposit")


def test_the_read_side_is_still_three_methods() -> None:
    """Receiving is a second protocol on purpose. Folding it into `StoragePort` would make
    "this is the read side of intake" a comment rather than a fact."""
    from ports.storage import StoragePort

    declared = {
        name
        for name in dir(StoragePort)
        if not name.startswith("_") and name != "name"
    }
    assert declared == {"list", "read", "stat"}


def test_every_storage_adapter_passes_the_one_conformance_suite() -> None:
    """Three adapters now, two of them over a network. A port whose adapters are each
    tested their own way is not an interface - it is three implementations sharing a
    name, and the first swap finds the differences in production."""
    assert set(ports.ready("storage")) == {"local_folder", "box", "sharefile"}
    assert ports.contracts("storage") == ()


# ============================================================ what may not leak


def test_no_adapter_puts_a_credential_in_its_repr(tmp_path: Path) -> None:
    """repr is where a credential ends up in a traceback, an f-string, or structlog's
    fallback rendering."""
    from ports.storage.box import BoxStorage
    from ports.storage.sharefile import ShareFileStorage
    from ports.storage.tokens import StoredToken

    for shown in (
        repr(BoxStorage("folder-1")),
        repr(ShareFileStorage("folder-2")),
        repr(StoredToken("sharefile", "rt-secret-value", "sub", "now")),
    ):
        assert "secret" not in shown.lower() or "rt-secret-value" not in shown
    assert "rt-secret-value" not in repr(
        StoredToken("sharefile", "rt-secret-value", "sub", "now")
    )


def test_a_connection_report_carries_presence_and_never_a_value(tmp_path: Path) -> None:
    from admin.connection import probe_box
    from ports.storage.box import BoxStorage
    from tests.fake_box import ROOT_ID, Credentials, FakeBox

    (tmp_path / "a.pdf").write_bytes(b"x")
    secrets = Credentials(BOX_CLIENT_SECRET="do-not-print-me")
    storage = BoxStorage(
        ROOT_ID, secrets=secrets, transport=FakeBox(tmp_path).transport()
    )
    assert "do-not-print-me" not in str(probe_box(storage, secrets).as_dict())


def test_the_refresh_token_is_not_stored_in_plain_text(tmp_path: Path) -> None:
    from ports.storage.tokens import StoredToken, TokenStore
    from tests.fake_sharefile import Credentials

    store = TokenStore(Credentials(), tmp_path / "t.enc")
    store.write(StoredToken("sharefile", "rt-plain-text-would-be-bad", "sub", "now"))
    assert b"rt-plain-text-would-be-bad" not in store.path.read_bytes()


def test_the_token_file_is_somewhere_the_repo_cannot_commit() -> None:
    from ports.storage.tokens import DEFAULT_PATH

    ignored = (ROOT / ".gitignore").read_text(encoding="utf-8").split()
    assert DEFAULT_PATH.split("/")[0] + "/" in ignored


# ============================================================ the two surfaces agree


def test_both_connection_tests_report_the_same_shape(tmp_path: Path) -> None:
    """One page renders both. Two report shapes would mean two renderers, and the second
    one is where a status nobody styled shows up as plain text."""
    from admin.connection import probe_box, probe_sharefile
    from ports.storage.box import BoxStorage
    from ports.storage.sharefile import ShareFileStorage
    from ports.storage.tokens import TokenStore
    from tests import fake_box, fake_sharefile

    (tmp_path / "a.pdf").write_bytes(b"x")
    box = probe_box(
        BoxStorage(
            fake_box.ROOT_ID,
            secrets=fake_box.Credentials(),
            transport=fake_box.FakeBox(tmp_path).transport(),
        ),
        fake_box.Credentials(),
    ).as_dict()

    held = fake_sharefile.Credentials()
    fake = fake_sharefile.FakeShareFile(tmp_path)
    fake.issued.append("rt-1")
    store = TokenStore(held, tmp_path / "t.enc")
    fake_sharefile.signed_in(store)
    sharefile = probe_sharefile(
        ShareFileStorage(
            fake_sharefile.ROOT_ID, secrets=held, tokens=store, transport=fake.transport()
        ),
        held,
    ).as_dict()

    assert set(box) == set(sharefile)
    assert {k for step in box["steps"] for k in step} <= {
        k for step in sharefile["steps"] for k in step
    } | {"diagnostic"}
    assert box["connected"] and sharefile["connected"]


def test_an_unknown_service_is_refused_rather_than_reported_as_broken() -> None:
    from unittest.mock import Mock

    from admin.console import AdminConsole, AdminRefused
    from tests.fake_box import Credentials

    preflight = Mock()
    preflight.secrets = Credentials()
    console = AdminConsole(Mock(), Mock(), preflight, constraints=Mock())
    with pytest.raises(AdminRefused):
        console.test_connection("dropbox")


def test_every_button_in_this_block_reaches_an_action_that_exists() -> None:
    """P81 found a button wired to a name nothing defined, as the first thing anybody
    would press on a fresh install. Four more buttons arrived in this block."""
    from admin.page import PAGE

    for action in ("testBox", "testShareFile", "signInShareFile", "updateFromShareFile"):
        assert f'data-act="{action}"' in PAGE, action
        assert f"ACTIONS.{action}" in PAGE, action
    assert "onclick=" not in PAGE, "values reach a handler through data- attributes"


def test_the_relay_refuses_a_destination_it_cannot_write_to(tmp_path: Path) -> None:
    """Before it copies anything. A half-finished relay - some files across, the rest not,
    and a traceback instead of a report - is the worst outcome available."""
    from intake.relay import relay
    from ports.storage.local_folder import LocalFolderStorage
    from ports.storage.sharefile import ShareFileStorage

    (tmp_path / "a.pdf").write_bytes(b"x")
    with pytest.raises(TypeError, match="ReceivingStorage"):
        relay(LocalFolderStorage(tmp_path), ShareFileStorage())


def test_a_missing_credential_and_a_refused_one_stay_different_diagnoses() -> None:
    """Across both services. One says add it to .env; the other says it is wrong, revoked,
    or the app lacks a permission - and they are fixed on different screens."""
    from registries.errors import WHAT_NOW

    assert "CONFIG.CREDENTIAL_REFUSED" in WHAT_NOW
    assert "SCOPE.MISSING_CREDENTIAL" in WHAT_NOW
    assert WHAT_NOW["CONFIG.CREDENTIAL_REFUSED"] != WHAT_NOW["SCOPE.MISSING_CREDENTIAL"]


def test_the_two_box_adapters_read_and_write_different_folders() -> None:
    """One setting for both is how a deliverable lands in a client's inbox."""
    from ports.delivery.box import ENV_ROOT as WRITE
    from ports.storage.box import ENV_ROOT as READ

    assert READ != WRITE


def test_nothing_in_this_block_left_a_seam_the_scan_cannot_see(tmp_path: Path) -> None:
    """The scan itself got sharper in P91 - it had been letting a package vouch for its
    own submodules. Held here because this block is where three new modules arrived."""
    import sys

    sys.path.insert(0, str(ROOT))
    from tests.p82.test_nothing_a_run_cannot_reach import ALLOWED, unreachable

    surprises = [name for name in unreachable() if name not in ALLOWED]
    assert not surprises, surprises
    for module in ("admin.connection", "intake.relay", "ports.storage.tokens"):
        assert module not in ALLOWED, f"{module} was built in this block and is excused"
