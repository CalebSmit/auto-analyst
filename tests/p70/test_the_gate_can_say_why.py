"""P70: the gate can always say why.

`gate.py` crashed with a `UnicodeEncodeError` in the middle of reporting a failing check.
The only tool permitted to mark a phase done, explaining why one had not passed, died
saying it - and what a person saw was a traceback from inside gate.py, which reads as the
gate being broken rather than the check having failed.

The refusal itself was right: nothing is written when a check fails. The only casualty was
the reason, at the single moment anybody wanted it.

`run()` already decodes a check's output with `errors="replace"`, so holding a replacement
character is the *normal* case rather than an odd one. Printing it to a cp1252 console is
what raised. These run against a real cp1252 stream rather than the machine's own console,
so they mean the same thing on a developer's UTF-8 terminal as on the Windows box where it
happened.
"""

from __future__ import annotations

import io

import pytest

from tools import gate

# A replacement character, as `run` produces for an undecodable byte; a section sign, which
# cp1252 *can* encode; and an em dash, which it cannot.
UNENCODABLE = "�"
CP1252_CAN = "§"
CP1252_CANNOT = "—"


def cp1252() -> io.TextIOWrapper:
    """A stream that behaves like the console this failed on."""
    return io.TextIOWrapper(io.BytesIO(), encoding="cp1252", newline="")


def written(stream: io.TextIOWrapper) -> str:
    stream.flush()
    raw: io.BytesIO = stream.buffer  # type: ignore[assignment]
    return raw.getvalue().decode("cp1252")


def test_a_character_the_console_cannot_encode_does_not_raise() -> None:
    """The crash itself."""
    stream = cp1252()
    gate.say(f"         E   assert {UNENCODABLE}4b in register", stream=stream)
    assert written(stream)


def test_the_line_survives_with_the_bad_character_replaced() -> None:
    """Replaced, not dropped. A line with one character the console cannot take is still
    the line, and losing it would be the same failure more quietly."""
    stream = cp1252()
    gate.say(f"FAILED tests/x.py::test_y {CP1252_CANNOT} because of {UNENCODABLE}", stream=stream)
    out = written(stream)
    assert "FAILED tests/x.py::test_y" in out
    assert "because of" in out
    assert "?" in out, "the unencodable character left no trace"


def test_what_the_console_can_encode_is_left_alone() -> None:
    """The replacement must not be applied to text that was fine."""
    stream = cp1252()
    gate.say(f"section {CP1252_CAN}4b is current", stream=stream)
    assert written(stream) == f"section {CP1252_CAN}4b is current\n"


def test_ordinary_output_is_unchanged() -> None:
    stream = cp1252()
    gate.say("  [PASS] python -m uv run pytest tests/p70 -q", stream=stream)
    assert written(stream) == "  [PASS] python -m uv run pytest tests/p70 -q\n"


def test_an_empty_line_is_still_a_line() -> None:
    stream = cp1252()
    gate.say(stream=stream)
    assert written(stream) == "\n"


def test_a_stream_with_no_encoding_still_takes_the_line() -> None:
    """`getattr(out, "encoding", None) or "ascii"` - a stream that reports no encoding must
    not turn the fallback into a second crash."""

    class Nameless(io.StringIO):
        def write(self, s: str) -> int:
            if any(ord(c) > 127 for c in s):
                raise UnicodeEncodeError("ascii", s, 0, 1, "nope")
            return super().write(s)

    stream = Nameless()
    gate.say(f"a line with {UNENCODABLE} in it", stream=stream)  # type: ignore[arg-type]
    assert "a line with" in stream.getvalue()


def test_the_reporting_path_uses_it() -> None:
    """`run_checks` is where the crash happened, so that is where it has to be used - a
    helper nothing calls would leave the defect exactly where it was."""
    import inspect

    body = inspect.getsource(gate.run_checks)
    assert "say(f" in body, "run_checks still prints a check's output directly"


@pytest.mark.parametrize("text", ["", "plain", UNENCODABLE, CP1252_CANNOT * 40])
def test_nothing_raises_whatever_it_is_given(text: str) -> None:
    gate.say(text, stream=cp1252())
