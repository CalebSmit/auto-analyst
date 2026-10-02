"""Setting up a report: one appendix at a time, and never in place.

The button. He points it at the Word document an appendix's data arrives in, presses it
when that data is ready, and one appendix changes.

Three decisions worth defending, because each of them is a way this could have gone
wrong quietly:

**One appendix, not the report.** Each appendix's source becomes ready at its own moment -
the industry data before the economic commentary, or the other way round. A single "update
the report" action would mean waiting for the slowest one, or running it repeatedly and
hoping the earlier appendices are put back the same way. So the unit of action is the
appendix, and an update that touched a second one would be a bug rather than a
convenience.

**It shows the change before it makes it.** `preview()` does everything `update()` does
except the write, and reports the same result. That matters because the thing being edited
is a report somebody is about to send, and "let me see what that does first" is the normal
way to work with one.

**It never edits the file it read.** The input is last year's report - often the only copy
of last year's work - and an in-place edit is unrecoverable the moment it is wrong. So a
new file is written and the original is left exactly as it was, byte for byte.

**And it cannot reach Appendix H.** Only appendices marked `updated` are reachable through
this module, and the certification is not one. There is no path here that writes it: it
arrives in the copy of last year's report like the rest of the boilerplate. *Nothing
concludes, signs or certifies* is true because no code exists to do it, not because a
check refuses.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from registries.errors import (
    PATH_UNREADABLE,
    UNKNOWN_CRITERIA,
    DiagnosticError,
    RegistryError,
    diagnose,
)
from report.anchors import find_anchor, normalise, span_of
from report.appendices import APPENDICES, Appendix, appendix, updatable
from report.transplant import Carried, Transplant

__all__ = ["Change", "preview", "set_up", "update"]


@dataclass(frozen=True)
class Change:
    """What an update did, or would do."""

    appendix_id: str
    letter: str
    anchor: str
    replaced_blocks: int
    """How much of the report this really takes out - the content under the appendix's
    heading, not counting the heading, which stays.

    Shown because an appendix that takes forty blocks out when it should take three means
    the anchor is bound to the wrong place, and that is visible here before it is visible
    in Word. It counts what was removed rather than what the anchor owns, because a number
    that was one larger than the truth would be worse than no number."""

    carried: Carried | None = None
    written_to: str = ""
    dry_run: bool = False
    source: str = ""

    prose: dict[str, Any] = field(default_factory=dict)
    """What `tools/prose_checks.py` found in the content arriving, in its own shape.

    Read here rather than left to somebody remembering to look, because this is the moment
    the prose moves and the analyst is standing in front of it. Appendix commentary is
    where a draft written with a model actually enters a report, and an em dash in it is
    the thing a reader notices.

    **It never stops the update.** Whether a sentence should say something else is the
    analyst's judgement; the findings sit beside the change so they are in front of them
    while the preview still is. Empty when the source could not be read as a document,
    with the reason inside - never empty because nothing was looked for."""

    @property
    def complete(self) -> bool:
        return self.carried is not None and self.carried.complete

    @property
    def slips(self) -> int:
        """Mechanical mistakes in the arriving content: a word typed twice, a space before
        a comma, a bracket that never closes. Separated from the tells because these are
        provably mistakes and a tell is a judgement."""
        return sum(1 for f in self.prose.get("findings", []) if f.get("kind") == "slip")

    def as_dict(self) -> dict[str, Any]:
        return {
            "appendix": self.appendix_id,
            "letter": self.letter,
            "anchor": self.anchor,
            "source": self.source,
            "replaced_blocks": self.replaced_blocks,
            "arriving_blocks": self.carried.blocks if self.carried else 0,
            "styles": list(self.carried.styles) if self.carried else [],
            "numbering": list(self.carried.numbering) if self.carried else [],
            "images": list(self.carried.images) if self.carried else [],
            "left_behind": list(self.carried.left_behind) if self.carried else [],
            "complete": self.complete,
            "dry_run": self.dry_run,
            "written_to": self.written_to,
            "prose": dict(self.prose),
        }

    def summary(self) -> str:
        head = (
            f"Appendix {self.letter}: {self.replaced_blocks} block(s) out, "
            f"{self.carried.summary() if self.carried else 'nothing'} in"
        )
        if found := self.prose.get("findings"):
            head += (
                f"; {len(found)} thing(s) to look at in the words arriving"
                + (f", {self.slips} of them mechanical" if self.slips else "")
            )
        if self.dry_run:
            return f"{head}  (nothing written)"
        return f"{head} -> {self.written_to}"


def set_up(last_year: Path | str, into: Path | str) -> Path:
    """Start this period's report as a copy of last year's.

    The whole of "setting up a report" begins here, and it is a file copy on purpose:
    everything that carries forward - the boilerplate, Appendix G, the certification,
    the qualifications - carries forward by being copied rather than by being regenerated.
    Nothing is regenerated that nobody asked to change.
    """
    source = Path(last_year)
    if not source.is_file():
        raise RegistryError(
            diagnose(
                PATH_UNREADABLE,
                f"there is no report at {source}. Setting up this period's report starts "
                f"from last year's file; point at the one to copy.",
                locator=str(source),
            )
        )
    target = Path(into)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    return target


def preview(
    report: Path | str,
    appendix_id: str,
    source: Path | str,
    *,
    registry: tuple[Appendix, ...] = APPENDICES,
) -> Change:
    """What pressing the button would do. Writes nothing."""
    return _run(report, appendix_id, source, into=None, registry=registry)


def update(
    report: Path | str,
    appendix_id: str,
    source: Path | str,
    *,
    into: Path | str | None = None,
    registry: tuple[Appendix, ...] = APPENDICES,
) -> Change:
    """Replace one appendix, and write the result to a new file.

    `into` defaults to a name beside the report carrying the appendix and the time, so
    pressing the button twice leaves two files rather than one overwritten one. The report
    that was read is never touched.
    """
    target = Path(into) if into else _beside(Path(report), appendix_id)
    return _run(report, appendix_id, source, into=target, registry=registry)


def _run(
    report: Path | str,
    appendix_id: str,
    source: Path | str,
    *,
    into: Path | None,
    registry: tuple[Appendix, ...],
) -> Change:
    from docx import Document  # noqa: PLC0415 - a heavy import, paid only when used

    entry = appendix(appendix_id, registry)
    if not entry.updated:
        # The line, held in the one place a caller could cross it. G, H and I arrive in
        # the copy of last year's report; there is no content for this to put anywhere.
        raise RegistryError(
            diagnose(
                UNKNOWN_CRITERIA,
                f"appendix {entry.letter} ({entry.title}) is not updated by this tool. It "
                f"carries forward in the copy of last year's report. The ones with an "
                f"update are {', '.join(a.id for a in updatable(registry))}.",
                locator=f"report/appendix/{entry.id}",
            )
        )

    into_report = Path(report)
    from_source = Path(source)
    for path, what in ((into_report, "report"), (from_source, "source document")):
        if not path.is_file():
            raise RegistryError(
                diagnose(
                    PATH_UNREADABLE,
                    f"there is no {what} at {path}.",
                    locator=str(path),
                )
            )

    document = Document(str(into_report))
    incoming = Document(str(from_source))
    prose = _read_the_words_arriving(from_source)

    anchor = find_anchor(document, entry.anchor)
    owned = span_of(document, anchor)

    blocks = _without_a_repeated_heading(incoming, entry.anchor)
    carried = Transplant(incoming, document).move(blocks, after=anchor.element)

    # Taken out after the new content is in, so the anchor is still there to insert
    # against - and so a transplant that refused leaves the report untouched rather than
    # emptied.
    #
    # **The anchor's own block stays.** `owned[0]` is the heading the appendix binds to,
    # and it carries the report's heading style and - when somebody has marked one - the
    # bookmark. Removing it worked once and made the appendix unreachable for ever after:
    # the second press could not find the anchor, because the first press had deleted it.
    # C55 found that, which is what a checkpoint is for. What gets replaced is the
    # *content under* the heading.
    removed = 0
    for block in owned[1:]:
        parent = block.getparent()
        if parent is not None:
            parent.remove(block)
            removed += 1

    if into is None:
        return Change(
            entry.id,
            entry.letter,
            entry.anchor,
            removed,
            carried,
            dry_run=True,
            source=str(from_source),
            prose=prose,
        )

    into.parent.mkdir(parents=True, exist_ok=True)
    document.save(str(into))
    return Change(
        entry.id,
        entry.letter,
        entry.anchor,
        removed,
        carried,
        written_to=str(into),
        source=str(from_source),
        prose=prose,
    )


def _read_the_words_arriving(source: Path) -> dict[str, Any]:
    """The prose checks over the document whose content is about to move.

    The whole source rather than only the blocks being moved, and the difference is at
    most a repeated heading - so the simpler reading is the honest one and it is what a
    person would check anyway.

    **It cannot stop an update.** A source this could not read is reported as unread
    inside the result, with the reason, rather than as a document with nothing wrong with
    it - and the appendix still moves, because whether the words are right is a separate
    question from whether the content got there.
    """
    from tools.prose_checks import check, read  # noqa: PLC0415 - only when a report moves

    try:
        paragraphs, skipped = read(source)
        return check(paragraphs, skipped=skipped).as_dict()
    except Exception as exc:  # noqa: BLE001 - a reading that failed is a reading that failed
        return {
            "findings": [],
            "skipped": [
                f"{source.name} could not be read for the prose checks ({exc}). The "
                f"appendix still moved; nothing was looked at in the words."
            ],
        }


def _without_a_repeated_heading(incoming: Any, anchor: str) -> tuple[Any, ...]:
    """The source's blocks, minus a leading heading that just repeats the anchor.

    The report keeps its own heading, so a source document that also starts with
    "Appendix C - Economic Conditions" would produce two. Some appendix documents carry
    their title and some do not, and neither is wrong - so the one case that would look
    like a mistake is handled rather than legislated about.
    """
    blocks = [b for b in incoming.element.body.iterchildren() if isinstance(b.tag, str)]
    if blocks:
        first = blocks[0]
        text = "".join(
            node.text or ""
            for node in first.iter(
                "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t"
            )
        )
        if text.strip() and normalise(text) == normalise(anchor):
            blocks = blocks[1:]
    return tuple(blocks)


def _beside(report: Path, appendix_id: str) -> Path:
    """A name that is not already taken.

    The timestamp alone was not enough: two presses inside the same second produced the
    same name and the second silently replaced the first, which is the exact thing writing
    a new file was supposed to avoid. Somebody pressing twice is comparing the two.
    """
    when = datetime.now(tz=UTC).strftime("%Y%m%d-%H%M%S")
    candidate = report.with_name(f"{report.stem}.{appendix_id}-{when}{report.suffix}")
    n = 2
    while candidate.exists():
        candidate = report.with_name(
            f"{report.stem}.{appendix_id}-{when}-{n}{report.suffix}"
        )
        n += 1
    return candidate


def what_would_change(
    report: Path | str, registry: tuple[Appendix, ...] = APPENDICES
) -> list[dict[str, Any]]:
    """For the page: each updatable appendix, and whether its anchor is even there.

    Asked before anything is pressed, because an anchor that does not resolve is worth
    knowing about while there is still time to bookmark it - not at the moment somebody
    is trying to get a report out.
    """
    from docx import Document  # noqa: PLC0415

    document = Document(str(report))
    rows: list[dict[str, Any]] = []
    for entry in updatable(registry):
        row: dict[str, Any] = {
            "appendix": entry.id,
            "letter": entry.letter,
            "title": entry.title,
            "anchor": entry.anchor,
            "note": entry.note,
        }
        try:
            found = find_anchor(document, entry.anchor)
        except DiagnosticError as refused:
            row.update(found=False, detail=refused.diagnostic.detail)
        else:
            row.update(found=True, kind=found.kind, owns=len(span_of(document, found)))
        rows.append(row)
    return rows
