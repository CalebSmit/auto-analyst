"""Storage adapter: a Box folder. The read side, where the documents actually are.

The build had this the other way round. `ports/storage/sharefile.py` sat on the read side
and `ports/delivery/box.py` on the write side, which assumed documents are read out of
ShareFile and deliverables written into Box. The real arrangement, settled in the fifth
interview session: the client uploads to ShareFile, the files are moved to **Box**, and
Box is where this tool reads. So Box needs an adapter on this side, and until P87 it had
none - nothing could sweep a Box folder at all.

**Authentication is client credentials with user impersonation, and the impersonation is
not optional.** A client-credentials grant alone authenticates as the *service account*,
which is a Box user that exists and can see almost nothing: it is not a member of the
folders a person works in, so `list()` would succeed and return an empty tuple. An empty
sweep and an unauthorised sweep would be indistinguishable, which is the failure this
whole port arrangement exists to prevent. So every token request carries
`box_subject_type=user` and `box_subject_id`, and the Box app has to have "Generate User
Access Tokens" enabled before Box will honour it. When it is not enabled Box refuses the
token outright, which is why that refusal has its own diagnosis naming the setting.

Three properties the port asks of every adapter, and how this one keeps them:

* **Stable order.** `list()` sorts by path. Box returns folder items in its own order and
  paginates; a sweep that inherited that order would produce a different run from the same
  inputs, and the plan hash downstream would mean nothing.
* **A sha256 that a figure can cite.** Box's own hash is **sha1**, which is not the id
  every figure in this system cites. `stat()` therefore downloads and hashes. That costs a
  round trip and is the honest price: two sources cannot share an id, and a sha1 relabelled
  as sha256 would be a lie told in the manifest.
* **No cache outliving a sweep.** A path is resolved to a Box file id by walking the folder
  tree from the root, every call, holding nothing between calls. Box ids are stable but the
  *mapping from a path to one* is not - a re-uploaded file takes a new id, and a cached
  mapping is how a run reads last week's bytes while reporting this week's name. The access
  token is cached, because a token is not a file.

What this module does not do: write anything (that is the Delivery Port), read credentials
from the environment (that is the Secrets Port), or follow a Box "shared link". Only the
folder it was pointed at.

**Nothing here has spoken to a real Box tenant.** The tests drive it through an injected
transport that replays Box's response shapes. That proves this adapter's use of the API -
its pagination, ordering, hashing and refusals - and it is not evidence that credentials,
app permissions or a folder id are right at work. P93 is where that is established, by a
person, on the machine that has them.
"""

from __future__ import annotations

# The port's method is called `list`, which shadows the builtin inside this class -
# so the annotations below name it through builtins rather than reading as recursion.
import builtins
import hashlib
import json
import os
import time
from datetime import datetime
from typing import TYPE_CHECKING, Any, NoReturn

from ports.storage import COPIED, RESENT, SKIPPED, Deposit, FileRef, FileStat
from registries.errors import (
    CREDENTIAL_REFUSED,
    MISSING_CREDENTIAL,
    UNREADABLE_FILE,
    RegistryError,
    diagnose,
)

if TYPE_CHECKING:  # pragma: no cover - import cost paid only by a type checker
    from ports.secrets import SecretsPort

__all__ = ["CREDENTIALS", "ENV_ROOT", "BoxStorage", "build"]

CREDENTIALS = ("BOX_CLIENT_ID", "BOX_CLIENT_SECRET", "BOX_USER_ID")
"""The three that work. An enterprise id is *not* among them - see the module docstring."""

ENV_ROOT = "AA_BOX_INBOX_FOLDER_ID"
"""The folder this adapter reads. Deliberately not the delivery adapter's root: the place
work is read from and the place deliverables are written to are different folders, and one
setting for both is how a deliverable lands in a client's inbox."""

API = "https://api.box.com/2.0"
UPLOAD = "https://upload.box.com/api/2.0"
"""Box uploads go to a different host from everything else. Sending content to
api.box.com is answered with a redirect nobody reads carefully."""
TOKEN_URL = "https://api.box.com/oauth2/token"
PAGE = 1000
"""Box's maximum page size. Asking for fewer would only mean more round trips."""

_FIELDS = "id,name,type,size,modified_at,sha1"
_EXPIRY_MARGIN = 60.0
"""Renew a minute early. A token that expires between the check and the call would fail
once and succeed on retry, which reads in a log as an intermittent fault rather than as
arithmetic."""


class BoxStorage:
    """Reads a Box folder tree through the Box Content API."""

    name = "box"

    def __init__(
        self,
        root_folder_id: str = "",
        *,
        secrets: SecretsPort | None = None,
        transport: Any | None = None,
    ) -> None:
        self.root_folder_id = root_folder_id or os.environ.get(ENV_ROOT, "")
        self._secrets = secrets
        self._transport = transport
        self._client: Any | None = None
        self._token: str = ""
        self._token_expires: float = 0.0
        self._subject: str = ""
        """The impersonated user's id, remembered after a token is issued so the
        connection test can show who the token was for. Not a credential: it is an
        account id, and showing it is how somebody notices it is the wrong person."""

    def __repr__(self) -> str:
        # No credential and no token, because repr is exactly where one leaks.
        return f"BoxStorage(folder={self.root_folder_id!r})"

    # ------------------------------------------------------------------ the port

    def list(self, prefix: str = "") -> tuple[FileRef, ...]:
        """Every file under prefix, sorted by path. Folders are not files."""
        start = self._root()
        base = ""
        if prefix:
            entry = self._walk(prefix)
            if entry is None or entry["type"] != "folder":
                return ()
            start = entry["id"]
            base = prefix.strip("/")

        found: builtins.list[FileRef] = []
        stack = [(start, base)]
        while stack:
            folder_id, at = stack.pop()
            for entry in self._entries(folder_id):
                path = f"{at}/{entry['name']}" if at else entry["name"]
                if entry["type"] == "folder":
                    stack.append((entry["id"], path))
                elif entry["type"] == "file":
                    found.append(FileRef(path))
        return tuple(sorted(found, key=lambda r: r.path))

    def authenticate(self) -> str:
        """Obtain a token, and say which user it is for. Raises if Box refuses.

        Public because the connection test asks this question on its own, before asking
        whether a folder can be listed. They have different repairs - one is a permission
        in the Box developer console, the other is an id copied out of a URL - and a check
        that ran them together could not tell anybody which to open.

        Returns the impersonated user's id, not the token. The id is the thing worth
        showing a person; the token is the thing that must never be shown.
        """
        self._access_token()
        return self._subject

    def read(self, ref: FileRef) -> bytes:
        return self._download(self._file_id(ref))

    def stat(self, ref: FileRef) -> FileStat:
        entry = self._walk(ref.path)
        if entry is None or entry["type"] != "file":
            _unreadable(ref.path, "no file at that path in the Box folder")
        data = self._download(entry["id"])
        return FileStat(
            ref=ref,
            # Box's own size, but the length actually received: a truncated download that
            # reported the full size would produce a hash nothing could reproduce.
            size_bytes=len(data),
            modified_at=_when(entry.get("modified_at"), ref.path),
            content_hash=f"sha256:{hashlib.sha256(data).hexdigest()}",
        )

    # ------------------------------------------------------------------ receiving

    def deposit(self, path: str, data: bytes) -> Deposit:
        """Receive a relayed copy from ShareFile. Never a silent overwrite.

        **The comparison uses Box's sha1, and that is deliberate rather than lazy.** This
        adapter refuses to let a sha1 stand in for the sha256 a figure cites, because two
        sources must not be able to share an id. The question here is a different one -
        "are these the exact bytes I already uploaded" - and for that Box's own sha1 is
        both sufficient and free, where a sha256 would mean downloading every file in the
        destination on every press of a button.
        """
        folder_id = self._ensure_folders(path.rsplit("/", 1)[0] if "/" in path else "")
        name = path.rsplit("/", 1)[-1]
        existing = next(
            (e for e in self._entries(folder_id) if e.get("name") == name), None
        )
        digest = f"sha256:{hashlib.sha256(data).hexdigest()}"

        if existing is not None and existing.get("type") == "file":
            if str(existing.get("sha1") or "") == hashlib.sha1(data).hexdigest():
                # Already here, byte for byte. Power Automate got there first, or this
                # button has been pressed twice. Nothing is written and it is reported.
                return Deposit(path, digest, SKIPPED, len(data))
            # A second version of something. Box's own versioning keeps both, which is
            # what makes this reportable rather than a collision somebody has to resolve.
            self._upload(f"{UPLOAD}/files/{existing['id']}/content", name, data, None)
            return Deposit(path, digest, RESENT, len(data))

        self._upload(f"{UPLOAD}/files/content", name, data, folder_id)
        return Deposit(path, digest, COPIED, len(data))

    def _ensure_folders(self, relative: str) -> str:
        """Make the path exist under the root, and give back the folder it ends at.

        Idempotent, and races the way a second copier does: Box answers a create with 409
        when the name is taken, which is looked up rather than treated as a failure. Power
        Automate creating the same folder a second earlier must not break this.
        """
        at = self._root()
        for segment in [s for s in relative.strip("/").split("/") if s]:
            found = next(
                (
                    e
                    for e in self._entries(at)
                    if e.get("name") == segment and e.get("type") == "folder"
                ),
                None,
            )
            if found is not None:
                at = str(found["id"])
                continue
            response = self._send(
                "POST",
                f"{API}/folders",
                json_body={"name": segment, "parent": {"id": at}},
                locator=f"box:folder/{at}/{segment}",
            )
            if response.status_code == 409:
                # Somebody created it between the look and the leap. Look again.
                again = next(
                    (
                        e
                        for e in self._entries(at)
                        if e.get("name") == segment and e.get("type") == "folder"
                    ),
                    None,
                )
                if again is None:
                    _unreadable(f"box:folder/{at}/{segment}", "Box refused to create or show it")
                at = str(again["id"])
                continue
            if response.status_code in (401, 403):
                _refused(response, f"box:folder/{at}/{segment}")
            if response.status_code >= 400:
                _unreadable(
                    f"box:folder/{at}/{segment}",
                    f"Box answered {response.status_code} creating the folder",
                )
            at = str(json.loads(response.content)["id"])
        return at

    def _upload(self, url: str, name: str, data: bytes, parent: str | None) -> None:
        attributes: dict[str, Any] = {"name": name}
        if parent is not None:
            attributes["parent"] = {"id": parent}
        response = self._send(
            "POST",
            url,
            files={"file": (name, data, "application/octet-stream")},
            form={"attributes": json.dumps(attributes)},
            locator=f"box:upload/{name}",
        )
        if response.status_code in (401, 403):
            _refused(response, f"box:upload/{name}")
        if response.status_code >= 400:
            _unreadable(
                f"box:upload/{name}", f"Box answered {response.status_code} on the upload"
            )

    # ------------------------------------------------------------------ paths to ids

    def _file_id(self, ref: FileRef) -> str:
        entry = self._walk(ref.path)
        if entry is None or entry["type"] != "file":
            _unreadable(ref.path, "no file at that path in the Box folder")
        return str(entry["id"])

    def _walk(self, path: str) -> dict[str, Any] | None:
        """Resolve a port-relative path to the Box entry at it, a segment at a time.

        Nothing is remembered between calls. A re-uploaded file takes a new Box id under
        the same name, so a cached path-to-id mapping is how a run reads last week's bytes
        while reporting this week's name - the exact failure `source_version` exists to
        catch, made invisible.
        """
        segments = [s for s in path.strip("/").split("/") if s]
        entry: dict[str, Any] = {"id": self._root(), "type": "folder", "name": ""}
        for i, segment in enumerate(segments):
            if entry["type"] != "folder":
                return None
            found = next(
                (e for e in self._entries(str(entry["id"])) if e["name"] == segment), None
            )
            if found is None:
                return None
            # A folder where a file was asked for is only an answer on the last segment.
            if found["type"] != "folder" and i < len(segments) - 1:
                return None
            entry = found
        # With no segments this is the root folder itself, which is what `list("")` wants.
        return entry

    def _root(self) -> str:
        """The folder this adapter reads, or a refusal.

        An unset root is not the root of the account. Box's root really is folder id 0, so
        an empty setting that fell through would list everything the impersonated user can
        see - every client at once, which the Policy Gate would then be asked to sort out
        one document at a time.
        """
        if not self.root_folder_id:
            raise RegistryError(
                diagnose(
                    MISSING_CREDENTIAL,
                    f"{ENV_ROOT} is not set, so this adapter has no folder to read. Set "
                    f"it to the id of the Box folder work arrives in. It is not defaulted "
                    f"to the account root, which would sweep every client at once.",
                    locator=ENV_ROOT,
                )
            )
        return self.root_folder_id

    def _entries(self, folder_id: str) -> builtins.list[dict[str, Any]]:
        """One folder's items, every page of them.

        Box paginates at `limit`; a caller that read only the first page would silently
        sweep part of a folder, which is worse than failing to sweep it.
        """
        items: builtins.list[dict[str, Any]] = []
        offset = 0
        while True:
            page = self._api(
                "GET",
                f"{API}/folders/{folder_id}/items",
                params={"limit": PAGE, "offset": offset, "fields": _FIELDS},
                locator=f"box:folder/{folder_id}",
            )
            entries = page.get("entries") or []
            items.extend(entries)
            offset += len(entries)
            total = page.get("total_count")
            if not entries or (isinstance(total, int) and offset >= total):
                return items

    # ------------------------------------------------------------------ the wire

    def _download(self, file_id: str) -> bytes:
        response = self._send(
            "GET", f"{API}/files/{file_id}/content", locator=f"box:file/{file_id}"
        )
        if response.status_code in (401, 403):
            _refused(response, f"box:file/{file_id}")
        if response.status_code >= 400:
            _unreadable(
                f"box:file/{file_id}",
                f"Box answered {response.status_code} for the file's content",
            )
        return bytes(response.content)

    def _api(
        self, method: str, url: str, *, params: dict[str, Any] | None = None, locator: str
    ) -> dict[str, Any]:
        response = self._send(method, url, params=params, locator=locator)
        if response.status_code in (401, 403):
            _refused(response, locator)
        if response.status_code >= 400:
            _unreadable(locator, f"Box answered {response.status_code}")
        try:
            body = json.loads(response.content)
        except ValueError:
            _unreadable(locator, "Box answered with something that is not JSON")
        if not isinstance(body, dict):
            _unreadable(locator, "Box answered with JSON that is not an object")
        return body

    def _send(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        files: dict[str, Any] | None = None,
        form: dict[str, Any] | None = None,
        locator: str,
    ) -> Any:
        """One request, with a single retry after re-authenticating.

        The retry exists for one case only: a token that expired between being checked and
        being used. It is not a general retry - a 401 that survives a fresh token is a
        credential problem, and retrying it would turn a clear refusal into a slow one.
        """
        import httpx2

        client = self._http()
        for attempt in (1, 2):
            try:
                response = client.request(
                    method,
                    url,
                    params=params,
                    json=json_body,
                    files=files,
                    data=form,
                    headers={"Authorization": f"Bearer {self._access_token()}"},
                )
            except httpx2.HTTPError as exc:
                _unreadable(locator, f"Box could not be reached: {exc}")
            if response.status_code == 401 and attempt == 1:
                self._token, self._token_expires = "", 0.0
                continue
            return response
        raise AssertionError  # unreachable: the loop returns or raises

    def _http(self) -> Any:
        if self._client is None:
            import httpx2

            self._client = httpx2.Client(
                transport=self._transport, follow_redirects=True, timeout=60.0
            )
        return self._client

    def _access_token(self) -> str:
        """A token, fetched when there is not a live one.

        Caching this is not caching a file. A Box token lasts about an hour, and fetching
        one per request would triple the calls a sweep makes for no property gained.
        """
        if self._token and time.monotonic() < self._token_expires:
            return self._token

        import httpx2

        secrets = self._secrets
        if secrets is None:
            from ports import get_secrets

            secrets = get_secrets()
        missing = tuple(name for name in CREDENTIALS if not secrets.has(name))
        if missing:
            raise RegistryError(
                diagnose(
                    MISSING_CREDENTIAL,
                    f"the Box storage adapter needs {', '.join(missing)}. BOX_USER_ID is "
                    f"the person whose folders are read: without it the token would "
                    f"authenticate as the service account, which is a member of nothing "
                    f"and would make an unauthorised sweep look like an empty one.",
                    locator="ports/storage/box.py",
                )
            )
        subject = str(secrets.get("BOX_USER_ID"))
        try:
            response = self._http().post(
                TOKEN_URL,
                data={
                    "grant_type": "client_credentials",
                    "client_id": str(secrets.get("BOX_CLIENT_ID")),
                    "client_secret": str(secrets.get("BOX_CLIENT_SECRET")),
                    "box_subject_type": "user",
                    "box_subject_id": subject,
                },
            )
        except httpx2.HTTPError as exc:
            _unreadable("box:token", f"Box could not be reached for a token: {exc}")
        if response.status_code >= 400:
            _refused(response, "box:token")
        try:
            body = json.loads(response.content)
            self._token = str(body["access_token"])
            expires_in = float(body.get("expires_in", 3600))
        except (ValueError, KeyError, TypeError):
            _unreadable("box:token", "Box's token response had no access_token in it")
        self._token_expires = time.monotonic() + max(expires_in - _EXPIRY_MARGIN, 0.0)
        self._subject = subject
        return self._token


def _when(raw: Any, locator: str) -> datetime:
    """Box's RFC 3339 timestamp, or a refusal.

    Guessing a time here would put a wrong `modified_at` into the Intake Window, which
    decides what counts as new. A missing one is reported instead.
    """
    if not isinstance(raw, str):
        _unreadable(locator, "Box returned a file with no modified_at")
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        _unreadable(locator, f"Box returned a modified_at that is not a timestamp: {raw!r}")


def _refused(response: Any, locator: str) -> NoReturn:
    """A credential the service rejected, which is a different repair from a missing one.

    Box says `unauthorized_client` when the app exists but has not been granted "Generate
    User Access Tokens", and that is the single most likely thing to be wrong the first
    time this runs at work. Naming it saves an afternoon.
    """
    detail, error = "", ""
    try:
        body = json.loads(response.content)
        if isinstance(body, dict):
            detail = str(body.get("error_description") or body.get("message") or "")
            # Box puts the machine-readable reason in `error` and the prose in
            # `error_description`. Reading only the prose is how the one hint worth having
            # gets missed, because the prose is whatever Box felt like saying that day.
            error = str(body.get("error") or "")
    except ValueError:
        detail, error = "", ""
    hint = (
        " Box refuses the token this way when the app does not have 'Generate User Access "
        "Tokens' enabled, which is the usual cause the first time."
        if "unauthorized_client" in f"{error} {detail}"
        else ""
    )
    raise RegistryError(
        diagnose(
            CREDENTIAL_REFUSED,
            f"Box refused the credentials with {response.status_code}"
            f"{f': {detail}' if detail else ''}.{hint}",
            locator=locator,
            expected="a token Box will honour for the impersonated user",
            found=f"HTTP {response.status_code}",
        )
    )


def _unreadable(locator: str, why: str) -> NoReturn:
    raise RegistryError(diagnose(UNREADABLE_FILE, why, locator=locator))


def build() -> BoxStorage:
    """Construct without a credential and without a network call.

    Both are deferred to the first request, so listing what exists - which `serve.py
    --check` and the admin console both do - never needs either.
    """
    return BoxStorage()
