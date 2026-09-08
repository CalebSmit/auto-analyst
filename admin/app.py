"""The FastAPI surface over the Admin Console.

Every write carries `who` and `reason`, because every write lands in the Config Change
Log and the log refuses an entry without either. A refusal comes back as a diagnostic:
code, owner, expected, found, what_now.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

import ports
from admin.console import AdminConsole, AdminRefused
from admin.page import PAGE
from intake.config import Destination, Watch
from intake.roster import RosterEntry, RosterState
from registries.errors import ADMIN_FORBIDDEN, DiagnosticError, diagnose  # noqa: F401

__all__ = ["create_admin_app", "install_identity", "who"]


class Change(BaseModel):
    who: str = ""
    """Optional, and checked when it is there.

    The name recorded is the identity the system resolved; a caller that sends one that
    disagrees is refused rather than corrected, and a caller that sends none - which is
    what the pages do - simply is not arguing. Required would mean rejecting the correct
    behaviour before the identity was ever consulted.
    """

    reason: str


class Registration(Change):
    engagement_id: str
    client: str
    scope_path: str
    watch_id: str
    destination_id: str
    folder: str = ""
    template_pin: str = ""
    budget_usd: float | None = None
    review_level: str = "standard"
    note: str = ""
    state: str = "paused"
    profile: dict[str, Any] | None = None


class Budget(Change):
    usd: float


class RecipeChoice(Change):
    recipe: str = ""
    """Empty means inherit the watch's, which is how an engagement undoes a choice."""


class Clearance(BaseModel):
    who: str = ""
    """A clearance names a person and nothing else - and the person is the identity the
    system resolved, so this is optional and checked, like every other `who`. There is no
    reason field: the reason for clearing methodology is always the same one, which is
    that somebody read it."""


class ReviewLevel(Change):
    level: str


class Profile(Change):
    profile: dict[str, Any]


class Binding(Change):
    destination_id: str | None = None
    template_pin: str | None = None
    watch_id: str | None = None
    folder: str | None = None


class ModelBinding(Change):
    layer: str
    file: str | None
    template_version: str | None
    why: str = ""


class WatchBody(Change):
    id: str
    kind: str
    name: str
    root: str
    recipe: str
    engagement_id: str | None = None
    depth: int = 2


class DestinationBody(Change):
    id: str
    name: str
    path: str
    adapter: str = "local_folder"
    credential: str | None = None


class CredentialBody(Change):
    name: str
    purpose: str
    expires_on: str | None = None


def install_identity(app: FastAPI, identity: Any | None = None) -> None:
    """Resolve who is asking on every request to `app`, or refuse before a route runs.

    Installed by the caller that assembles the application, because a router does not
    carry its application\'s middleware: `tools/serve.py` puts both consoles on one app,
    and this living on the admin app alone meant the combined one had no check at all.

    On the request rather than in each handler for the same reason - a check twenty
    handlers have to remember is a check one of them will not, and the one that forgets is
    the one that writes to the record.
    """
    port = identity or ports.get_identity()

    @app.middleware("http")
    async def _who_is_asking(request: Request, call_next: Any) -> Any:
        try:
            request.state.identity = port.resolve(
                request.client.host if request.client else None
            )
        except DiagnosticError as refused:
            return JSONResponse(
                status_code=401, content={"detail": {"refused": [refused.diagnostic.as_dict()]}}
            )
        return await call_next(request)


def who(request: Request, claimed: str | None) -> str:
    """The name that goes in the record.

    The system\'s answer, and a refusal when the caller sent a different one. Not ignored -
    refused - because a request that disagrees about who is making it is either a bug or an
    attempt, and silently correcting it hides both.
    """
    resolved = request.state.identity
    if claimed and claimed.strip() and claimed.strip() != resolved.name:
        raise HTTPException(
            status_code=403,
            detail={
                "refused": [
                    diagnose(
                        ADMIN_FORBIDDEN,
                        f"this change would be recorded against {claimed.strip()!r}, and "
                        f"the identity behind the request is {resolved.name!r}",
                        locator="identity",
                        expected=resolved.name,
                        found=claimed.strip(),
                    ).as_dict()
                ]
            },
        )
    return str(resolved.name)


def create_admin_app(console: AdminConsole, identity: Any | None = None) -> FastAPI:
    app = FastAPI(title="Chartwell Automated Analyst - admin", docs_url=None, redoc_url=None)
    install_identity(app, identity)

    @app.get("/admin", response_class=HTMLResponse)
    def dashboard() -> str:
        """The page. Everything it does goes through the API below it, so there is
        nothing it can do that is not also on the record."""
        return PAGE

    @app.post("/api/admin/initialise")
    def initialise(request: Request, body: Change) -> dict[str, Any]:
        """The first configuration for this environment. Everything else needs one."""
        return _guard(lambda: console.initialise(who=who(request, body.who), reason=body.reason))

    @app.get("/api/admin/whoami")
    def whoami(request: Request) -> dict[str, Any]:
        """Who this request is, as the system resolved it.

        The surfaces read it rather than asking a person to type their own name: the name
        on a recorded change is the system\'s answer, and a page that asked for one would
        be inviting somebody to disagree with it by accident.
        """
        found = request.state.identity
        return {"name": found.name, "method": found.method, "verified": found.verified}

    @app.get("/api/admin/setup")
    def setup() -> dict[str, Any]:
        # Through the guard: a machine nobody has configured yet raises rather than
        # returning an empty setup, and that is the first request the page makes. A
        # traceback there reads as "broken"; a diagnostic reads as "not set up".
        return _guard(console.setup)

    @app.get("/api/admin/preflight")
    def preflight(engagement_id: str | None = None) -> dict[str, Any]:
        return _guard(lambda: console.check(engagement_id).as_dict())

    @app.get("/api/admin/changes")
    def changes() -> list[dict[str, Any]]:
        return [c.__dict__ for c in console.changes()]

    @app.get("/api/admin/model")
    def model(scope_path: str) -> dict[str, Any]:
        return _guard(lambda: console.resolve_model(scope_path))

    @app.get("/api/admin/credentials/{name}")
    def credential(name: str) -> dict[str, Any]:
        return {"name": name, "present": console.credential_present(name)}

    @app.get("/api/admin/scopes")
    def scopes() -> dict[str, Any]:
        """What an engagement may be scoped to, from the registry rather than by hand."""
        return console.scope_choices()

    @app.get("/api/admin/recipes")
    def recipes() -> dict[str, Any]:
        """Which workflows the board approved, and which were edited afterwards."""
        return console.recipes()

    @app.get("/api/admin/methodology")
    def methodology() -> dict[str, Any]:
        return console.methodology()

    # `{name:path}` rather than `{name}`: a methodology file is identified by its layer and
    # its filename - `_firm/qc-conventions.md` - and a plain path parameter stops at the
    # slash, which would make every file below the first layer unreachable.
    @app.post("/api/admin/methodology/{name:path}/clear")
    def clear_methodology(name: str, request: Request, body: Clearance) -> dict[str, Any]:
        return _guard(lambda: console.clear_methodology(name, who=who(request, body.who)))

    @app.post("/api/admin/engagements")
    def register(request: Request, body: Registration) -> dict[str, Any]:
        entry = RosterEntry(
            engagement_id=body.engagement_id,
            client=body.client,
            scope_path=body.scope_path,
            watch_id=body.watch_id,
            destination_id=body.destination_id,
            state=RosterState(body.state),
            folder=body.folder,
            template_pin=body.template_pin,
            budget_usd=body.budget_usd,
            review_level=body.review_level,
            note=body.note,
        )
        return _guard(
            lambda: (
                console.register_engagement(
                    entry, profile=body.profile, who=who(request, body.who), reason=body.reason
                ).__dict__
            )
        )

    @app.post("/api/admin/engagements/{engagement_id}/activate")
    def activate(engagement_id: str, request: Request, body: Change) -> dict[str, Any]:
        return _guard(
            lambda: console.activate(engagement_id, who=who(request, body.who),
                reason=body.reason).__dict__
        )

    @app.post("/api/admin/engagements/{engagement_id}/pause")
    def pause(engagement_id: str, request: Request, body: Change) -> dict[str, Any]:
        return _guard(
            lambda: console.pause(engagement_id, who=who(request, body.who),
                reason=body.reason).__dict__
        )

    @app.post("/api/admin/engagements/{engagement_id}/archive")
    def archive(engagement_id: str, request: Request, body: Change) -> dict[str, Any]:
        return _guard(
            lambda: console.archive(engagement_id, who=who(request, body.who),
                reason=body.reason).__dict__
        )

    @app.post("/api/admin/engagements/{engagement_id}/budget")
    def budget(engagement_id: str, request: Request, body: Budget) -> dict[str, Any]:
        return _guard(
            lambda: (
                console.set_budget(
                    engagement_id, body.usd, who=who(request, body.who), reason=body.reason
                ).__dict__
            )
        )

    @app.post("/api/admin/engagements/{engagement_id}/recipe")
    def recipe(engagement_id: str, request: Request, body: RecipeChoice) -> dict[str, Any]:
        """What order the work happens in, for this engagement."""
        return _guard(
            lambda: {
                "version": console.set_recipe(
                    engagement_id, body.recipe, who=who(request, body.who), reason=body.reason
                )
            }
        )

    @app.post("/api/admin/engagements/{engagement_id}/review-level")
    def review_level(engagement_id: str, request: Request, body: ReviewLevel) -> dict[str, Any]:
        return _guard(
            lambda: (
                console.set_review_level(
                    engagement_id, body.level, who=who(request, body.who), reason=body.reason
                ).__dict__
            )
        )

    @app.get("/api/admin/engagements/{engagement_id}/profile/template")
    def profile_template(engagement_id: str) -> dict[str, Any]:
        """A skeleton to fill in, and what preflight still says is missing."""
        return _guard(lambda: console.profile_template(engagement_id))

    @app.post("/api/admin/engagements/{engagement_id}/profile")
    def profile(engagement_id: str, request: Request, body: Profile) -> dict[str, Any]:
        return _guard(
            lambda: {
                "version": console.set_profile(
                    engagement_id, body.profile, who=who(request, body.who), reason=body.reason
                )
            }
        )

    @app.post("/api/admin/engagements/{engagement_id}/bind")
    def bind(engagement_id: str, request: Request, body: Binding) -> dict[str, Any]:
        return _guard(
            lambda: (
                console.bind_engagement(
                    engagement_id,
                    who=who(request, body.who),
                    reason=body.reason,
                    destination_id=body.destination_id,
                    template_pin=body.template_pin,
                    watch_id=body.watch_id,
                    folder=body.folder,
                ).__dict__
            )
        )

    @app.post("/api/admin/models")
    def bind_model(request: Request, body: ModelBinding) -> dict[str, Any]:
        return _guard(
            lambda: {
                "version": console.bind_model(
                    body.layer,
                    body.file,
                    body.template_version,
                    why=body.why,
                    who=who(request, body.who),
                    reason=body.reason,
                )
            }
        )

    @app.post("/api/admin/watches")
    def add_watch(request: Request, body: WatchBody) -> dict[str, Any]:
        watch = Watch(
            body.id, body.kind, body.name, body.root, body.recipe, body.engagement_id, body.depth
        )
        return _guard(
            lambda: {"version": console.add_watch(watch, who=who(request, body.who),
                reason=body.reason)}
        )

    @app.post("/api/admin/destinations")
    def add_destination(request: Request, body: DestinationBody) -> dict[str, Any]:
        destination = Destination(body.id, body.name, body.path, body.adapter, body.credential)
        return _guard(
            lambda: {
                "version": console.add_destination(destination, who=who(request, body.who),
                    reason=body.reason)
            }
        )

    @app.post("/api/admin/credentials")
    def record_credential(request: Request, body: CredentialBody) -> dict[str, Any]:
        return _guard(
            lambda: {
                "version": console.record_credential(
                    body.name,
                    body.purpose,
                    expires_on=body.expires_on,
                    who=who(request, body.who),
                    reason=body.reason,
                )
            }
        )

    return app


def _guard[T](action: Callable[[], T]) -> T:
    """A refusal is a diagnostic the client can act on, not a stack trace."""
    try:
        return action()
    except AdminRefused as refused:
        raise HTTPException(
            status_code=409,
            detail={"refused": [d.as_dict() for d in refused.diagnostics]},
        ) from refused
    except DiagnosticError as refused:
        raise HTTPException(
            status_code=422, detail={"refused": [refused.diagnostic.as_dict()]}
        ) from refused
    except (KeyError, ValueError) as bad:
        raise HTTPException(status_code=400, detail=str(bad)) from bad
