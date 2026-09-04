"""`chart_of_accounts_lookup`: the firm taxonomy at its pinned version.

A gated read. The Policy Gate checks `version` against the run's pin before the tool
sees the call, which is how "tagged against coa-taxonomy@1.0.0" becomes a fact the
manifest can state rather than a hope. The loader is `registries/taxonomy.py`; this is
the name the runtime binds.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from registries.taxonomy import load_taxonomy

__all__ = ["chart_of_accounts_lookup"]


def chart_of_accounts_lookup(
    engagement_id: str,
    version: str,
    ids: Iterable[str] | None = None,
    limit: int | None = None,
    caps: dict[str, Any] | None = None,
    **_: Any,
) -> dict[str, Any]:
    """The tool. `engagement_id` and `version` are what the gate checks; the runtime
    passes `caps` and clamps `limit`. Returns the categories at the pinned version, all
    of them or the ids asked for, as rows."""
    taxonomy = load_taxonomy(version)
    rows = taxonomy.rows(None if ids is None else list(ids))
    cap = caps.get("max_rows") if caps else None
    bound = min(x for x in (limit, cap, len(rows)) if x is not None)
    return {
        "version": taxonomy.version,
        "effective": taxonomy.effective,
        "rules": dict(taxonomy.rules),
        "rows": rows[: int(bound)],
    }
