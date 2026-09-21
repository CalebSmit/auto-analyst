"""Storage adapter: ShareFile. Where the client uploads, before anything moves to Box.

**The thing that shapes this whole module: an MFA account cannot use a password grant.**
From the analyst's own `box.sharefile.automation` harness - *"ShareFile's password grant
cannot satisfy an MFA challenge, so any account with MFA enabled must authenticate
interactively."* So three environment variables are not a credential set. A person signs
in once, in a browser, and everything after lives on a **refresh token** that ShareFile may
replace at any refresh.

That has consequences the rest of the system has to carry rather than hide:

* **A run cannot get itself authenticated.** When there is no token, or the token has been
  revoked, the repair is a person opening a browser. That is not a retryable fault, and
  reporting it as one would put a run in a loop doing nothing.
* **Three states, not two.** *Nobody has signed in* is the state of a new machine and is
  not a failure. *Signed in, token no longer works* means revoked, expired, or a password
  change at the other end. *Connected* is the third. They have different repairs and they
  read differently.
* **A rotated token must be kept.** ShareFile returns a new refresh token on some
  refreshes. Dropping it gives a login that works once and then does not - which presents
  as an intermittent fault and is not one.

The login itself is finished on this machine: `authorize_url()` builds the link, ShareFile
redirects back to a route on the local server, and `exchange()` turns the code into tokens.
The `state` parameter is not decoration. The local server answers to any page that can
make a browser navigate to `127.0.0.1`, so without a state that was issued here and is
accepted once, any site could redirect this browser to the callback carrying *its* code and
quietly attach this tool to somebody else's ShareFile account.

**Nothing here has spoken to real ShareFile.** The tests drive it through a transport that
replays ShareFile's documented shapes. What that proves is this module's use of the API -
the flow, the rotation, the refusals, the state check - and it is not evidence that a
subdomain, a client id or a redirect registration is right at work. P93 is where that is
established, by a person, on the machine that has them.
"""

from __future__ import annotations

import builtins
import hashlib
import json
import os
import secrets as randomness
import time
from datetime import datetime
from typing import TYPE_CHECKING, Any, NoReturn
from urllib.parse import urlencode

from ports.storage import FileRef, FileStat
from ports.storage.tokens import NEVER, StoredToken, TokenStore, now
from registries.errors import (
    CREDENTIAL_REFUSED,
    MISSING_CREDENTIAL,
    UNREADABLE_FILE,
    RegistryError,
    diagnose,
)

if TYPE_CHECKING:  # pragma: no cover
    from ports.secrets import SecretsPort

__all__ = [
    "CREDENTIALS",
    "ENV_ROOT",
    "EXPIRED",
    "NEVER",
    "SERVICE",
    "ShareFileStorage",
    "authorize_url",
    "build",
    "new_state",
]

SERVICE = "sharefile"
CREDENTIALS = ("SHAREFILE_SUBDOMAIN", "SHAREFILE_CLIENT_ID", "SHAREFILE_CLIENT_SECRET")
ENV_ROOT = "AA_SHAREFILE_ROOT"

EXPIRED = "expired"
"""Signed in once, and the token no longer works. Distinct from `never` because the words
a person needs are different: one says sign in, the other says sign in *again*, and the
second usually means somebody revoked something."""

_EXPIRY_MARGIN = 60.0
_PAGE = 1000


def _host(subdomain: str) -> str:
    return f"https://{subdomain}.sharefile.com"


def new_state() -> str:
    """A one-time value tying a callback to the login that started it.

    Not decoration. This server answers to any page that can make a browser navigate to
    127.0.0.1, and a callback is a plain GET with no Origin header, so the request gate
    cannot tell one apart from a redirect somebody else arranged. Without this, a page
    could hand the tool an authorization code for an account nobody here owns.
    """
    return randomness.token_urlsafe(32)


def authorize_url(subdomain: str, client_id: str, redirect_uri: str, state: str) -> str:
    """Where the browser goes. The person signs in there, MFA included."""
    query = urlencode(
        {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "state": state,
        }
    )
    return f"{_host(subdomain)}/oauth/authorize?{query}"


class ShareFileStorage:
    """Reads a ShareFile folder, on a token a person's login produced."""

    name = "sharefile"

    def __init__(
        self,
        root: str = "",
        *,
        secrets: SecretsPort | None = None,
        tokens: TokenStore | None = None,
        transport: Any | None = None,
    ) -> None:
        self.root = root or os.environ.get(ENV_ROOT, "")
        self._secrets = secrets
        self._tokens = tokens
        self._transport = transport
        self._client: Any | None = None
        self._access: str = ""
        self._access_expires: float = 0.0

    def __repr__(self) -> str:
        return f"ShareFileStorage(root={self.root!r})"

    # ------------------------------------------------------------------ the login

    def sign_in_state(self) -> str:
        """`never`, `expired` or `present`, without asking ShareFile.

        Cheap, and therefore the thing a page can call on load. It cannot tell `present`
        from a token that was revoked five minutes ago - only a refresh can - so the
        connection test asks properly and this only says what is on disk.
        """
        return self.store().state(SERVICE)

    def begin_login(self, redirect_uri: str) -> tuple[str, str]:
        """Where the browser goes, and the one-time state that ties it back here.

        A method rather than two module functions because nothing outside `ports/` may
        import an adapter module - so a caller that had to reach for `authorize_url` and
        `new_state` separately would be breaking the boundary that makes the whole port
        arrangement worth having. Returning them together also makes it awkward to build
        the URL without a state, which is the mistake that matters.
        """
        state = new_state()
        return (
            authorize_url(
                self._credential("SHAREFILE_SUBDOMAIN"),
                self._credential("SHAREFILE_CLIENT_ID"),
                redirect_uri,
                state,
            ),
            state,
        )

    def finish_login(self, code: str, redirect_uri: str) -> StoredToken:
        """Turn an authorization code into a stored refresh token."""
        subdomain = self._credential("SHAREFILE_SUBDOMAIN")
        body = self._form(
            f"{_host(subdomain)}/oauth/token",
            {
                "grant_type": "authorization_code",
                "code": code,
                "client_id": self._credential("SHAREFILE_CLIENT_ID"),
                "client_secret": self._credential("SHAREFILE_CLIENT_SECRET"),
                "redirect_uri": redirect_uri,
            },
            locator="sharefile:login",
        )
        refresh = str(body.get("refresh_token") or "")
        if not refresh:
            _refused(
                "sharefile:login",
                "ShareFile returned no refresh_token, so this login would last an hour "
                "and then stop. The app registration has to ask for offline access.",
            )
        stored = StoredToken(SERVICE, refresh, subdomain, now())
        self.store().write(stored)
        self._take_access(body)
        return stored

    def authenticate(self) -> str:
        """Exchange the stored refresh token for an access token. Returns the subdomain.

        Public because the connection test asks this on its own: a refresh failing and a
        folder failing are different repairs, and one of them is "open a browser".
        """
        self._access_token()
        return self._credential("SHAREFILE_SUBDOMAIN")

    def store(self) -> TokenStore:
        if self._tokens is None:
            self._tokens = TokenStore(self._secrets_port())
        return self._tokens

    # ------------------------------------------------------------------ the port

    def list(self, prefix: str = "") -> tuple[FileRef, ...]:
        start = self._root()
        base = ""
        if prefix:
            found = self._walk(prefix)
            if found is None or not _is_folder(found):
                return ()
            start, base = str(found["Id"]), prefix.strip("/")

        out: builtins.list[FileRef] = []
        stack = [(start, base)]
        while stack:
            folder_id, at = stack.pop()
            for item in self._children(folder_id):
                name = str(item.get("FileName") or item.get("Name") or "")
                if not name:
                    continue
                path = f"{at}/{name}" if at else name
                if _is_folder(item):
                    stack.append((str(item["Id"]), path))
                else:
                    out.append(FileRef(path))
        return tuple(sorted(out, key=lambda r: r.path))

    def read(self, ref: FileRef) -> bytes:
        item = self._walk(ref.path)
        if item is None or _is_folder(item):
            _unreadable(ref.path, "no file at that path in ShareFile")
        return self._download(str(item["Id"]))

    def stat(self, ref: FileRef) -> FileStat:
        item = self._walk(ref.path)
        if item is None or _is_folder(item):
            _unreadable(ref.path, "no file at that path in ShareFile")
        # ShareFile offers an MD5-ish hash and this system cites sha256, so the bytes are
        # fetched and hashed here. The same trade the Box adapter makes, for the same
        # reason: two sources cannot share an id.
        data = self._download(str(item["Id"]))
        return FileStat(
            ref=ref,
            size_bytes=len(data),
            modified_at=_when(item.get("ClientModifiedDate") or item.get("CreationDate"), ref.path),
            content_hash=f"sha256:{hashlib.sha256(data).hexdigest()}",
        )

    # ------------------------------------------------------------------ paths to ids

    def _root(self) -> str:
        if not self.root:
            raise RegistryError(
                diagnose(
                    MISSING_CREDENTIAL,
                    f"{ENV_ROOT} is not set, so this adapter has no folder to read. It is "
                    f"not defaulted to the account root, which would reach every client "
                    f"at once.",
                    locator=ENV_ROOT,
                )
            )
        return self.root

    def _walk(self, path: str) -> dict[str, Any] | None:
        """A segment at a time, holding nothing between calls - as the Box adapter does,
        and for the same reason: a re-uploaded file takes a new id under the same name."""
        segments = [s for s in path.strip("/").split("/") if s]
        item: dict[str, Any] = {"Id": self._root(), "odata.type": "ShareFile.Api.Models.Folder"}
        for i, segment in enumerate(segments):
            if not _is_folder(item):
                return None
            found = next(
                (
                    child
                    for child in self._children(str(item["Id"]))
                    if (child.get("FileName") or child.get("Name")) == segment
                ),
                None,
            )
            if found is None:
                return None
            if not _is_folder(found) and i < len(segments) - 1:
                return None
            item = found
        return item

    def _children(self, folder_id: str) -> builtins.list[dict[str, Any]]:
        items: builtins.list[dict[str, Any]] = []
        skip = 0
        while True:
            body = self._api(
                f"{self._api_root()}/Items({folder_id})/Children",
                params={"$top": _PAGE, "$skip": skip},
                locator=f"sharefile:folder/{folder_id}",
            )
            page = body.get("value") or []
            items.extend(page)
            skip += len(page)
            if not page or len(page) < _PAGE:
                return items

    def _api_root(self) -> str:
        return f"{_host(self._credential('SHAREFILE_SUBDOMAIN'))}/sf/v3"

    # ------------------------------------------------------------------ the wire

    def _download(self, item_id: str) -> bytes:
        response = self._send(
            "GET", f"{self._api_root()}/Items({item_id})/Download",
            locator=f"sharefile:file/{item_id}",
        )
        if response.status_code in (401, 403):
            _refused(f"sharefile:file/{item_id}", f"ShareFile answered {response.status_code}")
        if response.status_code >= 400:
            _unreadable(
                f"sharefile:file/{item_id}",
                f"ShareFile answered {response.status_code} for the file's content",
            )
        return bytes(response.content)

    def _api(self, url: str, *, params: dict[str, Any], locator: str) -> dict[str, Any]:
        response = self._send("GET", url, params=params, locator=locator)
        if response.status_code in (401, 403):
            _refused(locator, f"ShareFile answered {response.status_code}")
        if response.status_code >= 400:
            _unreadable(locator, f"ShareFile answered {response.status_code}")
        try:
            body = json.loads(response.content)
        except ValueError:
            _unreadable(locator, "ShareFile answered with something that is not JSON")
        return dict(body) if isinstance(body, dict) else {}

    def _send(
        self, method: str, url: str, *, params: dict[str, Any] | None = None, locator: str
    ) -> Any:
        import httpx2

        client = self._http()
        for attempt in (1, 2):
            try:
                response = client.request(
                    method,
                    url,
                    params=params,
                    headers={"Authorization": f"Bearer {self._access_token()}"},
                )
            except httpx2.HTTPError as exc:
                _unreadable(locator, f"ShareFile could not be reached: {exc}")
            if response.status_code == 401 and attempt == 1:
                self._access, self._access_expires = "", 0.0
                continue
            return response
        raise AssertionError  # unreachable

    def _form(self, url: str, data: dict[str, str], *, locator: str) -> dict[str, Any]:
        import httpx2

        try:
            response = self._http().post(url, data=data)
        except httpx2.HTTPError as exc:
            _unreadable(locator, f"ShareFile could not be reached: {exc}")
        if response.status_code >= 400:
            detail = ""
            try:
                body = json.loads(response.content)
                if isinstance(body, dict):
                    detail = str(body.get("error_description") or body.get("error") or "")
            except ValueError:
                detail = ""
            _refused(locator, f"ShareFile refused with {response.status_code}"
                     f"{f': {detail}' if detail else ''}")
        try:
            body = json.loads(response.content)
        except ValueError:
            _unreadable(locator, "ShareFile's token response was not JSON")
        return dict(body) if isinstance(body, dict) else {}

    def _http(self) -> Any:
        if self._client is None:
            import httpx2

            self._client = httpx2.Client(
                transport=self._transport, follow_redirects=True, timeout=120.0
            )
        return self._client

    def _access_token(self) -> str:
        if self._access and time.monotonic() < self._access_expires:
            return self._access

        held = self.store().read(SERVICE)
        if held is None:
            raise RegistryError(
                diagnose(
                    CREDENTIAL_REFUSED,
                    "nobody has signed in to ShareFile on this machine. An account with "
                    "MFA cannot be signed in by a program, so this is a person opening a "
                    "browser once - not something a run can do for itself, and not "
                    "something to retry.",
                    locator=f"sharefile:{NEVER}",
                    expected="a stored refresh token",
                    found="none",
                )
            )
        body = self._form(
            f"{_host(held.subdomain)}/oauth/token",
            {
                "grant_type": "refresh_token",
                "refresh_token": held.refresh_token,
                "client_id": self._credential("SHAREFILE_CLIENT_ID"),
                "client_secret": self._credential("SHAREFILE_CLIENT_SECRET"),
            },
            locator=f"sharefile:{EXPIRED}",
        )
        rotated = str(body.get("refresh_token") or "")
        if rotated and rotated != held.refresh_token:
            # ShareFile replaced it. Keeping the old one would give a login that works
            # once and then does not, which reads as an intermittent fault and is not.
            self.store().write(
                StoredToken(SERVICE, rotated, held.subdomain, now())
            )
        self._take_access(body)
        return self._access

    def _take_access(self, body: dict[str, Any]) -> None:
        token = str(body.get("access_token") or "")
        if not token:
            _refused("sharefile:token", "ShareFile's response carried no access_token")
        self._access = token
        try:
            lasts = float(body.get("expires_in", 3600))
        except (TypeError, ValueError):
            lasts = 3600.0
        self._access_expires = time.monotonic() + max(lasts - _EXPIRY_MARGIN, 0.0)

    # ------------------------------------------------------------------ credentials

    def _secrets_port(self) -> Any:
        if self._secrets is None:
            from ports import get_secrets

            self._secrets = get_secrets()
        return self._secrets

    def _credential(self, name: str) -> str:
        secrets = self._secrets_port()
        if not secrets.has(name):
            raise RegistryError(
                diagnose(
                    MISSING_CREDENTIAL,
                    f"the ShareFile adapter needs {name}, which the environment does not "
                    f"set. See .env.example.",
                    locator=name,
                )
            )
        return str(secrets.get(name))


def missing_credentials(secrets: Any) -> tuple[str, ...]:
    """Which of the three are not set. Presence only; no value is read."""
    return tuple(name for name in CREDENTIALS if not secrets.has(name))


def _is_folder(item: dict[str, Any]) -> bool:
    """ShareFile types items through an OData annotation rather than a field.

    Checked by suffix because the annotation key itself has varied across versions
    (`odata.type`, `@odata.type`), and being wrong about this would put folders in a list
    of files - which downstream would try to read and report as unreadable documents.
    """
    kind = str(item.get("odata.type") or item.get("@odata.type") or "")
    return kind.endswith("Folder")


def _when(raw: Any, locator: str) -> datetime:
    if not isinstance(raw, str):
        _unreadable(locator, "ShareFile returned an item with no modified date")
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        _unreadable(locator, f"ShareFile returned a date that is not a timestamp: {raw!r}")


def _refused(locator: str, why: str) -> NoReturn:
    raise RegistryError(
        diagnose(
            CREDENTIAL_REFUSED,
            f"{why} Sign in again: a refresh token that no longer works has been revoked, "
            f"expired, or belongs to a password that changed. A run cannot do this for "
            f"itself, because an MFA account cannot be signed in by a program.",
            locator=locator,
        )
    )


def _unreadable(locator: str, why: str) -> NoReturn:
    raise RegistryError(diagnose(UNREADABLE_FILE, why, locator=locator))


def build() -> ShareFileStorage:
    """Construct without a credential, a token or a network call."""
    return ShareFileStorage()
