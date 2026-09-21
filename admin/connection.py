"""The connection test: four questions, asked in order, answered separately.

"Connection failed" is not an answer. The credentials live in `.env`, the permission that
lets a token impersonate lives in the Box developer console, and the folder id is copied
out of a URL - three settings on three screens, and knowing which one to open is the whole
value of pressing the button.

So the test walks four steps and reports each on its own:

1. **credentials** - are the three names set. Asked of the Secrets Port with `has()`, so
   no value is read in order to test one.
2. **token** - will Box issue an access token for the impersonated user. This is where a
   missing "Generate User Access Tokens" permission surfaces, and it is the single most
   likely thing to be wrong the first time.
3. **folder** - can the configured folder be listed. A wrong id and a refused credential
   fail here differently, which is the point of asking after the token rather than with it.
4. **file** - can a file's bytes actually be read. Listing a folder and downloading from it
   are different API calls with different failure modes, and a sweep needs both.

**A step after a failure is `not reached`, never `fail`.** Reporting the folder as failed
when the token never issued would send somebody to the Box console to fix a folder id that
was fine. The ordering carries information and throwing it away would make the report
worse than no report.

**An empty folder is not a broken connection.** Nothing can be downloaded from it, so the
file step reports `not reached` with that reason - a Monday morning before anything has
arrived is a normal state, and a test that called it a failure would be ignored by
Wednesday.

What this proves is that the connection worked **when the button was pressed**. Tokens
expire, permissions get revoked and folders get moved; a green test is evidence about a
moment, and the report says so in those words rather than implying a standing guarantee.

Nothing read is kept. The file step downloads the first file in the folder to prove the
call works, reports its name and its length, and discards the bytes - they are a client's
documents, and this is a plumbing check rather than a reason to hold them anywhere.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from registries.errors import Diagnostic, DiagnosticError

PASS = "pass"
FAIL = "fail"
NOT_REACHED = "not reached"

SHAREFILE_STEPS: tuple[tuple[str, str], ...] = (
    ("credentials", "The three ShareFile credentials are set"),
    ("signed_in", "Somebody has signed in on this machine"),
    ("token", "The stored refresh token still works"),
    ("folder", "The configured folder can be listed"),
    ("file", "A file's bytes can be read"),
)
"""Five, not four. ShareFile has a state Box does not: *nobody has signed in yet*, which
is the state of a new machine and is not a fault anything can retry. Folding it into the
token step would produce one message covering "open a browser" and "your token was
revoked", which are the same sentence to a computer and different afternoons to a person.
"""

BOX_STEPS: tuple[tuple[str, str], ...] = (
    ("credentials", "The three Box credentials are set"),
    ("token", "Box issues a token for the impersonated user"),
    ("folder", "The configured folder can be listed"),
    ("file", "A file's bytes can be read"),
)


@dataclass(frozen=True)
class Step:
    """One question and its answer."""

    id: str
    label: str
    status: str
    """`pass`, `fail`, or `not reached`."""
    detail: str
    diagnostic: Diagnostic | None = None

    def line(self) -> str:
        return f"[{self.status.upper():<11}] {self.label}: {self.detail}"


@dataclass(frozen=True)
class ConnectionReport:
    service: str
    ran_at: str
    steps: tuple[Step, ...]
    in_use: bool = True
    """Whether runs actually read through this adapter.

    A trap worth closing: the test builds a Box adapter deliberately, so it passes whether
    or not `AA_STORAGE_ADAPTER` names box. Somebody could get four ticks and still have
    every sweep reading the local folder, and would have no reason to suspect it. So the
    report says which, rather than leaving a green result to imply something it does not
    mean.
    """

    @property
    def connected(self) -> bool:
        """True when nothing failed.

        `not reached` is deliberately not a failure: an empty folder leaves the file step
        unreached and the connection is still good. What would make this wrong is a step
        left unreached *by* a failure - and that failure is itself in the list, so this
        stays honest without needing to know why any step stopped.
        """
        return not any(s.status == FAIL for s in self.steps)

    @property
    def failed(self) -> Step | None:
        """The one step to read. There is at most one, because the walk stops."""
        return next((s for s in self.steps if s.status == FAIL), None)

    def as_dict(self) -> dict[str, Any]:
        return {
            "service": self.service,
            "ran_at": self.ran_at,
            "connected": self.connected,
            "in_use": self.in_use,
            # Said here rather than only in a docstring, because this is what the page
            # renders and the page is where somebody could read more into a tick than it
            # means.
            "proves": "the connection worked when the button was pressed, and nothing "
            "about later - a token expires, a permission can be revoked, a folder moved",
            "steps": [
                {
                    "id": s.id,
                    "label": s.label,
                    "status": s.status,
                    "detail": s.detail,
                    **({"diagnostic": s.diagnostic.as_dict()} if s.diagnostic else {}),
                }
                for s in self.steps
            ],
        }

    def report(self) -> str:
        head = f"{self.service}: {'connected' if self.connected else 'NOT CONNECTED'}"
        lines = [f"{head}  ({self.ran_at})", *(f"  {s.line()}" for s in self.steps)]
        if self.connected and not self.in_use:
            lines.append(
                f"  NOTE: runs are not reading through {self.service}. Set "
                f"AA_STORAGE_ADAPTER={self.service} to make this the adapter a sweep "
                f"uses; until then this proves the plumbing and changes nothing."
            )
        return "\n".join(lines)


def probe_box(storage: Any, secrets: Any, *, in_use: bool = True) -> ConnectionReport:
    """Walk the four steps against a Box storage adapter.

    Named `probe_` rather than `test_` for a dull reason worth writing down: pytest
    collects any function whose name starts with `test`, so a production function called
    `test_box` becomes a broken test case in every module that imports it.

    Takes the adapter rather than building one so the caller decides which Box is being
    tested - the configured one at `/admin`, a replayed one in a test. A function that
    reached for the global adapter could only ever test the machine it ran on.
    """
    done: list[Step] = []

    for step_id, label in BOX_STEPS:
        if done and done[-1].status != PASS:
            done.append(
                Step(
                    step_id,
                    label,
                    NOT_REACHED,
                    f"not asked: {done[-1].id} did not pass",
                )
            )
            continue
        done.append(_ask(step_id, label, storage, secrets))

    return ConnectionReport(
        service="box",
        ran_at=datetime.now(tz=UTC).isoformat(timespec="seconds"),
        steps=tuple(done),
        in_use=in_use,
    )


def _refusal(step_id: str, label: str, refused: DiagnosticError) -> Step:
    """A failed step carries the adapter's own diagnosis, word for word.

    One function rather than three copies because the point of the whole module is that
    the three failures read differently - and three places that each decide how to say
    "it failed" is how they slowly start reading the same.
    """
    return Step(step_id, label, FAIL, refused.diagnostic.detail, refused.diagnostic)


def probe_sharefile(storage: Any, secrets: Any, *, in_use: bool = True) -> ConnectionReport:
    """Walk the five steps against a ShareFile adapter.

    The shape is the same as Box's and the middle is not. ShareFile cannot be signed in by
    a program at all - an MFA challenge needs a person - so the report's job is partly to
    say *that*, plainly, rather than presenting a login as something that failed.
    """
    done: list[Step] = []
    for step_id, label in SHAREFILE_STEPS:
        if done and done[-1].status != PASS:
            done.append(Step(step_id, label, NOT_REACHED, f"not asked: {done[-1].id} did not pass"))
            continue
        done.append(_ask_sharefile(step_id, label, storage, secrets))
    return ConnectionReport(
        service="sharefile",
        ran_at=datetime.now(tz=UTC).isoformat(timespec="seconds"),
        steps=tuple(done),
        in_use=in_use,
    )


def _ask_sharefile(step_id: str, label: str, storage: Any, secrets: Any) -> Step:
    if step_id == "credentials":
        return _named_credentials(step_id, label, secrets, "storage", "sharefile")
    if step_id == "signed_in":
        return _signed_in(label, storage)
    if step_id == "token":
        return _refresh(label, storage)
    if step_id == "folder":
        return _folder(label, storage)
    return _file(label, storage)


def _signed_in(label: str, storage: Any) -> Step:
    """Is there a token at all. Asked of the disk, so it costs nothing and cannot be
    confused with the question of whether the token still works."""
    from ports.storage.tokens import NEVER

    if storage.sign_in_state() == NEVER:
        return Step(
            "signed_in",
            label,
            FAIL,
            "nobody has signed in to ShareFile on this machine yet. Press Sign in - a "
            "ShareFile account with MFA cannot be signed in by a program, so this part is "
            "always a person with a browser, once.",
        )
    return Step("signed_in", label, PASS, "a refresh token from an earlier login is stored")


def _refresh(label: str, storage: Any) -> Step:
    """Does the stored token still work. The only way to know is to spend it."""
    try:
        subdomain = storage.authenticate()
    except DiagnosticError as refused:
        return _refusal("token", label, refused)
    return Step("token", label, PASS, f"exchanged for an access token on {subdomain}")


def _ask(step_id: str, label: str, storage: Any, secrets: Any) -> Step:
    if step_id == "credentials":
        return _credentials(label, secrets)
    if step_id == "token":
        return _token(label, storage)
    if step_id == "folder":
        return _folder(label, storage)
    return _file(label, storage)


def _named_credentials(
    step_id: str, label: str, secrets: Any, port: str, adapter: str
) -> Step:
    """Presence, never a value.

    `has()` exists for exactly this: a check that can report "BOX_USER_ID is missing"
    without there being a code path capable of printing one that is not.

    The names are asked of the ports registry rather than imported from the adapter:
    nothing outside `ports/` may name a concrete adapter module, and hard-coding them here
    is how they go stale - the Box three already changed once.
    """
    import ports

    names = ports.credentials_for(port, adapter)
    missing = tuple(name for name in names if not secrets.has(name))
    if missing:
        return Step(
            step_id,
            label,
            FAIL,
            f"not set: {', '.join(missing)}. Add them to .env - no value is read here, "
            f"only whether one is there.",
        )
    return Step(step_id, label, PASS, f"all three set: {', '.join(names)}")


def _credentials(label: str, secrets: Any) -> Step:
    return _named_credentials("credentials", label, secrets, "storage", "box")


def _token(label: str, storage: Any) -> Step:
    """Ask the adapter for a token by asking it for one directly.

    Deliberately not "list the folder and see if it works". A token failure and a folder
    failure have different repairs, and running them together is what produces the
    useless report this whole module exists to replace.
    """
    try:
        subject = storage.authenticate()
    except DiagnosticError as refused:
        return _refusal("token", label, refused)
    # The user id, never the token. Showing the id is how somebody notices the token is
    # being issued for the wrong person, which otherwise looks like an empty folder.
    return Step(
        "token",
        label,
        PASS,
        f"Box issued a token impersonating user {subject}, so the app may generate them",
    )


def _folder(label: str, storage: Any) -> Step:
    try:
        found = storage.list()
    except DiagnosticError as refused:
        return _refusal("folder", label, refused)
    if not found:
        return Step(
            "folder",
            label,
            PASS,
            "the folder was listed and is empty. That is a connection, not a fault - "
            "check the id is the folder you meant if you expected files",
        )
    return Step("folder", label, PASS, f"{len(found)} file(s) under the configured folder")


def _file(label: str, storage: Any) -> Step:
    """Read the first file, in the order the adapter lists them.

    The first and not the smallest, which was the obvious idea and is wrong here: sizes
    come from `stat`, and this adapter's `stat` downloads, because Box offers sha1 and
    every figure in this system cites a sha256. Looking for the smallest file would
    therefore download the whole folder to avoid downloading one file.

    The bytes are counted and dropped. They are a client's document, and this is a
    plumbing check rather than a reason to hold one anywhere.
    """
    try:
        found = storage.list()
        if not found:
            return Step(
                "file",
                label,
                NOT_REACHED,
                "the folder is empty, so there was nothing to read. An empty folder is "
                "not a broken connection",
            )
        first = found[0]
        data = storage.read(first)
    except DiagnosticError as refused:
        return _refusal("file", label, refused)
    return Step("file", label, PASS, f"read {len(data)} bytes of {first.path}")
