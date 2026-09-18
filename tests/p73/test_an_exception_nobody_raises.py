"""P73: an exception nobody raises.

An exception class is a claim that something can go wrong in a particular way. When
production never constructs one, the claim is false - and everything hanging off it looks
correct while being unreachable.

That has now cost real work twice. P55 found `RepairNeeded` raised in exactly one place,
and that place a test double. P72 found `TransportFailure`: declared, documented, caught,
given an event and a diagnostic code, and named in every shipped recipe's `retries`, with
nothing in production raising it - so a dropped connection quarantined a step on its first
attempt and the retry count was decoration. Both were found by a person looking.

**Construction, not raising, is the test.** Three of the exception classes here reach their
`raise` through a factory or a variable - `BudgetExceeded` is built, then raised;
`unauthenticated()` returns a `NotAuthenticated`; `as_repair()` returns a `RepairNeeded`.
A rule that looked for `raise X(...)` would report all three, every run, and a check that
cries wolf three times is one somebody switches off.

`test_a_class_only_tests_construct_is_reported` is the load-bearing one: without it this
file is satisfied by a scan that finds nothing ever.
"""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

SHIPPED = (
    "graph",
    "ops",
    "harness",
    "intake",
    "review",
    "privacy",
    "guards",
    "precedent",
    "registries",
    "deliver",
    "workers",
    "evals",
    "governance",
    "ports",
    "admin",
    "ui",
)

# A base class name ending in one of these makes the class an exception. Read from the
# name rather than by importing, so the scan needs nothing loaded and cannot be defeated
# by an import that fails on this machine.
EXCEPTION_BASES = (
    "Error",
    "Exception",
    "Failed",
    "Failure",
    "Refused",
    "Violation",
    "Denied",
    "Exceeded",
    "Needed",
)

ALLOWED: dict[str, str] = {}
"""Exceptions production never constructs, each with the reason it stays that way.

Empty, and worth keeping empty: an exception nothing can raise is a branch of the system
that cannot happen, and the honest fixes are to raise it or to delete it.
"""


def exception_classes() -> dict[str, tuple[str, int]]:
    found: dict[str, tuple[str, int]] = {}
    for package in SHIPPED:
        directory = ROOT / package
        if not directory.is_dir():
            continue
        for path in sorted(directory.rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if not isinstance(node, ast.ClassDef):
                    continue
                bases = {b.id for b in node.bases if isinstance(b, ast.Name)}
                bases |= {b.attr for b in node.bases if isinstance(b, ast.Attribute)}
                if any(b.endswith(EXCEPTION_BASES) or b in found for b in bases):
                    found[node.name] = (str(path.relative_to(ROOT)), node.lineno)
    return found


def constructed_in_production() -> set[str]:
    """Every name production calls - which, for a class, means builds one.

    Tests are excluded deliberately. A class only a test constructs is the defect: P55's
    `RepairNeeded` was raised by a test double and nothing else, and it read as wired to
    anything that counted a reference.
    """
    names: set[str] = set()
    roots = [ROOT / package for package in SHIPPED] + [ROOT / "tools"]
    for root in roots:
        if not root.is_dir():
            continue
        for path in root.rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            try:
                tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
            except SyntaxError:  # pragma: no cover
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    called = node.func
                    name = getattr(called, "id", None) or getattr(called, "attr", None)
                    if name:
                        names.add(name)
    return names


def never_raised() -> list[str]:
    built = constructed_in_production()
    return sorted(name for name in exception_classes() if name not in built)


# ------------------------------------------------------------------ the check


def test_no_exception_class_is_unraisable() -> None:
    surprises = [name for name in never_raised() if name not in ALLOWED]
    assert not surprises, (
        "exception class(es) production never constructs - so the handler, event or "
        f"diagnostic behind them cannot happen. Raise it, delete it, or excuse it: {surprises}"
    )


def test_an_allowed_entry_carries_a_reason() -> None:
    for name, why in ALLOWED.items():
        assert len(why.split()) >= 12, f"{name} is excused without saying why"


def test_an_allowed_entry_that_is_now_raised_is_removed() -> None:
    assert not [name for name in ALLOWED if name not in never_raised()], (
        "excused but now constructed - remove the entry, or it hides the day it stops being"
    )


# ------------------------------------------------------------------ the scan works


def test_the_scan_sees_the_exceptions_that_exist() -> None:
    """A check that found nothing would pass silently for ever."""
    found = exception_classes()
    assert len(found) > 20, found
    for known in ("TransportFailure", "RepairNeeded", "BudgetExceeded", "GuardFailed"):
        assert known in found, known


def test_a_class_reached_through_a_factory_is_not_reported() -> None:
    """The three that would make this check noise. Each reaches its `raise` indirectly, and
    each is properly wired - so a narrower rule would be wrong three times a run."""
    for wired in ("BudgetExceeded", "NotAuthenticated", "RepairNeeded"):
        assert wired not in never_raised(), f"{wired} is wired through a factory or a variable"


def test_a_class_only_tests_construct_is_reported() -> None:
    """The load-bearing one: this file would otherwise be satisfied by a scan that never
    finds anything. Proven on the real collector, with the defect P72 fixed simulated by
    removing the production construction from consideration."""
    built = constructed_in_production() - {"TransportFailure"}
    would_report = sorted(n for n in exception_classes() if n not in built)
    assert "TransportFailure" in would_report, (
        "with nothing in production building it, the scan must report it - that was the "
        "state of this repository until P72"
    )


def test_the_retry_class_is_the_one_that_proved_this_necessary() -> None:
    """Not a rule about a name, but a record of why the rule exists: P72's class must stay
    constructed in production, and if it stops, the general check above fails first."""
    assert "TransportFailure" not in never_raised()
