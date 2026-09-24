"""C67 - guards that were not guarding.

* **P119** — a figure could be bound to the cell of another year and every check after it
  passed. The Numeric Integrity Lock is a multiset: transpose two fiscal years and its
  difference is empty, every total re-adds, and the provenance is impeccable.
* **P120** — seven tests stood a substring in for the property they guarded, four of them
  the only enforcement of a named non-negotiable. The worst was defeated by the comment
  explaining the very line it was checking.

They are the same failure at two levels. P119 is a guard that was never written, in a place
where everything downstream assumed one. P120 is a set of guards that were written and did
not hold, in places where everything assumed they did. In both cases the build's own
description of itself — "a guard a model cannot relax", "OCR is local and that is not a
preference" — was true of the intent and not of the code.

So the question here is whether the two halves agree about one thing: that every claim this
build makes about what it refuses is a claim something actually refuses.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from harness.procedures.model_load import (
    SLOT_FOR_A_BENCHMARK,
    FigureRef,
    ModelLoad,
    ModelLoadInputs,
    ProposalRefused,
    TemplateInput,
)
from tests.importing import imported_modules, reaches_any
from tests.reading import python_code

ROOT = Path(__file__).resolve().parents[3]


def bound(input_period: str, figure_period: str) -> Any:
    """Put one binding through `ModelLoad.apply` with those two periods."""
    loaded = ModelLoadInputs(
        template_key="Chartwell_Input_Help_v1@1.0",
        template_version="1.0",
        inputs=(TemplateInput("Revenue_FY1", "Revenue", input_period, required=True),),
        catalogue=(
            FigureRef(
                figure_ref="timing:Revenue",
                source_output="timing",
                description="Revenue",
                period=figure_period,
                figure={"value": 1.0, "scale": 1000, "unit": "currency", "currency": "USD"},
            ),
        ),
    )
    rows = [
        {"name": i.name, "line": i.line, "period": i.period, "required": i.required}
        for i in loaded.inputs
    ]
    tools = type(
        "T",
        (),
        {
            "engagement_id": "ENG-C67",
            "__getitem__": lambda self, n: (
                lambda **_: type("R", (), {"value": {"rows": rows}})()
            ),
        },
    )()
    proposal = {
        "bindings": [{"named_range": "Revenue_FY1", "figure_ref": "timing:Revenue"}],
        "unmapped_template_inputs": [],
        "unrouted_upstream_figures": [],
    }
    return ModelLoad().apply(proposal, tools, loaded, "pin")


# ============================================================ the guard that was missing


def test_a_transposed_year_is_refused() -> None:
    """The failure the lock cannot see, and the reason it cannot: a multiset does not know
    where a number went, only that the same numbers came back."""
    with pytest.raises(ProposalRefused, match="wrong year"):
        bound("FY1", "FY3")


def test_the_right_year_still_goes_through() -> None:
    out = bound("FY1", "FY1")
    assert out["template_mapping"]["bindings"][0]["figure_ref"] == "timing:Revenue"


def test_the_one_row_that_is_not_a_fiscal_year_still_matches() -> None:
    """Where the check could have broken something: the profile's benchmark carried a
    date in the field every other row uses for the template's slot, so the check had to
    be given a vocabulary both ends share rather than being weakened to let it past."""
    from deliver.registry import TemplateInputs

    schema = TemplateInputs.load("Chartwell_Input_Help_v1@1.0")
    benchmark = schema.get("Owner_Comp_Benchmark")
    assert benchmark is not None and benchmark.period == SLOT_FOR_A_BENCHMARK


def test_what_is_not_checked_is_said_rather_than_implied() -> None:
    """The line is the model's judgement and cannot be compared - and an invariant
    somebody assumes is there is worse than one they know is not."""
    said = (ROOT / "harness" / "procedures" / "model_load.py").read_text(encoding="utf-8")
    assert "line is not checked, and cannot be" in said
    assert "Source column" in said, "and where a wrong line is meant to be seen instead"


# ============================================================ the guards that did not hold


def test_the_peer_address_guard_reads_what_uvicorn_is_given() -> None:
    """Deleting `proxy_headers=False` used to leave the test green, because the comment
    above it carried the same phrase."""
    import ast

    source = (ROOT / "tools" / "serve.py").read_text(encoding="utf-8")
    calls = [
        n
        for n in ast.walk(ast.parse(source))
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute)
        and n.func.attr == "run"
        and isinstance(n.func.value, ast.Name)
        and n.func.value.id == "uvicorn"
    ]
    assert calls
    for call in calls:
        given = {kw.arg: kw.value for kw in call.keywords}
        value = given.get("proxy_headers")
        assert isinstance(value, ast.Constant) and value.value is False


def test_no_guard_reaches_the_configuration_store() -> None:
    """*Guards are not configurable.* The substring version was defeated by
    `from intake import config`."""
    for folder in ("guards", "harness", "graph", "privacy"):
        for path in (ROOT / folder).rglob("*.py"):
            names = imported_modules(path.read_text(encoding="utf-8"))
            assert "intake" not in names and "intake.config" not in names, path


@pytest.mark.parametrize(
    "path", sorted((ROOT / "ports" / "ocr").glob("*.py")), ids=lambda p: p.name
)
def test_no_ocr_adapter_reaches_the_network(path: Path) -> None:
    """*OCR is local, and that is not a preference.* Every adapter, not the two the old
    list happened to name - and `rapidocr` is now installed on this machine and is the
    one CLAUDE.md recommends, so this is live rather than theoretical."""
    assert (
        reaches_any(
            path.read_text(encoding="utf-8"),
            ("requests", "httpx", "httpx2", "urllib", "http", "socket", "boto3", "ftplib"),
        )
        == ()
    )


def test_the_waiver_gate_takes_only_an_acceptance() -> None:
    """A rejection is not a waiver. Inverting one comparison satisfied every assertion the
    old test made, and would have let a person's refusal write the workbook they refused."""
    from ops.models import DecisionKind
    from workers.driver import RunDriver

    decided = [
        type("D", (), {"item_id": f"item:{kind.value}", "decision": kind})()
        for kind in DecisionKind
    ]
    driver = RunDriver.__new__(RunDriver)
    driver.wiring = type(  # type: ignore[attr-defined]
        "W", (), {"store": type("S", (), {"decisions": lambda self, r: decided})()}
    )()
    assert driver._waivers("r") == frozenset({"item:accepted"})  # noqa: SLF001


def test_a_page_from_nowhere_cannot_write() -> None:
    """`Origin: null` is what a sandboxed iframe on any website sends, and it was the one
    value explicitly excused."""
    said = python_code((ROOT / "ui" / "who.py").read_text(encoding="utf-8"))
    assert 'origin != "null"' not in said


# ============================================================ the rule, in one place


def test_the_three_helpers_exist_and_say_why() -> None:
    """`counting` for a number written twice, `importing` for a substring standing in for
    an import, `reading` for a comment satisfying a grep. Three shapes of the same
    mistake, and the rule is written where somebody adding a test will read it."""
    for name, rule in (
        ("counting", "derive"),
        ("importing", "Walk the tree, never the text"),
        ("reading", "asked of the code"),
    ):
        said = (ROOT / "tests" / f"{name}.py").read_text(encoding="utf-8")
        assert rule.lower() in said.lower(), name


def test_they_are_used_rather_than_merely_written() -> None:
    """A helper nobody calls is this build's most repeated defect wearing a test's
    clothes."""
    users = [
        path
        for path in (ROOT / "tests").rglob("test_*.py")
        if "tests.importing" in path.read_text(encoding="utf-8")
        or "tests.reading" in path.read_text(encoding="utf-8")
        or "tests.counting" in path.read_text(encoding="utf-8")
    ]
    assert len(users) >= 5, [p.name for p in users]
