"""P87 - Box, on the side documents are read from.

The conformance suite in `tests/p03` already runs this adapter over the same three files
as the local folder, which is where "it satisfies the interface" is established. What is
here is the part that is Box's alone: the impersonation without which a token sees
nothing, pagination, the sha256 that Box does not offer, and the difference between a
credential nobody set and a credential the service refused.

And one test that is about this file rather than about the adapter - that nothing in this
phase can be read as evidence a real Box tenant answered.
"""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

import pytest

from ports.storage import FileRef
from ports.storage.box import CREDENTIALS, ENV_ROOT, BoxStorage, build
from registries.errors import RegistryError
from tests.fake_box import ROOT_ID, Credentials, FakeBox, without

HERE = Path(__file__).resolve()
ROOT = HERE.parents[2]


@pytest.fixture
def folder(tmp_path: Path) -> Path:
    (tmp_path / "TB_FY25.xlsx").write_bytes(b"trial balance")
    (tmp_path / "statements").mkdir()
    (tmp_path / "statements" / "BS.pdf").write_bytes(b"balance sheet")
    return tmp_path


def adapter(folder: Path, **kwargs: object) -> tuple[BoxStorage, FakeBox]:
    box = FakeBox(folder, **kwargs)  # type: ignore[arg-type]
    return BoxStorage(ROOT_ID, secrets=Credentials(), transport=box.transport()), box


# ============================================================ impersonation


def test_the_token_is_always_asked_for_as_a_person(folder: Path) -> None:
    """Without box_subject_id the token is the service account's, and a service account
    is a member of almost nothing.

    That is the failure worth designing against, because it does not look like a failure:
    the call succeeds and the folder comes back empty. An unauthorised sweep and an empty
    one would be indistinguishable, so the fake refuses a token request that does not
    impersonate, and this test is what notices.
    """
    storage, box = adapter(folder)
    assert storage.list()
    assert box.tokens_issued == 1


def test_the_credential_that_names_the_person_is_one_of_the_three(folder: Path) -> None:
    """BOX_USER_ID, not an enterprise id. The delivery adapter had this wrong."""
    assert CREDENTIALS == ("BOX_CLIENT_ID", "BOX_CLIENT_SECRET", "BOX_USER_ID")


def test_a_missing_user_id_says_what_would_happen_without_it(folder: Path) -> None:
    storage = BoxStorage(
        ROOT_ID, secrets=without("BOX_USER_ID"), transport=FakeBox(folder).transport()
    )
    with pytest.raises(RegistryError) as refused:
        storage.list()
    d = refused.value.diagnostic
    assert d.code == "SCOPE.MISSING_CREDENTIAL"
    assert "BOX_USER_ID" in d.detail
    # The message has to carry the consequence, not only the name: somebody reading it
    # needs to know an empty folder is what the mistake looks like.
    assert "service account" in d.detail


# ============================================================ refused vs missing


def test_a_refused_credential_is_not_the_same_diagnosis_as_a_missing_one(
    folder: Path,
) -> None:
    """Different repairs. One is 'add it to .env'; the other is 'it is wrong, revoked, or
    the app lacks a permission'. A single code would send somebody to the wrong file."""
    storage, _ = adapter(folder, refuse_token="invalid_client")
    with pytest.raises(RegistryError) as refused:
        storage.list()
    assert refused.value.diagnostic.code == "CONFIG.CREDENTIAL_REFUSED"
    assert refused.value.diagnostic.owner == "config"


def test_the_permission_that_is_usually_wrong_is_named(folder: Path) -> None:
    """Box says unauthorized_client when the app has not been granted 'Generate User
    Access Tokens'. It is the most likely thing to be wrong the first time this runs at
    work, and naming it is the difference between a minute and an afternoon."""
    storage, _ = adapter(folder, refuse_token="unauthorized_client")
    with pytest.raises(RegistryError) as refused:
        storage.list()
    assert "Generate User Access Tokens" in refused.value.diagnostic.detail


def test_a_forbidden_call_is_a_credential_problem_not_a_missing_file(
    folder: Path,
) -> None:
    storage, _ = adapter(folder, refuse_with=403)
    with pytest.raises(RegistryError) as refused:
        storage.list()
    assert refused.value.diagnostic.code == "CONFIG.CREDENTIAL_REFUSED"


def test_a_missing_folder_id_refuses_rather_than_reading_the_whole_account(
    folder: Path,
) -> None:
    """An unset root is not the root of the account. Box's root really is id 0, so an
    empty setting defaulting to it would sweep everything the user can see."""
    storage = BoxStorage(
        "", secrets=Credentials(), transport=FakeBox(folder).transport()
    )
    with pytest.raises(RegistryError) as refused:
        storage.list()
    assert refused.value.diagnostic.code == "SCOPE.MISSING_CREDENTIAL"
    assert ENV_ROOT in refused.value.diagnostic.detail


# ============================================================ the API, used properly


def test_a_folder_larger_than_one_page_is_listed_whole(tmp_path: Path) -> None:
    """Reading only the first page would sweep part of a folder, which is worse than
    failing to sweep it: the run would be short by documents nobody knows are missing."""
    for i in range(23):
        (tmp_path / f"doc{i:02d}.pdf").write_bytes(f"page {i}".encode())
    storage, _ = adapter(tmp_path, page_size=5)
    assert len(storage.list()) == 23


def test_the_order_is_the_adapter_s_and_not_the_server_s(tmp_path: Path) -> None:
    """The fake returns items reversed on purpose. An adapter that passed the server's
    order through would produce a different run from the same inputs."""
    for name in ("c.pdf", "a.pdf", "b.pdf"):
        (tmp_path / name).write_bytes(b"x")
    storage, _ = adapter(tmp_path)
    assert [r.path for r in storage.list()] == ["a.pdf", "b.pdf", "c.pdf"]


def test_folders_are_not_returned_as_files(folder: Path) -> None:
    storage, _ = adapter(folder)
    assert [r.path for r in storage.list()] == ["TB_FY25.xlsx", "statements/BS.pdf"]


def test_a_prefix_lists_only_below_it(folder: Path) -> None:
    storage, _ = adapter(folder)
    assert [r.path for r in storage.list("statements")] == ["statements/BS.pdf"]


def test_the_hash_is_a_sha256_this_adapter_computed(folder: Path) -> None:
    """Box offers sha1. Every figure in this system cites a sha256, and a sha1 relabelled
    would be a lie told in the manifest - two sources could then share an id."""
    storage, _ = adapter(folder)
    stat = storage.stat(FileRef("TB_FY25.xlsx"))
    assert stat.content_hash == f"sha256:{hashlib.sha256(b'trial balance').hexdigest()}"
    assert hashlib.sha1(b"trial balance").hexdigest() not in stat.content_hash


def test_the_size_is_what_arrived_not_what_was_promised(folder: Path) -> None:
    """Box's metadata and Box's bytes can disagree, and the bytes are what was hashed.

    So the fake advertises a size the content does not have. An adapter reporting the
    advertised number would pair a size with a hash computed from something else, and the
    contradiction would surface a long way from here.
    """
    storage, _ = adapter(folder, lie_about_size=999_999)
    assert storage.stat(FileRef("TB_FY25.xlsx")).size_bytes == len(b"trial balance")


def test_a_file_with_no_modified_at_is_refused_rather_than_guessed(folder: Path) -> None:
    """modified_at decides what the Intake Window counts as new. A guess here is a
    document silently treated as already seen."""
    from ports.storage import box as box_module

    with pytest.raises(RegistryError) as refused:
        box_module._when(None, "some/file.pdf")
    assert refused.value.diagnostic.code == "INTAKE.UNREADABLE_FILE"


# ============================================================ what is not cached


def test_a_path_is_resolved_again_every_call(folder: Path) -> None:
    """Box ids are stable; the mapping from a path to one is not. A re-uploaded file takes
    a new id under the same name, so a cached mapping is how a run reads last week's bytes
    while reporting this week's name - invisible, and exactly what source_version exists
    to catch."""
    storage, box = adapter(folder)
    storage.read(FileRef("statements/BS.pdf"))
    first = len([c for c in box.calls if c.endswith("/items")])
    storage.read(FileRef("statements/BS.pdf"))
    second = len([c for c in box.calls if c.endswith("/items")])
    assert second == first * 2, "the second read re-walked the tree rather than reusing ids"


def test_the_token_is_kept_because_a_token_is_not_a_file(folder: Path) -> None:
    """The one thing worth caching. Fetching a token per request would triple the calls a
    sweep makes and gain no property at all."""
    storage, box = adapter(folder)
    storage.list()
    storage.list()
    assert box.tokens_issued == 1


def test_an_expired_token_is_retried_once_and_only_once(folder: Path) -> None:
    """The retry exists for one case: a token that expired between being checked and being
    used. A 401 that survives a fresh token is a credential problem, and retrying it would
    turn a clear refusal into a slow one."""
    storage, box = adapter(folder, expire_after=1)
    assert storage.list()
    assert box.tokens_issued == 2

    permanent, box2 = adapter(folder, refuse_with=401)
    with pytest.raises(RegistryError):
        permanent.list()
    assert box2.tokens_issued <= 2, "a persistent 401 must not loop"


# ============================================================ what may not leak


def test_neither_the_credential_nor_the_token_reaches_a_repr(folder: Path) -> None:
    """repr is where a credential ends up in a traceback, an f-string or a log line."""
    storage, _ = adapter(folder)
    storage.list()
    shown = repr(storage)
    assert "secret" not in shown and "tok1" not in shown
    assert "1234567" not in shown


def test_building_the_adapter_needs_no_credential_and_no_network() -> None:
    """serve.py --check and the admin console both list what exists. Neither may need a
    secret to do it."""
    assert build().name == "box"


# ============================================================ the correction, and honesty


def test_the_wrong_box_credential_is_gone_from_the_code() -> None:
    """BOX_ENTERPRISE_ID was a guess made before anyone had authenticated. It is a finding
    rather than a tidy-up, so the test is that no shipped file still names it."""
    from ports.delivery.box import CREDENTIALS as DELIVERY

    assert DELIVERY == ("BOX_CLIENT_ID", "BOX_CLIENT_SECRET", "BOX_USER_ID")
    for path in (ROOT / ".env.example",):
        assert "BOX_ENTERPRISE_ID" not in path.read_text(encoding="utf-8"), path


def test_the_two_box_adapters_read_and_write_different_folders() -> None:
    """One setting for both is how a deliverable lands in a client's inbox."""
    from ports.delivery.box import ENV_ROOT as WRITE

    assert ENV_ROOT != WRITE


def test_nothing_in_this_phase_can_be_read_as_a_real_tenant_answering() -> None:
    """The phase's own honesty check, and it has teeth.

    Every BoxStorage in this file is constructed with a replayed transport. A test written
    later without one would reach api.box.com - and would pass on a machine with
    credentials, fail on every other, and be read as evidence the connection works. So the
    file checks itself rather than relying on whoever adds the next test remembering.
    """
    tree = ast.parse(HERE.read_text(encoding="utf-8"))
    built = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "BoxStorage"
    ]
    assert built, "the scan found no constructions, so it is proving nothing"
    for node in built:
        assert any(kw.arg == "transport" for kw in node.keywords), (
            f"BoxStorage at line {node.lineno} has no replayed transport: "
            "that test would reach the real Box"
        )


def test_the_adapter_says_in_its_own_words_that_it_has_never_run(folder: Path) -> None:
    """A person reading the module is the one who needs to know, and a docstring is where
    they will look. The fake's own docstring carries it too."""
    from ports.storage import box as box_module
    from tests import fake_box

    assert "has spoken to a real Box tenant" in (box_module.__doc__ or "")
    assert "not evidence that Box works" in (fake_box.__doc__ or "")


def test_the_fake_serves_box_shapes_rather_than_the_adapter_s_own(folder: Path) -> None:
    """A fake written from the adapter proves the adapter agrees with itself. This one is
    written from Box's documented responses - entries, total_count, sha1 - so the test
    that the adapter ignores sha1 is a real test."""
    box = FakeBox(folder)
    response = box.transport().handle_request(
        __import__("httpx2").Request("GET", f"https://api.box.com/2.0/folders/{ROOT_ID}/items")
    )
    body = json.loads(response.read())
    assert {"entries", "total_count", "offset", "limit"} <= set(body)
    file_entry = next(e for e in body["entries"] if e["type"] == "file")
    assert "sha1" in file_entry and "sha256" not in file_entry
