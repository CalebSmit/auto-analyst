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


MODEL_STEPS: tuple[tuple[str, str], ...] = (
    ("adapter", "A real model adapter is selected"),
    ("credentials", "The API key is set"),
    ("call", "The model answers"),
    ("cost", "What the answer cost"),
)
"""Four, and the third one spends money.

Every other connection test in this module is free. This one buys the smallest completion
the API will sell, because the alternative is checking that a key is *shaped* like a key -
which passes for a revoked key, a key for the wrong account, and a key with no credit on
it. Those are the three things that actually go wrong, and none of them is visible without
making a call.

The cost is a step rather than a footnote so that the price of pressing the button is on
the same screen as the button.
"""


THE_SMALLEST_QUESTION = "Reply with the single word: ready"
"""The test call. Short, answerable in one token, and carrying nothing about anybody - it
crosses the same boundary a client payload would, and a connection test is not a reason to
send one."""


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
            f"not set: {', '.join(missing)}. Add them to .env on this machine - not to "
            f"knowledge/, not to a committed file, and not to a web form. No value is "
            f"read here, only whether one is there.",
        )
    plural = "all " + ("one" if len(names) == 1 else str(len(names)))
    return Step(step_id, label, PASS, f"{plural} set: {', '.join(names)}")


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


def probe_model(
    llm: Any, secrets: Any, *, in_use: bool = True, pin: Any = None
) -> ConnectionReport:
    """Walk the model door in order: adapter, key, a real call, and what it cost.

    The one connection test that spends money, which changes two things about it.

    **It asks whether the key is set before it calls.** `has()` on the Secrets Port, so the
    absence is reported without a request being made and without the value being read.

    **It says what the test itself cost.** A person who presses this a dozen times while
    getting a key right should be able to see what that came to, and a figure that only
    appears on a monthly invoice is not an answer.

    Takes the adapter rather than reaching for the configured one, like `probe_box`: a
    function that built its own could only ever test the machine it ran on, and a test that
    passes against an adapter no run uses is worse than no test - which is what `in_use` is
    for.
    """
    # Deferred: importing the port at module scope would make every admin page import
    # the model door, and this is the one function that needs it.
    from ports.llm import (  # noqa: PLC0415
        LLMRequest,
        Message,
        ModelPin,
        TransportFailure,
    )

    name = getattr(llm, "name", "unknown")
    done: list[Step] = []

    # 1. a real adapter. `fake` replays fixtures and `scripted` answers from a stand-in;
    # both would sail through a key check and neither would tell anybody anything.
    if name in ("fake", "scripted"):
        done.append(
            Step(
                "adapter",
                MODEL_STEPS[0][1],
                FAIL,
                f"the selected adapter is {name!r}, which answers without calling anybody. "
                "Set AA_LLM_ADAPTER=anthropic_messages to reach the API.",
            )
        )
    else:
        done.append(Step("adapter", MODEL_STEPS[0][1], PASS, f"{name}"))

    # 2. the key, asked of the secrets port rather than read.
    if done[-1].status != PASS:
        done.append(_not_reached("credentials", MODEL_STEPS[1][1], done[-1]))
    else:
        done.append(
            _named_credentials(
                "credentials", MODEL_STEPS[1][1], secrets, "llm", "anthropic_messages"
            )
        )

    # 3. the call itself.
    answered = None
    if done[-1].status != PASS:
        done.append(_not_reached("call", MODEL_STEPS[2][1], done[-1]))
    else:
        asked = ModelPin.for_tier("low") if pin is None else pin
        try:
            answered = llm.complete(
                LLMRequest(
                    pin=asked,
                    system="You are answering a connection test.",
                    messages=(Message(role="user", content=THE_SMALLEST_QUESTION),),
                    max_tokens=16,
                    metadata={"purpose": "connection_test"},
                    cache_system=False,
                )
            )
            served = answered.model
            done.append(
                Step(
                    "call",
                    MODEL_STEPS[2][1],
                    PASS,
                    f"{served} answered"
                    + (
                        f" (asked for {asked.model}; the provider served {served})"
                        if served != asked.model
                        else ""
                    ),
                )
            )
        except DiagnosticError as refused:
            done.append(_refusal("call", MODEL_STEPS[2][1], refused))
        except TransportFailure as failed:
            done.append(Step("call", MODEL_STEPS[2][1], FAIL, str(failed)[:300]))

    # 4. what it cost.
    if done[-1].status != PASS or answered is None:
        done.append(_not_reached("cost", MODEL_STEPS[3][1], done[-1]))
    else:
        done.append(Step("cost", MODEL_STEPS[3][1], PASS, _priced(answered)))

    return ConnectionReport(
        service="model",
        ran_at=datetime.now(tz=UTC).isoformat(timespec="seconds"),
        steps=tuple(done),
        in_use=in_use,
    )


def _not_reached(step_id: str, label: str, after: Step) -> Step:
    """The same rule the other two probes follow: a step after a failure is `not reached`.

    Reporting the call as failed when the key was never set would send somebody to the
    Anthropic console to debug a key that is simply absent from `.env`."""
    return Step(step_id, label, NOT_REACHED, f"not asked: {after.id} did not pass")


def _priced(answered: Any) -> str:
    """What the test call cost, from the published rates and the usage the API reported.

    Arithmetic over what came back rather than an estimate, which is the same rule the
    cost meter follows - "what did that cost" is a question with an answer.
    """
    from ports.llm import RATES_USD_PER_MTOK  # noqa: PLC0415

    usage = answered.usage
    rate = RATES_USD_PER_MTOK.get(answered.model)
    tokens = f"{usage.input_tokens} in, {usage.output_tokens} out"
    if rate is None:
        return f"{tokens}; no published rate for {answered.model} in this build"
    usd = (usage.input_tokens * rate[0] + usage.output_tokens * rate[1]) / 1_000_000
    return f"{tokens} - ${usd:.6f}"
