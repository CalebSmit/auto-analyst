"""The Provenance Check: no number without a source.

Every figure carries `source_id`, `locator` and `source_version`, and each of the three
has to mean something: the source is a document this run actually read, the locator
resolves in the Source Parse Store, and the version is the one the run holds. Fabricated
provenance - an id reading "derived", "model" or "analysis" - is rejected as hard as a
missing one; the figure envelope's contract refuses it by pattern before this guard even
asks the store.

Fails closed. A figure that cannot be traced to a file the run read is not evidence of
anything, and a run does not continue on figures that are not evidence.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping
from typing import Any

from guards import GuardResult, figures_in, report
from ops.events import EventBus
from ops.source_parse import SourceParseStore
from registries.contracts import ContractRegistry
from registries.errors import FABRICATED_SOURCE, NO_PROVENANCE, UNKNOWN_SOURCE

__all__ = ["ProvenanceGate"]


class ProvenanceGate:
    def __init__(
        self,
        contracts: ContractRegistry,
        parse_store: SourceParseStore,
        bus: EventBus | None = None,
    ) -> None:
        self.contracts = contracts
        self.parse_store = parse_store
        self.bus = bus

    def check(
        self,
        output: Any,
        run_id: str,
        sources: Mapping[str, int] | Collection[str],
    ) -> GuardResult:
        """Every figure in the output, against the envelope and the record.

        `sources` is the run's intake manifest: source_id to version, or just the ids.
        """
        versions: dict[str, int | None] = (
            dict(sources) if isinstance(sources, Mapping) else dict.fromkeys(sources)
        )
        reasons: list[str] = []
        code: str | None = None
        checked = 0

        for path, figure in figures_in(output):
            checked += 1
            # The envelope first: shape, pattern, and the fabricated-source refusal.
            envelope = [
                d
                for d in self.contracts.check("figure@1.0.0", figure)
                if d.code in (FABRICATED_SOURCE, NO_PROVENANCE)
            ]
            if envelope:
                worst = min(envelope, key=lambda d: _SEVERITY.index(d.code))
                code = _worse(code, worst.code)
                reasons.append(f"{path}: {worst.detail}")
                continue

            source_id = figure["source_id"]
            if source_id not in versions:
                code = _worse(code, UNKNOWN_SOURCE)
                reasons.append(f"{path}: cites {source_id[:19]}..., not in this run's intake")
                continue
            pinned = versions[source_id]
            if pinned is not None and figure["source_version"] != pinned:
                code = _worse(code, UNKNOWN_SOURCE)
                reasons.append(
                    f"{path}: cites version {figure['source_version']} of a source this run "
                    f"holds at version {pinned}"
                )
                continue
            if not self.parse_store.exists(run_id, source_id, figure["locator"]):
                code = _worse(code, UNKNOWN_SOURCE)
                reasons.append(f"{path}: locator {figure['locator']!r} is not in the parse store")

        return GuardResult(
            guard="provenance",
            passed=code is None,
            checked=checked,
            failed=len(reasons),
            code=code,
            reasons=tuple(reasons),
            detail={"figures": checked, "unsourced": len(reasons)},
        )

    def run(
        self,
        output: Any,
        run_id: str,
        engagement_id: str,
        sources: Mapping[str, int] | Collection[str],
        step_id: str | None = None,
    ) -> GuardResult:
        return report(
            self.bus,
            self.check(output, run_id, sources),
            "provenance_gate",
            run_id,
            engagement_id,
            step_id,
        )


_SEVERITY = (FABRICATED_SOURCE, NO_PROVENANCE, UNKNOWN_SOURCE)


def _worse(current: str | None, found: str) -> str:
    if current is None:
        return found
    return found if _SEVERITY.index(found) < _SEVERITY.index(current) else current
