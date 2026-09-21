"""Moving a body of Word content from one document into another.

**This is not a string operation, and treating it as one is the failure worth designing
against** - because it does not look like a failure. Copy the paragraphs out of one .docx
into another and the result opens without complaint, prints, and is laid out wrong.
Nobody notices until it has been sent.

Three things travel separately from the text and have to be brought with it:

* **Styles.** A paragraph carries a style *id*, not a style. If the destination has no
  style by that id, Word renders the paragraph as Normal - so a table of market indices
  arrives as body text. Any style the moved content names is copied into the destination
  when it is not already there, and a style that *is* already there is left alone, because
  the destination's own definition is the firm's formatting and this content is the guest.
* **Numbering.** A numbered list carries a `numId` that points into a completely different
  part of the file. Copied without it, the list either loses its numbers or - worse -
  silently joins a list that already exists in the destination and continues its
  numbering, so Appendix F's first point is item 7. Numbering definitions are copied and
  the ids **remapped**, because two documents' `numId`s mean different things.
* **Relationships.** An image, a chart, a hyperlink is a reference to another part by
  relationship id, and those ids are per-document. Copied without remapping, the image in
  Appendix E is whatever the destination's `rId7` happened to be, which is usually the
  firm's logo.

What cannot be carried is **named**, not dropped. An embedded object, a chart with a
spreadsheet behind it, a reference to something this code does not know how to bring -
each is reported by name and by where it was, so a person can put it in by hand. Silently
losing it is how a report goes out with a missing exhibit.
"""

from __future__ import annotations

import copy
import posixpath
import re
from dataclasses import dataclass, field
from io import BytesIO
from typing import Any

__all__ = ["Carried", "Transplant", "transplant"]

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"

BLOCKS = (f"{W}p", f"{W}tbl")

_CARRIED_RELATIONSHIPS = frozenset(
    {
        "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image",
        "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink",
    }
)
"""What this code knows how to bring. An image is a part to copy; a hyperlink is an
external address to re-register. Everything else - charts with workbooks behind them,
embedded objects, headers referenced from inside content - is reported rather than
guessed at, because a broken reference renders as an empty box that looks deliberate."""


@dataclass(frozen=True)
class Carried:
    """What a transplant did, and what it could not do."""

    blocks: int
    styles: tuple[str, ...] = ()
    """Style ids that had to be brought across. Empty means the destination already
    defined everything the content names, which is the usual case for two copies of the
    same template."""

    numbering: tuple[str, ...] = ()
    images: tuple[str, ...] = ()
    left_behind: tuple[str, ...] = ()
    """Named, not dropped. Each entry says what it was and where, so somebody can put it
    in by hand rather than discovering it is missing after the report has gone out."""

    @property
    def complete(self) -> bool:
        return not self.left_behind

    def summary(self) -> str:
        parts = [f"{self.blocks} block(s)"]
        for label, items in (
            ("style", self.styles),
            ("numbering", self.numbering),
            ("image", self.images),
        ):
            if items:
                parts.append(f"{len(items)} {label}{'s' if len(items) != 1 else ''}")
        if self.left_behind:
            parts.append(f"{len(self.left_behind)} NOT CARRIED")
        return ", ".join(parts)


@dataclass
class Transplant:
    """One move, from a source document into a destination.

    A class rather than a function because the remapping tables - which style ids have
    been copied, which numIds have become which - have to be shared across every block in
    the move. Two paragraphs in the same list must end up with the same new numId, and a
    function that rebuilt the table per paragraph would split one list into several.
    """

    source: Any
    destination: Any

    _styles: set[str] = field(default_factory=set)
    _numbering: dict[str, str] = field(default_factory=dict)
    _images: list[str] = field(default_factory=list)
    _left: list[str] = field(default_factory=list)

    def move(self, blocks: tuple[Any, ...], *, after: Any) -> Carried:
        """Copy `blocks` from the source into the destination, just after `after`.

        Inserted rather than appended: an appendix has a place, and the place is where the
        anchor was.
        """
        at = after
        moved = 0
        for block in blocks:
            if block.tag not in BLOCKS:
                continue
            fresh = copy.deepcopy(block)
            self._carry_styles(fresh)
            self._carry_numbering(fresh)
            self._carry_relationships(fresh)
            at.addnext(fresh)
            at = fresh
            moved += 1
        return Carried(
            blocks=moved,
            styles=tuple(sorted(self._styles)),
            numbering=tuple(sorted(self._numbering)),
            images=tuple(self._images),
            left_behind=tuple(self._left),
        )

    # ------------------------------------------------------------------ styles

    def _carry_styles(self, block: Any) -> None:
        """Bring any style the content names that the destination does not define.

        A style that *is* defined is left alone. The destination's definition is the firm's
        formatting, and the arriving content is the guest - overwriting Heading 2 with the
        source document's Heading 2 would reformat the whole report to match one appendix.
        """
        here = self.destination.styles.element
        defined = {
            s.get(f"{W}styleId") for s in here.findall(f"{W}style")
        }
        theirs = {
            s.get(f"{W}styleId"): s for s in self.source.styles.element.findall(f"{W}style")
        }
        for node in block.iter():
            if node.tag not in (f"{W}pStyle", f"{W}rStyle", f"{W}tblStyle"):
                continue
            style_id = node.get(f"{W}val")
            if not style_id or style_id in defined:
                continue
            definition = theirs.get(style_id)
            if definition is None:
                # The source names a style its own document does not define either. Word
                # falls back to Normal, and so does this - but it is said out loud.
                self._left.append(f"style {style_id!r}, which the source does not define")
                continue
            brought = copy.deepcopy(definition)
            here.append(brought)
            defined.add(style_id)
            self._styles.add(style_id)
            # A style based on another style needs that one too, or Word resolves the
            # inheritance to Normal and the result is subtly wrong rather than obviously.
            for parent in brought.findall(f"{W}basedOn"):
                self._carry_style_by_id(parent.get(f"{W}val"), here, defined, theirs)

    def _carry_style_by_id(
        self, style_id: str | None, here: Any, defined: set[str], theirs: dict[str, Any]
    ) -> None:
        if not style_id or style_id in defined:
            return
        definition = theirs.get(style_id)
        if definition is None:
            return
        here.append(copy.deepcopy(definition))
        defined.add(style_id)
        self._styles.add(style_id)

    # ------------------------------------------------------------------ numbering

    def _carry_numbering(self, block: Any) -> None:
        """Copy list definitions across, with new ids.

        Remapped rather than reused, because `numId` 3 means one thing in one document and
        something else in another. Left as it was, a list either loses its numbering or
        joins a list that already exists in the destination and continues *its* count - so
        the first bullet of Appendix F is item 7, which reads as a mistake somebody made.
        """
        wanted = [n for n in block.iter(f"{W}numId") if n.getparent().tag == f"{W}numPr"]
        if not wanted:
            return
        theirs = self._source_numbering()
        if theirs is None:
            for node in wanted:
                self._left.append("a numbered list; the source has no numbering definitions")
                node.getparent().remove(node)
            return
        mine = self._destination_numbering()
        if mine is None:
            for node in wanted:
                self._left.append(
                    "a numbered list; this report has no numbering part to add one to"
                )
                node.getparent().remove(node)
            return

        for node in wanted:
            old = node.get(f"{W}val")
            if old is None:
                continue
            if old not in self._numbering:
                fresh = self._copy_one_list(old, theirs, mine)
                if fresh is None:
                    self._left.append(f"a numbered list (numId {old}) the source does not define")
                    node.getparent().remove(node)
                    continue
                self._numbering[old] = fresh
            node.set(f"{W}val", self._numbering[old])

    def _copy_one_list(self, old: str, theirs: Any, mine: Any) -> str | None:
        num = next(
            (n for n in theirs.findall(f"{W}num") if n.get(f"{W}numId") == old), None
        )
        if num is None:
            return None
        abstract_ref = num.find(f"{W}abstractNumId")
        abstract_id = abstract_ref.get(f"{W}val") if abstract_ref is not None else None
        abstract = next(
            (
                a
                for a in theirs.findall(f"{W}abstractNum")
                if a.get(f"{W}abstractNumId") == abstract_id
            ),
            None,
        )
        if abstract is None:
            return None

        new_abstract = str(_next_id(mine, f"{W}abstractNum", f"{W}abstractNumId"))
        brought = copy.deepcopy(abstract)
        brought.set(f"{W}abstractNumId", new_abstract)
        # nsid ties an abstract list to a document; keeping the source's makes Word treat
        # two unrelated lists as the same one when the documents are later merged.
        for nsid in brought.findall(f"{W}nsid"):
            brought.remove(nsid)
        # w:abstractNum must precede w:num in the part, or Word rejects the document.
        first_num = mine.find(f"{W}num")
        if first_num is not None:
            first_num.addprevious(brought)
        else:
            mine.append(brought)

        new_num = str(_next_id(mine, f"{W}num", f"{W}numId"))
        instance = copy.deepcopy(num)
        instance.set(f"{W}numId", new_num)
        ref = instance.find(f"{W}abstractNumId")
        if ref is not None:
            ref.set(f"{W}val", new_abstract)
        mine.append(instance)
        return new_num

    def _source_numbering(self) -> Any | None:
        return _numbering_element(self.source)

    def _destination_numbering(self) -> Any | None:
        return _numbering_element(self.destination)

    # ------------------------------------------------------------------ relationships

    def _carry_relationships(self, block: Any) -> None:
        """Re-point every relationship id in the moved content at this document.

        An `r:embed` or `r:id` is a reference into *its own* document's relationship list.
        Left alone, the image in Appendix E becomes whatever the destination's rId7 is,
        which is usually the letterhead.
        """
        source_part = self.source.part
        destination_part = self.destination.part
        seen: dict[str, str] = {}

        for node in block.iter():
            for attribute, value in list(node.attrib.items()):
                if not attribute.startswith(R) or not str(value).startswith("rId"):
                    continue
                old = str(value)
                if old in seen:
                    node.set(attribute, seen[old])
                    continue
                fresh = self._bring_relationship(old, source_part, destination_part, node)
                if fresh is None:
                    node.getparent().remove(node)
                    break
                seen[old] = fresh
                node.set(attribute, fresh)

    def _bring_relationship(
        self, old: str, source_part: Any, destination_part: Any, node: Any
    ) -> str | None:
        related = source_part.rels.get(old)
        if related is None:
            self._left.append(f"a reference ({old}) the source document does not resolve")
            return None
        kind = str(related.reltype)
        if kind not in _CARRIED_RELATIONSHIPS:
            self._left.append(
                f"{_plain(kind)} at {_where(node)} - this moves text, styles, lists and "
                f"images; put this one in by hand"
            )
            return None
        if related.is_external:
            return str(destination_part.relate_to(related.target_ref, kind, is_external=True))

        # The image is re-created in the destination package rather than related to by
        # object, and that distinction is not a style choice. A part carries its own
        # partname - `/word/media/image1.png` - from the document it came from, and
        # relating it straight across puts a second part at a name the destination is
        # already using. The result is a .docx with a duplicate entry in its zip, which
        # is a corrupt file that python-docx writes with only a warning. Found by
        # updating two appendices from the same source, which is the ordinary case.
        #
        # `get_or_add_image` also dedupes by content hash, so the same chart appearing in
        # two appendices is stored once.
        image = related.target_part
        fresh_id, _ = destination_part.get_or_add_image(BytesIO(image.blob))
        self._images.append(posixpath.basename(str(image.partname)))
        return str(fresh_id)


def transplant(source: Any, destination: Any, blocks: tuple[Any, ...], *, after: Any) -> Carried:
    """One move. The usual entry point; `Transplant` is for a caller that wants the state."""
    return Transplant(source, destination).move(blocks, after=after)


def _numbering_element(document: Any) -> Any | None:
    try:
        return document.part.numbering_part.element
    except (KeyError, NotImplementedError, AttributeError):
        # A document that has never held a list has no numbering part at all.
        return None


def _next_id(numbering: Any, tag: str, attribute: str) -> int:
    used = [
        int(node.get(attribute) or 0)
        for node in numbering.findall(tag)
        if (node.get(attribute) or "").lstrip("-").isdigit()
    ]
    return max(used, default=0) + 1


def _plain(reltype: str) -> str:
    name = reltype.rsplit("/", 1)[-1]
    return re.sub(r"(?<!^)(?=[A-Z])", " ", name).lower()


def _where(node: Any) -> str:
    """Enough for a person to find it: the nearest text around the thing left behind."""
    holder = node
    for _ in range(6):
        if holder is None:
            break
        if holder.tag == f"{W}p":
            text = "".join(t.text or "" for t in holder.iter(f"{W}t")).strip()
            return f"{text[:60]!r}" if text else "a paragraph with no text"
        holder = holder.getparent()
    return "somewhere in the moved content"
