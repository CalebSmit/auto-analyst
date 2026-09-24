"""Read code as code, not as text — the third member of the set.

`tests/counting.py` exists because a number written down twice drifts. `tests/importing.py`
exists because a substring cannot answer "does this module import that package". This one
exists because of a failure that happened three times while writing P117 and P118, and
once before that in `tests/p45`:

    **a comment explaining the fix satisfied the grep that was meant to check the fix.**

`assert "proxy_headers=False" in source` is satisfied by the comment above the line, so
deleting the line leaves it green. `assert "'mature-company-valuation'" not in page` fails
against the comment saying the default used to be that. `assert "ANTHROPIC_API_KEY" not in
body` fails against the comment explaining why the name must not be there.

The rule: **an assertion about code is asked of the code.** Comments are prose, and the
better the comment, the more likely it is to contain exactly the phrase being searched
for — which makes this failure worse the more carefully the code is written.
"""

from __future__ import annotations

import re

_PY_COMMENT = re.compile(r"(?m)^\s*#.*$|(?<=\S)\s+#.*$")
_JS_BLOCK = re.compile(r"/\*.*?\*/", re.S)
_JS_LINE = re.compile(r"(?m)^\s*//.*$")


def python_code(source: str) -> str:
    """Python source with its `#` comments removed. Docstrings are left alone: they are
    part of what a module says about itself, and a test asserting on one means it."""
    return _PY_COMMENT.sub("", source)


def page_script(page_source: str) -> str:
    """The browser page's JavaScript, with the f-string brace doubling undone.

    `admin/page.py` is one HTML page held in a Python f-string, so `{{` in the file is a
    single brace in the page. Every test that reads the page wants it this way round."""
    blocks = re.findall(r"<script[^>]*>(.*?)</script>", page_source, re.S)
    return "\n".join(blocks).replace("{{", "{").replace("}}", "}")


def page_code(page_source: str) -> str:
    """The page's JavaScript with its comments removed as well."""
    return _JS_LINE.sub("", _JS_BLOCK.sub("", page_script(page_source)))
