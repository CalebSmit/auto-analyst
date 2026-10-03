"""P153: the reader decoded anything it did not recognise as text, and passed it on.

`read_document` ended in a branch that decoded its bytes as UTF-8 and called the result a
document. Measured:

* an RTF engagement letter became **one line** reading `{\\rtf1\\ansi\\ansicpg1252\\deff0
  {\\fonttbl{\\f0\\fnil Calibri;}}...`;
* a `.doc` - an OLE2 compound file - became replacement characters and a dump of the bytes
  0 to 255 across three lines.

Both were written to the Source Parse Store as rows a figure could cite, both were handed to
the classifier, and both were appended to the text a model is sent. **That is worse than
refusing**, because it is wrong *as content*: nothing downstream can tell a line of RTF
control words from a sentence somebody wrote.

The root is one assumption - that a file which is not a PDF and not a `.docx` is text - and
it applies to everything that reaches the reader, not only to the two formats that showed
it. So the question asked now is what the file *is*, from its first bytes rather than from
its name, and a file that is not text is refused with what it is and what to do about it.

**An RTF really is text**, and is read properly: `striprtf` leaves the font table, the
stylesheet and the generator behind and turns the escapes back into characters - which
matters here because an em dash is one of the things the prose checks are about.

**A `.doc` is refused on purpose.** A pure-Python reader for the format exists, and there is
no real `.doc` on this machine to measure one against. A half-working parser for a binary
format produces plausible partial text, and that is the failure this repository is most
careful about - so it is routed, named, and refused with the thing to do, which is to save
it as a `.docx`.
"""

from __future__ import annotations

import pytest

from intake.fingerprint import READ, kind_of, mime_of
from intake.readers.documents import NotText, looks_like, read_document

BS = chr(92)


def rtf(*paragraphs: str) -> bytes:
    """A well-formed RTF.

    Built here rather than written as a literal, because a control word is terminated by the
    first non-alphanumeric character: `\\parHenderson` is one unknown control word and not
    `\\par` followed by a name, and a fixture written that way tests the wrong thing.
    """
    head = (
        BS + "rtf1" + BS + "ansi" + BS + "ansicpg1252" + BS + "deff0"
        "{" + BS + "fonttbl{" + BS + "f0" + BS + "fnil Calibri;}}"
        "{" + BS + "stylesheet{" + BS + "s0 Normal;}}"
        "{" + BS + "*" + BS + "generator Riched20 10.0;}"
        + BS + "viewkind4" + BS + "uc1" + BS + "pard "
    )
    return ("{" + head + (BS + "par\n").join(paragraphs) + BS + "par\n}").encode("cp1252")


LETTER = rtf(
    BS + "b Engagement letter" + BS + "b0",
    "Henderson Manufacturing",
    "Fee: " + BS + "'2445,000 for the year ended 31 December 2025",
    "Caf" + BS + "'e9 expenses are excluded",
    "An em dash " + BS + "u8212? and a curly apostrophe " + BS + "u8217?",
)

OLE2 = bytes.fromhex("d0cf11e0a1b11ae1") + b"\x00" * 56 + bytes(range(256))
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 64
TIFF = b"II*\x00" + b"\x00" * 64
ZIP = b"PK\x03\x04" + b"\x00" * 64


# ----------------------------------------------------- what the file is, not what it is called


def test_a_binary_file_is_refused_rather_than_decoded() -> None:
    """Each of these used to come back as a `ParsedDocument` full of replacement characters,
    and each one was content from then on."""
    for data, expect in (
        (OLE2, "OLE2"),
        (PNG, "PNG"),
        (JPEG, "JPEG"),
        (TIFF, "TIFF"),
        (ZIP, "zip"),
    ):
        with pytest.raises(NotText) as refused:
            read_document(data, "whatever.txt")
        assert expect in refused.value.looks_like, refused.value.looks_like


def test_a_format_nobody_listed_is_still_caught() -> None:
    """The signatures name what they know and the list will always be shorter than the
    world. A NUL byte is the general catch: no text file in any encoding holds one, and
    every binary format does."""
    unknown = b"ARBITRARY\x00\x01\x02 format nobody has heard of"
    assert looks_like(unknown) == "a binary file"
    with pytest.raises(NotText):
        read_document(unknown, "export.dat")


def test_the_first_bytes_win_over_the_extension() -> None:
    """A `.doc` saved as `.txt` is still an OLE2 compound file, and a reader that trusted
    the name would decode it."""
    with pytest.raises(NotText) as refused:
        read_document(OLE2, "notes.txt")
    assert "Word 97-2003" in refused.value.looks_like


def test_text_is_still_text() -> None:
    """The branch that was taking everything still has to take what it was for."""
    plain = read_document(b"Henderson Manufacturing\nTrial balance\n", "notes.txt")
    assert [line.text for page in plain.pages for line in page.lines] == [
        "Henderson Manufacturing",
        "Trial balance",
    ]
    assert looks_like(b"Henderson Manufacturing\n") is None


def test_a_text_file_that_is_not_utf_8_is_still_read() -> None:
    """Excel and Word on Windows write cp1252 and say nothing. Decoding strictly and giving
    up would refuse a file that is perfectly readable."""
    latin = b"Cr" + bytes([0xE9]) + b"ances clients\n"
    doc = read_document(latin, "notes.txt")
    assert [line.text for page in doc.pages for line in page.lines] == ["Créances clients"]


# --------------------------------------------------------------------- the one that is text


def test_an_rtf_is_read_as_the_words_a_person_reads() -> None:
    doc = read_document(LETTER, "Engagement letter.rtf")
    assert [line.text for page in doc.pages for line in page.lines] == [
        "Engagement letter",
        "Henderson Manufacturing",
        "Fee: $45,000 for the year ended 31 December 2025",
        "Café expenses are excluded",
        "An em dash — and a curly apostrophe ’",
    ]


def test_an_rtf_leaves_its_markup_behind() -> None:
    """What the fallback reader was storing and sending to a model."""
    text = read_document(LETTER, "letter.rtf").as_text()
    assert BS not in text
    for leaked in ("rtf1", "Calibri", "fonttbl", "stylesheet", "Riched20", "viewkind"):
        assert leaked not in text, f"{leaked} is in the document text"


def test_an_rtfs_escapes_come_back_as_characters() -> None:
    """Both kinds. `\\'24` is a byte in the document's code page and `\\u8212?` is a
    codepoint with an ASCII fallback after it, and a reader that handled one and not the
    other would leave half the punctuation as markup - including the em dash, which this
    build has a prose check about.
    """
    text = read_document(LETTER, "letter.rtf").as_text()
    assert "$45,000" in text
    assert "Café" in text
    assert "—" in text
    assert "’" in text


# --------------------------------------------------------- and the routing table says so


def test_the_routing_table_names_what_is_read_and_what_is_only_routed() -> None:
    """Being routed and being read are two claims. A `.doc` is routed so that a person gets
    the diagnostic saying to save it as a `.docx`; it is not read, and the table says which
    is which rather than leaving a reader to find out by trying."""
    assert mime_of("letter.rtf") in READ
    assert mime_of("notes.md") in READ
    assert mime_of("Statements.pdf") in READ
    assert mime_of("letter.doc") not in READ
    assert kind_of(mime_of("letter.doc")) == "document", "it has to be routed to be refused"


def test_an_rtf_is_not_filed_as_a_word_document() -> None:
    """`mimetypes` calls an `.rtf` `application/msword` on some hosts, which put it in the
    same bucket as the one format in this group that cannot be read."""
    assert mime_of("letter.rtf") == "application/rtf"
    assert mime_of("letter.doc") == "application/msword"
    assert mime_of("letter.rtf") != mime_of("letter.doc")


def test_a_markdown_file_is_a_document() -> None:
    """It was declared in the extension table and left out of the document set, so a `.md`
    was `other` and reached no reader at all."""
    assert kind_of(mime_of("notes.md")) == "document"
