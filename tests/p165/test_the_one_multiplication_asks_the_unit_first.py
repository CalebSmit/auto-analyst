"""P165: the one multiplication, and the unit it asks first.

P162 gave a share count `unit: shares, scale: 1`, so the statement's thousands stopped
being applied to it. `harness/restate.py` then divided it by a thousand anyway: it read
`scale` and never `unit`, and rewrote the scale to the template's, so the writer's own
refusal for a figure at the wrong scale - the one that says *restating is arithmetic and
does not happen in the writer* - could never fire. 135,361,000 shares became 135,361, listed
in the run record as a restatement, claiming `unit: shares` and `scale: 1000` together.

The shape mattered more than the instance. **Six lines across three modules multiplied a
figure by its scale** - `harness/restate.py` twice, `deliver/workpaper.py` once,
`harness/procedures/ebitda_normalization.py` three times - and **two lines in the whole
repository read its unit**, both asking only whether it was currency. The restater's first
line already claimed to be "the one multiplication in the run"; five lines elsewhere made
that false, and making it true is the fix: `amount_of` and `expect_unit` are the one way a
figure becomes a number, every site reaches them, and the proof is not a search for a word -
it is making `_moved` raise and watching each site fail.

No registered template asks for a share count today, so the wrong *cell* was a trap armed
for the first template that does, or the first mapping that binds a count to a currency
cell - which nothing refused. The wrong *record* was live: `_figures` restates the whole
catalogue, bound or not, so any `(in shares)` row was divided and listed on every run.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest

import harness.restate as restate
from harness.restate import Amount, Left, amount_of, expect_unit, restated
from registries.errors import RegistryError

ROOT = Path(__file__).resolve().parents[2]

SHARES = {
    "value": 135_361_000.0,
    "unit": "shares",
    "scale": 1,
    "period": {"type": "FY", "end": "2025-12-31"},
}
DOLLARS = {
    "value": 85.0,
    "unit": "currency",
    "scale": 1000,
    "currency": "USD",
    "period": {"type": "FY", "end": "2025-12-31"},
}
WRONG = re.compile(r"135,361(?![,\d])")
"""The number that must appear in no output of any site: a count of shares in thousands.
A pattern, because `135,361,000` is the right number and contains the wrong one."""


def wrong_in(text: object) -> bool:
    return WRONG.search(str(text)) is not None


# ---------------------------------------------------------------- the restater, by identity


def test_a_count_of_shares_is_not_restated_and_is_listed() -> None:
    out, moves, left = restated({"shares": SHARES, "revenue": DOLLARS}, 1000)
    assert out["shares"] is SHARES, "returned as it came, not a copy with the scale rewritten"
    assert out["shares"]["scale"] == 1
    assert out["revenue"] is DOLLARS, "already at the template's scale, so untouched"
    assert moves == ()
    assert left == (
        Left(
            "shares",
            "shares",
            "a count of shares is not restated to a currency scale; a cell bound to it is "
            "refused by the writer",
        ),
    )
    assert left[0].as_row() == {"figure_ref": "shares", "unit": "shares", "why": left[0].why}


def test_a_dollar_figure_moves_exactly_as_it_did() -> None:
    """The currency path is unchanged, including the record it writes: this is P108's own
    assertion re-made, so the third part of the tuple cost the first two nothing."""
    out, moves, left = restated({"a": {**DOLLARS, "value": 1_234_567.89, "scale": 1}}, 1000)
    assert out["a"]["value"] == pytest.approx(1234.56789)
    assert out["a"]["scale"] == 1000
    (move,) = moves
    assert move.as_row() == {
        "figure_ref": "a",
        "from_scale": 1,
        "to_scale": 1000,
        "before": 1_234_567.89,
        "after": pytest.approx(1234.56789),
    }
    assert left == ()


def test_the_driver_records_what_was_left_beside_what_moved() -> None:
    """Through `RunDriver._figures` itself, so the event a person reads carries both."""
    from tests.p108.test_the_one_multiplication import driver_figures  # type: ignore[attr-defined]

    figures, bus = driver_figures(
        {"shares": SHARES, "revenue": {**DOLLARS, "scale": 1}}, template_scale=1000
    )
    assert figures["shares"]["value"] == 135_361_000.0
    assert figures["shares"]["scale"] == 1
    (event,) = bus.events
    assert event["type"] == "model.figures.restated"
    assert [r["figure_ref"] for r in event["payload"]["restated"]] == ["revenue"]
    assert [r["figure_ref"] for r in event["payload"]["left_as_they_are"]] == ["shares"]
    assert "1 left at their own unit" in event["message"]
    assert not wrong_in(event["payload"])


# ------------------------------------------------------------- the writer refuses, in words


def test_a_cell_bound_to_a_count_of_shares_is_refused_with_the_unit_in_the_sentence() -> None:
    from deliver.builder import _value_of

    for scale in (1, 1000):
        with pytest.raises(RegistryError) as refused:
            _value_of({**SHARES, "scale": scale}, 1000, "USD", "Revenue_FY1")
        said = str(refused.value)
        assert "a count of shares" in said
        assert "every input of this template is USD at scale 1000" in said
        assert "does not happen in the writer" not in said, (
            "the sentence must not invite a restatement"
        )
        assert not wrong_in(said)

    # A dollar figure at the right scale and currency goes through; at the wrong scale it is
    # the refusal it always was, and in another currency the refusal it always was.
    assert _value_of(DOLLARS, 1000, "USD", "Revenue_FY1") == 85.0
    with pytest.raises(RegistryError, match="does not happen in the writer"):
        _value_of({**DOLLARS, "scale": 1}, 1000, "USD", "Revenue_FY1")
    with pytest.raises(RegistryError, match="the figure is in CAD"):
        _value_of({**DOLLARS, "currency": "CAD"}, 1000, "USD", "Revenue_FY1")


def test_the_builder_still_does_no_arithmetic() -> None:
    """`expect_unit` is what lets the writer ask the unit: it does no arithmetic, so the
    Numeric Integrity Lock still brackets arithmetic-free code. Asserted the way P108
    asserts it, over the module's syntax tree."""
    import ast

    tree = ast.parse((ROOT / "deliver" / "builder.py").read_text(encoding="utf-8"))
    hits = [
        n for n in ast.walk(tree)
        if isinstance(n, ast.BinOp) and isinstance(n.op, ast.Mult | ast.Div | ast.FloorDiv)
    ]
    assert not hits


def test_model_load_refuses_the_binding_before_the_writer_has_to() -> None:
    """The earlier refusal, which goes round the recipe's repair loop rather than halting
    at release. Same class as the period check beside it: arithmetic, not judgement."""
    from harness.procedures.model_load import ProposalRefused
    from tests.p165.conftest import model_load_apply

    refs = {"timing:Revenue:FY1": DOLLARS, "timing:Shares:FY1": SHARES}
    bound = model_load_apply(refs, {"Revenue_FY1": "timing:Revenue:FY1"})
    assert bound["template_mapping"]["bindings"][0]["figure_ref"] == "timing:Revenue:FY1"
    with pytest.raises(ProposalRefused) as refused:
        model_load_apply(refs, {"Revenue_FY1": "timing:Shares:FY1"})
    said = str(refused.value)
    assert "a count of shares" in said
    assert "a figure that is not money passes every check after this one" in said


# ------------------------------------------------------------- the narrative and the tests


def test_the_workpaper_prints_a_count_as_a_count() -> None:
    from deliver.workpaper import _amount

    said = _amount({"candidate_id": "c1", "amount": SHARES}, "USD")
    assert said == "135,361,000 shares in FY2025", said
    assert _amount({"candidate_id": "c2", "amount": DOLLARS}, "USD") == "85,000 USD in FY2025"
    # A currency figure with no code of its own takes the template's, as it always did.
    bare = {k: v for k, v in DOLLARS.items() if k != "currency"}
    assert _amount({"candidate_id": "c3", "amount": bare}, "USD") == "85,000 USD in FY2025"


def test_amount_of_and_expect_unit_say_what_a_figure_is() -> None:
    assert amount_of(SHARES, "x") == Amount(135_361_000.0, "shares", None, "x")
    assert str(amount_of(SHARES, "x")) == "135,361,000 shares"
    assert str(amount_of(DOLLARS, "x")) == "85,000 USD"
    assert amount_of(250_000.0, "profile:benchmark") == Amount(
        250_000.0, "currency", None, "profile:benchmark"
    )
    with pytest.raises(RegistryError, match="a count of shares"):
        amount_of(SHARES, "x", unit="currency")
    with pytest.raises(RegistryError, match="the figure is in CAD and the threshold is USD"):
        expect_unit(
            {**DOLLARS, "currency": "CAD"},
            "x",
            unit="currency",
            currency="USD",
            destination="the threshold is USD",
        )
    # A bare number has no code to disagree with, so a currency expectation lets it through.
    expect_unit(250_000.0, "x", unit="currency", currency="USD", destination="d")


# ----------------------------------------------------- every site reaches the one place


def every_site(figure: dict[str, Any]) -> dict[str, Any]:
    """Drive each production site with one figure and collect what it said."""
    from deliver.workpaper import _amount

    out: dict[str, Any] = {}
    out["restated"] = restated({"f": figure}, 1000)
    out["workpaper"] = _amount({"candidate_id": "c", "amount": figure}, "USD")
    try:
        from deliver.builder import _value_of

        out["builder"] = _value_of(figure, int(figure.get("scale", 1)), "USD", "Cell")
    except RegistryError as refused:
        out["builder"] = str(refused)
    return out


def test_with_the_one_multiplication_made_to_raise_every_site_fails(
    monkeypatch, ebitda_sites
) -> None:
    """The proof of "one place" that is not a search for a word. A site that quietly went
    back to `value * scale` of its own would pass a dollar figure through without touching
    `_moved`, and this would go green on broken code - which is why it is the test."""

    class Sentinel(Exception):
        pass

    def boom(*_: Any, **__: Any) -> float:
        raise Sentinel

    sites = ebitda_sites(DOLLARS)
    assert set(sites) == {"review_items", "materiality", "officer_total"}
    monkeypatch.setattr(restate, "_moved", boom)
    from deliver.workpaper import _amount

    with pytest.raises(Sentinel):
        restated({"f": {**DOLLARS, "scale": 1}}, 1000)
    with pytest.raises(Sentinel):
        _amount({"candidate_id": "c", "amount": DOLLARS}, "USD")
    for site in sites.values():
        with pytest.raises(Sentinel):
            site()


def test_the_officer_total_goes_through_the_one_place_once_per_period(
    monkeypatch, ebitda_sites, world
) -> None:
    """The officer site cannot be proved by making `_moved` raise: `apply` reaches the
    materiality site right after it, so a sentinel is raised either way and the revert
    harness found the officer site could multiply on its own and stay green. Counted
    instead - with the candidate flagged as officer compensation the one place is reached
    exactly once more per period than without, and a site that multiplied on its own would
    make that difference zero."""
    calls: list[str] = []
    real = restate._moved

    def counting(value: float, from_scale: int, to_scale: int, ref: str) -> float:
        calls.append(ref)
        return real(value, from_scale, to_scale, ref)

    monkeypatch.setattr(restate, "_moved", counting)
    sites = ebitda_sites(DOLLARS)
    sites["materiality"]()
    plain = len(calls)
    calls.clear()
    sites["officer_total"]()
    assert len(calls) - plain == len(world["inputs"].periods), (plain, calls)


def test_the_driver_says_so_when_only_a_count_was_left() -> None:
    """Nothing moved, one figure left alone: still an event, because a count sitting in a
    catalogue restated to thousands is exactly what used to be divided in silence."""
    from tests.p108.test_the_one_multiplication import driver_figures  # type: ignore[attr-defined]

    figures, bus = driver_figures({"shares": SHARES}, template_scale=1000)
    assert figures["shares"] is SHARES
    (event,) = bus.events
    assert event["payload"]["restated"] == []
    assert [r["figure_ref"] for r in event["payload"]["left_as_they_are"]] == ["shares"]
    assert event["message"].startswith("0 figure(s) restated")
    assert "1 left at their own unit" in event["message"]


def test_the_wrong_number_appears_in_no_output_of_any_site(ebitda_sites) -> None:
    said = every_site(SHARES)
    assert not wrong_in(repr(said)), said
    assert "135,361,000 shares" in said["workpaper"]
    assert "a count of shares" in said["builder"]

    for name, site in ebitda_sites(SHARES).items():
        try:
            result = site()
        except Exception as refused:  # noqa: BLE001 - what each site says is the assertion
            result = str(refused)
        assert not wrong_in(repr(result)), (name, result)
        assert "a count of shares" in repr(result), (name, result)


def test_the_count_is_six_lines_and_now_one() -> None:
    """`intake/readers/units.py` and the backlog said three places. There were six lines in
    three modules, and the number matters because a fix has to reach all of them; this is
    the assertion that the only multiplication of a figure by its scale left is `_moved`."""
    import ast

    sites: list[str] = []
    for rel in (
        "harness/restate.py",
        "deliver/workpaper.py",
        "deliver/builder.py",
        "harness/procedures/ebitda_normalization.py",
        "harness/procedures/model_load.py",
        "workers/driver.py",
        "evals/metrics.py",
    ):
        tree = ast.parse((ROOT / rel).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.BinOp) or not isinstance(node.op, ast.Mult | ast.Div):
                continue
            text = ast.unparse(node)
            if "scale" in text and "value" in text:
                sites.append(f"{rel}:{node.lineno} {text}")
    assert sites == [
        "harness/restate.py:" + line
        for line in sites_in_moved()
    ], sites


def sites_in_moved() -> list[str]:
    """The two lines of `_moved`, found rather than typed, so the assertion above moves
    with the file."""
    import ast

    tree = ast.parse((ROOT / "harness" / "restate.py").read_text(encoding="utf-8"))
    out: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_moved":
            for inner in ast.walk(node):
                if isinstance(inner, ast.BinOp) and isinstance(inner.op, ast.Mult | ast.Div):
                    out.append(f"{inner.lineno} {ast.unparse(inner)}")
    return out
