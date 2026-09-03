#!/usr/bin/env python
"""Export the blueprint's graph model to graph/architecture.json.

The blueprint is the design of record and it is a single HTML file, which makes it easy
to read and impossible to assert against. This lifts the three arrays that matter -
`NODES`, `CONNECTIONS`, `INVARIANTS` - into a JSON file the architecture assertions run
over, checked into the repo beside them.

**Why a JS reader rather than a regex.** The literals are ordinary JavaScript: unquoted
keys, single-quoted strings, HTML and `\\uXXXX` escapes inside them, comments between
entries. A regex over that gets 95% of the way and then silently drops a field on the one
node whose description contains a brace. The reader below is small and total: it either
parses the whole literal or says where it stopped.

**Why not just run node.** Because then re-exporting needs node on whatever machine is
doing it, and the handoff to the work machine is meant to be boring. This has no
dependency beyond the standard library. Its output was checked against `node` at the
time it was written, and `tests/p07` re-checks the parse against the file on every run.

**Drift.** The JSON records a digest of the exact source blocks it came from. A test
recomputes that digest from the HTML, so editing the blueprint without re-exporting fails
a test rather than leaving the assertions running against a graph nobody has any more.

    python tools/export_architecture.py            # write graph/architecture.json
    python tools/export_architecture.py --check    # exit 1 if it would change
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BLUEPRINT = ROOT / "docs" / "architecture.html"
TARGET = ROOT / "graph" / "architecture.json"

# The three arrays the assertions need. Everything else in the blueprint is a mock, a
# table for a tab, or narration - none of it is the design.
ARRAYS = ("NODES", "CONNECTIONS", "INVARIANTS")


# ------------------------------------------------------------ the JS reader


class JsSyntaxError(ValueError):
    pass


class Reader:
    """Enough JavaScript to read an array literal of plain data. Deliberately no more."""

    def __init__(self, text: str) -> None:
        self.text = text
        self.i = 0

    def parse(self) -> Any:
        value = self.value()
        self.skip()
        if self.i != len(self.text):
            raise JsSyntaxError(f"trailing input at {self.where()}")
        return value

    # -- scanning

    def where(self) -> str:
        line = self.text.count("\n", 0, self.i) + 1
        return f"line {line} (offset {self.i}): {self.text[self.i:self.i + 40]!r}"

    def skip(self) -> None:
        """Whitespace and both comment styles, repeatedly."""
        while self.i < len(self.text):
            ch = self.text[self.i]
            if ch in " \t\r\n":
                self.i += 1
            elif self.text.startswith("//", self.i):
                end = self.text.find("\n", self.i)
                self.i = len(self.text) if end == -1 else end
            elif self.text.startswith("/*", self.i):
                end = self.text.find("*/", self.i)
                if end == -1:
                    raise JsSyntaxError(f"unclosed comment at {self.where()}")
                self.i = end + 2
            else:
                return

    def expect(self, ch: str) -> None:
        self.skip()
        if self.i >= len(self.text) or self.text[self.i] != ch:
            raise JsSyntaxError(f"expected {ch!r} at {self.where()}")
        self.i += 1

    # -- values

    def value(self) -> Any:
        self.skip()
        if self.i >= len(self.text):
            raise JsSyntaxError("input ended where a value was expected")
        ch = self.text[self.i]
        if ch == "[":
            return self.array()
        if ch == "{":
            return self.obj()
        if ch in "'\"":
            return self.string()
        for word, result in (("true", True), ("false", False), ("null", None)):
            if self.text.startswith(word, self.i):
                self.i += len(word)
                return result
        return self.number()

    def array(self) -> list[Any]:
        self.expect("[")
        items: list[Any] = []
        while True:
            self.skip()
            if self.i < len(self.text) and self.text[self.i] == "]":
                self.i += 1
                return items
            items.append(self.value())
            self.skip()
            if self.i < len(self.text) and self.text[self.i] == ",":
                self.i += 1

    def obj(self) -> dict[str, Any]:
        self.expect("{")
        found: dict[str, Any] = {}
        while True:
            self.skip()
            if self.i < len(self.text) and self.text[self.i] == "}":
                self.i += 1
                return found
            key = self.key()
            self.expect(":")
            found[key] = self.value()
            self.skip()
            if self.i < len(self.text) and self.text[self.i] == ",":
                self.i += 1

    def key(self) -> str:
        self.skip()
        if self.text[self.i] in "'\"":
            return self.string()
        start = self.i
        while self.i < len(self.text) and (
            self.text[self.i].isalnum() or self.text[self.i] in "_$"
        ):
            self.i += 1
        if start == self.i:
            raise JsSyntaxError(f"expected a key at {self.where()}")
        return self.text[start:self.i]

    def string(self) -> str:
        quote = self.text[self.i]
        self.i += 1
        out: list[str] = []
        while True:
            if self.i >= len(self.text):
                raise JsSyntaxError("unterminated string")
            ch = self.text[self.i]
            if ch == quote:
                self.i += 1
                return "".join(out)
            if ch != "\\":
                out.append(ch)
                self.i += 1
                continue
            escape = self.text[self.i + 1]
            if escape == "u":
                out.append(chr(int(self.text[self.i + 2:self.i + 6], 16)))
                self.i += 6
            else:
                out.append({"n": "\n", "t": "\t", "r": "\r"}.get(escape, escape))
                self.i += 2

    def number(self) -> float | int:
        start = self.i
        while self.i < len(self.text) and self.text[self.i] in "+-0123456789.eE":
            self.i += 1
        raw = self.text[start:self.i]
        if not raw:
            raise JsSyntaxError(f"expected a value at {self.where()}")
        return float(raw) if any(c in raw for c in ".eE") else int(raw)


# --------------------------------------------------------------- extraction


def source_block(html: str, name: str) -> str:
    """The `[...]` of `const NAME = [...];`, found by matching brackets.

    Bracket matching rather than a search for `\\n];`, so a change to the blueprint's
    formatting cannot silently truncate the export.
    """
    marker = f"const {name} = ["
    start = html.index(marker) + len(marker) - 1
    depth = 0
    i = start
    in_string: str | None = None
    while i < len(html):
        ch = html[i]
        if in_string:
            if ch == "\\":
                i += 2
                continue
            if ch == in_string:
                in_string = None
        elif ch in "'\"":
            in_string = ch
        elif ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                return html[start:i + 1]
        i += 1
    raise JsSyntaxError(f"const {name} = [ ... ] is not closed")


def build() -> dict[str, Any]:
    html = BLUEPRINT.read_text(encoding="utf-8")
    blocks = {name: source_block(html, name) for name in ARRAYS}
    parsed = {name: Reader(block).parse() for name, block in blocks.items()}

    digest = hashlib.sha256()
    for name in ARRAYS:
        digest.update(blocks[name].encode("utf-8"))

    return {
        "generated_from": "docs/architecture.html",
        "generated_by": "tools/export_architecture.py",
        "source_digest": f"sha256:{digest.hexdigest()}",
        "counts": {
            "nodes": len(parsed["NODES"]),
            "edges": len(parsed["CONNECTIONS"]),
            "invariants": len(parsed["INVARIANTS"]),
        },
        "nodes": parsed["NODES"],
        "edges": parsed["CONNECTIONS"],
        "invariants": parsed["INVARIANTS"],
    }


def rendered(graph: dict[str, Any]) -> str:
    return json.dumps(graph, indent=2, ensure_ascii=False) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--check",
        action="store_true",
        help="do not write; exit 1 if graph/architecture.json is out of date",
    )
    args = parser.parse_args()

    graph = build()
    body = rendered(graph)
    counts = graph["counts"]

    if args.check:
        if not TARGET.is_file():
            print(f"  {TARGET.relative_to(ROOT)} does not exist. Run this without --check.")
            return 1
        if TARGET.read_text(encoding="utf-8") != body:
            print(
                f"  {TARGET.relative_to(ROOT)} is out of date with the blueprint.\n"
                f"  Run: python tools/export_architecture.py"
            )
            return 1
        print(f"  up to date - {counts['nodes']} nodes, {counts['edges']} edges, "
              f"{counts['invariants']} invariants")
        return 0

    TARGET.write_text(body, encoding="utf-8")
    print(
        f"  wrote {TARGET.relative_to(ROOT)} - {counts['nodes']} nodes, "
        f"{counts['edges']} edges, {counts['invariants']} invariants"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
