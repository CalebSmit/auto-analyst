"""The prose checks: the tells, the slips, and the two spellings of one thing.

Two halves, and the second is the one that took the work.

**Finding things** is easy, and the first half of this file is one test per check over
prose written to contain its defect.

**Not finding things** is the whole value. The first version of this module, pointed at
this project's own four longest documents, reported about a hundred and fifty findings, of
which almost none were about the writing: a fenced code block is full of doubled spaces,
`--json` is two hyphens, `tools/gate.py` is a full stop with no space after it, every
fiscal year is a four-digit number with no thousands separator, and `What` appears
capitalised in the middle of a wrapped line. Each reading was correct about the characters
and wrong about the document.

So the second half of this file holds that measurement as tests: a Markdown document built
out of exactly those constructs, which must produce **no slips at all**. One of them -
`serial_comma_both_ways` - could not be made precise and was taken out rather than
shipped, and there is a test here that it stays out.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from tools.prose_checks import (
    CHECKS,
    SLIP,
    apply_fixes,
    check,
    main,
    paragraphs_of,
    printable,
    read,
    strip_markup,
)
from tools.prose_checks import Paragraph as P

# A paragraph of prose with one of everything in it. Written rather than generated so that
# each defect can be pointed at: the test below names the check and the phrase.
SLOPPY = """# Valuation Summary

In today's business environment, it is important to note that the Company's performance
has been robust. Revenue grew while margins improved \u2014 a testament to execution.

We delve into the key drivers below. The forecast may potentially be affected by
concentration. The the analysis is robust, and the following applies .

Revenue of $1.2 million compares to $1,450,000 in the prior year. As of
December 31, 2025 the valuation date was set; the prior report used 12/31/2024.
Margins of 14 percent compare to 12%. The company retained 12500 units.
The Company is the subject of this report, and the Company is privately held.

Robust is a word this paragraph uses so that robust reaches three uses of robust.

The subject interest  was valued at fair market value( as defined herein
"""

# The same length of document with nothing wrong with it. Short declarative sentences of
# varying length, one date format, one money format, no register vocabulary.
CLEAN = """# Valuation Summary

The Company's revenue grew 12% in the year to December 31, 2025. Margins held.
Management attributes the increase to two new contracts signed in the first quarter,
neither of which carries a renewal option.

Working capital rose $1.2 million. That is most of the change in free cash flow.
The debt schedule is unchanged from the prior year.

We relied on the audited statements for the three years presented. Where the internal
statements disagreed with the audited ones, we used the audited figures and noted the
difference in the workpaper.
"""

# Every construct that made the first version of this module useless, and nothing else.
# A slip reported on any of these is a bug in the checks.
MARKDOWN_THAT_IS_NOT_PROSE = """# How to run it

The gate is in `tools/gate.py` and the state is in `BUILD/STATE.md`. Pass `--json` to
get the answer as data, or `--all` for everything.

```
python -m uv run python tools/gate.py status
python -m uv run python tools/gate.py close P07    --signoff "reviewed"
```

    docs/architecture.html      <- the source of truth
    tools/sync_blueprint.py     <- publishes a read-only mirror

| Port     | Today            | On Azure   |
|----------|------------------|------------|
| Storage  | watched folder   | Blob       |
| Delivery | output folder    | SharePoint |

Fiscal 2024 and fiscal 2025 are the years presented. See [the guide](docs/USING.md) or
https://example.invalid/some/long/path?a=1 for the rest.
"""


def _checks(text: str) -> dict[str, list[Any]]:
    reading = check(paragraphs_of(text))
    found: dict[str, list[Any]] = {}
    for finding in reading.findings:
        found.setdefault(finding.check, []).append(finding)
    return found


# ------------------------------------------------------------------- the tells, found


def test_an_em_dash_is_found_and_named() -> None:
    found = _checks(SLOPPY)["em_dash"]
    assert len(found) == 1
    assert found[0].says == "an em dash"
    assert found[0].suggestion
    assert "[em dash]" in found[0].excerpt, (
        "the excerpt names the mark, because an em dash and an en dash are a pixel "
        "apart and a cp1252 console prints either as a replacement character"
    )


def test_the_phrases_that_read_as_machine_written() -> None:
    said = {f.evidence["phrase"] for f in _checks(SLOPPY)["register_phrase"]}
    assert said >= {"in today's", "it is important to note that", "a testament to", "delve into"}


def test_a_register_word_is_reported_by_how_often_it_appears() -> None:
    """'robust' once is ordinary. Four times is the finding, and the finding is the
    count - which is why this is measured over the document and not spotted in a line."""
    (found,) = [f for f in _checks(SLOPPY)["register_word"] if f.evidence["word"] == "robust"]
    assert found.evidence["times"] >= 3
    assert found.where == "the document"

    assert "register_word" not in _checks("The analysis is robust.\n")


def test_two_hedges_in_one_sentence() -> None:
    (found,) = _checks(SLOPPY)["hedge_stack"]
    assert set(found.evidence["hedges"]) >= {"may", "potentially"}


def test_sentences_that_open_by_announcing_themselves() -> None:
    found = _checks("Overall, the margin held.\n\nIt should be noted that cash rose.\n")
    assert {f.evidence["opener"] for f in found["empty_opener"]} == {
        "overall,",
        "it should be noted",
    }


def test_the_not_only_but_also_construction() -> None:
    assert "not_only_but" in _checks("Revenue not only grew but also accelerated.\n")


def test_three_paragraphs_in_a_row_opening_with_the_same_word() -> None:
    text = "\n\n".join(
        [
            "Furthermore, the margin held.",
            "Furthermore, the backlog grew.",
            "Furthermore, the debt was repaid.",
        ]
    )
    (found,) = _checks(text)["paragraphs_open_alike"]
    assert found.evidence["word"] == "furthermore"
    assert found.evidence["paragraphs"] == [1, 2, 3]


def test_three_item_lists_at_a_density_no_writer_sustains() -> None:
    one = "Growth was driven by price, volume, and mix."
    text = "\n\n".join([one] * 5)
    (found,) = _checks(text)["rule_of_three"]
    assert found.evidence["with_a_triple"] == 5
    assert "rule_of_three" not in _checks(f"{one}\n\nMargins held. Cash rose. Debt fell.\n")


def test_sentences_that_are_all_the_same_length() -> None:
    """Human writing is bursty. Fourteen sentences of eight words each is not, and the
    coefficient of variation says so without anybody reading them."""
    flat = " ".join(["The margin held at twelve percent this year."] * 14)
    (found,) = _checks(flat)["sentences_all_one_length"]
    assert found.evidence["variation"] < 0.35
    assert "sentences_all_one_length" not in _checks(CLEAN)


def test_a_bolded_lead_in_and_a_colon() -> None:
    """Needs the run structure, so it is asserted on paragraphs built with it rather
    than on text - reading a .docx as text loses the bold and the check with it."""
    para = P(index=0, text="Revenue: grew twelve percent.", bold_opening="Revenue:")
    (found,) = [f for f in check([para]).findings if f.check == "bold_lead_in"]
    assert found.evidence["lead_in"] == "Revenue:"


# ------------------------------------------------------------------- the slips, found


def test_a_word_typed_twice() -> None:
    (found,) = _checks(SLOPPY)["repeated_word"]
    assert found.evidence["word"] == "The"
    assert found.safe_fix


def test_that_that_and_had_had_are_left_alone() -> None:
    """Ugly and grammatical. A check that fired on them would be wrong about English."""
    assert "repeated_word" not in _checks("The point that that sentence makes is fine.\n")
    assert "repeated_word" not in _checks("He had had enough of the audit.\n")


def test_a_space_before_punctuation() -> None:
    (found,) = _checks(SLOPPY)["space_before_punctuation"]
    assert found.evidence["mark"] == "."
    assert found.safe_fix


def test_two_spaces_between_words() -> None:
    (found,) = _checks(SLOPPY)["doubled_space"]
    assert found.safe_fix


def test_a_bracket_that_never_closes() -> None:
    (found,) = _checks(SLOPPY)["unclosed_bracket"]
    assert found.evidence["opener"] == "("
    assert not found.safe_fix, "where the bracket should close is not mechanical"


def test_a_paragraph_that_does_not_end_in_punctuation() -> None:
    (found,) = _checks(SLOPPY)["paragraph_without_a_stop"]
    assert found.evidence["last"] == "n"


def test_a_heading_and_a_list_item_are_allowed_to_have_no_full_stop() -> None:
    text = "# Valuation Summary\n\n- the first point\n- the second point\n"
    assert "paragraph_without_a_stop" not in _checks(text)


def test_a_comma_with_no_space_after_it() -> None:
    found = _checks("Revenue grew,margins held, and cash rose.\n")
    assert [f.evidence["mark"] for f in found["missing_space_after_punctuation"]] == [","]


def test_a_filename_a_path_and_an_abbreviation_are_not_missing_spaces() -> None:
    """The three things that made this check useless, each still in prose rather than in
    a code span - a document does not always remember the backticks."""
    text = (
        "Read BUILD/STATE.md first, then run tools/gate.py status. "
        "The engine, e.g. the one in deliver/qc.py, is unchanged.\n"
    )
    assert "missing_space_after_punctuation" not in _checks(text)


# --------------------------------------------------- the two spellings of one thing


def test_a_defined_term_written_both_ways() -> None:
    (found,) = _checks(SLOPPY)["term_both_ways"]
    assert found.evidence["term"] == "Company"
    assert found.evidence["lowercase"] >= 1


def test_an_ordinary_word_that_sometimes_starts_a_line_is_not_a_defined_term() -> None:
    """The second half of the calibration. `What` eight times against `what` fifty-six
    is not a term written inconsistently, and the capitalised form of a real defined term
    is the common one - so the rule is that the capital has to win."""
    text = (
        "What the statements show is one thing.\nWhat the model shows is another.\n"
        "That is what the reconciliation is for, and what it does not cover is noted.\n"
        "We asked what the difference was and what had changed.\n"
    )
    assert "term_both_ways" not in _checks(text)


def test_money_written_both_ways() -> None:
    assert "money_both_ways" in _checks(SLOPPY)


def test_percentages_written_both_ways() -> None:
    assert "percent_both_ways" in _checks(SLOPPY)


def test_more_than_one_date_format() -> None:
    (found,) = _checks(SLOPPY)["dates_both_ways"]
    assert set(found.evidence["formats"]) == {"December 31, 2025", "12/31/2025"}


def test_a_number_with_no_thousands_separator_beside_ones_that_have_them() -> None:
    (found,) = _checks(SLOPPY)["thousands_both_ways"]
    assert found.evidence["other"] >= 1


def test_a_fiscal_year_is_not_an_unformatted_number() -> None:
    """The single most useful line in the module. Without it every year in a valuation
    report reads as a figure somebody forgot to format, which is dozens of findings and
    no signal at all."""
    text = "Revenue of $1,450,000 in fiscal 2025 compares to fiscal 2024 and 1999.\n"
    assert "thousands_both_ways" not in _checks(text)


def test_curly_and_straight_quotation_marks_together() -> None:
    assert "quotes_both_ways" in _checks('He said \u201cyes\u201d and she said "no".\n')


# ------------------------------------------------------ and silence, where it is due


def test_a_well_written_paragraph_produces_nothing() -> None:
    reading = check(paragraphs_of(CLEAN))
    assert reading.findings == (), [str(f) for f in reading.findings]
    assert reading.clean


def test_markdown_that_is_not_prose_produces_no_slips() -> None:
    """The measurement, held as a test. A fenced block, an indented block, a table, two
    inline code spans, a CLI flag, two file paths, two fiscal years and a URL - and not
    one of them is a mistake in the writing."""
    reading = check(paragraphs_of(MARKDOWN_THAT_IS_NOT_PROSE))
    assert reading.of(SLIP) == (), [str(f) for f in reading.of(SLIP)]


def test_a_cli_flag_is_not_a_dash() -> None:
    assert "double_hyphen_as_dash" not in _checks("Pass --json to get it as data.\n")
    assert "double_hyphen_as_dash" in _checks("The margin--which held--was twelve.\n")


def test_the_serial_comma_check_stays_out() -> None:
    """It was written, measured and removed: over this project's own documents it
    reported 23 lists with the Oxford comma and 26 without, and nearly every match was a
    comma joining two clauses. This is the test that stops it coming back by accident
    without the parser it would need."""
    assert "serial_comma_both_ways" not in CHECKS
    text = "That is the design, and it holds. Price, volume and mix drove growth.\n"
    assert "serial_comma_both_ways" not in _checks(text)


def test_stripping_markup_leaves_a_marker_rather_than_a_hole() -> None:
    stripped = strip_markup("Run `tools/gate.py status` to see it.\n")
    assert "[code]" in stripped
    assert stripped.startswith("Run ") and stripped.rstrip().endswith("to see it.")


# -------------------------------------------------------------- what it says about itself


def test_every_finding_names_a_check_the_module_describes() -> None:
    for text in (SLOPPY, MARKDOWN_THAT_IS_NOT_PROSE, CLEAN):
        for finding in check(paragraphs_of(text)).findings:
            assert finding.check in CHECKS, finding.check
            kind, description = CHECKS[finding.check]
            assert finding.kind == kind
            assert description.strip()


def test_a_character_the_terminal_cannot_encode_does_not_crash_the_report() -> None:
    """A real document has an arrow, a non-breaking space or an accented name somewhere.
    Printing one used to raise UnicodeEncodeError out of main - a traceback instead of
    the report, from a tool whose job is reading documents other people wrote.

    Asserted against cp1252 rather than against whatever this machine's console happens
    to be, because the bug only exists on a console that cannot encode the character and
    a test that asked the machine would pass everywhere by not reproducing it.
    """
    with pytest.raises(UnicodeEncodeError):
        "an arrow \u2192 here".encode("cp1252")

    said = printable("an arrow \u2192 here", "cp1252")
    assert said.encode("cp1252"), "survives the encoding that used to raise"
    assert "arrow" in said and "here" in said, "and the rest of the line is still readable"
    assert "\u2192" not in said


def test_the_report_prints_on_a_console_that_cannot_encode_the_document(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The same thing through `main`, with stdout claiming cp1252 - which is what a
    Windows console claims, and what this crashed on the first time it was pointed at
    one of this project's own documents."""
    document = tmp_path / "notes.md"
    document.write_text(
        "The flow is intake \u2192 mask \u2192 model. The  the margin held.\n", encoding="utf-8"
    )

    class Cp1252Console:
        """A console that claims cp1252 and refuses what cp1252 cannot hold - which is
        what the real one does, and the only version of it that reproduces the bug."""

        encoding = "cp1252"

        def __init__(self) -> None:
            self.written: list[str] = []

        def write(self, text: str) -> int:
            text.encode("cp1252")  # raises exactly where the real console raised
            self.written.append(text)
            return len(text)

        def flush(self) -> None:
            pass

    console = Cp1252Console()
    monkeypatch.setattr("tools.prose_checks.sys.stdout", console)
    assert main([str(document)]) == 1
    assert "margin" in "".join(console.written)


def test_a_word_document_is_read_with_its_styles_its_tables_and_its_bold(
    tmp_path: Path,
) -> None:
    """End to end on the format that matters. A restricted-use report is a `.docx`, and
    three things about it have to survive the read or a check is wrong about it: the
    heading style, so a heading is allowed to have no full stop; the table cells, because
    a report's appendices are mostly tables; and the bolded opening, which only exists in
    the run structure and is lost by reading the file as text."""
    from docx import Document

    path = tmp_path / "report.docx"
    document = Document()
    document.add_heading("Valuation Summary", 1)
    document.add_paragraph("The Company's revenue grew twelve percent.")
    lead = document.add_paragraph()
    lead.add_run("Revenue:").bold = True
    lead.add_run(" grew twelve percent in the year.")
    table = document.add_table(rows=1, cols=2)
    table.cell(0, 0).text = "Index"
    table.cell(0, 1).text = "the the change"
    document.save(path)

    paragraphs, skipped = read(path)
    assert skipped == ()
    assert any(p.is_heading and p.text == "Valuation Summary" for p in paragraphs)
    assert any(p.bold_opening == "Revenue:" for p in paragraphs)
    assert any(p.style == "TableCell" and "change" in p.text for p in paragraphs)

    reading = check(paragraphs, skipped=skipped)
    kinds = {f.check for f in reading.findings}
    assert "bold_lead_in" in kinds, "the bolded lead-in survived the read"
    assert "repeated_word" in kinds, "and a slip inside a table cell was found"
    assert "paragraph_without_a_stop" not in kinds, "the heading was left alone"


def test_a_docx_that_does_not_open_is_reported_as_unread(tmp_path: Path) -> None:
    """Not as clean. A document nothing could read has nothing wrong with it only in the
    sense that nothing looked."""
    broken = tmp_path / "report.docx"
    broken.write_bytes(b"not a word document at all")
    paragraphs, skipped = read(broken)
    assert paragraphs == ()
    assert skipped and "Nothing was checked" in skipped[0]
    assert not check(paragraphs, skipped=skipped).findings
    assert check(paragraphs, skipped=skipped).skipped


# ------------------------------------------------------------------------- fixing


def test_the_four_mechanical_substitutions_and_nothing_else() -> None:
    before = "The  the margin held , and the the cash rose .  \nIt  improved \u2014 a lot.\n"
    after, made = apply_fixes(before, markup=False)
    # The doubled space between "The" and "the" is gone before the doubled-space pass
    # runs, because collapsing a word typed twice takes the space with it. So the one
    # counted here is the one in "It  improved", and the order of the passes is the
    # reason - worth knowing if a count ever looks one short.
    assert made == {
        "repeated_word": 2,
        "space_before_punctuation": 2,
        "doubled_space": 1,
        "trailing_space": 1,
    }
    assert "The margin held, and the cash rose." in after
    assert "\u2014" in after, "the em dash is a decision about the sentence, not a substitution"


def test_fixing_does_not_touch_code() -> None:
    """A tool that reformatted a command's aligned arguments while tidying the prose is a
    tool whose output has to be read line by line afterwards."""
    before = (
        "The  gate is here.\n\n```\npython tools/gate.py close P07    --signoff \"x\"\n```\n"
        "\n| a  | b   |\n|----|-----|\n| 1  | 2   |\n"
    )
    after, made = apply_fixes(before)
    assert made == {"doubled_space": 1}
    assert 'close P07    --signoff "x"' in after, "the fenced block is untouched"
    assert "| a  | b   |" in after, "the table is untouched"
    assert "The gate is here." in after


def test_fix_refuses_without_being_told_where_to_write(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    document = tmp_path / "notes.md"
    document.write_text("The  the margin held.\n", encoding="utf-8")
    assert main([str(document), "--fix"]) == 2
    assert "--out" in capsys.readouterr().err
    assert document.read_text(encoding="utf-8") == "The  the margin held.\n"


def test_fix_refuses_on_a_word_document(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A paragraph's text is split across runs that carry the formatting, and a
    substitution across a run boundary loses the formatting of everything after it."""
    from docx import Document

    path = tmp_path / "report.docx"
    document = Document()
    document.add_paragraph("The  the margin held.")
    document.save(path)

    assert main([str(path), "--fix", "--out", str(tmp_path / "out.docx")]) == 3
    assert "does not edit a Word document" in capsys.readouterr().err


def test_fix_writes_where_it_is_told_and_says_what_it_did(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    document = tmp_path / "notes.md"
    document.write_text("The  the margin held .\n", encoding="utf-8")
    out = tmp_path / "fixed.md"
    main([str(document), "--fix", "--out", str(out)])
    assert out.read_text(encoding="utf-8") == "The margin held.\n"
    assert document.read_text(encoding="utf-8") == "The  the margin held .\n", "untouched"
    said = capsys.readouterr().out
    assert "repeated_word" in said and "judgement about a sentence" in said


# ------------------------------------------------------------------- the command line


def test_the_command_line_exits_nonzero_on_a_slip_and_zero_on_clean_prose(
    tmp_path: Path,
) -> None:
    sloppy = tmp_path / "sloppy.md"
    sloppy.write_text(SLOPPY, encoding="utf-8")
    clean = tmp_path / "clean.md"
    clean.write_text(CLEAN, encoding="utf-8")

    assert main([str(sloppy)]) == 1
    assert main([str(clean)]) == 0
    assert main([str(tmp_path / "nothing.md")]) == 2


def test_the_command_line_can_hand_its_answer_to_something_else(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    document = tmp_path / "sloppy.md"
    document.write_text(SLOPPY, encoding="utf-8")
    main([str(document), "--json"])
    body = json.loads(capsys.readouterr().out)
    assert body["findings"] and body["paragraphs"] and body["sentences"]


def test_a_tell_alone_is_not_a_failing_exit(tmp_path: Path) -> None:
    """An em dash is a judgement call, and a non-zero exit from a tool somebody wires
    into a hook would stop their commit over one. A slip is mechanical and provable; that
    is the one that fails."""
    document = tmp_path / "dashed.md"
    document.write_text("The margin held \u2014 at twelve percent.\n", encoding="utf-8")
    assert main([str(document)]) == 0


def test_in_place_writes_over_the_document_and_leaves_its_code_alone(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The destructive flag, tested - which it was not when it was written.

    An untested `--in-place` is the worst kind of untested path: the one that replaces
    somebody's file. What it must do is make the four substitutions in the prose and
    leave the fenced block byte-identical, in the same file.
    """
    document = tmp_path / "notes.md"
    document.write_text(
        "The  the margin held .\n\n```\npython x.py  --flag\n```\n", encoding="utf-8"
    )
    assert main([str(document), "--fix", "--in-place"]) == 1

    after = document.read_text(encoding="utf-8")
    assert after.startswith("The margin held.\n")
    assert "python x.py  --flag" in after, "the fenced block is untouched"
    assert "notes.md" in capsys.readouterr().out, "and it says which file it wrote"


def test_out_and_in_place_together_are_refused(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """They say two different things about where to write, and one of them replaces the
    document. Picking for the person would be guessing which they meant."""
    document = tmp_path / "notes.md"
    document.write_text("The  the margin held.\n", encoding="utf-8")
    out = tmp_path / "copy.md"

    assert main([str(document), "--fix", "--out", str(out), "--in-place"]) == 2
    assert "two different things" in capsys.readouterr().err
    assert not out.exists()
    assert document.read_text(encoding="utf-8") == "The  the margin held.\n"


def test_fix_says_so_and_writes_nothing_when_there_is_nothing_mechanical_to_fix(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A document whose only findings are tells. `--fix` touches none of them, and the
    honest answer is that it wrote nothing rather than that it fixed it."""
    document = tmp_path / "notes.md"
    document.write_text("The margin held — at twelve percent.\n", encoding="utf-8")
    out = tmp_path / "fixed.md"

    assert main([str(document), "--fix", "--out", str(out)]) == 0
    assert "Nothing to fix mechanically" in capsys.readouterr().out
    assert not out.exists(), "and no file was written"
