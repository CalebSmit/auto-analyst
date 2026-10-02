"""C71 - the three reads, and the one front door, agreeing with each other.

P125, P126, P127 and P128 each pass alone. Each of those suites asks whether one module
does what it says. What none of them can see is the thing a block of work is checkpointed
for: whether four pieces built over two days still say the same thing as each other.

Three properties, and each one is a way the four could have drifted apart without any of
their own tests noticing.

**One artifact, one answer.** A delivered workbook is audited in three places - the
release gate records it, the console route re-derives it, and `aa review` prints it. Three
surfaces reading the same bytes must produce the same findings. The console and the
command line could each have grown their own call into the engine with a different flag,
and the only symptom would be a reviewer told two different things about one file.

**No check has a default, anywhere.** Materiality belongs to the practice; there are nine
decisions in `BUILD/OPEN.md` that belong to people and one of them is the auto-accept bar.
Each of the three reads was written to have no default tolerance, and the way that rule
erodes is one module quietly acquiring a sensible-looking number. So: run all three with
nothing given, and assert that each reports what it did not ask rather than a verdict.

**Nothing concludes.** The blueprint's invariant, over the combined output of all three
reads on one engagement's artifacts rather than over any one module's. The dangerous
version is not a module saying "approved"; it is two modules whose words add up to it.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

import pytest

from deliver.audit import as_event_payload, audit_workbook
from tests.workbooks import a_model, a_tidy_model, with_cached_values
from tools import aa, formula_audit, prose_checks, reasonableness

ROOT = Path(__file__).resolve().parents[3]

A_TABLE = {
    "lines": [
        {
            "category": "revenue",
            "amounts": {"2023-12-31": 1_000_000, "2024-12-31": 1_100_000},
            "locator": "IS!B5",
        },
        {
            "category": "depreciation",
            "amounts": {"2023-12-31": 30_000, "2024-12-31": 31_000},
            "locator": "IS!B18",
        },
        {
            "category": "accounts_receivable",
            "amounts": {"2023-12-31": 110_000, "2024-12-31": 260_000},
            "locator": "BS!B6",
        },
    ]
}

A_REPORT = (
    "# Valuation Summary\n\n"
    "In today's business environment the Company's margin held — a testament to "
    "execution. The  the schedule is unchanged.\n"
)


@pytest.fixture
def an_engagements_artifacts(tmp_path: Path) -> Path:
    """One of each thing that leaves this system, in one folder."""
    (tmp_path / "Input help.xlsx").write_bytes(a_model())
    (tmp_path / "Draft report.md").write_text(A_REPORT, encoding="utf-8")
    (tmp_path / "Normalized.json").write_text(json.dumps(A_TABLE), encoding="utf-8")
    return tmp_path


# ------------------------------------------------------- one artifact, one answer


def test_the_three_surfaces_audit_a_workbook_identically(tmp_path: Path) -> None:
    """The release gate, the console route and the command line over one file.

    Asserted on the findings rather than on the rendered text, because the three render
    differently on purpose - an event payload, a JSON body and a report somebody reads -
    and what must not differ is what they found.
    """
    data = with_cached_values(a_model(), {"IS": {"C9": 999.0}})
    path = tmp_path / "Input help.xlsx"
    path.write_bytes(data)

    # What the release gate puts on the record.
    recorded = as_event_payload("Input help.xlsx", audit_workbook(data))
    # What the console route returns.
    through_the_console = audit_workbook(data).as_dict()
    # What the command line prints, read back as data.
    (through_the_command,) = aa.review(path)

    def keyed(findings: list[dict[str, Any]]) -> set[tuple[str, str, str]]:
        return {(f["check"], f["sheet"], f["cell"]) for f in findings}

    from_console = keyed(through_the_console["findings"])
    from_command = keyed(through_the_command.body["findings"])
    assert from_console == from_command, "the console and the command line disagree"

    # The event carries only what is worth seeing, capped - so it is a subset, and every
    # member of it has to be one of the findings the other two hold.
    assert keyed(recorded["findings"]) <= from_console
    assert recorded["counts"]["wrong"] == len(
        [f for f in through_the_console["findings"] if f["severity"] == "wrong"]
    )
    assert recorded["formulas"] == through_the_console["formulas"]


def test_the_release_record_and_a_later_audit_agree_on_what_could_not_be_evaluated(
    tmp_path: Path,
) -> None:
    """The one place the three are *allowed* to differ, and it has to be the honest one.

    A workbook this build generated has no saved values, so the footing check cannot run
    and both the record and the command line say so. Open it in Excel and save, and the
    check becomes possible - which is why the console re-derives rather than reading the
    event back, and why both must report the gap in the same words while it exists.
    """
    fresh = a_tidy_model()
    saved = with_cached_values(fresh, {"IS": {"C9": 188.0}})

    before = as_event_payload("x.xlsx", audit_workbook(fresh))
    after = as_event_payload("x.xlsx", audit_workbook(saved))

    assert any("could not run on 3" in note for note in before["did_not_run"])
    assert any("ran on 1 total(s) and could not run on 2" in n for n in after["did_not_run"])
    assert before["counts"] == after["counts"], "and neither invents a finding"


def test_the_dispatcher_sends_every_suffix_to_a_read_that_handles_it(
    an_engagements_artifacts: Path,
) -> None:
    """The join P128 makes over the three P125-P127 built. A suffix the dispatcher claims
    and no module reads is a file silently reported as clean."""
    results = {r.read: r for r in aa.review(an_engagements_artifacts, move={"points": 5.0})}
    assert set(results) == {"formulas", "prose", "questions"}
    assert all(r.worst for r in results.values()), "each found what its own suite says it finds"

    for suffix in aa.WORKBOOKS:
        assert aa.which_read(Path("x" + suffix)) == "formulas"
    for suffix in aa.DOCUMENTS:
        assert aa.which_read(Path("x" + suffix)) == "prose"
    for suffix in aa.TABLES:
        assert aa.which_read(Path("x" + suffix)) == "questions"


# --------------------------------------------------- no check has a default, anywhere


def test_asked_with_nothing_each_read_says_what_it_did_not_ask() -> None:
    """Run all three with no tolerance at all.

    The formula audit needs none - every one of its checks is arithmetic. The prose checks
    need none for the same reason. The questions need one per unit and have none, and the
    way that rule erodes is one of them quietly acquiring a sensible-looking number, so
    this is the test that notices.
    """
    from registries.taxonomy import load_taxonomy

    taxonomy = load_taxonomy("coa-taxonomy@1.0.0")
    lines = reasonableness.lines_from(A_TABLE)
    findings = reasonableness.run_questions(lines, taxonomy)

    unasked = [f for f in findings if f["result"] == "could_not_evaluate"]
    assert unasked, "a ratio with no tolerance is reported, not left out"
    assert any("nobody has said how far this may move" in f["evidence"] for f in unasked)
    assert any("nobody has said how many years" in f["evidence"] for f in unasked)
    assert all(f["threshold"] is None for f in unasked)

    # And a zero is refused rather than treated as "report everything".
    with pytest.raises(ValueError, match="no default and no zero"):
        reasonableness.ratios(lines, {"points": 0.0}, taxonomy)


def test_no_read_module_carries_a_materiality_number_as_a_default() -> None:
    """Read out of the source, because the rule is about what a future edit may add.

    Every keyword argument that names a tolerance, a threshold or a materiality across
    the three modules must default to `None` or be required. The two numeric constants
    that do exist are allowed by name and each says in its own comment why it is not a
    materiality decision: floating-point slack in a footing comparison, and a
    boundary epsilon.
    """
    allowed = {"FOOTING_TOLERANCE", "AT_THE_BOUNDARY"}
    offenders: list[str] = []
    for module in (formula_audit, prose_checks, reasonableness):
        path = Path(module.__file__ or "")
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            args = node.args
            pairs = list(
                zip(
                    [a.arg for a in args.kwonlyargs],
                    args.kw_defaults,
                    strict=True,
                )
            ) + list(
                zip(
                    [a.arg for a in args.args][len(args.args) - len(args.defaults) :],
                    args.defaults,
                    strict=True,
                )
            )
            for name, default in pairs:
                if not any(w in name for w in ("toleran", "threshold", "material", "move")):
                    continue
                if default is None:
                    continue  # required, which is the point
                if isinstance(default, ast.Constant) and default.value is None:
                    continue
                if isinstance(default, ast.Name) and default.id in allowed:
                    continue
                offenders.append(f"{path.name}:{node.name}({name}=...)")
    assert not offenders, (
        f"{offenders} default a tolerance. Materiality belongs to the practice "
        f"(BUILD/OPEN.md section 2); a default here is this build setting one."
    )


# ------------------------------------------------------------------ nothing concludes


def test_nothing_the_three_reads_say_together_concludes_anything(
    an_engagements_artifacts: Path,
) -> None:
    """Over the combined output, not over any one module's.

    The dangerous version of this failure is not one module saying "approved". It is two
    modules whose words add up to it when a person reads them one after the other, which
    is exactly how a reviewer reads the output of `aa review`.
    """
    said = " ".join(
        r.text for r in aa.review(an_engagements_artifacts, move={"points": 5.0, "days": 10.0})
    ).lower()
    assert said.strip()
    for phrase in (
        "approved",
        "we conclude",
        "the valuation is",
        "fair market value of",
        "is reasonable",
        "looks correct",
        "no issues",
        "certif",
        "sign-off",
        "signed off",
    ):
        assert phrase not in said, f"the three reads together say {phrase!r}"


def test_the_only_verdict_any_of_them_reaches_is_about_a_file_disagreeing_with_itself(
    an_engagements_artifacts: Path,
) -> None:
    """What the three *are* allowed to assert, stated as a test so the line is visible.

    `wrong` and `slip` are claims about an artifact, provable from the artifact. `fail`
    from the questions is not a claim at all - it is a question, and the report says so
    in words at the foot of itself.
    """
    results = {r.read: r for r in aa.review(an_engagements_artifacts, move={"points": 5.0})}
    assert results["formulas"].worst == "wrong"
    assert results["prose"].worst == "slip"
    assert results["questions"].worst == "fail"
    assert "a question, not a verdict" in results["questions"].text
    assert "never edits" not in results["formulas"].text.lower(), "the report is findings"


# --------------------------------------------------- and the boundary they were built behind


def test_the_record_the_console_and_the_command_reach_the_engine_through_one_module() -> None:
    """P128 moved the console's call behind `deliver/audit.py` because `ops/` may not bind
    a tool implementation. A checkpoint is where that would quietly come undone: the next
    person needing the audit in a surface will import `tools.formula_audit` because it
    works, and `tests/p10` will catch it - unless somebody adds `ops` to its allowlist.
    """
    scanned = {
        "ops/console/app.py": "deliver.audit",
        "deliver/release.py": "deliver.audit",
    }
    for relative, expected in scanned.items():
        tree = ast.parse((ROOT / relative).read_text(encoding="utf-8"))
        modules = {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        }
        assert expected in modules, f"{relative} no longer reaches the audit through {expected}"
        assert not any(
            m.startswith("tools.formula_audit") for m in modules
        ), f"{relative} binds the engine directly"

    # And the module in the middle reaches the engine and nothing from `ops`.
    tree = ast.parse((ROOT / "deliver" / "audit.py").read_text(encoding="utf-8"))
    modules = {
        node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module
    }
    assert any(m.startswith("tools.formula_audit") for m in modules)
    assert not any(m == "ops" or m.startswith("ops.") for m in modules), (
        "deliver/audit.py importing ops would put a cycle under the console's import"
    )
