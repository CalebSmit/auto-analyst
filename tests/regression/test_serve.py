"""The front door: the system can be started, and it does not overstate what it started.

Every component in this repo was built and proved as a component, and for a long time
nothing composed them - app factories nobody called, a worker pool nobody started, a sweep
loop that only ran inside tests. The build could say "v1, portable and handed off" while
the thing could not be launched at all, because no test asked whether it could.

This is that test. It lives in tests/regression rather than under a phase because it is
not a claim about a feature: it is the claim that the parts add up to something a person
can start, which is the one question a suite of component tests cannot answer.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tools.serve import Seam, build, readiness

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def served(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    """The whole system, wired, against a database of this test's own."""
    monkeypatch.setenv("AA_DB_URL", f"sqlite:///{(tmp_path / 'serve.db').as_posix()}")
    monkeypatch.setenv("AA_INBOX_ROOT", str(tmp_path / "inbox"))
    monkeypatch.setenv("AA_OUTBOX_ROOT", str(tmp_path / "outbox"))
    (tmp_path / "inbox" / "Clients" / "Acme Holdings" / "2026 Valuation").mkdir(parents=True)
    (tmp_path / "outbox").mkdir()

    import ports

    ports.reset()
    system = build()
    yield system
    system.close()
    ports.reset()


def test_the_system_can_be_assembled(served: Any) -> None:
    """The composition root. Nothing here is a mock: the same stores, ports, consoles and
    sweeper a run would use, built the way the command builds them."""
    assert served.app is not None
    assert served.admin is not None and served.ops is not None
    assert served.intake is not None, "the sweeper is part of the system, not of a test"


def test_a_machine_nobody_has_configured_says_so_rather_than_failing(served: Any) -> None:
    """The first-day case. A fresh clone has no configuration document, and every admin
    write reads one first - so without a way in, the dashboard is useless on the one day
    somebody most needs it."""
    client = TestClient(served.app)

    unconfigured = client.get("/api/admin/setup")
    assert unconfigured.status_code == 400, "a diagnostic, not a traceback"
    assert "no configuration written" in unconfigured.json()["detail"]

    made = client.post(
        "/api/admin/initialise", json={"who": "C. Smit", "reason": "first setup"}
    )
    assert made.status_code == 200
    # The model bindings are seeded from `templates/bindings.yaml`, which is checked in
    # and is the firm's own record of which model each layer builds into. Without them the
    # first engagement anybody registers resolves to no template and cannot be activated,
    # which reads like a broken system rather than an unconfigured one.
    assert made.json() == {"environment": "local", "version": 2, "model_bindings": 4}

    setup = client.get("/api/admin/setup")
    assert setup.status_code == 200
    assert setup.json()["watches"] == [] and setup.json()["roster"] == []


def test_initialising_twice_is_refused(served: Any) -> None:
    """Overwriting a live configuration is not an initialisation. The ordinary edits are
    how a configuration changes, and they keep the version history."""
    client = TestClient(served.app)
    client.post("/api/admin/initialise", json={"who": "C. Smit", "reason": "first"})
    again = client.post("/api/admin/initialise", json={"who": "C. Smit", "reason": "again"})
    assert again.status_code == 400
    assert "already configured" in again.json()["detail"]


def test_both_consoles_answer_on_one_app(served: Any) -> None:
    """One process, two surfaces, and the paths each was written against. Mounting them
    as sub-applications would have moved every admin path under a prefix, and the paths
    are what the page and every test are written to."""
    client = TestClient(served.app)
    client.post("/api/admin/initialise", json={"who": "C. Smit", "reason": "first"})

    assert client.get("/").status_code == 200, "the ops console"
    assert client.get("/admin").status_code == 200, "the admin page"
    assert client.get("/api/runs").status_code == 200
    assert client.get("/api/admin/scopes").status_code == 200
    assert client.get("/api/admin/methodology").status_code == 200


def test_the_admin_page_is_a_page_a_person_can_use(served: Any) -> None:
    """Not a check that it is pretty - a check that the things a non-developer has to do
    are on it. Each of these was reachable as JSON long before it was reachable at all."""
    body = TestClient(served.app).get("/admin").text
    for offered in (
        "/api/admin/initialise",
        "/api/admin/preflight",
        "/api/admin/scopes",
        "/api/admin/methodology",
        "/api/admin/engagements",
        "/api/readiness",
        "/profile/template",
    ):
        assert offered in body, offered
    assert "every change here is recorded against it" in body, "who did it travels with it"


def test_the_three_pages_are_served_and_reach_each_other(served: Any) -> None:
    """A page nobody can navigate to is a page nobody reads.

    Three surfaces, three questions: the admin page is "set it up", the ops console is
    "what is happening now", and analytics is "across every run, is it working". Each
    links to the other two, because the alternative is knowing the URLs.
    """
    client = TestClient(served.app)
    client.post("/api/admin/initialise", json={"who": "C. Smit", "reason": "first"})

    pages = {path: client.get(path) for path in ("/", "/admin", "/analytics")}
    assert all(page.status_code == 200 for page in pages.values()), {
        path: page.status_code for path, page in pages.items()
    }
    for path, page in pages.items():
        others = {other for other in pages if other != path}
        assert all(f'href="{other}"' in page.text for other in others), path


def test_the_analytics_page_renders_what_the_analytics_module_computes(served: Any) -> None:
    """The page and the data have to agree about the field names, or the dashboard shows
    blanks the first time somebody renames one - and a blank on a dashboard reads as a
    zero rather than as a bug."""
    client = TestClient(served.app)
    client.post("/api/admin/initialise", json={"who": "C. Smit", "reason": "first"})

    overview = client.get("/api/analytics").json()
    assert set(overview) >= {
        "since", "head", "outcomes", "funnel", "failures", "trends", "stuck", "skills"
    }

    page = client.get("/analytics").text
    for group in ("head", "outcomes", "funnel", "failures", "trends", "stuck", "skills"):
        assert f"a.{group}" in page, group
    for field in (
        "first_pass_yield",
        "time_to_first_reviewable_min",
        "released_then_corrected",
        "auto_accept_rate",
        "override_rate_human_baseline",
        "tieout_failure_rate",
        "quarantined_steps",
        "review_items_past_sla",
        "skills_flagged_by_drift",
    ):
        assert field in page, field

    # The baseline is the one number the dashboard must not invent.
    assert "unmeasured" in page
    assert "two analysts, 200 real line items" in page


def test_readiness_names_every_seam_and_does_not_flatter_itself(served: Any) -> None:
    """The part that keeps this honest.

    A launcher that printed "started" would be true and useless. What matters is which
    joins are made, and the one that is not is named with what is missing behind it.
    """
    seams = {seam.name: seam for seam in readiness()}
    assert set(seams) == {
        "admin",
        "ops console",
        "intake",
        "step execution",
        "run execution",
    }
    assert all(isinstance(s, Seam) for s in seams.values())

    assert all(seam.ready for seam in seams.values()), [
        s.name for s in seams.values() if not s.ready
    ]
    assert seams["step execution"].ready, "P34 joined the executor to the dispatcher"
    assert seams["run execution"].ready, "P35 joined the pool to a released run"

    # Every detail says what is joined rather than what is missing. If one starts naming
    # a gap again, something regressed and this is where it shows.
    for seam in seams.values():
        assert "nothing implements" not in seam.detail, seam.name
        assert "has never been given" not in seam.detail, seam.name

    over_http = TestClient(served.app).get("/api/readiness").json()
    assert over_http["ready"] is True
    assert [s["name"] for s in over_http["seams"]] == list(seams)


def test_readiness_is_derived_from_the_code_not_declared() -> None:
    """The claim flips on its own when somebody writes the missing piece. A constant here
    would be a fact somebody has to remember to update, which is the failure mode this
    whole build is arranged against."""
    import tools.serve as serve

    source = Path(serve.__file__).read_text(encoding="utf-8")
    assert source.count("import_module") == 2, "both seams asked at run time"
    assert serve.steps_are_wired() is True and serve.runs_are_wired() is True

    # Still derived rather than declared, which is what makes the answer worth reading:
    # both flipped on their own as the phases landed, and both would flip back.
    assert "return False" in source, "the absent case is still a real answer"


def test_the_sweep_loop_survives_a_bad_sweep(served: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """A network drive going away should not take the consoles down with it - the
    consoles are how anybody would find out what happened."""
    import threading

    from tools.serve import sweep_forever

    def explode() -> None:
        raise OSError("the drive went away")

    monkeypatch.setattr(served.intake, "sweep", explode)
    stop = threading.Event()
    threading.Timer(0.05, stop.set).start()
    sweep_forever(served, 0, stop)  # returns rather than raising


def test_the_command_reports_without_starting_anything(tmp_path: Path) -> None:
    """`--check` on an unconfigured machine: the case somebody runs first."""
    import subprocess
    import sys

    result = subprocess.run(  # noqa: S603
        [sys.executable, str(ROOT / "tools" / "serve.py"), "--check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        env={
            **__import__("os").environ,
            "AA_DB_URL": f"sqlite:///{(tmp_path / 'check.db').as_posix()}",
        },
        timeout=300,
        check=False,
    )
    assert "Chartwell Automated Analyst" in result.stdout
    assert "NOT WIRED" not in result.stdout, "every seam is joined"
    assert "no configuration document yet" in result.stdout
    assert result.returncode == 1, "an unconfigured machine still cannot take work"


def test_the_setup_path_in_the_guide_gets_an_engagement_activated(served: Any) -> None:
    """docs/USING.md tells somebody to do six things. This does them.

    Walked by hand during the review, and it dead-ended four times - no way to write a
    first configuration, no model bindings so nothing resolved to a template, no template
    registered so nothing could activate, and no way to complete an engagement profile.
    Each component was correct; the path between them had never been walked. A guide that
    is not executed drifts, so this is the executed one.
    """
    client = TestClient(served.app)
    who = {"who": "C. Smit", "reason": "the setup path"}

    # 1. A machine nobody has configured.
    started = client.post("/api/admin/initialise", json=who)
    assert started.status_code == 200, started.text
    assert started.json()["model_bindings"] > 0, "the checked-in bindings come with it"

    # 2. Where files arrive, and 3. where deliverables go.
    assert client.post("/api/admin/watches", json={
        **who, "id": "w-val", "kind": "pattern", "name": "Valuation",
        "root": "Clients", "recipe": "monthly-refresh", "depth": 2,
    }).status_code == 200
    assert client.post("/api/admin/destinations", json={
        **who, "id": "d-local", "name": "Pilot", "path": "_pilot", "adapter": "local_folder",
    }).status_code == 200

    # 4. An engagement, labelled with the practice group somebody picked from the list.
    offered = {p["scope_path"] for p in client.get("/api/admin/scopes").json()["paths"]}
    assert "valuation/esop/repeat" in offered
    assert client.post("/api/admin/engagements", json={
        **who, "engagement_id": "ACME-2026-01", "client": "Acme Holdings",
        "scope_path": "valuation/esop/repeat", "watch_id": "w-val",
        "destination_id": "d-local", "folder": "Acme Holdings/2026 Valuation",
    }).status_code == 200

    # It cannot be activated yet, and the refusal says which thing is missing.
    refused = client.post("/api/admin/engagements/ACME-2026-01/activate", json=who)
    assert refused.status_code == 409
    assert refused.json()["detail"]["refused"][0]["code"] == "CONFIG.PROFILE_INCOMPLETE"

    # 5. The profile: a skeleton with what the system already knows filled in.
    template = client.get("/api/admin/engagements/ACME-2026-01/profile/template")
    assert template.status_code == 200
    profile = template.json()["profile"]
    assert profile["practice"] == "valuation" and profile["segment"] == "esop"
    assert profile["engagement_id"] == "ACME-2026-01"
    assert template.json()["gaps"], "it says what is still missing"

    profile["industry_classification"] = {
        "system": "NAICS", "code": "332710", "description": "Machine shops"
    }
    profile["size_band"] = {"metric": "revenue", "band": "10-50M", "as_of": "2025-12-31"}
    profile["owner_compensation_baseline"] = {
        "amount": 285000, "currency": "USD", "basis": "survey_median",
        "source": "ERI 2025", "as_of": "2025-06-30",
    }
    profile["checkpoint_policy"]["owner"] = "reviewer@chartwell.invalid"
    profile["recorded_by"] = "setup@chartwell.invalid"
    profile["recorded_at"] = "2026-09-07T08:00:00Z"
    assert client.post(
        "/api/admin/engagements/ACME-2026-01/profile", json={**who, "profile": profile}
    ).status_code == 200

    # 6. Active, and preflight says so rather than anybody assuming it.
    activated = client.post("/api/admin/engagements/ACME-2026-01/activate", json=who)
    assert activated.status_code == 200, activated.text
    assert activated.json()["state"] == "active"

    report = client.get(
        "/api/admin/preflight", params={"engagement_id": "ACME-2026-01"}
    ).json()
    blocking = [
        f for c in report["checks"] for f in c["failures"]
        if f["severity"] == "fail"
        and (not f["engagement_ids"] or "ACME-2026-01" in f["engagement_ids"])
    ]
    assert not blocking, blocking


def test_the_guide_names_the_steps_the_walkthrough_takes() -> None:
    """The test above and docs/USING.md have to be the same six steps, or the executed
    path and the written one are two different paths."""
    guide = (ROOT / "docs" / "USING.md").read_text(encoding="utf-8")
    for step in (
        "Initialise the environment",
        "Add a watch",
        "Clear the methodology",
        "Register an engagement",
        "engagement profile",
    ):
        assert step in guide, step


def test_what_is_not_wired_is_written_down_where_a_person_looks() -> None:
    """The gap is real, so it is on the register and in the guide rather than only in a
    seam nobody reads until they start the process."""
    guide = (ROOT / "docs" / "USING.md").read_text(encoding="utf-8")
    assert "python tools/serve.py" in guide

    # Two skills in the shipped recipes have no mechanical half yet, so a run reaching one
    # stops there. That is the honest limit now, and the guide has to carry it rather than
    # implying the system finishes every job it starts.
    assert "qc-tieout" in guide, "the guide names what the system still cannot finish"
    register = (ROOT / "BUILD" / "OPEN.md").read_text(encoding="utf-8")
    assert "qc-tieout" in register, "and it is somebody's work, on the register"


def test_the_plan_owns_the_gap() -> None:
    """A missing join that is not in the plan is a missing join nobody will build. It is
    a phase with exit criteria, like everything else that has to be true."""
    plan = json.loads((ROOT / "BUILD" / "plan.json").read_text(encoding="utf-8"))
    named = [p for p in plan["phases"] if "StepRunner" in json.dumps(p)]
    assert named, "no phase names the seam"
    assert all(p["exit"] and p["checks"] for p in named)
