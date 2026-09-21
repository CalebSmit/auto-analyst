"""A ShareFile that answers from a local folder, for tests.

Same argument as `tests/fake_box.py`: the ShareFile adapter runs the **same** conformance
suite as the local folder and as Box, over the same fixture tree, because a port whose
adapters are each tested their own way is not an interface.

What it replays is ShareFile's shapes - the OAuth token endpoint for both the
authorization-code and refresh grants, `Items(id)/Children` with its `value` array and
OData type annotations, and `Items(id)/Download`. The things worth being awkward about are
the ones the adapter has to get right:

* items are typed by an **OData annotation**, not a field, so a folder that is treated as
  a file is a real possibility;
* the refresh grant **rotates** the refresh token, because ShareFile does and an adapter
  that drops the new one produces a login that works once;
* a spent refresh token is **refused**, which is what makes the rotation test mean
  something rather than being a value nobody checks.

**This is not evidence that ShareFile works.** It is evidence that the adapter uses the API
the way the API is documented to behave.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs

import httpx2

ROOT_ID = "fo-root"
FOLDER = "ShareFile.Api.Models.Folder"
FILE = "ShareFile.Api.Models.File"


def item_id(relative: str, *, folder: bool) -> str:
    import hashlib

    if not relative:
        return ROOT_ID
    prefix = "fo" if folder else "fi"
    return f"{prefix}-{hashlib.sha1(relative.encode('utf-8')).hexdigest()[:12]}"


class FakeShareFile:
    """Serves `root` over ShareFile's v3 API.

    Switches, each because the adapter has to behave differently:

    * `refuse_refresh` - the stored refresh token no longer works. Revoked, expired, or a
      password changed. The one case that must read as "sign in again" rather than as a
      fault a retry could fix.
    * `rotate` - hand back a new refresh token on refresh, as ShareFile does.
    * `no_refresh_token` - complete a login without one, which would give an hour of
      access and then silence.
    * `refuse_with` - a status on an API call.
    """

    def __init__(
        self,
        root: Path,
        *,
        subdomain: str = "chartwell",
        rotate: bool = False,
        refuse_refresh: bool = False,
        no_refresh_token: bool = False,
        refuse_with: int = 0,
    ) -> None:
        self.root = Path(root)
        self.subdomain = subdomain
        self.rotate = rotate
        self.refuse_refresh = refuse_refresh
        self.no_refresh_token = no_refresh_token
        self.refuse_with = refuse_with
        self.issued: list[str] = []
        """Every refresh token this fake has handed out, oldest first."""
        self.spent: set[str] = set()
        self.grants: list[str] = []
        self.calls: list[str] = []

    def transport(self) -> httpx2.MockTransport:
        return httpx2.MockTransport(self._handle)

    # ------------------------------------------------------------------ routing

    def _handle(self, request: httpx2.Request) -> httpx2.Response:
        path = request.url.path
        self.calls.append(path)
        if path == "/oauth/token":
            return self._token(request)
        if self.refuse_with:
            return _json(self.refuse_with, {"message": "forced by the test"})
        if path.endswith("/Children"):
            return self._children(request, _between(path))
        if path.endswith("/Download"):
            return self._download(_between(path))
        return _json(404, {"message": f"no such ShareFile route: {path}"})

    def _token(self, request: httpx2.Request) -> httpx2.Response:
        form = {k: v[0] for k, v in parse_qs(request.content.decode("utf-8")).items()}
        grant = form.get("grant_type", "")
        self.grants.append(grant)

        if grant == "authorization_code":
            if not form.get("code"):
                return _json(400, {"error": "invalid_grant"})
            body: dict[str, Any] = {"access_token": "at-1", "expires_in": 3600}
            if not self.no_refresh_token:
                body["refresh_token"] = self._issue()
            return _json(200, body)

        if grant == "refresh_token":
            given = form.get("refresh_token", "")
            if self.refuse_refresh:
                return _json(
                    400,
                    {"error": "invalid_grant", "error_description": "token revoked"},
                )
            if given in self.spent:
                # The point of rotation: an adapter that kept the old one lands here, and
                # it has to look like a refusal rather than like nothing happening.
                return _json(
                    400,
                    {"error": "invalid_grant", "error_description": "already used"},
                )
            if given not in self.issued:
                return _json(400, {"error": "invalid_grant", "error_description": "unknown"})
            out: dict[str, Any] = {"access_token": f"at-{len(self.grants)}", "expires_in": 3600}
            if self.rotate:
                self.spent.add(given)
                out["refresh_token"] = self._issue()
            return _json(200, out)

        return _json(400, {"error": "unsupported_grant_type"})

    def _issue(self) -> str:
        token = f"rt-{len(self.issued) + 1}"
        self.issued.append(token)
        return token

    # ------------------------------------------------------------------ items

    def _children(self, request: httpx2.Request, box_id: str) -> httpx2.Response:
        directory = self._path_of(box_id, want_dir=True)
        if directory is None:
            return _json(404, {"message": "no such folder"})
        entries = [self._entry(child) for child in sorted(directory.iterdir())]
        # Not in sorted order, so an adapter that passed the server's order through
        # would produce a different run from the same inputs and this would notice.
        entries.reverse()
        params = {k: v[0] for k, v in parse_qs(request.url.query.decode("utf-8")).items()}
        skip = int(params.get("$skip", "0"))
        top = int(params.get("$top", "1000"))
        return _json(200, {"odata.count": len(entries), "value": entries[skip : skip + top]})

    def _download(self, box_id: str) -> httpx2.Response:
        found = self._path_of(box_id, want_dir=False)
        if found is None:
            return _json(404, {"message": "no such file"})
        return httpx2.Response(200, content=found.read_bytes())

    def _entry(self, path: Path) -> dict[str, Any]:
        relative = path.relative_to(self.root).as_posix()
        info = path.stat()
        folder = path.is_dir()
        return {
            "odata.type": FOLDER if folder else FILE,
            "Id": item_id(relative, folder=folder),
            "FileName": path.name,
            "Name": path.name,
            "FileSizeBytes": 0 if folder else info.st_size,
            "ClientModifiedDate": datetime.fromtimestamp(info.st_mtime, tz=UTC)
            .isoformat()
            .replace("+00:00", "Z"),
        }

    def _path_of(self, box_id: str, *, want_dir: bool) -> Path | None:
        if box_id == ROOT_ID:
            return self.root if want_dir else None
        for candidate in self.root.rglob("*"):
            relative = candidate.relative_to(self.root).as_posix()
            if item_id(relative, folder=candidate.is_dir()) == box_id:
                return candidate if candidate.is_dir() is want_dir else None
        return None


def _between(path: str) -> str:
    """The id out of `/sf/v3/Items(fo-abc)/Children`."""
    if "Items(" not in path:
        return ""
    return path.split("Items(", 1)[1].split(")", 1)[0]


def _json(status: int, body: dict[str, Any]) -> httpx2.Response:
    return httpx2.Response(status, content=json.dumps(body).encode("utf-8"))


class Credentials:
    """A Secrets Port holding what ShareFile needs plus a vault key, and nothing real."""

    name = "in_memory"

    def __init__(self, **values: str) -> None:
        from cryptography.fernet import Fernet

        from ports.secrets import Secret

        self._values = {
            "SHAREFILE_SUBDOMAIN": "chartwell",
            "SHAREFILE_CLIENT_ID": "client",
            "SHAREFILE_CLIENT_SECRET": "secret",
            "AA_VAULT_KEY": Fernet.generate_key().decode(),
            **values,
        }
        self._secret = Secret

    def has(self, key: str) -> bool:
        return key in self._values

    def get(self, key: str) -> Any:
        return self._secret(self._values[key])

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._values))


def without(*missing: str) -> Credentials:
    held = Credentials()
    for name in missing:
        held._values.pop(name, None)
    return held


def signed_in(store: Any, subdomain: str = "chartwell", token: str = "rt-1") -> None:
    """Put a token in the store as a completed login would have.

    A helper rather than a fixture because most tests want the *already signed in* state
    and walking the whole browser flow to get there would make each of them about the
    flow instead of about what it is testing.
    """
    from ports.storage.tokens import StoredToken, now

    store.write(StoredToken("sharefile", token, subdomain, now()))
