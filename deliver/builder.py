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

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from deliver.registry import RegisteredTemplate
from graph.execute import Blocked
from guards import GuardResult
from guards.numeric_lock import NumericLock
from ops.events import EventBus
from registries.errors import WRITE_FAILED, RegistryError, diagnose
from tools.write_template import read_named, write_template

__all__ = ["Built", "ModelBuilder", "UNMAPPED_KIND"]

NODE = "model_builder"
UNMAPPED_KIND = "unmapped_inputs_require_review"


@dataclass(frozen=True)
class Built:
    """A workbook, the writes that made it, and the lock's verdict."""

    data: bytes
    template_key: str
    template_version: str
    writes: dict[str, float | str]
    locked_text: str
    lock: GuardResult

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
        if unmapped:
            listed = {u["named_range"] for u in mapping["unmapped_template_inputs"]}
            unlisted = [n for n in unmapped if n not in listed]
            raise Blocked(
                f"unmapped:{step_id}",
                f"{len(unmapped)} required template input(s) have no source: "
                f"{', '.join(unmapped)}"
                + (f" ({', '.join(unlisted)} not even listed by the mapping)" if unlisted else "")
                + "; nothing is written until a person supplies or waives them",
                kind=UNMAPPED_KIND,
            )

        writes: dict[str, float | str] = {}
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
        stamps = {"Template_Version": template.template_version, "Run_Id": run_id}
        data = write_template(template.read(), writes, schema.declared, stamps)
        after = _lock_text(read_named(data, writes))
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
                message=f"{template.key}: {len(writes)} named ranges written, locked",
                step_id=step_id,
                payload={
                    "template": template.key,
                    "written": sorted(writes),
                    "template_hash": template.content_hash,
                },
            )
        return Built(
            data=data,
            template_key=template.key,
            template_version=template.template_version,
            writes=writes,
            locked_text=before,
            lock=lock,
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
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, int | float):
        return f"{float(value):g}"
    return str(value)
