"""The outbound scan fails closed on what re-identifies a person on its own.

Found by a generated trial balance with a social security number in an officer-compensation
label - which real trial balances carry more often than anyone would like. The scan matched
the engagement's identifier list, which is the names and labels somebody typed into a
profile, and an SSN is on nobody's profile. It would have reached the model.

Two shapes, chosen for precision: an SSN and an EIN. The draft scanner's account-number
pattern is deliberately not here - it would match every `2025-12` period label, and a scan
that fires on every payload is a scan somebody turns off.
"""

from __future__ import annotations

import pytest

from privacy.payload_scan import IdentifierList, PayloadScan, ScanFailed

IDENTIFIERS = IdentifierList.of("HEND-2026-04", ["Henderson Manufacturing", "R. Henderson"])


def test_a_social_security_number_fails_the_scan() -> None:
    result = PayloadScan().check(
        "6000 Officer compensation - D. Okafor SSN 123-45-6789", IDENTIFIERS
    )
    assert not result.passed
    assert any("social security number" in r for r in result.reasons)


def test_an_employer_identification_number_fails_the_scan() -> None:
    result = PayloadScan().check("Payroll tax remittance EIN 12-3456789 Q3", IDENTIFIERS)
    assert not result.passed
    assert any("employer identification number" in r for r in result.reasons)


def test_the_value_is_never_echoed() -> None:
    """Counted and named by kind. Quoting the number into an event or an error would be
    the leak the scan exists to prevent, one level up."""
    result = PayloadScan().check("SSN 123-45-6789 and EIN 12-3456789", IDENTIFIERS)
    joined = " ".join(result.reasons) + " ".join(result.hits)
    assert "123-45-6789" not in joined and "12-3456789" not in joined
    assert "x1" in joined


def test_period_labels_and_ordinary_figures_do_not_trip_it() -> None:
    """Precision is the point. A scan that fires on every payload is one somebody disables."""
    clean = (
        "2025-12 close. Revenue 4,120,000. Account 1100-200. Phone 555-0100. "
        "FY2024-25 comparatives. Invoice 12-345. Lot 123-45."
    )
    result = PayloadScan().check(clean, IDENTIFIERS)
    assert result.passed, result.reasons


def test_the_scan_raises_and_records_when_it_fires() -> None:
    with pytest.raises(ScanFailed):
        PayloadScan().scan("owner SSN 987-65-4321", IDENTIFIERS, run_id="run_x")
