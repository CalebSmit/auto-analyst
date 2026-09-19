"""One conformance suite, parameterised over every registered adapter.

This is the point of the phase. A port whose adapters are each tested their own way is
not an interface, it is two implementations that happen to share a name - and the first
time ShareFile is swapped in, the differences surface in production rather than here.

Two tiers, because one adapter cannot be exercised offline:

  * **structural** - runs for every registered adapter of every port. Satisfies the
    Protocol, names itself, constructs without a credential or a network call, and does
    not leak anything through repr.
  * **behavioural** - runs for every adapter that can answer locally. For the Anthropic
    adapter that means a stubbed client, which still exercises the part most likely to
    be wrong: mapping the Messages API response shape onto LLMResponse.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

import ports
from ports.compute import ComputePort, ComputeTarget
from ports.delivery import DeliveryPort
from ports.identity import IdentityPort
from ports.llm import LLMPort, LLMRequest, LLMResponse, Message, ModelPin, Usage
from ports.ocr import OCRPort
from ports.queue import JobState, QueuePort
from ports.secrets import Secret, SecretsPort
from ports.storage import FileRef, StoragePort
from registries.errors import (
    MISSING_CREDENTIAL,
    UNKNOWN_ADAPTER,
    UNREADABLE_FILE,
    WRITE_FAILED,
    RegistryError,
)

PROTOCOLS: dict[str, Any] = {
    "identity": IdentityPort,
    "ocr": OCRPort,
    "storage": StoragePort,
    "delivery": DeliveryPort,
    "secrets": SecretsPort,
    "queue": QueuePort,
    "llm": LLMPort,
    "compute": ComputePort,
}

ALL_ADAPTERS = [(port, adapter) for port in sorted(ports.PORTS) for adapter in ports.ready(port)]
CONTRACT_ADAPTERS = [
    (port, adapter) for port in sorted(ports.PORTS) for adapter in ports.contracts(port)
]


# ============================================================ structural


@pytest.mark.parametrize(("port", "adapter"), ALL_ADAPTERS)
def test_every_adapter_satisfies_its_protocol(port: str, adapter: str) -> None:
    instance = ports.get_port(port, adapter)
    assert isinstance(instance, PROTOCOLS[port]), f"{port}/{adapter} does not satisfy the Protocol"


@pytest.mark.parametrize(("port", "adapter"), CONTRACT_ADAPTERS)
def test_a_contract_adapter_is_registered_and_refuses(port: str, adapter: str) -> None:
    """Two adapters are contracts waiting for one of the firm's existing connectors.

    They are registered rather than left out so that `AA_STORAGE_ADAPTER=sharefile` is a
    choice the system understands and refuses in words - an unknown name would be a
    different error, and a silent fallback to the local folder would be a run reading
    from somewhere nobody chose, which is the failure the ports exist to prevent.
    """
    with pytest.raises(RegistryError) as refused:
        ports.get_port(port, adapter)
    d = refused.value.diagnostic
    assert d.code in ("SCOPE.MISSING_CREDENTIAL", "SCOPE.ADAPTER_NOT_WIRED")
    assert d.owner == "config" and d.what_now
    assert adapter in ports.adapters(port) and adapter not in ports.ready(port)


@pytest.mark.parametrize(("port", "adapter"), ALL_ADAPTERS)
def test_every_adapter_names_itself(port: str, adapter: str) -> None:
    """The name is what the run manifest records. An adapter that cannot say which one
    it is makes the manifest's portability claim unverifiable."""
    assert ports.get_port(port, adapter).name == adapter


@pytest.mark.parametrize(("port", "adapter"), ALL_ADAPTERS)
def test_building_an_adapter_needs_no_credential_and_no_network(port: str, adapter: str) -> None:
    """Construction is free. The Anthropic adapter defers its SDK import and its key
    lookup to the first call, so listing what exists never requires either."""
    instance = ports.get_port(port, adapter)
    assert repr(instance)


@pytest.mark.parametrize("port", sorted(ports.PORTS))
def test_every_port_has_a_protocol_and_at_least_one_adapter(port: str) -> None:
    assert port in PROTOCOLS
    assert ports.adapters(port), f"{port} has no adapter"


def test_the_ports_are_the_ones_the_blueprint_names() -> None:
    """Storage, delivery, secrets, queue, llm, compute, identity, ocr.

    Each is a port because each is a deployment choice rather than an architecture.
    Compute so the manifest can record where a run happened and the pool can ask how much
    concurrency exists instead of guessing. Identity so a laptop can have one person and
    no accounts while the firm has a provider, without the admin surface knowing which.
    OCR because every PDF this firm receives is a scan, and which engine reads one is a
    choice a machine makes - while *that it is local* is not a choice at all, since the
    text has to exist before masking can happen (P74).

    The blueprint draws five port nodes and the code has eight. That is not a drift: a
    port is a choice behind an existing node rather than a new box on the map, which is
    why compute, identity and now ocr add none. The Document Reader is the node; the
    engine is what sits behind it, as a folder sits behind delivery.

    Every one has a protocol here, and adding a port without one would mean an adapter
    nothing checks - so the two sets are compared rather than the count.
    """
    assert set(ports.PORTS) == {
        "storage",
        "delivery",
        "secrets",
        "queue",
        "llm",
        "compute",
        "identity",
        "ocr",
    }
    assert set(PROTOCOLS) == set(ports.PORTS), "every port has a protocol to satisfy"


@pytest.mark.parametrize("port", sorted(ports.PORTS))
def test_an_unknown_adapter_is_refused_not_defaulted(port: str) -> None:
    with pytest.raises(RegistryError) as raised:
        ports.get_port(port, "no_such_adapter")
    assert raised.value.diagnostic.code == UNKNOWN_ADAPTER
    assert raised.value.diagnostic.owner == "config"
    assert raised.value.diagnostic.what_now


# ============================================================ storage


STORAGE = ports.ready("storage")


@pytest.fixture(params=STORAGE)
def storage(request: pytest.FixtureRequest, inbox: Path) -> Any:
    (inbox / "TB_FY23.xlsx").write_bytes(b"trial balance")
    (inbox / "sub").mkdir()
    (inbox / "sub" / "notes.txt").write_bytes(b"notes")
    return ports.get_port("storage", request.param)


def test_storage_lists_in_a_stable_order(storage: Any) -> None:
    """A sweep that returns files in filesystem order produces a different run from the
    same inputs, which makes a plan hash meaningless."""
    first = storage.list()
    assert [r.path for r in first] == ["TB_FY23.xlsx", "sub/notes.txt"]
    assert storage.list() == first


def test_storage_reads_bytes(storage: Any) -> None:
    assert storage.read(FileRef("TB_FY23.xlsx")) == b"trial balance"


def test_storage_stats_carry_the_hash_a_figure_will_cite(storage: Any) -> None:
    stat = storage.stat(FileRef("TB_FY23.xlsx"))
    assert stat.content_hash.startswith("sha256:")
    assert len(stat.content_hash) == len("sha256:") + 64
    assert stat.size_bytes == len(b"trial balance")


def test_storage_refuses_a_missing_file_rather_than_returning_nothing(storage: Any) -> None:
    """A figure that cites nothing is worse than a figure that never existed."""
    with pytest.raises(RegistryError) as raised:
        storage.read(FileRef("not-there.xlsx"))
    assert raised.value.diagnostic.code == UNREADABLE_FILE
    assert raised.value.diagnostic.owner == "client-data"


def test_storage_cannot_be_walked_out_of(storage: Any) -> None:
    """The Policy Gate checks engagement scope on every action, but a port that can be
    escaped with '..' would make that check advisory."""
    with pytest.raises((RegistryError, ValueError)):
        storage.read(FileRef("../secrets.txt"))


def test_a_file_ref_is_port_relative() -> None:
    for bad in ("/etc/passwd", "../up", ""):
        with pytest.raises(ValueError, match="port-relative"):
            FileRef(bad)


# ============================================================ delivery


@pytest.fixture(params=ports.ready("delivery"))
def delivery(request: pytest.FixtureRequest, outbox: Path) -> Any:
    return ports.get_port("delivery", request.param)


def test_delivery_writes_and_reports_what_it_wrote(delivery: Any) -> None:
    result = delivery.put("HEND-2026-04/manifest.json", b'{"run_id": "run_1"}')
    assert result.version == 1
    assert result.content_hash.startswith("sha256:")
    assert not result.already_present
    assert delivery.version("HEND-2026-04/manifest.json") == 1


def test_writing_identical_bytes_twice_is_not_a_duplicate(delivery: Any) -> None:
    """A keyed retry after a transport failure lands here. It must not produce a second
    copy of the deliverable."""
    delivery.put("out/report.json", b"same")
    again = delivery.put("out/report.json", b"same")
    assert again.already_present
    assert delivery.version("out/report.json") == 1


def test_different_bytes_take_a_new_version_rather_than_overwriting(delivery: Any) -> None:
    """The manifest is immutable in practice, not only by convention."""
    delivery.put("out/report.json", b"first")
    second = delivery.put("out/report.json", b"second")
    assert second.version == 2
    assert not second.already_present
    assert delivery.version("out/report.json") == 2


def test_ensure_folder_is_idempotent(delivery: Any) -> None:
    delivery.ensure_folder("HEND-2026-04")
    delivery.ensure_folder("HEND-2026-04")


def test_delivery_cannot_be_walked_out_of(delivery: Any) -> None:
    with pytest.raises(RegistryError) as raised:
        delivery.put("../escaped.txt", b"x")
    assert raised.value.diagnostic.code == WRITE_FAILED


# ============================================================ secrets


@pytest.fixture(params=ports.ready("secrets"))
def secrets(request: pytest.FixtureRequest, tmp_path: Path) -> Any:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "# a comment\nANTHROPIC_API_KEY=sk-ant-not-a-real-key\nAA_MODE=local\nEMPTY=\n",
        encoding="utf-8",
    )
    from ports.secrets.dotenv import DotenvSecrets  # noqa: PLC0415 - adapter under test

    builders = {"dotenv": lambda: DotenvSecrets(env_file)}
    return builders[request.param]()


def test_secrets_report_presence_without_producing_the_value(secrets: Any) -> None:
    """A preflight check must be able to say "the Box credential is missing" with no
    code path that could print one that is not."""
    assert secrets.has("ANTHROPIC_API_KEY")
    assert not secrets.has("BOX_CLIENT_SECRET")
    assert not secrets.has("EMPTY"), "a credential set to nothing is not set"


def test_secrets_return_the_value_when_asked_deliberately(secrets: Any) -> None:
    assert str(secrets.get("ANTHROPIC_API_KEY")) == "sk-ant-not-a-real-key"


def test_a_missing_credential_is_refused_not_empty(secrets: Any) -> None:
    with pytest.raises(RegistryError) as raised:
        secrets.get("BOX_CLIENT_SECRET")
    assert raised.value.diagnostic.code == MISSING_CREDENTIAL
    assert "BOX_CLIENT_SECRET" in str(raised.value)


def test_a_diagnostic_about_a_credential_never_carries_the_credential(secrets: Any) -> None:
    with pytest.raises(RegistryError) as raised:
        secrets.get("BOX_CLIENT_SECRET")
    assert "sk-ant" not in str(raised.value)


def test_names_lists_keys_never_values(secrets: Any) -> None:
    listed = secrets.names()
    assert "ANTHROPIC_API_KEY" in listed
    assert all("sk-ant-not-a-real-key" not in n for n in listed)


def test_the_adapter_repr_does_not_leak(secrets: Any) -> None:
    assert "sk-ant" not in repr(secrets)


def test_a_secret_does_not_leak_through_repr_or_an_f_string() -> None:
    """repr and format are exactly where a credential reaches a log line by accident -
    a traceback, a debug f-string, structlog's fallback rendering."""
    secret = Secret("sk-ant-super-secret")
    assert "super-secret" not in repr(secret)
    assert "super-secret" not in f"{secret}"
    assert "super-secret" not in f"key={secret!r}"
    assert str(secret) == "sk-ant-super-secret", "reading it deliberately still works"


# ============================================================ queue


@pytest.fixture(params=ports.ready("queue"))
def queue(request: pytest.FixtureRequest) -> Any:
    return ports.get_port("queue", request.param)


def test_a_job_runs_and_reports_its_result(queue: Any) -> None:
    queue.register("double", lambda job: job.payload["n"] * 2)
    job_id = queue.submit("double", {"n": 21}, engagement_id="HEND-2026-04")
    assert queue.status(job_id).state is JobState.QUEUED
    queue.drain()
    done = queue.status(job_id)
    assert done.state is JobState.SUCCEEDED
    assert done.result == 42
    assert done.job.engagement_id == "HEND-2026-04"


def test_a_failing_job_is_recorded_not_raised(queue: Any) -> None:
    """One job blowing up must not take the drain with it - the other engagements in a
    nightly sweep still have to run."""

    def explode(job: Any) -> None:
        raise RuntimeError("the trial balance does not foot")

    queue.register("boom", explode)
    queue.register("fine", lambda job: "ok")
    bad = queue.submit("boom", {})
    good = queue.submit("fine", {})
    queue.drain()
    assert queue.status(bad).state is JobState.FAILED
    assert "does not foot" in queue.status(bad).error
    assert queue.status(good).state is JobState.SUCCEEDED


def test_a_job_with_no_handler_fails_rather_than_vanishing(queue: Any) -> None:
    job_id = queue.submit("nothing_handles_this", {})
    queue.drain()
    assert queue.status(job_id).state is JobState.FAILED


def test_retry_keeps_the_job_id_and_counts_the_attempt(queue: Any) -> None:
    """A retry that produces a new identity is how duplicate work becomes invisible."""
    attempts: list[int] = []

    def flaky(job: Any) -> str:
        attempts.append(job.attempts)
        if job.attempts < 2:
            raise RuntimeError("transient")
        return "recovered"

    queue.register("flaky", flaky)
    job_id = queue.submit("flaky", {})
    queue.drain()
    assert queue.status(job_id).state is JobState.FAILED

    assert queue.retry(job_id) == job_id
    queue.drain()
    assert queue.status(job_id).state is JobState.SUCCEEDED
    assert attempts == [1, 2]


def test_an_unknown_job_id_is_an_error(queue: Any) -> None:
    with pytest.raises(KeyError):
        queue.status("job_99999")


# ============================================================ llm


def _prepare_llm(adapter: str, tmp_path: Path) -> tuple[Any, LLMRequest]:
    """Arrange a canned answer for one adapter, and return it with the request.

    The two adapters are canned differently - a recorded fixture, a stubbed client - but
    what the suite then asserts about them is identical, which is the whole point.
    """
    request = LLMRequest(
        pin=ModelPin.for_tier("mid"),
        system="You align periods. You do not conclude anything.",
        messages=(Message(role="user", content="Align FY22 and FY23."),),
    )

    if adapter == "fake":
        from ports.llm.fake import FakeLLM  # noqa: PLC0415 - adapter under test

        port = FakeLLM(tmp_path)
        port.record(
            request,
            LLMResponse(
                text="aligned",
                model="claude-sonnet-5",
                stop_reason="end_turn",
                usage=Usage(input_tokens=120, output_tokens=8),
            ),
        )
        return port, request

    if adapter == "scripted":
        # Answers from the request only where nothing was recorded; a recording wins,
        # replayed exactly as the fake replays it. Same canned answer, same assertions.
        from ports.llm.scripted import ScriptedAnalyst  # noqa: PLC0415 - adapter under test

        scripted = ScriptedAnalyst(tmp_path)
        scripted.record(
            request,
            LLMResponse(
                text="aligned",
                model="claude-sonnet-5",
                stop_reason="end_turn",
                usage=Usage(input_tokens=120, output_tokens=8),
            ),
        )
        return scripted, request

    if adapter == "anthropic_messages":
        from ports.llm.anthropic_messages import AnthropicMessagesLLM  # noqa: PLC0415

        class _Block:
            type = "text"
            text = "aligned"

        class _Usage:
            input_tokens = 120
            output_tokens = 8
            cache_read_input_tokens = 0
            cache_creation_input_tokens = 0

        class _Response:
            content = [_Block()]
            model = "claude-sonnet-5"
            stop_reason = "end_turn"
            usage = _Usage()
            _request_id = "req_stub"

        class _Messages:
            def create(self, **kwargs: Any) -> _Response:
                # The request shape matters as much as the response: single turn, the
                # pinned model, effort from the pin.
                assert kwargs["model"] == "claude-sonnet-5"
                assert kwargs["output_config"] == {"effort": "high"}
                assert len(kwargs["messages"]) == 1
                return _Response()

        class _Client:
            messages = _Messages()

        port = AnthropicMessagesLLM()
        port._client = _Client()
        return port, request

    raise AssertionError(f"no conformance setup for llm adapter {adapter!r}")


@pytest.mark.parametrize("adapter", ports.adapters("llm"))
def test_one_call_returns_one_response(adapter: str, tmp_path: Path) -> None:
    port, request = _prepare_llm(adapter, tmp_path)
    response = port.complete(request)
    assert response.text == "aligned"
    assert response.model == "claude-sonnet-5"
    assert response.stop_reason == "end_turn"
    assert response.usage.input_tokens == 120
    assert response.usage.output_tokens == 8


@pytest.mark.parametrize("adapter", ports.adapters("llm"))
def test_the_port_offers_no_way_to_take_a_second_turn(adapter: str) -> None:
    """max_turns == 1 is the shape of the interface, not a setting. A skill that needs a
    tool result cannot get one by asking again - that is another compiled step."""
    port = ports.get_port("llm", adapter)
    public = {n for n in dir(port) if not n.startswith("_")}
    assert "complete" in public
    assert not public & {"chat", "converse", "continue_", "loop", "run_until_done"}


def test_a_missing_fixture_is_an_error_naming_what_to_record(tmp_path: Path) -> None:
    """Never an invented response. Every test downstream of a made-up answer is
    meaningless, and nothing about it looks wrong."""
    from ports.llm.fake import FakeLLM, FixtureMissing  # noqa: PLC0415

    port = FakeLLM(tmp_path)
    request = LLMRequest(
        pin=ModelPin.for_tier("mid"), system="s", messages=(Message("user", "unrecorded"),)
    )
    with pytest.raises(FixtureMissing) as raised:
        port.complete(request)
    assert request.content_hash() in str(raised.value)


def test_a_changed_prompt_is_a_different_call(tmp_path: Path) -> None:
    """A cache miss, not a stale answer quietly reused."""
    one = LLMRequest(pin=ModelPin.for_tier("mid"), system="s", messages=(Message("user", "a"),))
    two = LLMRequest(pin=ModelPin.for_tier("mid"), system="s", messages=(Message("user", "b"),))
    assert one.content_hash() != two.content_hash()

    effort_changed = LLMRequest(
        pin=ModelPin(model="claude-sonnet-5", effort="low"),
        system="s",
        messages=(Message("user", "a"),),
    )
    assert one.content_hash() != effort_changed.content_hash()


def test_tiers_resolve_to_the_models_the_blueprint_priced() -> None:
    """The blueprint prices low/mid/high at $1/$5, $2/$10 and $5/$25 per MTok. Those are
    the Haiku, Sonnet and Opus rates."""
    assert ModelPin.for_tier("low").model == "claude-haiku-4-5"
    assert ModelPin.for_tier("mid").model == "claude-sonnet-5"
    assert ModelPin.for_tier("high").model == "claude-opus-5"
    with pytest.raises(ValueError, match="unknown tier"):
        ModelPin.for_tier("cheap")


def test_a_pin_renders_as_the_manifest_records_it() -> None:
    assert str(ModelPin.for_tier("high")) == "claude-opus-5 @ effort=high"


# ============================================================ compute


@pytest.fixture(params=ports.ready("compute"))
def compute(request: pytest.FixtureRequest) -> Any:
    return ports.get_port("compute", request.param)


def test_compute_describes_where_the_run_happened(compute: Any) -> None:
    target = compute.target()
    assert isinstance(target, ComputeTarget)
    assert target.kind in {"local_process", "docker", "container_host"}
    assert target.max_parallelism >= 1
    assert target.workdir
    assert target.describe()


def test_the_scratch_directory_is_not_inside_the_repo(compute: Any) -> None:
    """Run artifacts hold client data. They never land somewhere git might see them."""
    from tests.p03.conftest import ROOT  # noqa: PLC0415

    workdir = Path(compute.target().workdir).resolve()
    assert ROOT not in workdir.parents and workdir != ROOT


def test_parallelism_comes_from_config_and_is_never_zero(
    compute: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A malformed value falls back to the default. Silently zero would stop the worker
    pool without saying so."""
    from ports.compute import env_int  # noqa: PLC0415

    monkeypatch.setenv("AA_MAX_PARALLELISM", "4")
    assert env_int("AA_MAX_PARALLELISM", 1) == 4
    monkeypatch.setenv("AA_MAX_PARALLELISM", "0")
    assert env_int("AA_MAX_PARALLELISM", 1) == 1
    monkeypatch.setenv("AA_MAX_PARALLELISM", "lots")
    assert env_int("AA_MAX_PARALLELISM", 2) == 2
