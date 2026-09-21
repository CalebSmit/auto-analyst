"""A Box that answers from a local folder, for tests.

The point is not to have a mock. It is that `ports/storage/box.py` can run the **same**
conformance suite as every other storage adapter - `tests/p03` parameterises over the
folder adapter and this one together, with the same fixture tree behind both. A port whose
adapters are each tested their own way is not an interface, and Box arriving as the first
network adapter is exactly when that would have started to be true.

What it replays is Box's shapes, not Box: the token exchange, `GET /2.0/folders/{id}/items`
with its `entries` / `total_count` pagination, and `GET /2.0/files/{id}/content`. Ids are
derived from the path so the map stays consistent without the fake holding state, and the
tree is re-read on every request so a test that writes a file after construction sees it.

**This is not evidence that Box works.** It is evidence that the adapter uses the API the
way the API is documented to behave. The difference is the whole reason P93 exists.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs

import httpx2

SEP = b"\r\n\r\n"
"""Where a multipart part's headers stop and its body starts."""

ROOT_ID = "0"
"""Box's own name for the root of an account. Using it makes the fixture read like Box."""


def folder_id(relative: str) -> str:
    """A stable id for a path. Opaque enough that a test cannot accidentally depend on the
    path being recoverable from it by anything but this module."""
    if not relative:
        return ROOT_ID
    return hashlib.sha1(relative.encode("utf-8")).hexdigest()[:15]


class FakeBox:
    """Serves `root` over Box's Content API.

    The failure switches are deliberate and few. Each one exists because an adapter has to
    behave differently for it, and the difference is what the tests are for:

    * `refuse_token` - the app has no "Generate User Access Tokens" permission, which is
      the single most likely thing to be wrong the first time this runs at work.
    * `refuse_with` - a 401 or 403 on an API call, which is a credential problem rather
      than a missing file.
    * `expire_after` - hand out a token that the next call rejects once. Proves the single
      re-authenticating retry, and proves it does not become a general retry.
    * `page_size` - fewer items per page than a folder holds, so pagination is exercised
      rather than assumed.
    * `lie_about_size` - advertise a size the content does not have. Box's metadata and
      Box's bytes can disagree, and an adapter that reported the metadata would produce a
      size no hash could be reproduced from.
    """

    def __init__(
        self,
        root: Path,
        *,
        page_size: int = 1000,
        refuse_token: str = "",
        refuse_with: int = 0,
        expire_after: int = 0,
        lie_about_size: int = 0,
    ) -> None:
        self.root = Path(root)
        self.page_size = page_size
        self.refuse_token = refuse_token
        self.refuse_with = refuse_with
        self.expire_after = expire_after
        self.lie_about_size = lie_about_size
        self.tokens_issued = 0
        self.uploads: list[str] = []
        """Every path this fake was asked to write. A test that wants to prove nothing was
        uploaded reads this rather than inferring it from the folder's contents."""
        self.calls: list[str] = []
        """Every URL path asked for, in order. A test that wants to prove nothing was
        cached between calls reads this rather than trusting the absence of a field."""

    # ------------------------------------------------------------------ the transport

    def transport(self) -> httpx2.MockTransport:
        return httpx2.MockTransport(self._handle)

    def _handle(self, request: httpx2.Request) -> httpx2.Response:
        path = request.url.path
        self.calls.append(path)

        if path == "/oauth2/token":
            return self._token(request)
        if self.refuse_with:
            return _json(self.refuse_with, {"message": "forced by the test"})
        if self.expire_after and len(self.calls) - 1 > self.expire_after:
            # One expiry, then the next token works. A permanent 401 is `refuse_with`.
            self.expire_after = 0
            return _json(401, {"message": "the access token expired"})

        if path.startswith("/2.0/folders/") and path.endswith("/items"):
            return self._items(request, path.split("/")[3])
        if path == "/2.0/folders" and request.method == "POST":
            return self._make_folder(request)
        # Uploads go to upload.box.com, under /api/2.0 rather than /2.0. Serving them at
        # the same path as everything else would hide an adapter that sent content to the
        # wrong host, which Box answers with a redirect nobody reads carefully.
        if path == "/api/2.0/files/content" and request.method == "POST":
            return self._upload_new(request)
        if path.startswith("/api/2.0/files/") and path.endswith("/content"):
            return self._upload_version(request, path.split("/")[4])
        if path.startswith("/2.0/files/") and path.endswith("/content"):
            return self._content(path.split("/")[3])
        return _json(404, {"message": f"no such Box route: {path}"})

    # ------------------------------------------------------------------ writing

    def _make_folder(self, request: httpx2.Request) -> httpx2.Response:
        body = json.loads(request.content)
        parent = self._path_of(str(body["parent"]["id"]), want_dir=True)
        if parent is None:
            return _json(404, {"message": "no such parent"})
        made = parent / str(body["name"])
        if made.exists():
            # Box's answer when the name is taken. The adapter has to look again rather
            # than treat it as a failure, because the other copier creates folders too.
            return _json(409, {"code": "item_name_in_use"})
        made.mkdir()
        return _json(201, self._entry(made))

    def _upload_new(self, request: httpx2.Request) -> httpx2.Response:
        attributes, data = _multipart(request)
        parent = self._path_of(str(attributes["parent"]["id"]), want_dir=True)
        if parent is None:
            return _json(404, {"message": "no such parent"})
        target = parent / str(attributes["name"])
        if target.exists():
            return _json(409, {"code": "item_name_in_use"})
        target.write_bytes(data)
        self.uploads.append(target.relative_to(self.root).as_posix())
        return _json(201, {"entries": [self._entry(target)]})

    def _upload_version(self, request: httpx2.Request, box_id: str) -> httpx2.Response:
        found = self._path_of(box_id, want_dir=False)
        if found is None:
            return _json(404, {"message": "no such file"})
        _, data = _multipart(request)
        # Box keeps the previous version. The fake keeps it beside, so a test can prove
        # a re-send did not destroy what was there.
        n = 1
        while (found.with_name(f"{found.stem}.v{n}{found.suffix}")).exists():
            n += 1
        found.with_name(f"{found.stem}.v{n}{found.suffix}").write_bytes(found.read_bytes())
        found.write_bytes(data)
        self.uploads.append(found.relative_to(self.root).as_posix())
        return _json(201, {"entries": [self._entry(found)]})

    # ------------------------------------------------------------------ the routes

    def _token(self, request: httpx2.Request) -> httpx2.Response:
        form = parse_qs(request.content.decode("utf-8"))
        if self.refuse_token:
            return _json(400, {"error": self.refuse_token, "error_description": "refused"})
        # Box ignores a client-credentials grant's subject fields only when the app is not
        # allowed to impersonate; when it is, their absence is what makes the token the
        # service account's. The adapter must always send them, so the fake insists.
        if form.get("box_subject_type") != ["user"] or not form.get("box_subject_id"):
            return _json(
                400,
                {
                    "error": "invalid_request",
                    "error_description": "no box_subject_id: this token would be the "
                    "service account's, which is a member of nothing",
                },
            )
        self.tokens_issued += 1
        return _json(200, {"access_token": f"tok{self.tokens_issued}", "expires_in": 3600})

    def _items(self, request: httpx2.Request, box_id: str) -> httpx2.Response:
        directory = self._path_of(box_id, want_dir=True)
        if directory is None:
            return _json(404, {"message": "no such folder"})
        entries = [self._entry(child) for child in sorted(directory.iterdir())]
        # Box's own order is not sorted; returning it sorted here would hide an adapter
        # that relied on the server's order. Reversed is the cheapest way to be unhelpful.
        entries.reverse()
        params = parse_qs(request.url.query.decode("utf-8"))
        offset = int(params.get("offset", ["0"])[0])
        limit = min(int(params.get("limit", ["1000"])[0]), self.page_size)
        return _json(
            200,
            {
                "total_count": len(entries),
                "offset": offset,
                "limit": limit,
                "entries": entries[offset : offset + limit],
            },
        )

    def _content(self, box_id: str) -> httpx2.Response:
        found = self._path_of(box_id, want_dir=False)
        if found is None:
            return _json(404, {"message": "no such file"})
        return httpx2.Response(200, content=found.read_bytes())

    # ------------------------------------------------------------------ paths and ids

    def _entry(self, path: Path) -> dict[str, Any]:
        relative = path.relative_to(self.root).as_posix()
        info = path.stat()
        entry: dict[str, Any] = {
            "id": folder_id(relative),
            "name": path.name,
            "type": "folder" if path.is_dir() else "file",
            "modified_at": datetime.fromtimestamp(info.st_mtime, tz=UTC).isoformat(),
        }
        if path.is_file():
            entry["size"] = self.lie_about_size or info.st_size
            # Box offers sha1. The adapter must not mistake it for the sha256 a figure
            # cites, so the fake offers it the way Box does.
            entry["sha1"] = hashlib.sha1(path.read_bytes()).hexdigest()
        return entry

    def _path_of(self, box_id: str, *, want_dir: bool) -> Path | None:
        if box_id == ROOT_ID:
            return self.root if want_dir else None
        for candidate in self.root.rglob("*"):
            relative = candidate.relative_to(self.root).as_posix()
            if folder_id(relative) == box_id:
                if candidate.is_dir() is not want_dir:
                    return None
                return candidate
        return None


def _multipart(request: httpx2.Request) -> tuple[dict[str, Any], bytes]:
    """The `attributes` field and the file's bytes out of a multipart upload.

    Parsed rather than assumed: Box takes the metadata as a JSON form field beside the
    content, and an adapter that sent one without the other would otherwise pass here and
    fail at work.
    """
    content_type = request.headers.get("content-type", "")
    boundary = content_type.split("boundary=", 1)[1].encode("utf-8")
    attributes: dict[str, Any] = {}
    data = b""
    for part in request.content.split(b"--" + boundary):
        if SEP not in part:
            continue
        head, body = part.split(SEP, 1)
        body = body.rsplit(b"\r\n", 1)[0]
        if b'name="attributes"' in head:
            attributes = json.loads(body)
        elif b'name="file"' in head:
            data = body
    if not attributes:
        raise AssertionError("an upload with no attributes field: Box would refuse it")
    return attributes, data


def _json(status: int, body: dict[str, Any]) -> httpx2.Response:
    return httpx2.Response(status, content=json.dumps(body).encode("utf-8"))


class Credentials:
    """A Secrets Port holding exactly the three Box needs, and nothing real.

    Built here rather than monkeypatching the environment so a test cannot pass by
    accident on a machine where somebody has set real ones.
    """

    name = "in_memory"

    def __init__(self, **values: str) -> None:
        from ports.secrets import Secret

        self._values = {
            "BOX_CLIENT_ID": "client",
            "BOX_CLIENT_SECRET": "secret",
            "BOX_USER_ID": "1234567",
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
    """The same credentials with one removed, for the tests about a missing one."""
    held = Credentials()
    for name in missing:
        held._values.pop(name, None)
    return held
