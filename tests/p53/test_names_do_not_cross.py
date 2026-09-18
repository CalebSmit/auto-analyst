"""A person's name does not cross from one client's engagement into another's.

The masker substitutes what it has been declared, and what is declared is the client's
company name and the distinctive words of it - `workers.driver._identifiers`. The vault has
a `PERSON` kind and production has never issued one, because the engagement profile has no
field that names a person (checked: its schema has none).

On the outbound path that is defensible. The model is already reading this client's
documents, and `privacy/README.md` is explicit that masking is the cross-client isolation
boundary rather than a boundary against the provider.

The Precedent Store is where that stops being defensible, because it is the one place where
text written on one engagement is deliberately shown on another: `PrecedentStore.records`
filters by practice and skill and not by client. So the ordinary case of valuation add-back
work - a rationale naming an owner or an officer - masked to itself, cleared a scan that had
never heard of the name, and was admitted.

Three things had to be true at once for that to happen, and each of these holds one of them
down.
"""

from __future__ import annotations

from privacy.payload_scan import IdentifierList, PayloadScan
from privacy.people import looks_like_a_person
from workers.driver import _distinctive_words

# ------------------------------------------------------------------ the shape of the leak


def test_the_scan_alone_cannot_see_a_person_and_never_could() -> None:
    """Not a regression - the standing fact this whole file exists because of. The scan
    looks for what it was given, and a person is never given to it."""
    declared = IdentifierList(
        engagement_id="E1",
        identifiers=("Brightwater Holdings LLC", "Brightwater", "Holdings"),
    )
    named = "Officer salary - R. Whitfield (owner); auto lease for M. Whitfield"
    verdict = PayloadScan().check(named, declared)
    assert verdict.passed, "the scan passes, which is why a second check is needed here"
    assert verdict.checked == 3, "it checked three things, none of which is a person"


def test_a_rationale_that_names_a_person_is_caught_by_shape() -> None:
    for naming in (
        "Officer salary - R. Whitfield (owner); auto lease for M. Whitfield",
        "Rent paid to Mr. Whitfield for the Elm Street property",
        "Salary to John Smith, the owner",
        "Jane Doe, president, discretionary bonus",
        "Note payable to M. J. Whitfield",
        "Vehicle allowance for the owner, Robert Hale",
    ):
        assert looks_like_a_person(naming), naming


def test_an_ordinary_add_back_rationale_is_not() -> None:
    """A check that fires on every schedule is a check somebody turns off inside a week.
    These are the sentences this store is *for*."""
    for ordinary in (
        "Officer compensation above the benchmark for the period",
        "Owner compensation normalised to the market benchmark",
        "Related party rent held for the market-rent fact",
        "Non-recurring legal settlement, Q3",
        "Discretionary charitable contributions, added back",
        "Accrued Interest on the revolving facility",
        "Cost of Capital and Deferred Revenue reclassified",
        "Officer salary normalised to the Chartwell benchmark",
    ):
        assert not looks_like_a_person(ordinary), ordinary


def test_what_it_reports_never_quotes_what_it_found() -> None:
    """The reason travels into an event and into a diagnostic. Reporting a leak verbatim
    is the leak, one level up - `privacy.payload_scan` takes the same care."""
    found = looks_like_a_person("Officer salary - R. Whitfield (owner)")
    assert found.reasons
    for reason in found.reasons:
        assert "Whitfield" not in reason
        assert "R." not in reason


def test_the_writeback_refuses_rather_than_writing() -> None:
    """The cost of a false positive here is one example that is not learned from. The cost
    of a false negative is a name in another client's workpaper, so this path fails closed.
    """
    import inspect

    from precedent.writeback import PrecedentWriteback

    source = inspect.getsource(PrecedentWriteback.write)
    assert "looks_like_a_person(masked.text)" in source
    assert "reads as naming a person" in source
    assert "stays un-learned rather than carrying" in source
    # After the masker and the scan, so a name the masker did handle is never reported.
    assert source.index("self.masker.mask") < source.index("looks_like_a_person")


# ------------------------------------------------------------------ nothing is undefended


def test_no_client_is_left_with_no_identifier_at_all() -> None:
    """`_distinctive_words` drops a word under four letters, a generic word, and any word
    the firm's own text uses. For `BRW Partners` that was all of them, so only the exact
    string "BRW Partners" was ever masked - and `BRW FY2025 Trial Balance.xlsx`, `BRW's
    owner` and `BRW Holdings II` all reached the model untouched and tripped nothing.

    A noisy guard is worth having. An absent one is not.
    """
    for name in (
        "BRW Partners",
        "ACME LLC",
        "Hale & Co",
        "Brightwater Holdings LLC",
        "Summit Manufacturing Co",
    ):
        assert _distinctive_words(name), f"{name} would be masked only as its exact string"


def test_the_ordinary_case_still_prefers_the_distinctive_word() -> None:
    """The fallback is a fallback. Where a real distinctive word exists it is still the
    only one listed, so the guard does not start firing on the firm's own text."""
    assert _distinctive_words("Brightwater Holdings LLC") == ("Brightwater",)
    assert _distinctive_words("Northgate Dental Partners") == ("Northgate",)


# ------------------------------------------------------------------ the check that lied


def test_the_identifier_scan_refuses_to_call_an_empty_register_clean() -> None:
    """CLAUDE.md names `interview.py scan` as the thing that keeps client data inside
    knowledge/. `knowledge/identifiers.txt` held nothing but comments, so `scan` returned
    early and printed `clean: 0 identifiers checked` - unconditionally, for as long as
    nobody remembered to write a name in a file nothing reminds them about.

    A check that cannot fail is worse than no check, because the record says it ran.
    """
    import inspect

    from tools.interview import _knowledge_has_answers, _scan

    source = inspect.getsource(_scan)
    assert "UNCHECKED" in source
    assert "not names and _knowledge_has_answers()" in source
    assert "return 1" in source.split("UNCHECKED")[1], "and it is a failure, not a note"
    # Still silent on a clone where no interview has happened, which is the honest case.
    assert callable(_knowledge_has_answers)
