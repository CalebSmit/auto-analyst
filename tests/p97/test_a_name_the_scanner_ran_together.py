"""P97 - a name a scanner ran into the next word.

The first real client folder's scanned PDFs read at about 0.97 mean confidence and still
came back with the words joined: `BOARDMEETINGMINUTES`, `ThefollowingcontainstheBoardmceting
minutes`. Not every space, which is worse than all of them - the loss is unpredictable, so
nothing downstream may assume either spacing.

Until P97 the masker located a declared identifier with `re.escape(value)` and the scan with
`value.lower() in text.lower()`. Both are plain substrings, so `John Smith` was found in
`Present: John Smith (President).` and not in `Present:JohnSmith(President).`

The second half is what makes it a defect rather than a gap. `privacy/payload_scan.py`'s
docstring says the masker and the scan are two nodes on purpose, so that "a masker that
silently no-ops and a scanner that silently passes" cannot be the same bug. They were still
two implementations of one idea, and when the idea was wrong they were wrong together: the
check could not catch the miss because it shared it.

**This is not a security boundary.** CLAUDE.md records that the firm's Claude account is
sanctioned for client data. What masking buys is cross-client isolation and precedent
portability - a precedent carrying an unmasked name cannot be reused on another
engagement - and that is the whole point of the feature rather than a side effect of it.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

from privacy import mask as mask_module
from privacy.mask import ACCOUNT_NUMBER, Masker
from privacy.payload_scan import IdentifierList, PayloadScan, loosely

ROOT = Path(__file__).resolve().parents[2]

#: What the engine actually produced, from the board minutes in the first real client
#: folder. Kept as the shape of the problem; the names in it are invented, because the
#: names in that document were redacted before it ever reached this machine.
AS_OCR_READ_IT = (
    "2023 BOARDMEETINGMINUTES January17,2023 "
    "In attendancewere thetwoOfficersof theCompany:JohnSmith"
    "(ChairmanoftheBoard)and MaryJones(President)."
)


# ===================================================================== the rule itself


@pytest.mark.parametrize(
    ("text", "found"),
    [
        ("Present: John Smith (President).", True),
        # The one that was missed. No space where the page lost it.
        ("Present:JohnSmith(President).", True),
        ("John  Smith", True),
        ("John\nSmith", True),
        ("John\tSmith", True),
        # And not a different name that merely starts the same way.
        ("Johnson Smithers", False),
        ("Smith John", False),
        ("Jon Smith", False),
    ],
)
def test_a_declared_name_is_found_however_the_page_spaced_it(text: str, found: bool) -> None:
    assert bool(loosely("John Smith").search(text)) is found


def test_the_error_has_a_direction_and_it_is_the_survivable_one() -> None:
    """`\\s*` matches more than was meant, not less. A short identifier will now also match
    its joined form wherever that appears, and that masks text nobody needed masked - which
    is a control doing its job too often. The other direction is the one this module exists
    to prevent."""
    assert loosely("A B").search("AB Corp"), "the over-match is real and is stated, not denied"
    assert not loosely("Henderson Tool").search("Henderson Manufacturing")


def test_what_it_does_not_cover_is_said_rather_than_implied() -> None:
    """A scanner that drops a letter defeats this as completely as it defeated the
    substring. Asserted so that nobody reads P97 as having solved OCR error in general."""
    assert not loosely("John Smith").search("Present: John Smlth (President).")
    said = inspect.getdoc(loosely) or ""
    # The concrete example, not the word "letter" - which also appears in "two-letter"
    # three lines up, so the first version of this assertion was satisfied by a sentence
    # about something else entirely and could not go red.
    assert "Smlth" in said, "the uncovered case has to be named where the function is"


# ===================================================================== one rule, not two


def test_the_masker_and_the_scan_share_the_function_rather_than_resembling_each_other() -> None:
    """The defect was not the substring; it was that there were two substrings. Two nodes
    that must agree, each with its own matching, agree until the day one is fixed."""
    assert mask_module.loosely is loosely

    for module in ("privacy/mask.py", "privacy/payload_scan.py"):
        source = (ROOT / module).read_text(encoding="utf-8")
        tree = ast.parse(source)
        defined = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
        if module.endswith("mask.py"):
            assert "loosely" not in defined, "the masker grew its own copy"
        # The old spelling, in either file, is the regression.
        assert "re.escape(ident.value)" not in source, module
        assert "ident.lower() in lowered" not in source, module


def test_neither_module_reaches_a_model() -> None:
    """P12's invariant, re-asked because P97 changed the matching. Deterministic Python
    throughout is what makes this the one step where being plausible is not allowed."""
    for module in ("privacy/mask.py", "privacy/payload_scan.py"):
        tree = ast.parse((ROOT / module).read_text(encoding="utf-8"))
        named: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                named.update(a.name for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                named.add(node.module)
        for forbidden in ("ports.llm", "anthropic", "openai", "harness", "skills"):
            assert not any(n == forbidden or n.startswith(forbidden + ".") for n in named), module


# ===================================================================== the scan catches it


def a_list(*identifiers: str, tokens: tuple[str, ...] = ()) -> IdentifierList:
    return IdentifierList.of("ENG-1", identifiers, tokens)


def test_the_scan_catches_a_joined_name_a_no_op_masker_left_behind() -> None:
    """P12's exit criterion, asked of the case that defeated it: a masker that does nothing,
    and the scan catching it. Before P97 the scan passed this payload."""
    scan = PayloadScan()
    result = scan.check(AS_OCR_READ_IT, a_list("John Smith", "Mary Jones"))
    assert not result.passed
    assert len(result.hits) == 2


def test_the_scan_reports_without_quoting_what_it_found() -> None:
    """Echoing the identifier into an event or an error would be the leak the scan exists to
    prevent, one level up. Re-asked because P97 changed what counts as a hit."""
    result = PayloadScan().check(AS_OCR_READ_IT, a_list("John Smith"))
    assert not result.passed
    assert "John" not in " ".join(result.reasons)
    assert "JohnSmith" not in " ".join(result.reasons)


def test_a_payload_with_nothing_in_it_still_passes() -> None:
    """The other half of a guard that means anything: it has to be able to say yes."""
    result = PayloadScan().check(
        "Total revenue for 2025-12 was 4,120,000.", a_list("John Smith")
    )
    assert result.passed
    assert result.checked == 1


# ===================================================================== what must not change


def test_masking_still_leaves_a_period_label_and_a_figure_alone() -> None:
    """Looser matching on names may not start eating the things timing normalisation and
    tie-out read. A masked period label is the most expensive silent error here: it hides
    the one thing the timing detector needs."""
    assert not ACCOUNT_NUMBER.match("2025-12")
    assert not ACCOUNT_NUMBER.match("4,120,000")
    assert PayloadScan().check(
        "FY2025 total assets 11,000,000", a_list("Henderson Tool")
    ).passed


def test_an_account_number_is_still_found_by_shape() -> None:
    assert ACCOUNT_NUMBER.search("Account 12345678 balance")
    assert not ACCOUNT_NUMBER.search("Revenue was 4,120,000")


def test_an_iso_date_is_a_period_and_survives_the_masker(masker: Masker) -> None:
    """Separated out from the figures because it is the expensive one. A period end looks
    like an account number to the shape pattern, and a masked period end hides the single
    thing the timing detector reads - so the masker skips it explicitly, and this is the
    assertion that says so rather than the tautology that was here first."""
    out = masker.mask(
        "Balance at 2025-12-31 was 11,000,000",
        "ENG-1",
        [mask_module.Identifier("CLIENT", "Henderson Tool")],
    )
    assert "2025-12-31" in out.text
    assert out.substitutions == {}


def test_the_masker_substitutes_the_joined_form_too(masker: Masker) -> None:
    """The half the scan cannot prove. A scan that catches the leak and a masker that still
    lets it through would leave every run failing closed - correct, and useless."""
    out = masker.mask(AS_OCR_READ_IT, "ENG-1", [mask_module.Identifier("PERSON", "John Smith")])
    assert "JohnSmith" not in out.text
    assert out.substitutions["John Smith"].startswith("[[PERSON_")
    # And what it replaced it with is what the scan then expects to find.
    assert PayloadScan().check(out.text, out.identifiers).hits == ()
