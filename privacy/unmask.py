"""The Unmasking Engine: deterministic reverse substitution, reading the vault directly.

Runs after all model work is complete, on validated output only. Pure Python. No agent
has a tool that reaches this function; it is called by the pipeline, not by a skill.
Re-identification is the one step where a plausible-looking mistake is indistinguishable
from correctness, so it is the last place a model belongs.

Resolves only what the vault holds for this engagement. A token the vault does not
know - because it was issued elsewhere, or purged - is left exactly as it was found and
reported, so the integrity check that follows can say which.
"""

from __future__ import annotations

from dataclasses import dataclass

from privacy.payload_scan import TOKEN_PATTERN
from privacy.vault import MaskVault

__all__ = ["Unmasked", "Unmasker"]


@dataclass(frozen=True)
class Unmasked:
    """The re-identified text and an exact account of what happened to each token."""

    text: str
    engagement_id: str
    found: frozenset[str]
    """Every token that appeared in the input."""
    resolved: frozenset[str]
    """The ones the vault answered for, under this engagement."""

    @property
    def unresolved(self) -> frozenset[str]:
        return self.found - self.resolved


class Unmasker:
    def __init__(self, vault: MaskVault) -> None:
        self.vault = vault

    def unmask(self, text: str, engagement_id: str) -> Unmasked:
        found = frozenset(TOKEN_PATTERN.findall(text))
        resolved: set[str] = set()
        out = text
        for token in sorted(found, key=len, reverse=True):
            value = self.vault.resolve(engagement_id, token)
            if value is None:
                continue
            out = out.replace(token, value)
            resolved.add(token)
        return Unmasked(
            text=out, engagement_id=engagement_id, found=found, resolved=frozenset(resolved)
        )
