"""P37: the division focus, and the interview that fills it.

The interview itself is a model asking questions; what is tested is everything around it
that must not depend on a model remembering - the coverage map, the session log, the
ordering of what to ask next, and the scan that keeps a client's name out of anything git
would commit.
"""

from __future__ import annotations

import subprocess
from datetime import date
from pathlib import Path

import pytest

from graph.resolve import ScopeResolver
from registries.errors import RegistryError
from registries.scopes import ScopePath, ScopeRegistry
from tools import interview

ROOT = Path(__file__).resolve().parents[2]


# ------------------------------------------------------------------ the focus


def test_the_focus_is_non_esop_valuation_and_esop_is_parked() -> None:
    registry = ScopeRegistry.load()
    assert registry.focus == ("valuation", "non-esop")
    esop = registry.practice("valuation").segment("esop")
    assert esop is not None and esop.parked
    assert registry.in_focus(ScopePath("valuation", "non-esop", "repeat"))
    assert not registry.in_focus(ScopePath("valuation", "esop", "repeat"))


def test_a_parked_segment_still_resolves() -> None:
    resolved = ScopeResolver().resolve("valuation/esop/repeat")
    assert "repurchase-obligation" in resolved.names


def _scopes_with(tmp_path: Path, old: str, new: str) -> Path:
    text = (ROOT / "scope" / "scopes.yaml").read_text(encoding="utf-8")
    assert old in text
    target = tmp_path / "scopes.yaml"
    target.write_text(text.replace(old, new, 1), encoding="utf-8")
    return target


def test_a_focus_on_an_undeclared_segment_is_refused(tmp_path: Path) -> None:
    bad = _scopes_with(tmp_path, "  segment: non-esop\n", "  segment: nowhere\n")
    with pytest.raises(RegistryError, match="not declared"):
        ScopeRegistry.load(bad)


def test_a_focus_on_a_parked_segment_is_refused(tmp_path: Path) -> None:
    bad = _scopes_with(tmp_path, "  segment: non-esop\n", "  segment: esop\n")
    with pytest.raises(RegistryError, match="parked"):
        ScopeRegistry.load(bad)


def test_no_focus_is_a_legal_state(tmp_path: Path) -> None:
    text = (ROOT / "scope" / "scopes.yaml").read_text(encoding="utf-8")
    start = text.index("focus:\n")
    end = text.index("practices:\n")
    target = tmp_path / "scopes.yaml"
    target.write_text(text[:start] + text[end:], encoding="utf-8")
    registry = ScopeRegistry.load(target)
    assert registry.focus is None
    assert not registry.in_focus(ScopePath("valuation", "non-esop", "repeat"))


# ------------------------------------------------------------ the first session's base


@pytest.mark.parametrize("scope", ["valuation/non-esop/repeat", "valuation/non-esop/non-repeat"])
def test_the_pilot_recipe_compiles_for_the_focus(scope: str) -> None:
    from graph.compile import PlanContext, compile_recipe
    from graph.recipes import load_recipe

    recipe = load_recipe("mature-company-valuation")
    context = PlanContext(
        engagement_id="PILOT-1",
        scope=ScopeResolver().resolve(scope),
        taxonomy_version="coa-taxonomy@1.0.0",
        precedent_snapshot="snap-pilot",
    )
    plan = compile_recipe(recipe, context)
    order = list(plan.order)
    # The analyst's order: historicals before everything built on them, comps before WACC,
    # WACC before the DCF, and the model checks last before release.
    assert order.index("timing") < order.index("tagging") < order.index("dcf")
    assert order.index("gpc") < order.index("wacc") < order.index("dcf")
    assert order.index("model") < order.index("qc") < order.index("release")


def test_historical_financials_are_the_only_document_the_pilot_waits_for() -> None:
    import yaml

    raw = yaml.safe_load((ROOT / "recipes" / "mature-company-valuation.yaml").read_text("utf-8"))
    assert raw["intake"]["required_types"] == ["financial_statements"]


def test_the_non_esop_methodology_would_clear() -> None:
    """Drafted from the interview; a person still has to clear it. This proves only that
    the clearance scan would not refuse it for looking like client data."""
    from registries.methodology import MethodologyRegister, body_of

    register = MethodologyRegister()
    path = (ROOT / "foundations/valuation/non-esop/_segment/how-we-work.md").resolve()
    assert "valuation/non-esop/_segment" in register.layers()
    assert register.scan(body_of(path), register.name_of(path)) == ()


def test_pre_revenue_is_not_an_edge_case_here() -> None:
    topics = {t.id: t for t in interview.load_topics()}
    assert "pre-revenue" in topics
    assert not any("pre-revenue or" in angle for angle in topics["edge-cases"].angles)


# ------------------------------------------------------------------ the map


def test_the_topic_map_loads_and_every_topic_can_be_asked() -> None:
    topics = interview.load_topics()
    assert len({t.id for t in topics}) == len(topics)
    assert all(t.angles and t.done_when and t.feeds for t in topics)
    assert any(t.id == "projects" and t.priority == 1 for t in topics)
    assert any(t.id == "document-arrival" for t in topics)


def test_a_duplicate_topic_is_refused(tmp_path: Path) -> None:
    text = (ROOT / "interview" / "topics.yaml").read_text(encoding="utf-8")
    first = text.index("  - id: role")
    second = text.index("  - id: engagement-types")
    doubled = tmp_path / "topics.yaml"
    doubled.write_text(text + text[first:second], encoding="utf-8")
    with pytest.raises(ValueError, match="declared twice"):
        interview.load_topics(doubled)


# ------------------------------------------------------------- the knowledge folder


def test_init_lays_down_the_skeleton_and_never_overwrites(tmp_path: Path) -> None:
    created = interview.init(tmp_path)
    assert len(created) == len(interview.SKELETON)
    (tmp_path / "decisions.md").write_text("mine", encoding="utf-8")
    assert interview.init(tmp_path) == []
    assert (tmp_path / "decisions.md").read_text(encoding="utf-8") == "mine"


def test_sessions_count_up_within_a_day(tmp_path: Path) -> None:
    day = date(2026, 9, 16)
    assert interview.start_session(tmp_path, day).name == "2026-09-16-1.md"
    assert interview.start_session(tmp_path, day).name == "2026-09-16-2.md"


def test_mark_records_status_notes_and_sessions(tmp_path: Path) -> None:
    interview.mark("role", "partial", "reviewer known", "2026-09-16-1", knowledge=tmp_path)
    entry = interview.mark("role", "covered", "", "2026-09-16-1", knowledge=tmp_path)
    assert entry == {
        "status": "covered",
        "notes": ["reviewer known"],
        "sessions": ["2026-09-16-1"],
    }
    assert interview.load_coverage(tmp_path)["role"]["status"] == "covered"
    with pytest.raises(ValueError, match="not in"):
        interview.mark("no-such-topic", "open", knowledge=tmp_path)
    with pytest.raises(ValueError, match="status"):
        interview.mark("role", "finished", knowledge=tmp_path)


def test_next_topics_open_before_partial_and_priority_first() -> None:
    topics = interview.load_topics()
    coverage = {"role": {"status": "covered"}, "engagement-types": {"status": "partial"}}
    picked = interview.next_topics(topics, coverage, limit=50)
    ids = [t.id for t, _ in picked]
    assert "role" not in ids
    assert picked[0] == (next(t for t in topics if t.id == "lifecycle"), "open")
    priorities = [t.priority for t, _ in picked]
    assert priorities == sorted(priorities)
    first_partial = ids.index("engagement-types")
    assert all(t.priority == 1 and s == "open" for t, s in picked[:first_partial])


def test_followups_and_backlog_are_read_from_their_files(tmp_path: Path) -> None:
    interview.init(tmp_path)
    (tmp_path / "followups.md").write_text(
        "# F\n- [ ] why five years\n- [x] asked already\n", encoding="utf-8"
    )
    (tmp_path / "backlog.md").write_text(
        "## B-001 a\nstatus: proposed\n## B-002 b\nstatus: built\n"
        "## B-003 c\nstatus: proposed\n",
        encoding="utf-8",
    )
    assert interview.open_followups(tmp_path) == ["why five years"]
    assert interview.backlog_counts(tmp_path) == {"proposed": 2, "built": 1}


# ----------------------------------------------------------------- the boundary


def test_knowledge_travels_with_the_repo() -> None:
    probe = subprocess.run(
        ["git", "check-ignore", "-q", "knowledge/sessions/probe.md"],
        cwd=ROOT,
        capture_output=True,
    )
    assert probe.returncode == 1, "knowledge/ is committed so the interview moves machines"


def test_knowledge_never_goes_into_the_image() -> None:
    assert "knowledge/" in (ROOT / ".dockerignore").read_text(encoding="utf-8")


def test_the_scan_finds_an_identifier_and_only_whole_words(tmp_path: Path) -> None:
    leaky = tmp_path / "SKILL.md"
    leaky.write_text("Example: acme widgets added back rent.\n", encoding="utf-8")
    clean = tmp_path / "other.md"
    clean.write_text("The client added back rent. Acmesque is not a name.\n", encoding="utf-8")
    hits = interview.scan([leaky, clean], ["Acme Widgets", "Acme"])
    assert [(p.name, line, name) for p, line, name in hits] == [
        ("SKILL.md", 1, "acme widgets")
    ]


def test_identifiers_skip_comments_and_fragments(tmp_path: Path) -> None:
    interview.init(tmp_path)
    (tmp_path / "identifiers.txt").write_text("# note\nAcme\nAB\n\n", encoding="utf-8")
    assert interview.identifiers(tmp_path) == ["Acme"]


def test_the_committed_tree_is_clean_against_the_local_watch_list() -> None:
    """Empty on a clone with no interview; the real check on a machine that has one."""
    assert interview.scan(interview.committable_files(), interview.identifiers()) == []


# ------------------------------------------------------------------ the command


@pytest.mark.parametrize(
    "wrapper", [".claude/commands/improve-agent.md", ".cursor/commands/improve-agent.md"]
)
def test_both_tools_run_the_same_protocol(wrapper: str) -> None:
    body = (ROOT / wrapper).read_text(encoding="utf-8")
    assert "interview/PROTOCOL.md" in body
    assert len(body.splitlines()) < 15, "a wrapper holds no behaviour of its own"


def test_cursor_is_pointed_at_the_session_rules() -> None:
    assert "CLAUDE.md" in (ROOT / ".cursor" / "rules" / "project.mdc").read_text(encoding="utf-8")


def test_the_protocol_names_every_command_it_relies_on() -> None:
    body = (ROOT / "interview" / "PROTOCOL.md").read_text(encoding="utf-8")
    assert "One question per message" in body
    assert "governance chain" in body
    for command in ("status", "session", "mark", "scan"):
        assert f"interview.py {command}" in body


def test_status_runs_against_a_fresh_knowledge_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    for fn in (
        interview.init,
        interview.load_coverage,
        interview.open_followups,
        interview.backlog_counts,
        interview.projects,
        interview.identifiers,
    ):
        monkeypatch.setattr(fn, "__defaults__", (tmp_path,))
    monkeypatch.setattr(interview, "KNOWLEDGE", tmp_path)
    assert interview.main(["status"]) == 0
    out = capsys.readouterr().out
    assert "first session" in out
    assert "focus: valuation/non-esop" in out
    assert "identifiers kept inside knowledge/" in out
    assert (tmp_path / "coverage.yaml").exists()
