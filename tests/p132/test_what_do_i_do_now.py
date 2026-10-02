"""P132: the dashboard answers "what do I do now".

Found by running the console against a store of eighteen real runs and reading the screen
rather than the source. Four things, and each was visible in one look:

**An engagement with one run printed everything twice.** The group header carried the
client, the scope and the time; the run row under it carried the client, the scope, the
run id and the same time. Every one of the eighteen engagements had exactly one run - which
is every engagement until a client comes back - so the fold was pure duplication. Seven
engagements now fit where four did, with nothing lost.

**The two counts in the chrome read as disjoint and were not.** "12 need attention . 2
waiting on you" counted twelve *runs* and two *questions*, and both questions sat on runs
already inside the twelve. Naming the unit is the fix.

**The counts were facts, not controls.** Somebody reads "12 need a person" and the next
thing they want is those twelve. Now the number is what they press.

**And the primary button contradicted the sentence above it.** A quarantined run says
"stopped on itself - a step failed in a way retrying will not fix", and **Resume** was the
dark button - so the design pointed at the one action the sentence had just ruled out.

What is *not* changed is the order. Newest-first is how somebody finds the job they were
just working on, and reordering by state would answer a different question than the one
people usually arrive with. The filter answers the other one and leaves the default alone.
"""

from __future__ import annotations

import re

from ops.console.app import PAGE as ACTIVITY


def script() -> str:
    return "\n".join(re.findall(r"<script>(.*?)</script>", ACTIVITY, re.S))


def body_of(name: str, *, with_comments: bool = False) -> str:
    """One function's body, so an assertion is about that function rather than the page.

    Comments are taken out by default, and that is not tidiness. The first version of
    `test_the_two_counts_name_their_units` asserted that "need attention" no longer
    appears - and failed on the comment that *explains* why it no longer appears. A test
    failing on its own documentation is the thing `tests/p55` wrote down after doing it
    once, and `tests/importing.py` opens by saying it: walk the code, never the prose.

    The `//` rule deliberately ignores a `//` that follows a colon, so a URL in a string
    is not read as the start of a comment.
    """
    found = re.search(rf"function {re.escape(name)}\([^)]*\)\s*\{{(.*?)\n\}}", script(), re.S)
    assert found, f"the page has no {name}"
    inner = found.group(1)
    if with_comments:
        return inner
    inner = re.sub(r"/\*.*?\*/", " ", inner, flags=re.S)
    return re.sub(r"(?<!:)//[^\n]*", " ", inner)


# --------------------------------------------------------------- one run, one row


def test_an_engagement_with_one_run_is_one_row() -> None:
    """The fold earns its line when it summarises more than one thing. Folding one run is
    indenting it under itself."""
    inner = body_of("paintRuns")
    assert "if (rs.length === 1) return runRow(rs[0]);" in inner, (
        "a single-run engagement still gets a group header"
    )


def test_an_engagement_with_several_runs_still_folds() -> None:
    """The fold is right for a repeat client, which is what P63 built it for. Taking it
    out entirely would undo that."""
    inner = body_of("paintRuns")
    assert "grp-head" in inner and "grp-runs" in inner
    assert "rs.map(runRow)" in inner


def test_the_run_row_carries_what_the_group_header_used_to() -> None:
    """A row standing on its own has to say the client, the engagement and the scope -
    otherwise collapsing the header loses them."""
    row = body_of("runRow")
    assert "runName(r)" in row, "the client's name"
    assert "r.engagement_id" in row
    assert "r.scope_path" in row
    assert "r.run_id" in row


# ----------------------------------------------- the counts say what they count


def test_the_two_counts_name_their_units() -> None:
    """One counts runs and one counts questions, and a question sits on a run already in
    the first number. Written without the units they read as two disjoint buckets."""
    inner = body_of("refresh")
    # Through `needAPerson`, which owns the phrase *and its verb*. Both surfaces wrote the
    # sentence themselves and the engagement header read "1 need a person" on a real
    # engagement with one halted run; P138 moved it into one function.
    assert "needAPerson(" in inner
    assert "'question', 'questions'" in inner, "the second count does not say it counts questions"
    assert "need attention" not in inner, "the old wording is back"
    assert "waiting on you" not in inner, "the old wording is back"


def test_the_counts_are_the_controls() -> None:
    """Somebody reads a number and wants the things it counted. The number is pressable
    rather than a fact to go and act on somewhere else."""
    inner = body_of("refresh")
    assert 'data-act="onlyNeedsAPerson"' in inner
    assert 'data-act="toReview"' in inner
    assert "ACTIONS.onlyNeedsAPerson" in script()
    assert "ACTIONS.toReview" in script()


def test_the_chip_is_a_named_action_rather_than_a_handler_in_the_markup() -> None:
    """`ui/who.py`'s rule, which this had to keep while adding a control to the chrome:
    a page builds no handler out of data."""
    inner = body_of("refresh")
    assert "onclick" not in inner
    assert "javascript:" not in inner


def test_a_chip_is_reachable_from_the_keyboard() -> None:
    """It is a `b` carrying a role, so without a tabindex it is unreachable - and the
    shared listener already answers Enter and Space for anything with `data-act`."""
    inner = body_of("refresh")
    chips = re.findall(r'<b class="chip"[^>]*', inner)
    assert chips, "no chip in the chrome"
    for chip in chips:
        assert 'role="button"' in chip, chip
        assert 'tabindex="0"' in chip, chip


# ------------------------------------------------------------------- the filter


def test_the_filter_narrows_to_what_needs_a_person_and_composes_with_the_search() -> None:
    """Two narrowings of one list. Either alone, or both - a person who typed a client's
    name and then pressed the button means both."""
    inner = body_of("matching")
    assert "ONLY_NEEDS" in inner
    assert "NEEDS_ATTENTION.has(r.state)" in inner
    assert "haystack(r).includes(q)" in inner, "the text filter is gone"
    assert "get(" not in inner and "/api/" not in inner, "narrowing asks the server"


def test_the_default_order_is_not_changed_by_any_of_this() -> None:
    """Newest-first is how somebody finds the job they were just working on. The filter
    answers "what do I do now" without taking that away."""
    inner = body_of("matching")
    assert "sort" not in inner, "matching() reorders the list"
    assert "ONLY_NEEDS = false" in script(), "the narrowing is off until it is asked for"


def test_clearing_clears_both_narrowings() -> None:
    """A Clear that left one of them on would be a list that looks filtered for no
    visible reason."""
    found = re.search(r"ACTIONS\.clearFilter = \(\) => \{(.*?)\n\};", script(), re.S)
    assert found
    assert "ONLY_NEEDS = false" in found.group(1)
    assert "q.value = ''" in found.group(1)


def test_the_button_says_how_many_and_what_pressing_it_again_does() -> None:
    inner = body_of("paintRuns")
    assert "Needs a person (${waiting})" in inner
    assert "'All runs'" in inner, "there is no way back without reading the Clear button"
    assert "needs.hidden = !waiting" in inner, "offered even when it would filter to nothing"


def test_a_narrowed_list_says_why_it_is_short() -> None:
    """An empty or short panel is a claim about the work. When a filter is what shortened
    it, the panel has to say so."""
    inner = body_of("paintRuns")
    assert "needing a person" in inner
    assert "No run ${both}" in inner


# ------------------------------------ and the button that contradicted itself


def test_resume_is_not_the_primary_action_on_a_run_that_stopped_on_itself() -> None:
    """The page says retrying will not fix it. Making Resume the dark button pointed at
    the one action that sentence had ruled out."""
    inner = body_of("actions")
    resume = re.search(r'<button class="([^"]*)"[^>]*data-do="resume"', inner, re.S)
    assert resume, "no resume button"
    assert "primary" not in resume.group(1), "Resume is the primary action again"


def test_both_actions_say_what_they_do_before_they_are_pressed() -> None:
    inner = body_of("actions")
    assert "Only useful once whatever stopped it has been fixed" in inner
    assert "Nothing partial is delivered" in inner


def test_the_sentence_resume_is_measured_against_is_still_the_one_shown() -> None:
    """If the quarantined wording ever changed, the reason this button is not primary
    would go with it - so the two are asserted together."""
    says = re.search(r"const STATE_SAYS = \{(.*?)\n\};", script(), re.S)
    assert says
    assert "retrying will not fix" in says.group(1)


def test_the_comment_stripper_would_be_caught_being_wrong() -> None:
    """A helper that silently returned the whole body would make every assertion above
    weaker without failing, so the stripping is proved on a function that has both kinds
    of comment in it and a URL-like string to not break."""
    assert "/*" in body_of("refresh", with_comments=True), "refresh has a block comment"
    assert "/*" not in body_of("refresh")
    assert "need attention" in body_of("refresh", with_comments=True), "in its comment"
    assert "need attention" not in body_of("refresh"), "and nowhere else"

    stripped = body_of("runAction")
    assert "/api/" in stripped, "a path in a string survived the // rule"


def test_the_group_header_uses_the_same_words_as_the_chrome() -> None:
    """Two words for one thing on one page is the reader's problem, not the writer's.
    The chrome says "need a person" and the engagement header said "need attention" -
    and the header is still shown, for a client with several runs."""
    inner = body_of("paintRuns")
    assert "needAPerson(" in inner, "the header writes the sentence itself again"
    assert "need attention" not in inner
    assert "'question' : 'questions'" in inner, "the open count does not say what it counts"
