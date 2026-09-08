"""LLM adapter: replays recorded fixtures. No API key, no network, no cost.

Phases 4 to 10 build the whole engine - compiler, executor, harness, guards, loops -
against this. That is deliberate: debugging a graph compiler and a model's output at the
same time means trusting neither, and a test suite that costs money per run is a test
suite people stop running.

A fixture is looked up by the request's content hash, so a changed prompt is a cache
miss rather than a stale answer quietly reused. A miss is an error naming the hash and
where to put the recording - never an invented response, which would make every test
downstream of it meaningless.
"""

from __future__ import annotations

import json
from pathlib import Path

from ports.llm import LLMRequest, LLMResponse, Usage

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = REPO_ROOT / "fixtures" / "llm"


def _relative(path: Path) -> str:
    """The fixture path as it appears in the repo, never as it appears on one machine.

    This message lands in the run record when a call has no recording, and a run record
    that says `C:/dev/...` is a fact about a laptop inside a document that is meant to
    travel.
    """
    try:
        return path.resolve().relative_to(FIXTURE_DIR.resolve().parents[1]).as_posix()
    except ValueError:
        return path.name


class FixtureMissing(LookupError):
    """No recording for this call. Says which one, and what to do about it."""

    def __init__(self, request: LLMRequest, path: Path) -> None:
        self.request = request
        self.path = path
        super().__init__(
            f"no LLM fixture for {request.content_hash()} "
            f"({request.pin.model}, {len(request.messages)} message(s)). "
            f"Record one at {_relative(path)}, or fix the prompt if the change was not intended - "
            f"a changed prompt is a different call, not the same one."
        )


class FakeLLM:
    """Replays what was recorded. Records nothing itself - see P22's replay harness."""

    name = "fake"

    def __init__(self, fixture_dir: Path | str | None = None) -> None:
        self.fixture_dir = Path(fixture_dir) if fixture_dir is not None else FIXTURE_DIR
        self.calls: list[LLMRequest] = []

    def __repr__(self) -> str:
        return f"FakeLLM(fixtures={self.fixture_dir.name}, calls={len(self.calls)})"

    def complete(self, request: LLMRequest) -> LLMResponse:
        self.calls.append(request)
        path = self.path_for(request)
        if not path.is_file():
            raise FixtureMissing(request, path)
        recorded = json.loads(path.read_text(encoding="utf-8"))
        usage = recorded.get("usage") or {}
        return LLMResponse(
            text=recorded["text"],
            model=recorded.get("model", request.pin.model),
            stop_reason=recorded.get("stop_reason", "end_turn"),
            usage=Usage(
                input_tokens=usage.get("input_tokens", 0),
                output_tokens=usage.get("output_tokens", 0),
                cache_read_input_tokens=usage.get("cache_read_input_tokens", 0),
                cache_creation_input_tokens=usage.get("cache_creation_input_tokens", 0),
            ),
            request_id=recorded.get("request_id", "replayed"),
        )

    def path_for(self, request: LLMRequest) -> Path:
        return self.fixture_dir / f"{request.content_hash().removeprefix('sha256:')[:32]}.json"

    def record(self, request: LLMRequest, response: LLMResponse) -> Path:
        """Write a fixture. Used by the recording tools, never during a run."""
        path = self.path_for(request)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "request_hash": request.content_hash(),
                    "model": response.model,
                    "text": response.text,
                    "stop_reason": response.stop_reason,
                    "usage": {
                        "input_tokens": response.usage.input_tokens,
                        "output_tokens": response.usage.output_tokens,
                        "cache_read_input_tokens": response.usage.cache_read_input_tokens,
                        "cache_creation_input_tokens": (
                            response.usage.cache_creation_input_tokens
                        ),
                    },
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        return path


def build() -> FakeLLM:
    return FakeLLM()
