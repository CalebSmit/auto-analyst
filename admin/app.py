"""The FastAPI surface over the Admin Console.

Every write carries `who` and `reason`, because every write lands in the Config Change
Log and the log refuses an entry without either. A refusal comes back as a diagnostic:
code, owner, expected, found, what_now.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from admin.console import AdminConsole, AdminRefused
from intake.config import Destination, Watch
from intake.roster import RosterEntry, RosterState
from registries.errors import DiagnosticError

__all__ = ["create_admin_app"]


class Change(BaseModel):
    who: str
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


def create_admin_app(console: AdminConsole) -> FastAPI:
    app = FastAPI(title="Chartwell Automated Analyst - admin", docs_url=None, redoc_url=None)

    @app.get("/api/admin/setup")
    def setup() -> dict[str, Any]:
        return console.setup()

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

    @app.post("/api/admin/engagements")
    def register(body: Registration) -> dict[str, Any]:
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
                    entry, profile=body.profile, who=body.who, reason=body.reason
                ).__dict__
            )
        )

    @app.post("/api/admin/engagements/{engagement_id}/activate")
    def activate(engagement_id: str, body: Change) -> dict[str, Any]:
        return _guard(
            lambda: console.activate(engagement_id, who=body.who, reason=body.reason).__dict__
        )

    @app.post("/api/admin/engagements/{engagement_id}/pause")
    def pause(engagement_id: str, body: Change) -> dict[str, Any]:
        return _guard(
            lambda: console.pause(engagement_id, who=body.who, reason=body.reason).__dict__
        )

    @app.post("/api/admin/engagements/{engagement_id}/archive")
    def archive(engagement_id: str, body: Change) -> dict[str, Any]:
        return _guard(
            lambda: console.archive(engagement_id, who=body.who, reason=body.reason).__dict__
        )

    @app.post("/api/admin/engagements/{engagement_id}/budget")
    def budget(engagement_id: str, body: Budget) -> dict[str, Any]:
        return _guard(
            lambda: (
                console.set_budget(
                    engagement_id, body.usd, who=body.who, reason=body.reason
                ).__dict__
            )
        )

    @app.post("/api/admin/engagements/{engagement_id}/review-level")
    def review_level(engagement_id: str, body: ReviewLevel) -> dict[str, Any]:
        return _guard(
            lambda: (
                console.set_review_level(
                    engagement_id, body.level, who=body.who, reason=body.reason
                ).__dict__
            )
        )

    @app.post("/api/admin/engagements/{engagement_id}/profile")
    def profile(engagement_id: str, body: Profile) -> dict[str, Any]:
        return _guard(
            lambda: {
                "version": console.set_profile(
                    engagement_id, body.profile, who=body.who, reason=body.reason
                )
            }
        )

    @app.post("/api/admin/engagements/{engagement_id}/bind")
    def bind(engagement_id: str, body: Binding) -> dict[str, Any]:
        return _guard(
            lambda: (
                console.bind_engagement(
                    engagement_id,
                    who=body.who,
                    reason=body.reason,
                    destination_id=body.destination_id,
                    template_pin=body.template_pin,
                    watch_id=body.watch_id,
                    folder=body.folder,
                ).__dict__
            )
        )

    @app.post("/api/admin/models")
    def bind_model(body: ModelBinding) -> dict[str, Any]:
        return _guard(
            lambda: {
                "version": console.bind_model(
                    body.layer,
                    body.file,
                    body.template_version,
                    why=body.why,
                    who=body.who,
                    reason=body.reason,
                )
            }
        )

    @app.post("/api/admin/watches")
    def add_watch(body: WatchBody) -> dict[str, Any]:
        watch = Watch(
            body.id, body.kind, body.name, body.root, body.recipe, body.engagement_id, body.depth
        )
        return _guard(
            lambda: {"version": console.add_watch(watch, who=body.who, reason=body.reason)}
        )

    @app.post("/api/admin/destinations")
    def add_destination(body: DestinationBody) -> dict[str, Any]:
        destination = Destination(body.id, body.name, body.path, body.adapter, body.credential)
        return _guard(
            lambda: {
                "version": console.add_destination(destination, who=body.who, reason=body.reason)
            }
        )

    @app.post("/api/admin/credentials")
    def record_credential(body: CredentialBody) -> dict[str, Any]:
        return _guard(
            lambda: {
                "version": console.record_credential(
                    body.name,
                    body.purpose,
                    expires_on=body.expires_on,
                    who=body.who,
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
