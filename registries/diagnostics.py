"""The Diagnostics Registry: the third registry, over every code the system can raise.

The codes themselves live in `registries.errors`, beside the exception types that carry
them, because that is where a module raising one looks. This registry is the view over
that set that CI asserts against: every code has a family the blueprint names, an owner
one of six people can act on, and a `what_now` that says something. A code missing any of
those is a message nobody can act on, and a message nobody can act on is a defect.

Versioned like the contracts and the constraints. A run records which version of the
diagnostics it was judged under, so a code that later changes meaning does not quietly
rewrite the history of runs that carried it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import get_args

from registries import errors
from registries.errors import (
    DIAGNOSTICS_INVALID,
    WHAT_NOW,
    Owner,
    RegistryError,
    diagnose,
)

VERSION = "1.0.0"

# The families the blueprint's diagnostics table declares, in its order. A code outside
# these is not a new kind of failure, it is a typo.
FAMILIES = (
    "INTAKE",
    "SCOPE",
    "PRIVACY",
    "POLICY",
    "SKILL",
    "GUARD",
    "DELIVER",
    "LOOP",
    "PROCESS",
    "CONFIG",
)

OWNERS: tuple[str, ...] = get_args(Owner)

__all__ = ["FAMILIES", "OWNERS", "VERSION", "Code", "DiagnosticsRegistry"]


@dataclass(frozen=True)
class Code:
    """One stable failure code and what a person needs to know about it."""

    code: str
    owner: str
    what_now: str

    @property
    def family(self) -> str:
        return self.code.split(".", 1)[0]

    @property
    def name(self) -> str:
        return self.code.split(".", 1)[1]


class DiagnosticsRegistry:
    """Every code, checked. Built from `registries.errors` rather than from a second
    list, so there is exactly one place a code is declared."""

    def __init__(self, codes: dict[str, Code], version: str = VERSION) -> None:
        self.version = version
        self._codes = codes

    @classmethod
    def load(cls) -> DiagnosticsRegistry:
        registry = cls(
            {code: Code(code=code, owner=owner, what_now=what_now)
             for code, (owner, what_now) in WHAT_NOW.items()}
        )
        problems = registry.self_check()
        if problems:
            raise RegistryError(
                diagnose(DIAGNOSTICS_INVALID, "; ".join(problems), locator="registries/errors.py")
            )
        return registry

    def __len__(self) -> int:
        return len(self._codes)

    def __contains__(self, code: object) -> bool:
        return code in self._codes

    def get(self, code: str) -> Code:
        if code not in self._codes:
            raise RegistryError(
                diagnose(DIAGNOSTICS_INVALID, f"{code!r} is not a registered code", locator=code)
            )
        return self._codes[code]

    def codes(self) -> tuple[str, ...]:
        return tuple(sorted(self._codes))

    def by_family(self, family: str) -> tuple[Code, ...]:
        return tuple(c for _, c in sorted(self._codes.items()) if c.family == family)

    def by_owner(self, owner: str) -> tuple[Code, ...]:
        return tuple(c for _, c in sorted(self._codes.items()) if c.owner == owner)

    def self_check(self) -> list[str]:
        """What CI asserts. Returns problems rather than raising, so a report can list
        all of them - "three codes are broken" and "a code is broken" are different
        reports and only one of them is useful."""
        problems: list[str] = []
        for code, entry in sorted(self._codes.items()):
            if "." not in code or entry.family not in FAMILIES:
                problems.append(f"{code}: family is not one of {', '.join(FAMILIES)}")
            if not entry.name.isupper() or not entry.name.replace("_", "").isalnum():
                problems.append(f"{code}: the name is not UPPER_SNAKE")
            if entry.owner not in OWNERS:
                problems.append(f"{code}: owner {entry.owner!r} is not one of {', '.join(OWNERS)}")
            if len(entry.what_now.split()) < 12:
                problems.append(f"{code}: what_now is too short to act on")

        # Every constant declared in errors.py is registered. A code that is raised but
        # has no what_now would pass every other check by never being looked up.
        declared = {
            value
            for name, value in vars(errors).items()
            if name.isupper() and isinstance(value, str) and "." in value
            and value.split(".", 1)[0] in FAMILIES
        }
        for missing in sorted(declared - set(self._codes)):
            problems.append(f"{missing} is declared in errors.py and has no what_now")
        return problems
