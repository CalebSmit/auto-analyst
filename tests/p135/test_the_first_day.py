"""P135: a fresh clone could not set itself up.

Started a server against an empty store - the state Caleb's work machine begins in - and
opened `/admin`. The page was twelve grey rectangles under a red banner reading *"This page
cannot reach the server"*, and the console said:

    TypeError: Cannot read properties of null (reading 'recipes')
        at checklist

Five things, each of which alone would have been enough to stop the first day:

1. **`SETUP` was `null` and `checklist()` dereferenced it.** Most of the page guarded for
   null; one step did not, threw, and took every panel after it down with it - the roster,
   preflight, the scopes, the methodology, the workflows, the seams, the report. Null was
   the wrong shape for "nothing is set up"; an empty object is the right one.

2. **A refusal was reported as an unreachable server.** `refresh()` tested `e.code` to tell
   a refusal from a dead connection, and only *structured* diagnostics carry a code. The one
   refusal this page exists to handle - no configuration document yet - is a plain sentence,
   so it took the other branch.

3. **The two steps that come before setup had no answers.** The masking key and the model
   adapter are facts about the machine and need no configuration document, but they were
   only ever returned inside `/api/admin/setup`, which refuses when there is none. So step
   one read "unknown" and step two read "Skills are answered by ? - unknown", on the one
   machine where those two steps are the whole job.

4. **`SETUP.recipes` is returned by no route at all.** The workflows live behind
   `/api/admin/recipes`, which is what the panel beside the checklist has always used. So on
   *every* machine, configured or not, step seven could not be ticked, its Approve button
   could not appear, and the checklist could not reach "Ready to run" however much was done.
   The right answer was on screen two inches away under another name.

5. **And the button that writes the first configuration never rendered.** A step's control
   showed only when that step was `next`. A fresh clone runs on the fake adapter, so step
   two - connect the AI model - can never be marked done, so it was permanently `next`, so
   step three's **Set it up** never appeared. There was no way to configure the machine from
   the page whose only purpose is configuring it.

Plus two things the screen said that were not sentences: `the firm ceiling of $undefined`,
and `Next: connect the ai model`.

Every one of these was invisible from the source and obvious from the screen.
"""

from __future__ import annotations

import re
from typing import Any

from admin.page import PAGE as SETUP_PAGE
from ui.theme import CSS  # noqa: F401 - imported to prove the module loads as the page does


def script() -> str:
    return "\n".join(re.findall(r"<script>(.*?)</script>", SETUP_PAGE, re.S))


def without_comments(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    return re.sub(r"(?<!:)//[^\n]*", " ", text)


# ------------------------------------------------- 1. nothing is set up is not nothing


def test_setup_is_an_object_before_anything_has_answered() -> None:
    """The declaration itself. `null` is what made a missing key a thrown exception rather
    than an empty list, and every `(SETUP.x || [])` on the page was written expecting the
    second."""
    body = without_comments(script())
    assert "let SETUP = {}" in body, "SETUP starts as null again"
    assert "SETUP = null" not in body, "something still sets it back to null"


def test_whether_a_configuration_exists_is_its_own_fact() -> None:
    """It used to be inferred from `SETUP` being truthy, which is why SETUP could not be
    given a safe empty value. Two questions, two answers."""
    body = without_comments(script())
    assert "CONFIGURED = false" in body
    assert "CONFIGURED = true" in body, "nothing ever sets it"
    assert "const configured = CONFIGURED" in body
    assert "!!SETUP" not in body, "the old inference is back"


def test_no_step_reads_through_setup_without_a_fallback() -> None:
    """The defect was one unguarded dereference among many guarded ones, so the property
    worth holding is about all of them: every read of a list off SETUP falls back.

    Walks the text of the checklist rather than the whole page, because this is the
    function that runs before anything else has a chance to."""
    body = without_comments(script())
    found = re.search(r"function checklist\(\) \{(.*?)\n\}", body, re.S)
    assert found, "checklist() is gone"
    inside = found.group(1)
    # One key is bound bare and then tested for undefined two lines later, which is a
    # fallback written the other way round. It is named here rather than matched by shape:
    # an earlier version of this test accepted `= SETUP.x;` as a form of guard, and
    # breaking the code on purpose showed it then accepted `const roster = SETUP.roster;` -
    # the exact dereference it exists to catch. A rule that reads "bound to a name" cannot
    # tell the two apart, so the exception is a list of one with its reason beside it.
    tested_for_undefined = {"firm_ceiling_usd"}
    assert "ceiling === undefined" in inside, "the one exception no longer tests what it bound"

    for read in re.findall(r"SETUP\.([a-z_]+)", inside):
        if read in tested_for_undefined:
            continue
        guarded = re.search(rf"SETUP\.{read}\s*\|\|", inside) or re.search(
            rf"SETUP\s*&&\s*SETUP\.{read}", inside
        )
        assert guarded, f"SETUP.{read} is read in checklist() with no fallback"


# ------------------------------------------------ 2. a refusal is not an unreachable server


def test_every_refusal_says_it_came_back_from_a_server() -> None:
    """In `ui/theme.py`, because all three pages share it. The flag is on the answer rather
    than inferred from whether a code happened to be present."""
    from pathlib import Path

    theme = (Path(__file__).resolve().parents[2] / "ui" / "theme.py").read_text(encoding="utf-8")
    found = re.search(r"async function refusal\(response\) \{(.*?)\n\}", theme, re.S)
    assert found, "refusal() is gone"
    returns = re.findall(r"return \{([^}]*)\}", found.group(1))
    assert len(returns) == 3, "a return was added or removed; each one has to be marked"
    for one in returns:
        assert "refused: true" in one, f"this answer does not say it was refused: {one}"


def test_the_page_tests_for_the_refusal_rather_than_for_a_code() -> None:
    body = without_comments(script())
    assert "e.refused" in body, "the page is back to guessing from the code"
    assert "!e.code" not in body


# ------------------------------- 3. the machine's own facts do not need a configuration


def test_the_environment_can_be_asked_without_a_configuration_document() -> None:
    """`AdminConsole.environment()` reads the vault and the ports and nothing else. The
    proof that matters is that it does not go near the configuration document, so it is
    asserted by calling it on a console whose document raises."""
    from admin.console import AdminConsole

    source = AdminConsole.environment.__doc__ or ""
    assert "configuration document" in source, "the reason it exists is no longer written down"

    class Raises:
        environment = "local"

        def document(self) -> dict[str, Any]:
            raise KeyError("no configuration written for environment 'local'")

    console = AdminConsole.__new__(AdminConsole)
    console.config = Raises()  # type: ignore[attr-defined]
    answered = {"environment_ready": {"vault": {}}, "ai_model": {"adapter": "fake"}}
    console._environment = lambda: answered["environment_ready"]  # type: ignore[assignment]
    console._ai_model = lambda: answered["ai_model"]  # type: ignore[assignment]
    assert console.environment() == answered


def test_the_route_is_reachable_on_a_machine_with_no_configuration(served: Any) -> None:
    """End to end on the real app, against a store nobody has written to. The route that
    refuses and the route that answers, side by side - which is the whole point."""
    from fastapi.testclient import TestClient

    client = TestClient(served.app)
    assert client.get("/api/admin/setup").status_code == 400, "the fixture is already set up"

    answer = client.get("/api/admin/environment")
    assert answer.status_code == 200, answer.text
    body = answer.json()
    assert body["environment_ready"]["vault"]["name"], "the key's name is what a person sets"
    assert body["ai_model"]["adapter"], "no adapter named, so step two says nothing"


def test_the_page_asks_for_it_when_it_has_no_configuration() -> None:
    body = without_comments(script())
    assert "/api/admin/environment" in body, "the route exists and the page never calls it"
    assert "if (!CONFIGURED)" in body, "it asks unconditionally, or not at all"


# -------------------------------------------- 4. the step that could never be completed


def test_the_workflows_step_reads_the_route_that_has_workflows() -> None:
    """`SETUP.recipes` was returned by nothing. Asserted across both files, because each
    was self-consistent: the page read a key, the console never wrote one, and nothing
    compared them."""
    from pathlib import Path

    console = (Path(__file__).resolve().parents[2] / "admin" / "console.py").read_text(
        encoding="utf-8"
    )
    setup = re.search(r"def setup\(self\).*?\n        \}\n", console, re.S)
    assert setup, "setup() is gone"
    assert '"recipes"' not in setup.group(0), (
        "setup() returns recipes now - then the page may read them from there, but this "
        "test has to be the thing that says so"
    )

    body = without_comments(script())
    assert "SETUP.recipes" not in body, "the key nothing produces is being read again"
    assert "RECIPES" in body
    assert "/api/admin/recipes" in body


def test_the_recipes_are_fetched_before_the_step_that_reads_them() -> None:
    """One fetch, two readers, in that order. The panel used to do its own and the
    checklist had none; if the order slips back the step is empty again."""
    body = without_comments(script())
    found = re.search(r"async function refresh\(\) \{(.*?)\n\}", body, re.S)
    assert found
    inside = found.group(1)
    assert inside.index("/api/admin/recipes") < inside.index("checklist()"), (
        "checklist() runs before the recipes arrive, so step seven is empty again"
    )


def test_the_panel_and_the_step_read_one_list() -> None:
    """They disagreed on screen - four approved in the panel, none in the step - because
    they read different things. One variable now, so they cannot.

    The modals still fetch when they open, which is right: a dialog should show the state
    at the moment it is opened, not at the moment the page was loaded. What matters is that
    the two things rendered side by side come from the same place."""
    body = without_comments(script())
    panel = re.search(r"function workflows\(\) \{(.*?)\n\}", body, re.S)
    assert panel, "the workflows panel is gone"
    assert "RECIPES" in panel.group(1), "the panel fetches its own list again"
    assert "get('/api/admin/recipes')" not in panel.group(1)


# ------------------------------------- 5. the control that writes the first configuration


def test_a_step_with_something_to_press_shows_it_whether_or_not_it_is_next() -> None:
    """The dead end. `i === next` gated the button, and on a fake adapter `next` never got
    past step two - so the button that writes the first configuration never rendered."""
    body = without_comments(script())
    found = re.search(r"const drawn = (.*?);\n", body, re.S)
    assert found, "the step renderer is gone"
    drawn = found.group(1)
    assert "${s.go ?" in drawn, "the button is conditional on something other than having one"
    assert "s.go && i === next" not in drawn, "the gate is back"
    # The emphasis is kept - that part was right. Only the gate was wrong.
    assert "i === next ? 'primary' : 'quiet'" in drawn, "every button now shouts equally"


def test_the_step_that_writes_the_first_configuration_still_has_its_control() -> None:
    body = without_comments(script())
    assert "'Set it up', 'initialise'" in body
    assert "ACTIONS.initialise" in body, "the action it names is not registered"


# --------------------------------------------- and two things that were not sentences


def test_no_step_prints_a_number_the_machine_does_not_have() -> None:
    """`the firm ceiling of $undefined a run`, on the fresh-machine screen, twice."""
    body = without_comments(script())
    found = re.search(r"function checklist\(\) \{(.*?)\n\}", body, re.S)
    assert found
    # Scoped to the checklist on purpose. The settings dialog interpolates the same figure
    # and is right to: it opens on a roster entry, and a machine with a roster has a
    # configuration document. The checklist is the one thing that renders before there is
    # one, which is why it is the one place the guard is required.
    assert "of $' + SETUP.firm_ceiling_usd" not in found.group(1), "interpolated unguarded again"
    assert "ceiling === undefined" in found.group(1), "nothing checks whether there is one"


def test_the_next_line_does_not_lowercase_the_step_it_names() -> None:
    """"Next: connect the ai model" - the one title with an acronym in it."""
    body = without_comments(script())
    assert "steps[next].t.toLowerCase()" not in body
    assert "Next: ${esc(steps[next].t)}" in body


# ------------------------------------------------------- what the command says on day one


def test_the_first_command_does_not_name_an_exception_class() -> None:
    """`python tools/serve.py --check` is what docs/USING.md says to run first. It answered
    `no configuration document yet (KeyError).`, which tells a person nothing they can act
    on and reads like a fault rather than a first day."""
    from pathlib import Path

    serve = (Path(__file__).resolve().parents[2] / "tools" / "serve.py").read_text(
        encoding="utf-8"
    )
    found = re.search(r"def report\(served.*?\n    return 0", serve, re.S)
    assert found, "report() is gone"
    report = found.group(0)
    assert "no configuration document yet ({unread.__class__.__name__})" not in report
    assert "nothing is set up yet on this machine" in report
    assert "except KeyError:" in report, "every failure is one message again"
    # Anything that is not a missing document is still a fault, and still says so.
    assert "the configuration could not be read" in report


def test_assembling_the_system_prints_nothing() -> None:
    """`build()` says it has no side effects and then printed a diagnostic about a practice
    group with no input schema - above the banner, before anything said what the program
    was. A fresh machine's first line of output was a raw refusal about a group that is not
    the focus division and that nobody intends to finish."""
    import ast
    from pathlib import Path

    serve = (Path(__file__).resolve().parents[2] / "tools" / "serve.py").read_text(
        encoding="utf-8"
    )
    tree = ast.parse(serve)
    build = next(
        n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "build"
    )
    printed = [
        n
        for n in ast.walk(build)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "print"
    ]
    assert not printed, "build() prints again, so a test and a rehearsal print it too"


def test_what_could_not_be_registered_is_carried_and_then_said_in_words(served: Any) -> None:
    """Carried on the assembled system, reported by the command, and the sentence says the
    thing a person needs: other groups still work."""
    from pathlib import Path

    assert isinstance(served.unregistered, tuple)
    for layer, why in served.unregistered:
        assert layer and why, "an entry with nothing in it says nothing"
        assert "DELIVER." not in why, "the whole rendering again, rather than its sentence"

    serve = (Path(__file__).resolve().parents[2] / "tools" / "serve.py").read_text(
        encoding="utf-8"
    )
    assert "Practice groups with no model set up here:" in serve
    assert "Engagements in every other group are unaffected." in serve


# ------------------------------------- and two things a new machine is the only one to see


def test_an_empty_state_styles_its_title_and_not_its_emphasis() -> None:
    """The Activity console on an empty store shows "here is how one starts", and two of
    its four steps name a control in bold mid-sentence. `.empty b` styled every `b` inside
    an empty state as a display-serif heading, so "files" and "Waiting on a person" became
    headings on their own lines with the sentence's full stop orphaned below.

    Only a machine with no runs ever sees that panel, which is why it survived.
    """
    from pathlib import Path

    theme = (Path(__file__).resolve().parents[2] / "ui" / "theme.py").read_text(encoding="utf-8")
    assert ".empty>b:first-child{display:block" in theme, "the heading rule is unscoped again"
    assert "\n.empty b{display:block" not in theme
    assert ".empty b{font-weight:600" in theme, "emphasis inside one has no rule at all"


def test_every_empty_state_puts_its_title_first() -> None:
    """Which is what makes `:first-child` the right selector. If one of them ever leads
    with something else, its title stops being a title - so the convention is asserted
    rather than remembered."""
    import re as _re
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    for page in (root / "ops" / "console").glob("*.py"):
        for found in _re.findall(r'class="empty"[^>]*>(.{0,8})', page.read_text(encoding="utf-8")):
            assert found.startswith("<b>") or found.startswith("Unavail"), (
                f"{page.name}: an empty state that does not lead with its title: {found!r}"
            )


def test_the_analytics_chrome_shows_a_date_rather_than_a_wire_format() -> None:
    """`since 2026-09-02T14:19:01Z` in the corner of a page whose every other time is
    "4 min ago"."""
    from pathlib import Path

    console = Path(__file__).resolve().parents[2] / "ops" / "console"
    page = (console / "analytics_page.py").read_text(encoding="utf-8")
    assert "'since ' + esc(a.since)" not in page, "the raw value is rendered again"
    assert "replace('T', ' ')" in page


def test_nothing_tests_setup_for_truthiness_any_more() -> None:
    """The regression this phase nearly introduced.

    Making SETUP an empty object fixed the page that threw and, in the same move, silently
    disarmed `if (!SETUP)` in `showAdd()` - an empty object is truthy, so the engagement
    form would have opened on a machine with no configuration to save into. Found by
    pressing the button, not by reading the diff.

    Every "has this been set up" question is `CONFIGURED`. SETUP is data; whether there is
    any is a different fact, and the whole point of splitting them was that one value
    cannot answer both.
    """
    body = without_comments(script())
    assert "!SETUP" not in body, "something reads SETUP's truthiness as a presence test"
    assert "if (!CONFIGURED)" in body, "the refusal in showAdd() is gone entirely"
