"""The Provenance Check: no number without a source.

Every figure carries `source_id`, `locator` and `source_version`, and each of the three
has to mean something: the source is a document this run actually read, the locator
resolves in the Source Parse Store, and the version is the one the run holds. Fabricated
provenance - an id reading "derived", "model" or "analysis" - is rejected as hard as a
missing one; the figure envelope's contract refuses it by pattern before this guard even
asks the store.

A fourth, for a figure **read off the page** (no derivation): the number has to actually be
at the place it cites. A location that exists is not enough - a model can cite a real row
and carry a different amount, and nothing downstream re-derives a figure with nothing to
re-derive. This is the citation check the LlamaIndex due-diligence agent is built around
(docs/research/ai-in-valuation.md): a citation is verified by finding the cited value in the
source, with a few forgiving matches for how numbers are printed, and one that is not found
is shown, not hidden. Here "shown" means the guard fails with both numbers, and the guard
repair loop hands them back to the skill before a person sees them. Derived figures are the
Tie-Out Check's business and are not matched here.

Fails closed. A figure that cannot be traced to a file the run read is not evidence of
anything, and a run does not continue on figures that are not evidence.
"""

from __future__ import annotations

import math
import re
from collections.abc import Collection, Iterable, Mapping
from typing import Any

from guards import GuardResult, figures_in, report
from ops.events import EventBus
from ops.source_parse import Row, SourceParseStore
from registries.contracts import ContractRegistry
from registries.errors import (
    CITED_VALUE_ABSENT,
    FABRICATED_SOURCE,
    NO_PROVENANCE,
    UNKNOWN_SOURCE,
)

__all__ = ["ProvenanceGate", "cited_value_found", "printed_number"]

# Half a cent. Printed statements round to the unit or the cent; anything further apart is a
# different number, not a rounding.
TOLERANCE = 0.005


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
            rows = self.parse_store.resolve(run_id, source_id, figure["locator"])
            if not rows:
                code = _worse(code, UNKNOWN_SOURCE)
                reasons.append(f"{path}: locator {figure['locator']!r} is not in the parse store")
                continue
            if figure.get("derivation"):
                continue  # re-derived by the Tie-Out Check, not read off the page
            found, why = cited_value_found(float(figure["value"]), rows)
            if not found:
                code = _worse(code, CITED_VALUE_ABSENT)
                reasons.append(f"{path}: {figure['locator']!r} {why}")

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


_SEVERITY = (FABRICATED_SOURCE, NO_PROVENANCE, UNKNOWN_SOURCE, CITED_VALUE_ABSENT)

_CURRENCY = re.compile(r"[$€£¥]|\b(?:USD|EUR|GBP)\b", re.IGNORECASE)


def printed_number(raw: str) -> float | None:
    """A number as a statement prints it: `1,234.50`, `$1,234`, `(1,234)`, `1,234-`, `−1,234`.

    Returns None rather than guessing for anything else - `1.2M`, `52 billion`, a percent, a
    date. A suffix changes the scale, and the figure envelope states scale; reading one into
    the other here would be the silent thousands-versus-units error the envelope exists to
    prevent.
    """
    text = _CURRENCY.sub("", raw or "").strip().replace("−", "-").replace(" ", "")
    if not text:
        return None
    negative = False
    if text.startswith("(") and text.endswith(")"):
        negative, text = True, text[1:-1]
    if text.endswith("-") and len(text) > 1:
        negative, text = True, text[:-1]
    if text.startswith("-"):
        negative, text = not negative, text[1:]
    if not re.fullmatch(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?", text):
        return None
    value = float(text.replace(",", ""))
    return -value if negative else value


def cited_value_found(value: float, rows: Iterable[Row]) -> tuple[bool, str]:
    """Whether `value` is the amount on one of the cited rows, and if not, what the rows say.

    In order, the way the due-diligence agent's citation matcher relaxes: the parsed value;
    the printed text read as a number (currency stripped, parentheses as negative). Never
    the absolute value - an expense cited as a gain is the error, not a formatting
    difference - but an opposite sign is named, because it is the likeliest honest mistake.
    """
    rows = tuple(rows)
    seen: list[str] = []
    for row in rows:
        candidates = [row.value, printed_number(row.raw)]
        for candidate in candidates:
            if candidate is not None and math.isclose(value, candidate, abs_tol=TOLERANCE):
                return True, ""
        shown = row.raw or ("" if row.value is None else f"{row.value:,.2f}")
        seen.append(f"{row.label} {shown}".strip() or "(an empty row)")
    opposite = any(
        c is not None and math.isclose(-value, c, abs_tol=TOLERANCE)
        for row in rows
        for c in (row.value, printed_number(row.raw))
    )
    says = "; ".join(seen[:3]) + (f"; and {len(seen) - 3} more" if len(seen) > 3 else "")
    hint = " - the source has it with the opposite sign" if opposite else ""
    return False, f"does not show {value:,.2f}; it says: {says}{hint}"


def _worse(current: str | None, found: str) -> str:
    if current is None:
        return found
    return found if _SEVERITY.index(found) < _SEVERITY.index(current) else current
