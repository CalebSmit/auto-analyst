"""Steps pass content-addressed refs, never values.

The exit criterion, and the one that is easiest to satisfy by accident and lose by
accident. Three guarantees rest on it: the idempotency key can be computed at all, a
resumed run costs nothing for work already done, and the manifest can name the exact
bytes a step was shown.

So this file checks the *shape* of what crosses the executor's boundary, not only that a
particular run happened to behave. A field added later that carried a payload would pass
every behavioural test in the phase and fail here.
"""

from __future__ import annotations

import dataclasses
import json

import pytest

from graph.compile import CompiledGraph
from graph.execute import Attempt, StepExecutor
from ops.blobs import ContentRef, LocalContentStore, content_hash
from registries.errors import RegistryError
from tests.p08.conftest import CONTEXT_REF, Recorder


def test_what_a_step_is_handed_is_refs(
    executor: StepExecutor, plan: CompiledGraph, started: str,
    run_inputs: dict[str, ContentRef], recorder: Recorder,
) -> None:
    executor.execute(plan, started, run_inputs, CONTEXT_REF)
    assert recorder.seen, "nothing ran, so this proved nothing"
    for step_id, inputs in recorder.seen.items():
        for name, ref in inputs.items():
            assert isinstance(ref, ContentRef), f"{step_id} was handed {name} as {type(ref)}"


def test_an_attempt_has_no_field_that_could_hold_a_value() -> None:
    """The structural half. `inputs` is a mapping of refs and there is nowhere else for
    bytes to travel - a `payload` or `data` field added later fails here rather than
    quietly making the key uncomputable."""
    fields = {f.name for f in dataclasses.fields(Attempt)}
    assert fields == {
        "step", "attempt", "step_key", "inputs", "context_ref", "timeout_s", "run_id",
        "iteration",  # P14: which admitted loop iteration this is - an int, not a value
    }
    for suspicious in ("payload", "data", "value", "body", "content", "bytes"):
        assert suspicious not in fields


def test_a_ref_has_no_field_that_could_hold_a_value() -> None:
    fields = {f.name for f in dataclasses.fields(ContentRef)}
    assert fields == {"content_hash", "media_type", "size_bytes", "name"}


def test_a_ref_must_actually_be_a_hash() -> None:
    """A ref that cannot be resolved is a value that lost its provenance on the way."""
    ContentRef(content_hash="sha256:" + "a" * 64)
    for bad in ("", "abc", "sha256:short", "md5:" + "a" * 64, "a" * 64):
        with pytest.raises(ValueError, match="content hash"):
            ContentRef(content_hash=bad)


def test_a_runner_has_to_ask_for_the_bytes(
    executor_with, plan: CompiledGraph, started: str,
    run_inputs: dict[str, ContentRef], blobs: LocalContentStore,
) -> None:
    """A deliberate extra step. It makes "this step read that blob" a thing that
    happened rather than a thing that was implied."""
    read: list[str] = []

    class Reads:
        def __call__(self, attempt):  # noqa: ANN001 - a test double
            for ref in attempt.inputs.values():
                read.append(ref.content_hash)
                assert isinstance(blobs.get(ref), bytes)
            return blobs.put_json({"step": attempt.step_id}, name=attempt.step_id)

    executor_with(Reads()).execute(plan, started, run_inputs, CONTEXT_REF)
    assert read, "no step resolved a ref, so nothing was passed at all"


# --------------------------------------------------------- the store itself


def test_the_address_is_the_content(blobs: LocalContentStore) -> None:
    body = b'{"total": 486200.0}'
    ref = blobs.put(body)
    assert ref.content_hash == content_hash(body)
    assert blobs.get(ref) == body
    assert ref.size_bytes == len(body)


def test_writing_the_same_bytes_twice_is_the_same_address(blobs: LocalContentStore) -> None:
    """Write-once by construction. There is no update operation because there is nothing
    an update could mean."""
    first = blobs.put(b"same")
    second = blobs.put(b"same")
    assert first.content_hash == second.content_hash


def test_different_bytes_cannot_land_on_an_existing_address(blobs: LocalContentStore) -> None:
    assert blobs.put(b"one").content_hash != blobs.put(b"two").content_hash


def test_json_is_canonical(blobs: LocalContentStore) -> None:
    """Two structurally identical results that hashed differently because a dict happened
    to iterate in another order would make a resumed run pay for work it had done."""
    a = blobs.put_json({"b": 2, "a": 1})
    b = blobs.put_json({"a": 1, "b": 2})
    assert a.content_hash == b.content_hash
    assert json.loads(blobs.get(a)) == {"a": 1, "b": 2}


def test_a_ref_that_does_not_resolve_is_a_diagnostic(blobs: LocalContentStore) -> None:
    """Not a KeyError. A missing blob means a step's input is gone and the run cannot be
    reconstructed, which is exactly what content addressing was for."""
    with pytest.raises(RegistryError) as raised:
        blobs.get(ContentRef(content_hash="sha256:" + "9" * 64))
    assert raised.value.diagnostic.code == "INTAKE.UNREADABLE_FILE"


def test_the_hash_is_checked_on_the_way_out(blobs: LocalContentStore) -> None:
    """Content addressing is only a guarantee if it is verified when read. Corrupt the
    file behind a ref and the read fails rather than returning the wrong bytes."""
    ref = blobs.put(b"the original")
    stem = ref.content_hash.removeprefix("sha256:")
    (blobs.root / stem[:2] / stem).write_bytes(b"something else")

    with pytest.raises(RegistryError, match="hash to"):
        blobs.get(ref)


def test_the_store_has_no_delete(blobs: LocalContentStore) -> None:
    """A run's inputs must still resolve when somebody asks about it in eighteen months."""
    for forbidden in ("delete", "remove", "purge", "clear", "unlink"):
        assert not hasattr(blobs, forbidden)


def test_a_ref_reads_usefully(blobs: LocalContentStore) -> None:
    """It appears in event payloads and failure messages, so it should say something."""
    ref = blobs.put_json({"x": 1}, name="tagging")
    assert "tagging" in str(ref)
    assert "application/json" in str(ref)
