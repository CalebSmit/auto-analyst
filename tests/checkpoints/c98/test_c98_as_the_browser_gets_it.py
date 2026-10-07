"""Checkpoint C98 - every box, every target, every name, as the browser gets it.

P173 renamed ten sizes, added a target minimum, moved twelve hand-picked values off the
pages and changed what a row does with a sentence. Every one of those was proved against the
string a module holds. A stylesheet is only true of the page it is *served with*, and this is
where the halves meet.

Three joins, and each one fails silently rather than loudly.

* **A token a page names and the sheet it is served does not declare.** `var(--hit)` with no
  `--hit` behind it is not an error: it computes to nothing, the minimum quietly does not
  apply, and every control is back to 20px with no sign of it anywhere. P173 added four
  tokens and moved ten declarations onto them, which is four new chances for exactly that.
* **Two rules whose order decides the answer.** `[hidden]` is a `display:none` the
  user-agent sheet makes, and the `display:inline-flex` controls now carry outranks it. The
  rule that puts it back has to be served *after* the one that broke it, and `in CSS` cannot
  see an ordering.
* **A page that is served two stylesheets.** The Activity console gets the theme and the
  map's, so a question asked of one module is only ever half the answer about that page.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from tools.serve import build

SURFACES = ("/", "/admin", "/analytics", "/help")


@pytest.fixture
def served(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    monkeypatch.setenv("AA_DB_URL", f"sqlite:///{(tmp_path / 'c98.db').as_posix()}")
    monkeypatch.setenv("AA_INBOX_ROOT", str(tmp_path / "inbox"))
    monkeypatch.setenv("AA_OUTBOX_ROOT", str(tmp_path / "outbox"))
    monkeypatch.setenv("AA_VAULT_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("AA_NO_ENV_FILE", "1")
    (tmp_path / "inbox").mkdir()
    (tmp_path / "outbox").mkdir()

    import ports

    ports.reset()
    system = build()
    yield TestClient(system.app)
    system.close()
    ports.reset()


def sheets(page: str) -> str:
    """Everything between the page's style tags - both of them, where there are two."""
    return "\n".join(re.findall(r"<style>(.*?)</style>", page, re.S))


def without_comments(text: str) -> str:
    return re.sub(r"/\*.*?\*/", "", text, flags=re.S)


# ------------------------------------------------- a name the page is served with


@pytest.mark.parametrize("path", SURFACES)
def test_every_token_a_served_page_names_is_declared_in_what_it_is_served(
    served: TestClient, path: str
) -> None:
    """`var(--hit)` with no `--hit` behind it renders as nothing at all - no error, no
    warning, just a minimum that quietly does not apply. The page and the sheet are different
    modules, so only the served bytes can answer this."""
    page = served.get(path).text
    declared = set(re.findall(r"--([\w-]+)\s*:", page))
    named = set(re.findall(r"var\(--([\w-]+)[,)]", page))
    missing = sorted(named - declared)
    assert missing == [], f"{path} names tokens it is not served: {missing}"


@pytest.mark.parametrize("path", SURFACES)
def test_the_scale_the_page_is_served_covers_every_size_on_it(
    served: TestClient, path: str
) -> None:
    """The claim the sheet makes about itself - *two scales, and nothing off them* - asked of
    the page rather than of the module, and of both stylesheets rather than one."""
    page = served.get(path).text
    stray = []
    for found in re.finditer(r"font(?:-size)?\s*:\s*([^;}]+)", without_comments(sheets(page))):
        value = found.group(1)
        if "clamp(" in value:
            continue
        if re.search(r"(?<![\w(-])\d*\.?\d+(px|rem|em)\b", value):
            stray.append(value.strip()[:60])
    assert stray == [], f"{path} is served a type size chosen by eye: {stray}"
    for step in ("t-display", "t-title", "t-subtitle", "t-body", "t-sm", "t-xs", "t-label"):
        assert f"--{step}:" in page, f"{path} is served a scale missing {step}"


@pytest.mark.parametrize("path", SURFACES)
def test_no_served_page_writes_a_length_or_a_size_on_an_element(
    served: TestClient, path: str
) -> None:
    """Eight bare pixel lengths and two type sizes were written on elements. On a page whose
    root is fluid a pixel does not follow the type, so it is *proportionally smaller* on the
    bigger monitor it had more room on."""
    page = served.get(path).text
    body = page[page.rindex("</style>") :]
    assert not re.search(r'style="[^"]*font-size', body), f"{path} sets a type size on an element"
    stray = re.findall(r'style="[^"]*?(?<![\w(-])\d+px[^"]*"', body)
    assert stray == [], f"{path} writes a pixel length on an element: {stray[:3]}"


# ------------------------------------------------ two rules whose order is the answer


@pytest.mark.parametrize("path", SURFACES)
def test_the_target_minimum_is_served_and_nothing_served_after_it_undoes_it(
    served: TestClient, path: str
) -> None:
    """The regression P173 made and caught by looking: the moment controls got a display of
    their own, every button the pages hide by attribute came back. `in page` cannot see an
    ordering, and the ordering is the whole of the fix."""
    page = served.get(path).text
    assert "--hit:24px" in page, f"{path} is served no target size"
    base = page.index("button,.btn{")
    assert "min-height:var(--hit)" in page[base : page.index("}", base)], (
        f"{path} serves a base control with no minimum"
    )
    restore = page.find("button[hidden],.btn[hidden]{display:none}")
    assert restore > 0, f"{path} is served no rule putting [hidden] back"
    assert restore > page.index("display:inline-flex", base), (
        f"{path} serves the restoring rule before the display that outranks [hidden]"
    )


@pytest.mark.parametrize("path", SURFACES)
def test_the_quiet_ink_is_served_only_where_nobody_reads_it(
    served: TestClient, path: str
) -> None:
    """`--ink-4` measures 2.86:1 and is for a placeholder, a disabled control and a
    decorative marker. Asked of the served page, so the map's own sheet is in scope on the
    one page that carries it."""
    page = served.get(path).text
    allowed = ("::placeholder", "summary::before", "#dmap.focused", "aria-pressed")
    worn = [
        found.group(1).strip().replace("\n", " ")
        for found in re.finditer(
            r"([^{}]+)\{([^}]*var\(--ink-4\)[^}]*)\}", without_comments(sheets(page))
        )
    ]
    stray = [s for s in worn if not any(ok in s for ok in allowed)]
    assert stray == [], f"{path} serves the placeholder ink on text: {stray}"


# ------------------------------------------- the four pages are served one language


def test_the_four_pages_are_served_the_same_heading_and_the_same_target(
    served: TestClient,
) -> None:
    """One product. A token that drifted between pages would be two design systems wearing
    the same colours, and each page's own tests would stay green."""
    values = {}
    for path in SURFACES:
        page = served.get(path).text
        for token in ("t-title", "t-figure", "hit", "ink-3", "ink-4"):
            found = re.search(rf"--{token}:\s*([^;]+);", page)
            assert found, f"{path} is served no --{token}"
            values.setdefault(token, {})[path] = found.group(1).strip()
    for token, by_page in values.items():
        assert len(set(by_page.values())) == 1, f"--{token} differs between pages: {by_page}"


@pytest.mark.parametrize("path", SURFACES)
def test_a_row_that_holds_a_sentence_is_served_one_that_wraps(
    served: TestClient, path: str
) -> None:
    """The defect this phase began with, asked of every page rather than of the one it was
    found on - and of the markup too, because the nine hand-written overrides were what made
    the sheet's default survive being wrong for so long."""
    page = served.get(path).text
    rule = re.search(r"\.r \.sub\{([^}]*)\}", page)
    assert rule, f"{path} is served no sub"
    assert "nowrap" not in rule.group(1), f"{path} serves a sub held to one line"
    body = page[page.rindex("</style>") :]
    assert "white-space:normal" not in body, f"{path} still overrides the wrapping by hand"
