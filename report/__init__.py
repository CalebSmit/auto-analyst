"""The report: last year's document, with this period's appendices put into it.

Setting up a report is not writing one. The analyst described it exactly: *"copying and
pasting the report from last year, then only setting it up. Meaning getting the right
appendix information in."* So this package does two things and refuses a third:

* it finds the **place** an appendix belongs, by name;
* it **moves** a body of Word content into that place, with the things that make Word
  content render carried along with it;
* it does not write, conclude, or sign anything. Appendix H is the certification, and it
  is not touched at all - it arrives in the copy of last year's report, which means there
  is no code here that could produce the conclusion it attests to. The non-negotiable is
  satisfied by construction rather than by a check, which is the stronger of the two.

**Binding is by name.** The model's rule is *bind by named range, never by cell address*,
and `B44` is not a contract. The Word equivalent is a bookmark or a heading, never a
paragraph index - a report somebody added a sentence to would otherwise get Appendix F
written into Appendix E, and it would look fine.

**The move is not a string operation.** A paragraph carries a style *name* that has to
resolve in the destination or Word renders it as Normal; a numbered list carries a
numbering reference that lives in a different part of the file entirely; an image is a
separate relationship. Copying the paragraphs alone produces a document that opens without
complaint and is laid out wrong, and that is the failure worth designing against, because
nobody notices it until it has been sent.

`modules`:

* `anchors.py`    - where things are, by name
* `appendices.py` - which appendices exist and what each one binds to. Data, not code.
* `transplant.py` - the move itself
* `setup.py`      - the buttons: copy last year's report, then one appendix at a time
"""

from __future__ import annotations

from report.anchors import Anchor, anchors_in, find_anchor, span_of
from report.appendices import APPENDICES, Appendix, appendix, registry_from
from report.setup import Change, preview, set_up, update, what_would_change
from report.transplant import Carried, Transplant, transplant

__all__ = [
    "APPENDICES",
    "Anchor",
    "Appendix",
    "Carried",
    "Change",
    "Transplant",
    "anchors_in",
    "appendix",
    "find_anchor",
    "preview",
    "registry_from",
    "set_up",
    "span_of",
    "transplant",
    "update",
    "what_would_change",
]
