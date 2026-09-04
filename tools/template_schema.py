"""`template_schema_lookup`: the pinned template's declared inputs. Reads the schema;
writes nothing.

A gated read. The Policy Gate checks `version` against the run's pin
(`pinned_versions_only`), so a skill can only ask about the template the run is
building into. Returns the inputs as rows - name, line, period, required - which is what
the model-load procedure checks a proposed mapping against.
"""

from __future__ import annotations

from typing import Any

from deliver.registry import TemplateInputs

__all__ = ["template_schema_lookup"]


def template_schema_lookup(
    engagement_id: str,
    version: str,
    limit: int | None = None,
    caps: dict[str, Any] | None = None,
    **_: Any,
) -> dict[str, Any]:
    schema = TemplateInputs.load(version)
    rows = [i.as_row() for i in schema.inputs]
    cap = caps.get("max_rows") if caps else None
    bound = min(x for x in (limit, cap, len(rows)) if x is not None)
    return {
        "version": schema.key,
        "template": schema.file,
        "template_version": schema.template_version,
        "scale": schema.scale,
        "currency": schema.currency,
        "stamps": list(schema.stamps),
        "rows": rows[: int(bound)],
    }
