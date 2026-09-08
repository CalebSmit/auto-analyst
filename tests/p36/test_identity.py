"""P36: the name on a recorded change is one the system verified.

Every change this system records carries a name - who paused the engagement, who cleared
the methodology, who approved the workflow, who decided the review item. Until this phase
that name was a string the caller sent, which made the change log an unverified list of
claims in exactly the place it is meant to be evidence, and meant anybody who could reach
the port could record a change as anybody.

Four claims:

1. Neither surface serves anything outside a loopback bind without an authenticated
   identity.
2. The `who` on a write is the authenticated identity, and a client-supplied name is
   refused.
3. The provider is behind a port, so the local run stays a local run with no accounts.
4. A review decision records the identity that made it, and the precedent store will not
   accept one without.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

import ports
from admin.app import create_admin_app
from ports.identity import Identity, IdentityPort, NotAuthenticated, loopback
from ports.identity.local_user import OVERRIDE, LocalUserIdentity

ROOT = Path(__file__).resolve().parents[2]


class Remote:
    """A client that is not this machine. Starlette's TestClient always reports
    `testclient`, which the adapter treats as local - correctly, since an in-process call
    is not a network - so a test about the remote case supplies the host itself."""

    name = "remote_probe"

    def __init__(self, host: str) -> None:
        self.host = host
        self.real = LocalUserIdentity()

    def resolve(self, _host: str | None) -> Identity:
        return self.real.resolve(self.host)


class Somebody:
    """An identity the test chose, for the cases about what is recorded."""

    name = "chosen"

    def __init__(self, who: str) -> None:
        self.who = who

    def resolve(self, _host: str | None) -> Identity:
        return Identity(name=self.who, method="test", verified=True)


# ------------------------------------------------------------- the port


def test_identity_is_a_port_like_every_other_deployment_choice() -> None:
    """The third exit criterion. Which provider vouches for a name at the firm is a
    deployment choice; the admin surface must not know which."""
    assert "identity" in ports.PORTS
    spec = ports.PORTS["identity"]
    assert spec.env_var == "AA_IDENTITY_ADAPTER" and spec.default == "local_user"
    assert isinstance(ports.get_identity(), IdentityPort)


def test_the_local_user_is_the_person_at_the_keyboard(monkeypatch: pytest.MonkeyPatch) -> None:
    """A machine with one person on it does not need accounts, and inventing a login there
    would be ceremony that teaches people to click through."""
    monkeypatch.setenv(OVERRIDE, "C. Smit")
    who = LocalUserIdentity().resolve("127.0.0.1")

    assert who.name == "C. Smit"
    assert who.method == "operating_system"
    assert who.verified is False, "the OS user is a fact about the machine, not a proof"


def test_the_local_user_adapter_refuses_anything_that_is_not_this_machine() -> None:
    """The first exit criterion, and the safety of the whole arrangement: binding the
    surface to a network address without a provider that authenticates does not quietly
    work."""
    for host in ("10.0.0.5", "192.168.1.9", "example.invalid", None, ""):
        with pytest.raises(NotAuthenticated) as refused:
            LocalUserIdentity().resolve(host)
        diagnostic = refused.value.diagnostic
        assert diagnostic.owner == "config"
        assert "bind it to 127.0.0.1" in diagnostic.detail.lower()
        assert diagnostic.what_now


def test_what_counts_as_this_machine() -> None:
    for here in ("127.0.0.1", "::1", "localhost", "testclient", "LOCALHOST"):
        assert loopback(here), here
    for away in ("10.0.0.5", "", None, "127.0.0.1.evil.invalid"):
        assert not loopback(away), away


def test_an_identity_has_a_name() -> None:
    for blank in ("", "   "):
        with pytest.raises(ValueError, match="an identity has a name"):
            Identity(name=blank, method="test", verified=True)


# ------------------------------------------------------------- the surface


def test_the_surface_refuses_a_request_it_cannot_attribute(console: Any) -> None:
    """The first exit criterion, at the surface. A refusal a dashboard can render, and a
    401 rather than a 500: the request is not malformed, it is unattributable."""
    client = TestClient(create_admin_app(console, identity=Remote("10.0.0.5")))
    answer = client.get("/api/admin/setup")

    assert answer.status_code == 401
    assert answer.json()["detail"]["refused"][0]["code"] == "SCOPE.MISSING_CREDENTIAL"
    assert answer.json()["detail"]["refused"][0]["what_now"]


def test_a_write_is_recorded_against_the_identity_not_the_claim(
    console: Any, henderson: Any
) -> None:
    """The second exit criterion."""
    client = TestClient(create_admin_app(console, identity=Somebody("R. Partner")))
    made = client.post(
        "/api/admin/engagements/HEND-2026-04/pause",
        json={"who": "R. Partner", "reason": "waiting on the client"},
    )
    assert made.status_code == 200

    latest = console.changes()[-1]
    assert latest.who == "R. Partner"


def test_a_client_supplied_name_that_disagrees_is_refused(console: Any, henderson: Any) -> None:
    """Refused rather than overwritten: a request that disagrees with the system about who
    is making it is either a bug or somebody trying, and quietly correcting it hides
    both."""
    client = TestClient(create_admin_app(console, identity=Somebody("R. Partner")))
    refused = client.post(
        "/api/admin/engagements/HEND-2026-04/pause",
        json={"who": "Somebody Else", "reason": "not me"},
    )

    assert refused.status_code == 403
    diagnostic = refused.json()["detail"]["refused"][0]
    assert diagnostic["code"] == "CONFIG.ADMIN_FORBIDDEN"
    assert "R. Partner" in diagnostic["detail"] and "Somebody Else" in diagnostic["detail"]

    before = len(console.changes())
    client.post(
        "/api/admin/engagements/HEND-2026-04/pause",
        json={"who": "Somebody Else", "reason": "again"},
    )
    assert len(console.changes()) == before, "nothing was written"


def test_a_request_that_sends_no_name_is_recorded_against_the_identity(
    console: Any, henderson: Any
) -> None:
    """The name is the system's answer. A caller that sends none is not anonymous - it is
    simply not arguing."""
    client = TestClient(create_admin_app(console, identity=Somebody("R. Partner")))
    made = client.post(
        "/api/admin/engagements/HEND-2026-04/pause", json={"who": "", "reason": "quiet"}
    )
    assert made.status_code == 200
    assert console.changes()[-1].who == "R. Partner"


def test_the_surface_says_who_it_resolved(console: Any) -> None:
    """The page reads this rather than asking. Found by using it: a page that asks for a
    name invites somebody to type one that disagrees with the identity, and a disagreement
    is refused - which reads like a broken button rather than a mismatch they could fix."""
    client = TestClient(create_admin_app(console, identity=Somebody("R. Partner")))
    me = client.get("/api/admin/whoami")

    assert me.status_code == 200
    assert me.json() == {"name": "R. Partner", "method": "test", "verified": True}


def test_sending_no_name_is_the_ordinary_case(console: Any, henderson: Any) -> None:
    """`who` is optional and checked, not required and ignored.

    Required would reject the correct behaviour - a caller letting the system fill in the
    name - before the identity was ever consulted, which is what it did until somebody
    tried it.
    """
    client = TestClient(create_admin_app(console, identity=Somebody("R. Partner")))
    made = client.post(
        "/api/admin/engagements/HEND-2026-04/pause", json={"reason": "no name sent"}
    )

    assert made.status_code == 200
    assert console.changes()[-1].who == "R. Partner"


def test_the_page_shows_the_identity_and_does_not_ask_for_one() -> None:
    """A page that keeps a name in local storage is a page that will disagree with the
    server the first time somebody uses a different machine."""
    from admin.page import PAGE

    assert "/api/admin/whoami" in PAGE
    assert "acting as" in PAGE
    assert "prompt(" not in PAGE.split("function who()")[0], "it does not ask for a name"
    assert "localStorage" not in PAGE, "and does not remember one"


def test_the_check_is_installed_where_the_app_is_assembled() -> None:
    """A router does not carry its application's middleware, and the front door puts both
    consoles on one app. This is the mistake that made, found by a test rather than by a
    change log full of identities nobody resolved."""
    import inspect

    from admin.app import install_identity
    from tools import serve

    assert "install_identity(app)" in inspect.getsource(serve.build)
    assert callable(install_identity)


# ------------------------------------------------------------- the record


def test_a_review_decision_names_who_made_it() -> None:
    """The fourth exit criterion. A decision nobody made is not a decision."""
    import inspect

    from review.surface import ReviewSurface

    source = inspect.getsource(ReviewSurface.decide)
    assert "decided_by" in source
    assert "if not decided_by.strip():" in source, "refused, not defaulted"


def test_the_precedent_store_refuses_a_decision_with_no_decider() -> None:
    """Only a human decision writes to the Precedent Store, and a decision with no name on
    it is not one. This is the last place the identity has to be real, and the one where
    getting it wrong compounds: precedent is what the system learns from."""
    import inspect

    from precedent.store import PrecedentStore

    source = inspect.getsource(PrecedentStore)
    assert "not decision.decided_by.strip()" in source
    assert "writes_precedent" in source


def test_the_env_example_documents_both_new_variables() -> None:
    """A setting nobody wrote down is a setting nobody knows to change on the work
    machine."""
    example = (ROOT / ".env.example").read_text(encoding="utf-8")
    assert "AA_IDENTITY_ADAPTER=local_user" in example
    assert "AA_IDENTITY_NAME" in example
    assert "refuses any request that did not come from this machine" in example


def test_the_guide_says_there_are_no_accounts_and_what_that_means() -> None:
    """The people who will run this need to know the shape of what protects it."""
    guide = (ROOT / "docs" / "USING.md").read_text(encoding="utf-8")
    assert "127.0.0.1" in guide
    assert "P36" in guide or "identity" in guide.lower()
