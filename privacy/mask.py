"""The Masking Engine: deterministic substitution, and nothing that guesses.

`Bob's LLC Checking` becomes `[[ACCOUNT_1]] Checking`. The same account gets the same
token across every file and every run, because the vault is asked before a token is
issued. No model is involved anywhere in this module; the identifiers come declared,
from the engagement profile and the intake, and a run of digits long enough to be an
account number is caught by a pattern.

Masking is not a security boundary here - the firm's Claude account is sanctioned for
client data. It is kept for cross-client isolation and precedent portability: a
precedent store can reuse one client's approved decisions on another's engagement only
if the descriptions in it name no one.

Emits both the masked payload and the identifier list the Outbound Payload Scan checks
against, so the masker and the scan agree about what should have been substituted by
construction rather than by convention.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

from privacy.payload_scan import IdentifierList
from privacy.vault import TOKEN_KINDS, MaskVault

__all__ = ["Identifier", "Masked", "Masker", "ACCOUNT_NUMBER"]

# Eight or more digits, dashes allowed inside. Bank, loan and policy numbers, not years
# and not amounts - an amount has a decimal point or a comma the pattern does not admit.
ACCOUNT_NUMBER = re.compile(r"(?<![\d.,])\d(?:[\d-]{6,})\d(?![\d.,])")


@dataclass(frozen=True)
class Identifier:
    """One thing that re-identifies, and what kind of thing it is."""

    kind: str
    value: str

    def __post_init__(self) -> None:
        if self.kind not in TOKEN_KINDS:
            raise ValueError(f"{self.kind!r} is not a token kind (have: {', '.join(TOKEN_KINDS)})")
        if not self.value.strip():
            raise ValueError("an identifier cannot be blank")


@dataclass(frozen=True)
class Masked:
    """The masked text, and the account of what was substituted."""

    text: str
    engagement_id: str
    substitutions: dict[str, str]
    """value -> token, for everything found in the text."""
    identifiers: IdentifierList
    """What the Outbound Payload Scan checks: the values that must be absent and the
    tokens that must be present."""

    @property
    def tokens(self) -> tuple[str, ...]:
        return tuple(sorted(set(self.substitutions.values())))


class Masker:
    """Substitute declared identifiers and account numbers with vault tokens."""

    def __init__(self, vault: MaskVault) -> None:
        self.vault = vault

    def mask(
        self,
        text: str,
        engagement_id: str,
        identifiers: Iterable[Identifier],
        run_id: str | None = None,
    ) -> Masked:
        declared = list(identifiers)
        substitutions: dict[str, str] = {}
        out = text

        # Longest first, so "Bob Henderson" is masked before "Bob" could split it.
        for ident in sorted(declared, key=lambda i: len(i.value), reverse=True):
            pattern = re.compile(re.escape(ident.value), re.IGNORECASE)
            if not pattern.search(out):
                continue
            token = self.vault.issue(engagement_id, ident.kind, ident.value, run_id)
            out = pattern.sub(token, out)
            substitutions[ident.value] = token

        # Account numbers nobody declared. Found by shape, masked as NUMBER.
        for match in list(ACCOUNT_NUMBER.finditer(out)):
            number = match.group(0)
            if number in substitutions:
                continue
            token = self.vault.issue(engagement_id, "NUMBER", number, run_id)
            substitutions[number] = token
        for number, token in substitutions.items():
            if ACCOUNT_NUMBER.fullmatch(number):
                out = out.replace(number, token)

        numbers = [n for n in substitutions if ACCOUNT_NUMBER.fullmatch(n)]
        return Masked(
            text=out,
            engagement_id=engagement_id,
            substitutions=substitutions,
            identifiers=IdentifierList.of(
                engagement_id, [i.value for i in declared] + numbers, substitutions.values()
            ),
        )
