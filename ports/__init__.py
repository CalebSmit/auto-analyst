"""The ports: eight interfaces, their adapters, and the one way to choose between them.

Everything outside this package imports from here and from the six protocol modules -
never from an adapter. That is not a convention to remember: `tests/p03` walks the import
graph and fails on any module outside `ports/` that names a concrete adapter, because
the portability argument is worth exactly as much as its weakest import statement.

    from ports import get_storage
    from ports.storage import StoragePort, FileRef      # types, fine
    from ports.storage.local_folder import LocalFolderStorage   # refused

Which adapter answers is config: AA_STORAGE_ADAPTER, AA_DELIVERY_ADAPTER,
AA_SECRETS_ADAPTER, AA_QUEUE_ADAPTER, AA_LLM_ADAPTER, AA_COMPUTE_ADAPTER,
AA_IDENTITY_ADAPTER, AA_OCR_ADAPTER. An unknown
name is SCOPE.UNKNOWN_ADAPTER, never a silent fallback to the default - a run reading
from somewhere nobody chose is the failure this whole arrangement exists to prevent.
"""

from __future__ import annotations

import importlib
import os
from dataclasses import dataclass
from typing import Any

from registries.errors import UNKNOWN_ADAPTER, RegistryError, diagnose

__all__ = [
    "env_file_values",
    "load_env_file",
    "PORTS",
    "PortSpec",
    "adapters",
    "contracts",
    "get_compute",
    "get_delivery",
    "get_identity",
    "get_llm",
    "get_ocr",
    "get_queue",
    "get_secrets",
    "get_storage",
    "get_port",
    "ready",
    "reset",
]


@dataclass(frozen=True)
class PortSpec:
    """One port: what selects it, what it defaults to, and what implements it.

    Adapters are named to module paths rather than imported here, so listing what exists
    costs nothing and an adapter whose optional dependency is absent does not break
    every other port at import time.
    """

    name: str
    env_var: str
    default: str
    adapters: dict[str, str]
    contracts: frozenset[str] = frozenset()
    """Adapters that are declared and refuse: a port contract written for one of the
    firm's existing connectors, registered so selecting it is a loud refusal rather than
    an unknown name or a silent fallback. `ready()` is the rest."""


PORTS: dict[str, PortSpec] = {
    "storage": PortSpec(
        name="storage",
        env_var="AA_STORAGE_ADAPTER",
        default="local_folder",
        adapters={
            "local_folder": "ports.storage.local_folder",
            "sharefile": "ports.storage.sharefile",
        },
        contracts=frozenset({"sharefile"}),
    ),
    "delivery": PortSpec(
        name="delivery",
        env_var="AA_DELIVERY_ADAPTER",
        default="local_folder",
        adapters={
            "local_folder": "ports.delivery.local_folder",
            "box": "ports.delivery.box",
        },
        contracts=frozenset({"box"}),
    ),
    "secrets": PortSpec(
        name="secrets",
        env_var="AA_SECRETS_ADAPTER",
        default="dotenv",
        adapters={"dotenv": "ports.secrets.dotenv"},
    ),
    "queue": PortSpec(
        name="queue",
        env_var="AA_QUEUE_ADAPTER",
        default="in_process",
        adapters={
            "in_process": "ports.queue.in_process",
            "redis_rq": "ports.queue.redis_rq",
        },
    ),
    "llm": PortSpec(
        name="llm",
        env_var="AA_LLM_ADAPTER",
        # The fake replays fixtures, so the default costs nothing and needs no key.
        # A run that means to reach a model says so.
        default="fake",
        adapters={
            "fake": "ports.llm.fake",
            "anthropic_messages": "ports.llm.anthropic_messages",
            # Answers every skill from the request. Builds only with AA_REHEARSAL=1:
            # it is how a rehearsal walks the review loop without a key, and never
            # how a run reaches a model.
            "scripted": "ports.llm.scripted",
        },
    ),
    "compute": PortSpec(
        name="compute",
        env_var="AA_COMPUTE_ADAPTER",
        default="local_process",
        adapters={"local_process": "ports.compute.local_process"},
    ),
    "identity": PortSpec(
        name="identity",
        env_var="AA_IDENTITY_ADAPTER",
        default="local_user",
        adapters={"local_user": "ports.identity.local_user"},
    ),
    "ocr": PortSpec(
        name="ocr",
        env_var="AA_OCR_ADAPTER",
        # `none` refuses rather than returning an empty page, so the default is the honest
        # state of a machine where nobody has installed an engine - and a scanned page stays
        # reported as scanned, which is what the reader did before this port existed.
        default="none",
        adapters={
            "none": "ports.ocr.none",
            # Two local engines, and the difference that matters on a managed laptop is
            # how they install: tesseract wants an executable on PATH, rapidocr is a wheel
            # with its models in it. Which reads this firm's scans better is a question for
            # a benchmark, which is why both stay registered.
            "rapidocr": "ports.ocr.rapidocr",
            "tesseract": "ports.ocr.tesseract",
        },
    ),
}

_built: dict[tuple[str, str], Any] = {}


def adapters(port: str) -> tuple[str, ...]:
    """Every adapter name registered for a port, contracts included."""
    return tuple(sorted(_spec(port).adapters))


def ready(port: str) -> tuple[str, ...]:
    """The adapters that can actually be built.

    The difference is the handoff: a contract is registered so that choosing it is a
    refusal somebody can read, but it has no implementation to conform to anything yet.
    The conformance suite runs over these.
    """
    spec = _spec(port)
    return tuple(sorted(set(spec.adapters) - spec.contracts))


def contracts(port: str) -> tuple[str, ...]:
    """The adapters that are contracts waiting for one of the firm's connectors."""
    return tuple(sorted(_spec(port).contracts))


def selected(port: str) -> str:
    """Which adapter config asks for. Reads the environment every call, so a test that
    changes it does not have to know about caching."""
    spec = _spec(port)
    return os.environ.get(spec.env_var) or spec.default


def get_port(port: str, adapter: str | None = None) -> Any:
    """Build (and reuse) the adapter for a port.

    Instances are cached per (port, adapter) because a storage client is not free to
    construct, and reset() exists for the tests that need a fresh one.
    """
    spec = _spec(port)
    name = adapter or selected(port)
    if name not in spec.adapters:
        raise RegistryError(
            diagnose(
                UNKNOWN_ADAPTER,
                f"{name!r} is not registered for the {port} port "
                f"(have: {', '.join(sorted(spec.adapters))})",
                locator=spec.env_var,
            )
        )
    key = (port, name)
    if key not in _built:
        module = importlib.import_module(spec.adapters[name])
        _built[key] = module.build()
    return _built[key]


def reset() -> None:
    """Drop every cached adapter. For tests that swap configuration."""
    _built.clear()


def get_storage(adapter: str | None = None) -> Any:
    return get_port("storage", adapter)


def get_delivery(adapter: str | None = None) -> Any:
    return get_port("delivery", adapter)


def get_secrets(adapter: str | None = None) -> Any:
    return get_port("secrets", adapter)


def get_queue(adapter: str | None = None) -> Any:
    return get_port("queue", adapter)


def get_llm(adapter: str | None = None) -> Any:
    return get_port("llm", adapter)


def get_ocr(adapter: str | None = None) -> Any:
    return get_port("ocr", adapter)


def get_identity(adapter: str | None = None) -> Any:
    return get_port("identity", adapter)


def get_compute(adapter: str | None = None) -> Any:
    return get_port("compute", adapter)


def _spec(port: str) -> PortSpec:
    if port not in PORTS:
        raise RegistryError(
            diagnose(
                UNKNOWN_ADAPTER,
                f"{port!r} is not a port (have: {', '.join(sorted(PORTS))})",
            )
        )
    return PORTS[port]


def env_file_values(text: str) -> dict[str, str]:
    """KEY=value lines, as .env writes them: comments and blanks skipped, one pair of
    surrounding quotes removed. The one parser, shared by the secrets adapter and the
    command that starts the system."""
    values: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[key.strip()] = value
    return values


def load_env_file(path: Any = None) -> tuple[str, ...]:
    """Put the settings in .env into this process's environment, where the ports read them.

    Without this, a local start read only the secrets from .env: the adapters, the database
    and the folder roots are chosen from the process environment, so `AA_LLM_ADAPTER=
    anthropic_messages` written in .env changed nothing, silently. A container gets the file
    through `--env-file`; this is the same thing for `python tools/serve.py`.

    The real environment wins over the file, as it does for secrets: a value exported in the
    shell is a deliberate override. Empty values are skipped, so a placeholder line does not
    blank a setting. Returns the names it set, never a value.
    """
    from pathlib import Path

    target = Path(path) if path is not None else Path(__file__).resolve().parents[1] / ".env"
    if not target.is_file():
        return ()
    applied = []
    for key, value in env_file_values(target.read_text(encoding="utf-8")).items():
        if value and key not in os.environ:
            os.environ[key] = value
            applied.append(key)
    return tuple(applied)
