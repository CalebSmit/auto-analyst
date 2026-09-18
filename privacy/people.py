"""A name that looks like a person's, found without being told it is one.

The masker substitutes what it has been *declared*. Every declaration in production today
is the client's company name and the distinctive words of it (`workers/driver.py`), so a
natural person is never on the list - the vault has a `PERSON` kind and nothing has ever
issued one. That is fine on the outbound path, where the payload is this client's own
documents going to a model that is already reading them.

It is not fine on the way into the Precedent Store, which is the one place where text
written on one engagement is deliberately shown on another. `PrecedentStore.records`
filters by practice and skill and not by client, because cross-client reuse is the whole
point of precedent. So an add-back rationale reading "Officer salary - R. Whitfield
(owner)" - the ordinary case in valuation work, not an edge case - masks to itself, clears
the scan because the scan has never heard of Whitfield, and is admitted. The next run in
the same practice puts that name in a different client's model context.

This is the second check on that path only. It fails closed, which it can afford to do:
the cost of a false positive here is one example that is not learned from, and the store is
better one example short than carrying somebody's name across a wall.

**Nothing here echoes what it matched.** The reason strings name the shape and count, the
way `privacy.payload_scan` does, because a leak reported verbatim into an event or an error
is the leak, one level up.

Deterministic, like everything else in this package. No model decides whether a name is a
person's.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

__all__ = ["PersonLike", "looks_like_a_person"]

# An initial and a surname: "R. Whitfield", "M. J. Whitfield". The most common way a
# person appears on a schedule of add-backs, and unmistakable - no ordinary accounting
# phrase has this shape.
_INITIAL_SURNAME = re.compile(r"\b(?:[A-Z]\.\s*){1,3}[A-Z][a-z]{2,}\b")

# An honorific and a name.
_HONORIFIC = re.compile(r"\b(?:Mr|Mrs|Ms|Miss|Dr|Prof|Messrs|Sr|Jr)\.?\s+[A-Z][a-z]{2,}\b")

# A role and a name beside it: "salary to John Smith", "owner Jane Doe", "paid to
# M Whitfield". The role words are the ones that put a person on an add-back schedule in
# the first place, so this is narrow on purpose rather than "two capitalised words".
_ROLES = (
    "owner", "officer", "president", "director", "shareholder", "member", "partner",
    "founder", "principal", "manager", "employee", "spouse", "son", "daughter",
    "ceo", "cfo", "coo", "lender", "guarantor", "trustee", "beneficiary",
)
# The role is matched case-insensitively and the name is not - `re.I` on the whole pattern
# would make `[A-Z][a-z]{2,}` match lowercase, and "Officer compensation above the
# benchmark" would read as a person. The capitalisation is the only thing separating a name
# from a sentence, so it is the one part that stays case-sensitive.
_ROLE = r"(?i:" + "|".join(_ROLES) + r")"
_NAME = r"[A-Z][a-z]{2,}\s+[A-Z][a-z]{2,}"
_ROLE_THEN_NAME = re.compile(rf"\b{_ROLE}\b[^.;:\n]{{0,24}}?\b{_NAME}\b")
_NAME_THEN_ROLE = re.compile(rf"\b{_NAME}\b[^.;:\n]{{0,24}}?\b{_ROLE}\b")

_PATTERNS = (
    ("an initial and a surname", _INITIAL_SURNAME),
    ("an honorific and a name", _HONORIFIC),
    ("a role and a name beside it", _ROLE_THEN_NAME),
    ("a name and a role beside it", _NAME_THEN_ROLE),
)


@dataclass(frozen=True)
class PersonLike:
    """What was found, by shape and count. Never the text itself."""

    found: bool
    reasons: tuple[str, ...] = ()

    def __bool__(self) -> bool:
        return self.found


def looks_like_a_person(text: str) -> PersonLike:
    """Whether `text` reads as though it names a natural person.

    Conservative in what it claims and deliberately not clever: four shapes, all of which
    take a role word or an honorific or an initial to fire. "Officer salary" alone does
    not; "Officer salary - R. Whitfield" does. A two-word capitalised phrase on its own -
    "Cost of Capital", "Deferred Revenue", "Accrued Interest" - is not a person and is not
    matched, because a check that fires on every schedule is a check somebody turns off.
    """
    reasons = [
        f"{shape} (x{len(found)})"
        for shape, pattern in _PATTERNS
        if (found := pattern.findall(text))
    ]
    return PersonLike(found=bool(reasons), reasons=tuple(reasons))
