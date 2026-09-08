"""Who is asking, for any surface that writes to the record.

Shared by the admin console and the ops console. The identity middleware resolves the
person on every request; this is the one place a handler turns that into the name it
records, and the one place a request that disagrees about who is making it is refused.
"""

from __future__ import annotations

from fastapi import HTTPException, Request

from registries.errors import ADMIN_FORBIDDEN, diagnose

__all__ = ["who"]


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
