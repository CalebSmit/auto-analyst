"""The Model Builder: resolves the validated mapping and hands it to the Template Writer.

Deterministic Python. Inputs are unmasked, tied-out, locked figures only - nothing
reaches here that has not cleared every guard on the band above. The interesting part
(which line goes where) was the model-load skill's judgment; the risky part (writing
numbers into cells) is arithmetic-free code, and the Numeric Integrity Lock brackets it:
the values resolved from the mapping are tokenised before the write and read back from
the workbook after it, and the multiset difference must be empty.

Refuses to build when a required template input has no source. `unmapped_inputs_require
_review` is the skill's own declaration; the builder is where "fails at binding rather
than delivering two empty cells" becomes true.
"""

from __future__ import annotations

import hashlib
from collections.abc import Collection, Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from deliver.registry import SOURCE_SUFFIX, RegisteredTemplate
from graph.execute import Blocked
from guards import GuardResult
from guards.numeric_lock import NumericLock
from ops.events import EventBus
from registries.errors import WRITE_FAILED, RegistryError, diagnose
from tools.write_template import read_named, write_template

__all__ = ["NOT_FOUND", "Built", "ModelBuilder", "UNMAPPED_KIND", "waiver_for"]

NODE = "model_builder"
UNMAPPED_KIND = "unmapped_inputs_require_review"

FROM_THE_PROFILE = "the engagement profile"
"""What a figure's source cell says when it did not come out of a client document.

The owner-compensation benchmark is a number a person recorded at setup. It has no
locator because there is no page to point at, and saying so is the honest answer - a
source column that was blank there would read as an oversight beside forty filled ones."""

NOT_FOUND = "not found"
"""What a waived input's own cell says.

Not a blank. This workbook exists to be read and copied into a model, and a blank cell
next to forty filled ones reads as a zero - which in a valuation is a number, and a wrong
one. Text cannot be mistaken for a figure and cannot be summed by accident, and it says
the true thing: nothing in this client's folder answered this input."""


def source_of(figure: Mapping[str, Any] | float | int, documents: Mapping[str, str]) -> str:
    """Where this figure came from, in words an analyst can act on.

    The document's own name and the row inside it, because a content hash is provenance a
    machine can check and a person cannot. `documents` maps source_id to filename; a hash
    that is not in it falls back to the hash, which is worse to read and still true.
    """
    if not isinstance(figure, Mapping):
        return FROM_THE_PROFILE
    source_id = str(figure.get("source_id") or "")
    locator = str(figure.get("locator") or "")
    where = documents.get(source_id, source_id)
    return f"{where} {locator}".strip() or FROM_THE_PROFILE


def waiver_for(step_id: str, unmapped: Iterable[str]) -> str:
    """The review item id for one exact list of unfilled inputs.

    The list is in the id, as a digest, and that is the whole point. A waiver is a person
    saying "write it without *these*", and a mapping that changes between the question and
    the answer is a different question - so a re-run that finds a different set of inputs
    unfilled derives a different id, finds no decision at it, and asks again. An id of
    just `unmapped:release` would have let yesterday's waiver cover today's silently.
    """
    listed = ",".join(sorted(unmapped))
    return f"unmapped:{step_id}:{hashlib.sha256(listed.encode()).hexdigest()[:12]}"


@dataclass(frozen=True)
class Built:
    """A workbook, the writes that made it, and the lock's verdict."""

    data: bytes
    template_key: str
    template_version: str
    writes: dict[str, float | str]
    locked_text: str
    lock: GuardResult
    waived: tuple[str, ...] = ()
    """Required inputs a person said to write without. Empty on a total mapping."""

    @property
    def name(self) -> str:
        return f"{self.template_key.split('@', 1)[0]}.xlsx"


class ModelBuilder:
    def __init__(self, bus: EventBus | None = None) -> None:
        self.bus = bus
        self.lock = NumericLock(bus)

    def build(
        self,
        mapping_output: Mapping[str, Any],
        figures: Mapping[str, Mapping[str, Any] | float | int],
        template: RegisteredTemplate,
        *,
        run_id: str,
        engagement_id: str,
        step_id: str = "model",
        waived: Collection[str] = (),
        documents: Mapping[str, str] | None = None,
    ) -> Built:
        """Resolve every binding to a value, write, read back, lock.

        `figures` is figure_ref -> a figure envelope (value, scale, currency) or a plain
        number for a profile input. The template's declared scale must match a figure's:
        restating is arithmetic, and it does not happen here.
        """
        mapping = mapping_output["template_mapping"]
        if mapping["template_version"] != template.template_version:
            raise RegistryError(
                diagnose(
                    WRITE_FAILED,
                    f"the mapping was made for template version "
                    f"{mapping['template_version']}; the registered template is "
                    f"{template.template_version}",
                    locator=template.key,
                )
            )
        schema = template.inputs
        bound = {b["named_range"] for b in mapping["bindings"]}
        unmapped = [n for n in schema.required if n not in bound]
        item = waiver_for(step_id, unmapped)
        if unmapped and item not in waived:
            listed = {u["named_range"] for u in mapping["unmapped_template_inputs"]}
            unlisted = [n for n in unmapped if n not in listed]
            raise Blocked(
                item,
                f"{len(unmapped)} required template input(s) have no source: "
                f"{', '.join(unmapped)}"
                + (f" ({', '.join(unlisted)} not even listed by the mapping)" if unlisted else "")
                + "; accept this to write the workbook without them - each will say "
                f"{NOT_FOUND!r} in its own cell - or supply them and run again",
                kind=UNMAPPED_KIND,
            )

        writes: dict[str, float | str] = {}
        # A waived input is written, not skipped. Skipping leaves the template's own blank
        # in place, and this workbook is read and copied from - see NOT_FOUND.
        for name in unmapped:
            writes[name] = NOT_FOUND
        for binding in mapping["bindings"]:
            name = binding["named_range"]
            ref = binding["figure_ref"]
            if name not in schema.declared:
                raise RegistryError(
                    diagnose(
                        WRITE_FAILED,
                        f"{name!r} is not a declared input of {template.key}",
                        locator=name,
                    )
                )
            if ref not in figures:
                raise RegistryError(
                    diagnose(
                        WRITE_FAILED,
                        f"{ref!r} is bound to {name} but no locked figure carries that ref",
                        locator=name,
                    )
                )
            writes[name] = _value_of(figures[ref], schema.scale, schema.currency, name)

        before = _lock_text(writes)
        # The provenance beside each figure. Stamps rather than writes: the writer derives
        # them from the figure it just resolved, and the mapping may never name one.
        names = dict(documents or {})
        stamps: dict[str, str] = {
            "Template_Version": template.template_version,
            "Run_Id": run_id,
        }
        if schema.sources_beside_values:
            for binding in mapping["bindings"]:
                name = binding["named_range"]
                stamps[f"{name}{SOURCE_SUFFIX}"] = source_of(
                    figures[binding["figure_ref"]], names
                )
        data = write_template(template.read(), writes, schema.declared, stamps)
        after = _lock_text(read_named(data, writes))
        # And read the provenance back too. The numeric lock covers the figures; a source
        # cell pointing at the wrong row is worse than an empty one, because it is an
        # invitation to check and be reassured by the wrong page.
        written_back = read_named(data, list(stamps))
        wrong = [n for n, text in stamps.items() if str(written_back.get(n)) != str(text)]
        if wrong:
            raise RegistryError(
                diagnose(
                    WRITE_FAILED,
                    f"{len(wrong)} provenance cell(s) did not read back as written: "
                    f"{', '.join(sorted(wrong)[:5])}",
                    locator=template.key,
                )
            )
        lock = self.lock.run(before, after, run_id, engagement_id, step_id)
        if not lock.passed:
            raise RegistryError(
                diagnose(
                    WRITE_FAILED,
                    f"the numeric lock failed after the write: {'; '.join(lock.reasons)}",
                    locator=template.key,
                )
            )
        if self.bus is not None:
            self.bus.emit(
                run_id=run_id,
                engagement_id=engagement_id,
                node_id=NODE,
                type="model.built",
                message=f"{template.key}: {len(writes)} named ranges written, locked"
                + (f"; {len(unmapped)} waived and marked {NOT_FOUND!r}" if unmapped else ""),
                step_id=step_id,
                payload={
                    "template": template.key,
                    "written": sorted(writes),
                    "template_hash": template.content_hash,
                    # Named, not counted. Which inputs went out unfilled is the first
                    # question anybody asks about this workbook.
                    "waived": sorted(unmapped),
                },
            )
        return Built(
            data=data,
            template_key=template.key,
            template_version=template.template_version,
            writes=writes,
            locked_text=before,
            lock=lock,
            waived=tuple(sorted(unmapped)),
        )


def _value_of(
    figure: Mapping[str, Any] | float | int, scale: int, currency: str, name: str
) -> float:
    if isinstance(figure, int | float):
        return float(figure)
    if int(figure.get("scale", 1)) != scale:
        raise RegistryError(
            diagnose(
                WRITE_FAILED,
                f"{name}: the figure is at scale {figure.get('scale')} and the template "
                f"expects {scale}; restating is arithmetic and does not happen in the writer",
                locator=name,
            )
        )
    if figure.get("unit") == "currency" and figure.get("currency") != currency:
        raise RegistryError(
            diagnose(
                WRITE_FAILED,
                f"{name}: the figure is in {figure.get('currency')} and the template "
                f"expects {currency}",
                locator=name,
            )
        )
    return float(figure["value"])


def _lock_text(writes: Mapping[str, Any]) -> str:
    return "\n".join(f"{name} {_plain(value)}" for name, value in sorted(writes.items()))


def _plain(value: Any) -> str:
    """The locked text of one value, at every digit the float actually has.

    This used to be `:g`, which is six significant digits. That was harmless while every
    figure was a whole number read off a statement and stopped being harmless the moment
    P108 started restating to thousands: 1234.56789 and 1234.5678912 both render
    `1234.57`, so the lock would have been blind to precisely the decimals the analyst
    asked to keep. `repr` of a float is the shortest string that reads back as the same
    float, which is the strongest claim the lock can make about a round trip.
    """
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, int | float):
        return repr(float(value))
    return str(value)
