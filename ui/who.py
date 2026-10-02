"""Who is asking, for any surface that writes to the record.

Shared by the admin console and the ops console. The identity middleware resolves the
person on every request; this is the one place a handler turns that into the name it
records, and the one place a request that disagrees about who is making it is refused.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

import ports
from registries.errors import ADMIN_FORBIDDEN, DiagnosticError, diagnose

__all__ = ["ALLOWED_HOSTS", "install_identity", "who"]


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


def _not_stored(answer: Any) -> Any:
    """Tell the browser not to keep a page.

    The three consoles are Python strings built at import time, so the only way a new one
    reaches a person is a restart - and a response with no cache headers at all is one a
    browser may reuse without asking. It does: after a restart, `/admin` kept serving the
    previous page until the URL was changed, with nothing on screen to say so. On the
    machine this is moving to that reads as "I updated it and the fix is not there".

    Only the pages. The API answers are already asked for afresh by the scripts on them, and
    a rule that reached them would be a rule about something that is not a problem.

    Written here rather than on each route because a route added later would not know to do
    it, which is how `/analytics` and `/help` would have been missed.
    """
    kind = answer.headers.get("content-type", "")
    if kind.startswith("text/html"):
        answer.headers["Cache-Control"] = "no-store"
    return answer


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
        unwelcome = _foreign(request)
        if unwelcome is not None:
            return JSONResponse(status_code=403, content={"detail": {"refused": [unwelcome]}})
        try:
            request.state.identity = port.resolve(request.client.host if request.client else None)
        except DiagnosticError as refused:
            return JSONResponse(
                status_code=401, content={"detail": {"refused": [refused.diagnostic.as_dict()]}}
            )
        answer = await call_next(request)
        return _not_stored(answer)


ALLOWED_HOSTS = frozenset({"127.0.0.1", "localhost", "::1", "testserver"})
"""The names this server answers to. `testserver` is Starlette's in-process client, which is
not reaching it over a network."""


def _foreign(request: Request) -> dict[str, Any] | None:
    """A request from somebody else's page, refused before a route sees it.

    Two checks, because the identity port can only see the socket's peer address and a
    browser presents this machine's address whatever page asked it to. The `Host` a request
    carries is the name the browser resolved, so a hostname pointed at 127.0.0.1 - the DNS
    rebinding a page does to make itself same-origin with a local tool - arrives with a Host
    this server does not answer to. `Origin` is sent on every cross-origin request, and this
    server is only ever its own pages' origin.
    """
    host = (request.headers.get("host") or "").rsplit(":", 1)[0].strip("[]").lower()
    if host and host not in ALLOWED_HOSTS:
        return diagnose(
            ADMIN_FORBIDDEN,
            f"this server answers to this machine, not to {host!r}; a page that reached it "
            f"under another name is not this machine's page",
            locator="host",
            expected="127.0.0.1",
            found=host,
        ).as_dict()
    origin = (request.headers.get("origin") or "").strip()
    if origin:
        from urllib.parse import urlsplit  # noqa: PLC0415

        # `null` used to be excused, and it is the one value that should not be. A page in
        # a sandboxed iframe sends it, so does a `file://` page, and either of those is on
        # somebody else's website. Several write routes take no body at all, which makes a
        # cross-origin POST a *simple* request - no preflight, so the absent CORS headers
        # do not stop it - and a page the analyst happens to have open could pause every
        # engagement or clear a methodology file. A null origin has no hostname, so it
        # fails the check below rather than being routed around it.
        where = urlsplit(origin).hostname or ""
        if where.lower() not in ALLOWED_HOSTS:
            return diagnose(
                ADMIN_FORBIDDEN,
                f"a page at {origin} asked this server to act; only this machine's own "
                f"pages may",
                locator="origin",
                expected="this machine",
                found=origin,
            ).as_dict()
    return None
