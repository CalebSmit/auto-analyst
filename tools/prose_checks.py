"""Prose checks: the tells, the slips, and the two spellings of one thing.

The analyst asked for three reads of a deliverable before it goes out. This is two of
them, over the one thing a valuation engagement actually sends a client in words - a
restricted-use report, which is last year's document with this period's numbers and
paragraphs in it.

**The tells.** Writing that reads as machine-written. The em dash first, because it is the
one everybody has learned to spot, and then the register: the vocabulary, the three-item
rhythm, the bolded lead-in, the paragraph that opens by announcing it is about to say
something. A finding here is never "this is wrong"; it is "a reader will notice this", and
the suggested replacement is there because a person is going to want it rather than
because this module knows what the sentence should say.

**The slips.** The mechanical mistakes, which are provably mistakes: a word typed twice, a
space before a comma, a bracket that never closes, a number that runs into the next word.
These are the ones worth fixing mechanically and the only ones `--fix` will touch.

**The two spellings of one thing.** The third kind, and the one that is specific to this
work: a report that says *the Company* in one paragraph and *the company* in the next, or
$1.2 million on one page and $1,200,000 on the next, or December 31, 2025 beside
12/31/2025. Each is individually fine and the pair is the finding, which is why a
spellchecker has never caught one.

Three principles, and they are the same three the formula audit keeps:

* **It reports.** `--fix` exists and touches only the findings marked `safe_fix` - a
  repeated word, a space before punctuation, a doubled space, trailing whitespace. It
  will not rewrite a sentence, because deciding what a sentence should say is the
  analyst's work and the whole value of this tool is that it is not doing that.
* **It never writes over the original** unless told twice: `--fix` needs `--out` or
  `--in-place`.
* **It says what it could not read.** A `.docx` whose body this cannot parse is reported
  as unread, not as clean.

    python -m uv run python tools/prose_checks.py <report.docx>
    python -m uv run python tools/prose_checks.py <notes.md> --json
    python -m uv run python tools/prose_checks.py <notes.md> --fix --out fixed.md

Reads `.docx`, `.md`, `.txt` and anything else as text. Pure Python; no model is asked
anything, because "does this contain an em dash" is not a question that needs one.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:  # this is run as a script, from wherever somebody is standing
    sys.path.insert(0, str(ROOT))

from tools._environment import needs  # noqa: E402

TELL, SLIP, INCONSISTENT = "tell", "slip", "inconsistent"

__all__ = [
    "CHECKS",
    "Finding",
    "Paragraph",
    "Reading",
    "apply_fixes",
    "check",
    "printable",
    "paragraphs_of",
    "read",
    "report",
    "strip_markup",
]


# Every check, with its kind and what the finding means. One table: the CLI groups by it,
# a slash command reads it, and `tests/p126` asserts every finding names an entry - so a
# check added without a sentence explaining it fails rather than printing a bare id.
CHECKS: dict[str, tuple[str, str]] = {
    # ---------------------------------------------------------------------- the tells
    "em_dash": (
        TELL,
        "An em or en dash. The single most recognised mark of machine-written prose, "
        "and this firm's own house style uses a comma or a spaced hyphen.",
    ),
    "double_hyphen_as_dash": (
        TELL,
        "Two hyphens standing in for a dash. Typewriter punctuation in a typeset "
        "document, and a reader reads it as an em dash that did not get converted.",
    ),
    "register_word": (
        TELL,
        "A word that marks the register rather than carrying meaning. Reported by how "
        "often it appears, not on sight, because several are ordinary in one use and a "
        "tell in five.",
    ),
    "register_phrase": (
        TELL,
        "A phrase that reads as machine-written wherever it appears.",
    ),
    "empty_opener": (
        TELL,
        "A sentence that opens by announcing it is about to say something. Delete the "
        "opener and the sentence says the same thing in fewer words.",
    ),
    "not_only_but": (
        TELL,
        "The not-only-but-also construction. Say the second thing.",
    ),
    "hedge_stack": (
        TELL,
        "Two hedges in one sentence. One is a judgement; two is a sentence that has "
        "declined to make one, which in a valuation report is worse than either.",
    ),
    "rule_of_three": (
        TELL,
        "Three-item lists at a density no human writer sustains. The rhythm is the "
        "tell, not any one sentence.",
    ),
    "bold_lead_in": (
        TELL,
        "A paragraph that opens with a bolded phrase and a colon. Common in a chat "
        "answer, uncommon in a report, and instantly recognised.",
    ),
    "paragraphs_open_alike": (
        TELL,
        "Three or more paragraphs in a row opening with the same word.",
    ),
    "sentences_all_one_length": (
        TELL,
        "Sentence length barely varies across the document. Human writing is bursty - "
        "a long sentence, then a short one - and the absence of that is measurable.",
    ),
    # ---------------------------------------------------------------------- the slips
    "repeated_word": (
        SLIP,
        "The same word typed twice in a row.",
    ),
    "space_before_punctuation": (
        SLIP,
        "A space before a comma, full stop, semicolon or closing bracket.",
    ),
    "missing_space_after_punctuation": (
        SLIP,
        "A comma or full stop with no space after it, where what follows is a word "
        "rather than a digit - so decimals and dates are left alone.",
    ),
    "doubled_space": (
        SLIP,
        "Two spaces inside a sentence.",
    ),
    "trailing_space": (
        SLIP,
        "A paragraph ending in whitespace.",
    ),
    "unclosed_bracket": (
        SLIP,
        "A bracket or quotation mark opened in this paragraph and never closed.",
    ),
    "paragraph_without_a_stop": (
        SLIP,
        "A body paragraph that does not end in punctuation. Often a sentence that lost "
        "its tail in an edit.",
    ),
    # -------------------------------------------------------------- the two spellings
    "term_both_ways": (
        INCONSISTENT,
        "A defined term written capitalised in one place and lowercase in another. In a "
        "report where 'the Company' is a defined term, the lowercase one is a different "
        "claim.",
    ),
    "money_both_ways": (
        INCONSISTENT,
        "Amounts written both as words and as digits - $1.2 million beside $1,200,000.",
    ),
    "percent_both_ways": (
        INCONSISTENT,
        "Percentages written both with a sign and as a word.",
    ),
    "dates_both_ways": (
        INCONSISTENT,
        "More than one date format in one document.",
    ),
    # No `serial_comma_both_ways`. It was written, measured and taken out, and the
    # measurement is the reason: over this project's own four longest documents it
    # reported 23 lists with the Oxford comma and 26 without, and almost every match was
    # an ordinary compound sentence - "That is the design, and ..." is a comma before
    # "and" joining two clauses and has nothing to do with a list. Telling the two apart
    # needs to know where the clause boundaries are, which needs a parser rather than a
    # pattern. A check whose findings are mostly not findings is worse than no check,
    # because it teaches a reader to skip the section it is in. Recorded as B-086.
    "quotes_both_ways": (
        INCONSISTENT,
        "Curly and straight quotation marks in the same document.",
    ),
    "thousands_both_ways": (
        INCONSISTENT,
        "Four-digit-and-up numbers written both with and without a thousands separator.",
    ),
}

# Phrases that read as machine-written wherever they appear. Reported on sight.
#
# Kept deliberately short and deliberately specific. A long list catches a valuation
# report writing ordinary English - "comprehensive", "significant" and "key" are terms
# of art in this work - and a tool that fires on ordinary English is a tool nobody runs
# twice. Anything whose wrongness depends on how often it appears is in REGISTER_WORDS
# below and is measured rather than spotted.
REGISTER_PHRASES: tuple[str, ...] = (
    "a testament to",
    "at the end of the day",
    "delve into",
    "deep dive",
    "ever-evolving",
    "ever-changing landscape",
    "game changer",
    "in the ever",
    "in today's",
    "it is important to note that",
    "it is worth noting that",
    "let's dive in",
    "navigate the complexities",
    "navigating the complexities",
    "paradigm shift",
    "rich tapestry",
    "stands as a",
    "that being said",
    "the realm of",
    "unlock the potential",
    "when it comes to",
)

# Words whose single use is ordinary and whose fifth is a register. Reported when a word
# appears at least REGISTER_FLOOR times, because the finding is the density.
REGISTER_WORDS: tuple[str, ...] = (
    "crucial",
    "delve",
    "furthermore",
    "holistic",
    "leverage",
    "moreover",
    "myriad",
    "pivotal",
    "plethora",
    "robust",
    "seamless",
    "showcase",
    "synergy",
    "underscore",
    "underscores",
    "utilise",
    "utilize",
    "vital",
)
REGISTER_FLOOR = 3

# Sentence openers that spend a clause announcing a sentence.
EMPTY_OPENERS: tuple[str, ...] = (
    "it is important to",
    "it should be noted",
    "it is worth",
    "it bears mentioning",
    "needless to say",
    "in conclusion",
    "in summary",
    "overall,",
    "ultimately,",
    "importantly,",
    "notably,",
)

HEDGES: tuple[str, ...] = (
    "may",
    "might",
    "could",
    "possibly",
    "potentially",
    "perhaps",
    "arguably",
    "generally",
    "typically",
    "tends to",
    "somewhat",
    "relatively",
    "appears to",
    "seems to",
)

# Above this share of sentences carrying a three-item list, the rhythm is the finding.
RULE_OF_THREE_SHARE = 0.18
RULE_OF_THREE_FLOOR = 4

# Below this coefficient of variation in sentence length, over at least this many
# sentences, length is not varying. Human prose sits well above it; a document written in
# one pass by a model sits below.
BURSTINESS_FLOOR = 0.35
BURSTINESS_SENTENCES = 12


@dataclass(frozen=True)
class Paragraph:
    """One paragraph of a document, with the two things about it that matter here.

    `style` is the Word paragraph style name where there is one, so a heading can be told
    from body text - a heading legitimately has no full stop, and a check that could not
    tell them apart would fire on every heading in the document.

    `bold_opening` is whether the paragraph begins in bold, which needs the run structure
    and so cannot be recovered from the text. Reading a `.docx` as text loses it, which is
    why `read` goes through python-docx rather than through a zip and a regex.
    """

    index: int
    text: str
    style: str = ""
    bold_opening: str = ""

    @property
    def is_heading(self) -> bool:
        style = self.style.lower()
        return style.startswith("heading") or style in {"title", "subtitle", "caption"}


@dataclass(frozen=True)
class Finding:
    check: str
    kind: str
    where: str
    excerpt: str
    says: str
    suggestion: str = ""
    safe_fix: bool = False
    """Whether `apply_fixes` may make this change without a person looking at it. True
    only for a mechanical substitution with one possible answer."""
    evidence: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "check": self.check,
            "kind": self.kind,
            "where": self.where,
            "excerpt": self.excerpt,
            "says": self.says,
            "suggestion": self.suggestion,
            "safe_fix": self.safe_fix,
            "evidence": self.evidence,
        }

    def __str__(self) -> str:
        return f"{self.where}  {self.check}  {self.says}"


@dataclass(frozen=True)
class Reading:
    findings: tuple[Finding, ...]
    paragraphs: int
    words: int
    sentences: int
    skipped: tuple[str, ...] = ()

    def of(self, *kinds: str) -> tuple[Finding, ...]:
        return tuple(f for f in self.findings if f.kind in kinds)

    @property
    def clean(self) -> bool:
        return not self.findings

    def as_dict(self) -> dict[str, Any]:
        return {
            "paragraphs": self.paragraphs,
            "words": self.words,
            "sentences": self.sentences,
            "skipped": list(self.skipped),
            "findings": [f.as_dict() for f in self.findings],
        }


# ------------------------------------------------------------------- reading a document


def read(path: Path) -> tuple[tuple[Paragraph, ...], tuple[str, ...]]:
    """A document as paragraphs, and whatever could not be read.

    A `.docx` goes through python-docx so the paragraph style and the bold opening
    survive. Everything else is read as text, which is the right answer for Markdown and
    for a paste into a file.
    """
    if path.suffix.lower() in (".docx", ".dotx"):
        needs("docx", script="tools/prose_checks.py")
        try:
            return _read_docx(path.read_bytes()), ()
        except Exception as exc:  # noqa: BLE001 - "could not read it" is the finding
            return (), (
                f"{path.name} did not open as a Word document ({exc}). Nothing was "
                f"checked in it - which is not the same as nothing being wrong.",
            )
    text = path.read_text(encoding="utf-8", errors="replace")
    return paragraphs_of(text), ()


def _read_docx(data: bytes) -> tuple[Paragraph, ...]:
    from docx import Document  # noqa: PLC0415 - only when a .docx is actually given

    document = Document(BytesIO(data))
    out: list[Paragraph] = []
    for i, para in enumerate(document.paragraphs):
        # The bolded opening, if the paragraph has one: the leading runs that are bold,
        # stopping at the first run that carries text and is not. A run with no text in
        # it is skipped rather than ending the opening, because Word splits a paragraph
        # into runs wherever anything changes and an empty one means nothing.
        bold = ""
        for run in para.runs:
            if not run.text.strip():
                continue
            if not run.bold:
                break
            bold += run.text
        out.append(
            Paragraph(
                index=i,
                text=para.text,
                style=getattr(para.style, "name", "") or "",
                bold_opening=bold.strip(),
            )
        )
    # A table cell is prose too, and a report's appendices are mostly tables. Read after
    # the body so the indices of the body paragraphs are the ones Word would count.
    for table in document.tables:
        for row in table.rows:
            for cell in row.cells:
                for para in cell.paragraphs:
                    if para.text.strip():
                        out.append(
                            Paragraph(index=len(out), text=para.text, style="TableCell")
                        )
    return tuple(out)


CODE = "[code]"

# Suffixes read as markup: code spans and fences in them are not prose and are not
# edited. Anything else is read exactly as it is written.
MARKUP = (".md", ".markdown", ".mdx", ".rst", ".txt")

FENCE = re.compile(r"^[ \t]*(```|~~~).*?^[ \t]*\1[^\n]*$", re.M | re.S)
INLINE_CODE = re.compile(r"`[^`\n]+`")
MD_LINK = re.compile(r"\[([^\]\n]*)\]\([^)\n]*\)")
BARE_URL = re.compile(r"\b(?:https?://|www\.)\S+")
TABLE_ROW = re.compile(r"^[ \t]*\|.*\|[ \t]*$", re.M)

# An indented code block: a run of lines each starting with four spaces or a tab, after a
# blank line. Markdown's older way of writing one, and this project's documents use it -
# `CLAUDE.md` shows the two blueprint paths that way, with the arrows aligned by hand, and
# every one of those alignments reads as a doubled space in prose.
INDENTED_CODE = re.compile(r"(?:^(?:[ ]{4,}|\t)[^\n]*\n?)+", re.M)

# Every pattern whose match is not prose, in the order they have to be taken out. The
# fence first: a fenced block can contain anything, including a table row and a backtick,
# and taking the inner patterns out first would cut the fence in half.
NOT_PROSE = (FENCE, INDENTED_CODE, TABLE_ROW, INLINE_CODE, BARE_URL)

# A dot that is part of a filename rather than the end of a sentence. The extensions this
# project's own documents are full of, plus the abbreviations every report has in it.
EXTENSIONS = (
    "cmd", "csv", "css", "docx", "env", "html", "js", "json", "lock", "md", "pdf",
    "pptx", "py", "sh", "toml", "txt", "xlsx", "xml", "yaml", "yml", "zip",
)
ABBREVIATIONS = ("e.g", "i.e", "etc", "vs", "inc", "co", "ltd", "llc", "no", "al")


def strip_markup(text: str) -> str:
    """Markdown with the parts that are not prose taken out.

    Written because the first run of this tool over this project's own documents reported
    a hundred and fifty findings and almost none of them were about the writing. A fenced
    code block is full of doubled spaces; `--json` is two hyphens; `tools/gate.py` is a
    full stop with no space after it; a table row never ends in a sentence. Each of those
    is a correct reading of the characters and a wrong reading of the document.

    Code is replaced by a marker rather than deleted, so an excerpt quoting the sentence
    around it still reads as a sentence and nobody is left wondering what was there.
    """
    for pattern in NOT_PROSE:
        text = pattern.sub(CODE, text)
    return MD_LINK.sub(r"\1", text)


def paragraphs_of(text: str, *, markup: bool = True) -> tuple[Paragraph, ...]:
    """Plain text or Markdown as paragraphs, blank-line separated.

    A Markdown heading carries its own style so the no-full-stop check leaves it alone,
    the same way a Word heading style does. `markup=False` reads the text exactly as
    given, for a document that is not Markdown and where a backtick is a backtick.
    """
    if markup:
        text = strip_markup(text)
    out: list[Paragraph] = []
    for block in re.split(r"\n\s*\n", text):
        body = block.strip("\n")
        if not body.strip():
            continue
        style = "Heading" if body.lstrip().startswith("#") else ""
        if re.match(r"^\s*([-*+>]|\d+[.)])\s", body):
            style = "ListParagraph"
        if body.strip() == CODE or body.strip().startswith(CODE):
            style = "Code"
        out.append(Paragraph(index=len(out), text=body, style=style))
    return tuple(out)


# ------------------------------------------------------------------------- the checks

SENTENCE_END = re.compile(r"(?<=[.!?])[\s\u00a0]+(?=[A-Z\u201c\"(])")
WORD = re.compile(r"[A-Za-z][A-Za-z'\u2019-]*")

# `X, Y, and Z` or `X, Y, or Z` - the three-item list. One pattern, named, because it is
# counted in one place and the matching sentence is quoted in another, and two copies of
# a regular expression is how a count and its example come to be about different things.
TRIPLE = re.compile(r"\w,\s[^,]{2,40},\s(and|or)\s")

# A number with four or more digits and no separator - `12500` where the document
# elsewhere writes `12,500`.
#
# The negative lookahead for `19xx`/`20xx` is the whole usefulness of this check. Without
# it every fiscal year in the report reads as an unformatted figure, which on a valuation
# report is dozens of findings and no signal at all. The cost is a real figure that
# happens to look like a year - revenue of exactly 2,025 - and that trade is the right way
# round: a false negative on one ambiguous token beats a false positive on every year.
UNSEPARATED = re.compile(r"(?<![\d,.$/-])(?!(?:19|20)\d{2}(?!\d))(\d{4,})(?![\d,.%/-])")
SEPARATED = re.compile(r"\b\d{1,3}(?:,\d{3})+\b")

MONEY_WORDS = re.compile(r"\$\s?\d[\d.,]*\s*(million|billion|thousand|m\b|bn\b)", re.I)
MONEY_DIGITS = re.compile(r"\$\s?\d{1,3}(?:,\d{3}){2,}(?:\.\d+)?")

DATE_LONG = re.compile(
    r"\b(January|February|March|April|May|June|July|August|September|October|"
    r"November|December)\s+\d{1,2},\s+\d{4}\b"
)
DATE_SLASH = re.compile(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b")
DATE_DAY_FIRST = re.compile(
    r"\b\d{1,2}\s+(January|February|March|April|May|June|July|August|September|"
    r"October|November|December)\s+\d{4}\b"
)
DATE_ISO = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")

OPENERS = {"(": ")", "[": "]", "{": "}", "\u201c": "\u201d"}


def check(paragraphs: Sequence[Paragraph], *, skipped: Sequence[str] = ()) -> Reading:
    """Every check, over a document already read into paragraphs."""
    findings: list[Finding] = []
    sentences: list[str] = []
    words = 0

    for para in paragraphs:
        para_sentences = _sentences(para.text)
        sentences.extend(para_sentences)
        words += len(WORD.findall(para.text))
        findings.extend(_per_paragraph(para, para_sentences))

    findings.extend(_across_the_document(paragraphs, sentences))

    return Reading(
        findings=tuple(_ordered(findings)),
        paragraphs=len(paragraphs),
        words=words,
        sentences=len(sentences),
        skipped=tuple(skipped),
    )


def _sentences(text: str) -> list[str]:
    body = text.strip()
    if not body:
        return []
    return [s.strip() for s in SENTENCE_END.split(body) if s.strip()]


def _per_paragraph(para: Paragraph, sentences: Sequence[str]) -> Iterator[Finding]:
    text = para.text
    where = f"paragraph {para.index + 1}"
    if para.style == "Code":
        return  # a code block is not prose and every check here would be wrong about it

    for match in re.finditer(r"[\u2014\u2013]", text):
        yield Finding(
            check="em_dash",
            kind=TELL,
            where=where,
            excerpt=_around(text, match.start()),
            says=f"an {'em' if match.group() == chr(0x2014) else 'en'} dash",
            suggestion="a comma, a colon, or a spaced hyphen",
            evidence={"offset": match.start()},
        )

    # A dash, not a flag. `--json` is two hyphens at the start of a word and every
    # command in this project's documents has one; requiring a word character, then
    # whitespace or nothing, then the hyphens, keeps the check off them.
    for match in re.finditer(r"(?<=\w)(?: --(?= )|--(?=\w))", text):
        yield Finding(
            check="double_hyphen_as_dash",
            kind=TELL,
            where=where,
            excerpt=_around(text, match.start()),
            says="two hyphens standing in for a dash",
            suggestion=" - ",
            evidence={"offset": match.start()},
        )

    lowered = text.lower()
    for phrase in REGISTER_PHRASES:
        start = lowered.find(phrase)
        if start >= 0:
            yield Finding(
                check="register_phrase",
                kind=TELL,
                where=where,
                excerpt=_around(text, start),
                says=f"{phrase!r} reads as machine-written",
                evidence={"phrase": phrase},
            )

    for sentence in sentences:
        low = sentence.lower()
        for opener in EMPTY_OPENERS:
            if low.startswith(opener):
                yield Finding(
                    check="empty_opener",
                    kind=TELL,
                    where=where,
                    excerpt=_line(sentence, 120),
                    says=f"opens with {opener!r}",
                    suggestion="delete the opener; the sentence says the same thing",
                    evidence={"opener": opener},
                )
                break
        if "not only" in low and ("but also" in low or "but " in low):
            yield Finding(
                check="not_only_but",
                kind=TELL,
                where=where,
                excerpt=_line(sentence, 160),
                says="the not-only-but-also construction",
                evidence={},
            )
        stacked = [h for h in HEDGES if re.search(rf"\b{re.escape(h)}\b", low)]
        if len(stacked) >= 2:
            yield Finding(
                check="hedge_stack",
                kind=TELL,
                where=where,
                excerpt=_line(sentence, 160),
                says=f"{len(stacked)} hedges in one sentence: {', '.join(stacked)}",
                evidence={"hedges": stacked},
            )

    if para.bold_opening and text.strip().startswith(para.bold_opening):
        rest = text.strip()[len(para.bold_opening) :].lstrip()
        if rest.startswith(":") or para.bold_opening.rstrip().endswith(":"):
            yield Finding(
                check="bold_lead_in",
                kind=TELL,
                where=where,
                excerpt=_line(para.bold_opening, 80),
                says="a bolded lead-in and a colon",
                evidence={"lead_in": para.bold_opening},
            )

    # ------------------------------------------------------------------- the slips

    for match in re.finditer(r"\b(\w+)\s+\1\b", text, re.I):
        word = match.group(1)
        if word.lower() in {"that", "had", "no"}:
            continue  # "that that" and "had had" are grammatical, if ugly
        yield Finding(
            check="repeated_word",
            kind=SLIP,
            where=where,
            excerpt=_around(text, match.start()),
            says=f"{word!r} twice in a row",
            suggestion=word,
            safe_fix=True,
            evidence={"word": word, "offset": match.start()},
        )

    for match in re.finditer(r"\s+([,.;:!?)\]])", text):
        yield Finding(
            check="space_before_punctuation",
            kind=SLIP,
            where=where,
            excerpt=_around(text, match.start()),
            says=f"a space before {match.group(1)!r}",
            suggestion=match.group(1),
            safe_fix=True,
            evidence={"mark": match.group(1), "offset": match.start()},
        )

    for match in re.finditer(r"(?<=[a-z])([,.;])(?=[A-Za-z]{2})", text):
        if _is_a_filename_or_an_abbreviation(text, match):
            continue
        yield Finding(
            check="missing_space_after_punctuation",
            kind=SLIP,
            where=where,
            excerpt=_around(text, match.start()),
            says=f"no space after {match.group(1)!r}",
            suggestion=f"{match.group(1)} ",
            safe_fix=True,
            evidence={"mark": match.group(1), "offset": match.start()},
        )

    for match in re.finditer(r"(?<=\S)  +(?=\S)", text):
        yield Finding(
            check="doubled_space",
            kind=SLIP,
            where=where,
            excerpt=_around(text, match.start()),
            says=f"{len(match.group())} spaces between words",
            suggestion=" ",
            safe_fix=True,
            evidence={"offset": match.start()},
        )

    if text and text != text.rstrip():
        yield Finding(
            check="trailing_space",
            kind=SLIP,
            where=where,
            excerpt=_line(text.rstrip()[-60:]),
            says="the paragraph ends in whitespace",
            suggestion="",
            safe_fix=True,
            evidence={},
        )

    for opener, closer in OPENERS.items():
        opened, closed = text.count(opener), text.count(closer)
        if opened != closed:
            yield Finding(
                check="unclosed_bracket",
                kind=SLIP,
                where=where,
                excerpt=_line(text, 120),
                says=(
                    f"{opened} {opener!r} and {closed} {closer!r} in this paragraph"
                ),
                evidence={"opener": opener, "opened": opened, "closed": closed},
            )
    if text.count('"') % 2:
        yield Finding(
            check="unclosed_bracket",
            kind=SLIP,
            where=where,
            excerpt=_line(text, 120),
            says=f"an odd number of straight quotation marks ({text.count(chr(34))})",
            evidence={"opener": '"', "opened": text.count('"'), "closed": 0},
        )

    body = text.rstrip()
    if (
        body
        and not para.is_heading
        and para.style not in {"ListParagraph", "TableCell", "Code"}
        and body[-1] not in ".!?:;\u201d\")]*`_"
        and not body.endswith(CODE)
        and len(WORD.findall(body)) >= 4
    ):
        yield Finding(
            check="paragraph_without_a_stop",
            kind=SLIP,
            where=where,
            excerpt=_line(body[-80:]),
            says=f"ends in {body[-1]!r}",
            evidence={"last": body[-1]},
        )


def _across_the_document(
    paragraphs: Sequence[Paragraph], sentences: Sequence[str]
) -> Iterator[Finding]:
    """The findings that are about the document rather than about a paragraph.

    Every one of these is a pair, a ratio or a density - the things a reader notices and
    no single-paragraph check can see. The two spellings of one thing live here because
    the finding *is* that both spellings are present.
    """
    body = "\n".join(p.text for p in paragraphs)
    lowered = body.lower()

    counts = Counter(w.lower() for w in WORD.findall(body))
    for word in REGISTER_WORDS:
        n = counts[word]
        if n >= REGISTER_FLOOR:
            yield Finding(
                check="register_word",
                kind=TELL,
                where="the document",
                excerpt=_first_use(paragraphs, word),
                says=f"{word!r} {n} times",
                evidence={"word": word, "times": n},
            )

    triples = [s for s in sentences if TRIPLE.search(s)]
    if sentences and len(triples) >= RULE_OF_THREE_FLOOR:
        share = len(triples) / len(sentences)
        threes = len(triples)
        if share >= RULE_OF_THREE_SHARE:
            yield Finding(
                check="rule_of_three",
                kind=TELL,
                where="the document",
                excerpt=_line(triples[0], 140),
                says=(
                    f"{threes} of {len(sentences)} sentences carry a three-item list "
                    f"({share:.0%})"
                ),
                evidence={"sentences": len(sentences), "with_a_triple": threes},
            )

    lengths = [len(WORD.findall(s)) for s in sentences if WORD.findall(s)]
    if len(lengths) >= BURSTINESS_SENTENCES:
        mean = sum(lengths) / len(lengths)
        spread = (sum((n - mean) ** 2 for n in lengths) / len(lengths)) ** 0.5
        variation = spread / mean if mean else 0.0
        if variation < BURSTINESS_FLOOR:
            yield Finding(
                check="sentences_all_one_length",
                kind=TELL,
                where="the document",
                excerpt="",
                says=(
                    f"{len(lengths)} sentences averaging {mean:.0f} words with a spread "
                    f"of {spread:.1f} - a variation of {variation:.2f}, where human "
                    f"prose sits above {BURSTINESS_FLOOR}"
                ),
                evidence={"mean": round(mean, 1), "stdev": round(spread, 2),
                          "variation": round(variation, 3)},
            )

    openings = [
        (p.index, WORD.findall(p.text)[0].lower())
        for p in paragraphs
        if WORD.findall(p.text) and not p.is_heading
    ]
    run: list[tuple[int, str]] = []
    for item in [*openings, (-1, "")]:
        if run and item[1] == run[-1][1]:
            run.append(item)
            continue
        if len(run) >= 3:
            yield Finding(
                check="paragraphs_open_alike",
                kind=TELL,
                where=f"paragraphs {run[0][0] + 1}-{run[-1][0] + 1}",
                excerpt=run[0][1],
                says=f"{len(run)} paragraphs in a row open with {run[0][1]!r}",
                evidence={"word": run[0][1], "paragraphs": [i + 1 for i, _ in run]},
            )
        run = [item]

    # ------------------------------------------------------- the two spellings of one thing

    yield from _both_ways(
        "money_both_ways",
        body,
        MONEY_WORDS,
        MONEY_DIGITS,
        "amounts in words ({a}) and in full digits ({b})",
    )
    yield from _both_ways(
        "percent_both_ways",
        body,
        re.compile(r"\d\s?%"),
        re.compile(r"\d\s+per\s?cent", re.I),
        "percentages with a sign ({a}) and spelled out ({b})",
    )
    yield from _both_ways(
        "thousands_both_ways",
        body,
        SEPARATED,
        UNSEPARATED,
        "numbers with a thousands separator ({a}) and without ({b})",
    )

    formats = {
        "December 31, 2025": len(DATE_LONG.findall(body)),
        "31 December 2025": len(DATE_DAY_FIRST.findall(body)),
        "12/31/2025": len(DATE_SLASH.findall(body)),
        "2025-12-31": len(DATE_ISO.findall(body)),
    }
    present = {k: v for k, v in formats.items() if v}
    if len(present) > 1:
        yield Finding(
            check="dates_both_ways",
            kind=INCONSISTENT,
            where="the document",
            excerpt="",
            says=", ".join(f"{k} x{v}" for k, v in present.items()),
            evidence={"formats": present},
        )

    curly = sum(body.count(c) for c in "\u201c\u201d\u2018\u2019")
    straight = body.count('"') + body.count("'")
    if curly and straight:
        yield Finding(
            check="quotes_both_ways",
            kind=INCONSISTENT,
            where="the document",
            excerpt="",
            says=f"{curly} curly and {straight} straight quotation mark(s)",
            evidence={"curly": curly, "straight": straight},
        )

    yield from _terms_both_ways(paragraphs, lowered)


def _both_ways(
    name: str,
    body: str,
    one: re.Pattern[str],
    other: re.Pattern[str],
    says: str,
) -> Iterator[Finding]:
    a, b = len(one.findall(body)), len(other.findall(body))
    if a and b:
        yield Finding(
            check=name,
            kind=INCONSISTENT,
            where="the document",
            excerpt="",
            says=says.format(a=a, b=b),
            evidence={"one": a, "other": b},
        )


def _terms_both_ways(paragraphs: Sequence[Paragraph], lowered: str) -> Iterator[Finding]:
    """Defined terms written both ways.

    Two rules, and both were put in after measuring, because the first version of this
    check reported fourteen findings on a document with nothing wrong with it:

    1. **Not the first word on a line.** A capitalised word mid-*sentence* is the signal,
       and a sentence splitter working on prose that is hard-wrapped at eighty columns
       sees the start of every line as the middle of a sentence. So `What`, `Every`,
       `That` and `Where` were all reported as defined terms.
    2. **The capitalised form has to be at least as common as the lowercase one.** That is
       what a defined term looks like: a report that defines *the Company* writes
       `Company` almost every time and `company` by accident. `What` eight times against
       `what` fifty-six is not a defined term written inconsistently; it is an ordinary
       word that sometimes starts a sentence.

    Together they take a document that is fine from fourteen findings to none, and leave
    `Company`/`company` - which is the one this exists for.
    """
    del lowered
    body = "\n".join(p.text for p in paragraphs)
    openers = {
        match.group()
        for line in body.splitlines()
        for match in [WORD.match(line.lstrip())]
        if match
    }

    capitalised: Counter[str] = Counter()
    for sentence in (s for p in paragraphs for s in _sentences(p.text)):
        for match in WORD.finditer(sentence):
            if match.start() == 0:
                continue
            word = match.group()
            if word in openers:
                continue
            if word[0].isupper() and word[1:].islower() and len(word) > 3:
                capitalised[word] += 1

    for word, times in capitalised.items():
        if times < 2:
            continue
        lower = word.lower()
        plain = len(re.findall(rf"(?<![.!?]\s)(?<!^)\b{re.escape(lower)}\b", body))
        if plain and times >= plain:
            yield Finding(
                check="term_both_ways",
                kind=INCONSISTENT,
                where="the document",
                excerpt=word,
                says=f"{word!r} {times} times and {lower!r} {plain} time(s)",
                evidence={"term": word, "capitalised": times, "lowercase": plain},
            )


def _is_a_filename_or_an_abbreviation(text: str, match: re.Match[str]) -> bool:
    """Whether a full stop with no space after it is one of the things that is fine.

    Three of them, and all three are everywhere in this work: a filename
    (`gate.py`, `STATE.md`), a path, and an abbreviation (`e.g.`, `Inc.`). Reporting
    those was most of what this check did on its first run, and a check whose findings
    are mostly not findings is one nobody reads to the end of.
    """
    if match.group(1) != ".":
        return False
    tail = text[match.end() :]
    extension = re.match(r"[A-Za-z0-9]+", tail)
    if extension and extension.group().lower() in EXTENSIONS:
        return True
    start = text.rfind(" ", 0, match.start()) + 1
    token = text[start : match.start()]
    if token.lower() in ABBREVIATIONS:
        return True
    return "/" in token or "\\" in token


def _first_use(paragraphs: Sequence[Paragraph], word: str) -> str:
    for para in paragraphs:
        match = re.search(rf"\b{re.escape(word)}\b", para.text, re.I)
        if match:
            return _around(para.text, match.start())
    return ""


#   What a mark is called, for an excerpt somebody reads in a terminal.
#
#   An em dash and an en dash are a pixel apart on a good day and identical in most
#   monospace fonts, and a Windows console encoded cp1252 prints either as a replacement
#   character - so the finding that says "an em dash" would quote an excerpt in which the
#   em dash is invisible or wrong. Naming it in the excerpt is both more legible and the
#   only version that survives the terminal it is read in.
NAMED_MARKS = {
    "\u2014": "[em dash]",
    "\u2013": "[en dash]",
    "\u201c": '"',
    "\u201d": '"',
    "\u2018": "'",
    "\u2019": "'",
    "\u00a0": " ",
}


def _line(text: str, limit: int = 120) -> str:
    """A fragment on one line, with the marks a terminal cannot show named.

    The same treatment `_around` gives an excerpt it cuts out of the middle, for the
    findings whose excerpt is the whole of something.
    """
    body = re.sub(r"\s+", " ", text).strip()
    for mark, name in NAMED_MARKS.items():
        body = body.replace(mark, name)
    return body[:limit] + ("..." if len(body) > limit else "")


def _around(text: str, offset: int, span: int = 38) -> str:
    """An excerpt a person can read on one line.

    Newlines are collapsed because a paragraph in a `.md` file is wrapped and an excerpt
    that kept its line breaks reads as two findings when it is one.
    """
    start, end = max(0, offset - span), min(len(text), offset + span)
    body = re.sub(r"\s+", " ", text[start:end]).strip()
    for mark, name in NAMED_MARKS.items():
        body = body.replace(mark, name)
    return ("..." if start else "") + body + ("..." if end < len(text) else "")


def _ordered(findings: Iterable[Finding]) -> list[Finding]:
    rank = {SLIP: 0, INCONSISTENT: 1, TELL: 2}
    seen: set[tuple[str, str, str]] = set()
    unique: list[Finding] = []
    for f in findings:
        key = (f.check, f.where, f.excerpt)
        if key in seen:
            continue
        seen.add(key)
        unique.append(f)
    return sorted(unique, key=lambda f: (rank.get(f.kind, 9), f.check, f.where))


# ---------------------------------------------------------------------------- fixing


def apply_fixes(text: str, *, markup: bool = True) -> tuple[str, dict[str, int]]:
    """Make the substitutions that have one possible answer, and say what was made.

    Four of them, and the shortness of the list is the point. Each is a mechanical
    substitution: a word typed twice becomes the word; a space before a comma goes; two
    spaces become one; trailing whitespace goes. The em dash is **not** here - replacing
    it with a comma, a colon or a pair of brackets is a decision about the sentence, and
    a tool that made that decision silently across a report would have rewritten the
    report.

    **Code is not touched.** `markup=True` protects every span `strip_markup` would have
    taken out - fenced and indented blocks, inline spans, table rows, URLs - and fixes
    only what lies between them. Without that, "two spaces become one" would reformat a
    command's aligned arguments and a table's columns, in a file this tool was pointed at
    to tidy the writing in. A tool that edits a code block while fixing prose is a tool
    that has to be checked line by line afterwards, which is the opposite of the point.
    """
    counts: Counter[str] = Counter()

    def fix_one(piece: str) -> str:
        def sub(pattern: str, repl: str, name: str, flags: int = 0) -> None:
            nonlocal piece
            piece, n = re.subn(pattern, repl, piece, flags=flags)
            if n:
                counts[name] += n

        sub(r"\b(?!(?:that|had|no)\b)(\w+)\s+\1\b", r"\1", "repeated_word", re.I)
        sub(r"[ \t]+([,.;:!?)\]])", r"\1", "space_before_punctuation")
        sub(r"(?<=\S)[ \t]{2,}(?=\S)", " ", "doubled_space")
        sub(r"[ \t]+$", "", "trailing_space", re.M)
        return piece

    if not markup:
        return fix_one(text), dict(counts)

    out: list[str] = []
    for piece, is_prose in _split_out_code(text):
        out.append(fix_one(piece) if is_prose else piece)
    return "".join(out), dict(counts)


def _split_out_code(text: str) -> list[tuple[str, bool]]:
    """The text as alternating pieces, each flagged prose or not.

    Spans are found with the same patterns `strip_markup` uses, so what `--fix` leaves
    alone and what the checks ignore cannot drift apart. Overlaps are resolved by taking
    the earliest span and then the earliest that starts after it ends, which is what
    "the fence wins over what is inside it" means in practice.
    """
    spans: list[tuple[int, int]] = []
    for pattern in NOT_PROSE:
        spans.extend((m.start(), m.end()) for m in pattern.finditer(text))
    spans.sort()

    pieces: list[tuple[str, bool]] = []
    at = 0
    for start, end in spans:
        if start < at:
            continue  # inside a span already taken, such as a backtick inside a fence
        if start > at:
            pieces.append((text[at:start], True))
        pieces.append((text[start:end], False))
        at = end
    if at < len(text):
        pieces.append((text[at:], True))
    return pieces


# ------------------------------------------------------------------------------- CLI


def printable(text: str, encoding: str | None = None) -> str:
    """The report, reduced to what the terminal it is going to can encode.

    A Windows console is cp1252 and a real document has an arrow, a non-breaking space or
    an accented name in it somewhere. Printing one raised `UnicodeEncodeError` out of
    `main` - a traceback instead of the report, from a tool whose entire job is to read
    documents other people wrote. The findings keep full fidelity; only the print is
    reduced, and `--json` is already escaped by `json.dumps`.

    `encoding` is an argument so the behaviour can be asserted against the encoding the
    bug needs rather than against whatever the machine running the test happens to have.
    Under pytest that is UTF-8, which encodes everything - so a test that asked the
    machine would have passed everywhere by never reproducing the failure.
    """
    encoding = encoding or getattr(sys.stdout, "encoding", None) or "utf-8"
    return text.encode(encoding, errors="backslashreplace").decode(encoding, errors="replace")


def report(reading: Reading, *, as_json: bool) -> str:
    if as_json:
        return json.dumps(reading.as_dict(), indent=2, default=str)
    lines = [
        f"  {reading.paragraphs} paragraph(s), {reading.sentences} sentence(s), "
        f"{reading.words} word(s)"
    ]
    if not reading.findings:
        lines.append("\n  Nothing found.")
    for kind, heading in (
        (SLIP, "Slips - mechanical, and provably mistakes"),
        (INCONSISTENT, "Two spellings of one thing"),
        (TELL, "Tells - a reader will notice these"),
    ):
        group = reading.of(kind)
        if not group:
            continue
        lines.append(f"\n  {heading}  ({len(group)})")
        for f in group:
            lines.append(f"    {f.where}: {f.says}")
            if f.excerpt:
                lines.append(f"        {f.excerpt}")
            if f.suggestion:
                lines.append(f"        -> {f.suggestion!r}")
    if reading.skipped:
        lines.append("\n  Did not read")
        for note in reading.skipped:
            lines.append(f"    - {note}")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="prose_checks.py",
        description="Find the tells, the slips and the two spellings of one thing.",
    )
    parser.add_argument("document", type=Path)
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument(
        "--fix",
        action="store_true",
        help="make the mechanical substitutions. Needs --out or --in-place, and does "
        "not touch anything that is a judgement about a sentence.",
    )
    parser.add_argument("--out", type=Path, help="where --fix writes")
    parser.add_argument(
        "--in-place",
        action="store_true",
        help="let --fix write over the document. Said separately on purpose.",
    )
    args = parser.parse_args(argv)

    if not args.document.is_file():
        print(f"  no such document: {args.document}", file=sys.stderr)
        return 2

    paragraphs, skipped = read(args.document)
    reading = check(paragraphs, skipped=skipped)
    print(printable(report(reading, as_json=args.as_json)))

    if args.fix:
        code = _fix(args)
        if code:
            return code
    return 1 if reading.of(SLIP) else 0


def _fix(args: argparse.Namespace) -> int:
    """The write half of `--fix`, and every refusal it makes."""
    if args.document.suffix.lower() in (".docx", ".dotx"):
        print(
            "\n  --fix does not edit a Word document. A paragraph's text is split "
            "across runs that carry the formatting, and a substitution across a run "
            "boundary silently loses the formatting of everything after it. The "
            "findings above name the paragraph and quote the text; make the change in "
            "Word, where you can see what it did.",
            file=sys.stderr,
        )
        return 3
    if args.out and args.in_place:
        print(
            "\n  --out and --in-place say two different things about where to write. "
            "Pick one: --out writes a copy, --in-place writes over the document. "
            "Choosing for you would mean guessing which of the two you meant, over a "
            "file one of them replaces.",
            file=sys.stderr,
        )
        return 2
    if not args.out and not args.in_place:
        print(
            "\n  --fix needs somewhere to write: --out <path>, or --in-place to write "
            "over the document. Said separately because overwriting somebody's report "
            "is not a default.",
            file=sys.stderr,
        )
        return 2

    original = args.document.read_text(encoding="utf-8")
    fixed, made = apply_fixes(original, markup=args.document.suffix.lower() in MARKUP)
    target = args.out or args.document
    if fixed == original:
        print(f"\n  Nothing to fix mechanically; {target} not written.")
        return 0
    target.write_text(fixed, encoding="utf-8", newline="")
    print("\n  Fixed, into " + str(target))
    for name, n in sorted(made.items()):
        print(f"    {name}: {n}")
    print("  Everything else is above and is a judgement about a sentence.")
    return 0


if __name__ == "__main__":  # pragma: no cover - the CLI's own line
    raise SystemExit(main())

