"""`precedent_lookup`: prior approved decisions, retrieved scope-built - never the store.

A gated read. The Policy Gate checks that the `scope` the caller declares is this run's
practice (`precedent_scope_declared`) and that `engagement_id` is this run's; the query
is then built from that scope path and nothing else. There is no argument that names
another engagement's rows, because rows are not addressed by engagement - they are
addressed by scope, and the scope is the run's.

Two shapes of call. `ids` fetches specific precedents the model cited, so a citation can
be verified against what the store actually holds in scope. `terms` ranks the scope's
examples against descriptions. Both come back as rows under the registry's cap.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from harness.context import PrecedentQuery
from harness.runtime import Tool
from precedent.store import PrecedentStore

__all__ = ["precedent_lookup_tool"]


def precedent_lookup_tool(store: PrecedentStore) -> Tool:
    """Bind the tool to a store. The runtime registers the result under its name."""

    def precedent_lookup(
        engagement_id: str,
        scope: str,
        ids: Iterable[str] | None = None,
        terms: Iterable[str] | None = None,
        limit: int | None = None,
        caps: dict[str, Any] | None = None,
        **_: Any,
    ) -> dict[str, Any]:
        parts = scope.split("/")
        practice = parts[0]
        segment = parts[1] if len(parts) > 1 else ""
        disposition = parts[2] if len(parts) > 2 else ""
        cap = caps.get("max_rows") if caps else None
        bound = int(min(x for x in (limit, cap) if x is not None)) if (limit or cap) else None

        if ids is not None:
            records = store.get(ids, practice=practice)
        else:
            query = PrecedentQuery(
                engagement_id=engagement_id,
                client_id="",
                practice=practice,
                segment=segment,
                disposition=disposition,
                precedent_scope="scope_only",
                skill="",
                limit=bound or 8,
                terms=tuple(terms or ()),
            )
            records = store.records(query)
        rows = [r.as_row() for r in records]
        if bound is not None:
            rows = rows[:bound]
        return {"scope": scope, "rows": rows}

    return precedent_lookup
