"""A failing preflight check blocks activation of that engagement rather than failing
later in a run, and every failure carries a code, an owner and a what_now."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from admin import AdminConsole, AdminRefused, Preflight
from admin.preflight import CHECKS
from intake.roster import RosterState
from registries.diagnostics import DiagnosticsRegistry
from tests.p24.conftest import HEND, NOVK, WHO, Clock, entry, profile_for


def test_every_check_in_the_table_runs_and_a_clean_setup_passes_them_all(
    console: AdminConsole, henderson: Any
) -> None:
    """The report is the table, in order. How many there are is the blueprint's business,
    asserted once in tests/p30 - here what matters is that none of them is declared and
    then not run, which is how a check quietly stops covering anything."""
    report = console.check(HEND)
    assert [c.id for c in report.checks] == [c[0] for c in CHECKS]
    assert len(set(CHECKS)) == len(CHECKS), "a check id is declared twice"
    assert report.passed, report.report()
    assert all(c.status == "pass" for c in report.checks), report.report()
    by_id = {c.id: c for c in report.checks}
    assert by_id["credentials"].detail.endswith("presence only, never the value")
    assert by_id["bindings"].detail.startswith("1 of 1")
    assert "probe written" in by_id["destinations_writable"].detail
    assert "firm ceiling $40.00" in by_id["recipes_and_budgets"].detail


def test_a_failing_check_blocks_activation_and_names_what_to_fix(
    console: AdminConsole, preflight: Preflight
) -> None:
    """No profile: three skills read it as a required input, so the engagement does
    not go active. The refusal is the diagnostic, with the owner set to config."""
    console.register_engagement(entry(), profile=None, who=WHO, reason="letter signed")
    with pytest.raises(AdminRefused) as refused:
        console.activate(HEND, who=WHO, reason="go live")
    (d,) = refused.value.diagnostics
    assert d.code == "CONFIG.PROFILE_INCOMPLETE" and d.owner == "config"
    assert "no engagement profile recorded" in d.detail and d.what_now
    assert console.roster.get(HEND).state is RosterState.PAUSED, "nothing changed"

    console.set_profile(HEND, profile_for(HEND), who=WHO, reason="profile recorded")
    assert console.activate(HEND, who=WHO, reason="go live").state is RosterState.ACTIVE


def test_every_preflight_failure_carries_a_code_an_owner_and_a_what_now(
    console: AdminConsole, preflight: Preflight, environment: dict[str, Path]
) -> None:
    """Break the setup six ways at once and read every failure back as a diagnostic."""
    registry = DiagnosticsRegistry.load()
    console.register_engagement(
        entry(budget_usd=99.0, destination_id="d-nowhere"),
        profile=profile_for(HEND, "valuation/esop/non-repeat"),  # not the roster's scope
        who=WHO,
        reason="setup",
    )
    console.record_credential(
        "BOX_CLIENT_SECRET", "delivery", expires_on="2026-01-01", who=WHO, reason="rotated"
    )
    console.bind_model(
        "valuation/esop/_segment", "Ghost_Model_v1.xlsx", "1.0", why="", who=WHO, reason="typo"
    )
    (environment["inbox"] / "Clients").rename(environment["inbox"] / "Gone")

    report = console.check(HEND)
    assert not report.passed
    codes = {f.diagnostic.code for f in report.failures}
    assert codes >= {
        "CONFIG.PATH_UNREADABLE",
        "SCOPE.MISSING_CREDENTIAL",
        "CONFIG.PROFILE_INCOMPLETE",
        "CONFIG.BINDING_MISSING",
        "CONFIG.TEMPLATE_UNREGISTERED",
        "CONFIG.BUDGET_ABOVE_CEILING",
    }
    for failure in report.failures:
        d = failure.diagnostic
        assert d.code in registry, d.code
        assert d.owner == "config" and d.what_now and d.detail, d
        assert d.code.split(".")[0] in ("CONFIG", "SCOPE", "INTAKE")
    blocking = report.blocking(HEND)
    assert {f.diagnostic.code for f in blocking} == codes, "every one of these blocks it"
    with pytest.raises(AdminRefused) as refused:
        console.activate(HEND, who=WHO, reason="go live")
    assert len(refused.value.diagnostics) == len(blocking)
    assert "watch w-val" in str(
        next(d for d in refused.value.diagnostics if d.code.endswith("PATH_UNREADABLE"))
    )


def test_a_setup_failure_is_scoped_to_the_engagement_it_touches(
    console: AdminConsole, henderson: Any
) -> None:
    """Henderson's setup is clean; Novak's budget is not. Novak is blocked, Henderson
    is not, and the environment-wide checks say pass."""
    console.register_engagement(
        entry(
            NOVK,
            client="Novak Industries",
            scope_path="valuation/non-esop/non-repeat",
            folder="Novak Industries/2026 Valuation",
            budget_usd=1000.0,
        ),
        profile=profile_for(NOVK, "valuation/non-esop/non-repeat"),
        who=WHO,
        reason="setup",
    )
    report = console.check(NOVK)
    (failure,) = report.failures
    assert failure.check == "recipes_and_budgets" and failure.engagement_ids == (NOVK,)
    assert report.blocking(HEND) == () and report.blocking(NOVK) == (failure,)
    assert console.activate(HEND, who=WHO, reason="go").state is RosterState.ACTIVE
    with pytest.raises(AdminRefused):
        console.activate(NOVK, who=WHO, reason="go")


def test_a_template_edited_in_place_fails_the_hash_check(
    console: AdminConsole, henderson: Any, preflight: Preflight, tmp_path: Path
) -> None:
    registered = preflight.templates.get("Chartwell_ESOP_Model_v9@9.4")
    edited = tmp_path / "edited.xlsx"
    edited.write_bytes(registered.path.read_bytes() + b"\x00")
    from deliver.registry import RegisteredTemplate

    preflight.templates._registered[registered.key] = RegisteredTemplate(  # noqa: SLF001
        **{**registered.__dict__, "path": edited}
    )
    report = console.check(HEND)
    (failure,) = report.failures
    assert failure.diagnostic.code == "CONFIG.TEMPLATE_HASH_MISMATCH"
    assert failure.diagnostic.owner == "config" and failure.engagement_ids == (HEND,)
    assert "not the registered bytes" in failure.diagnostic.detail


def test_credentials_are_checked_for_presence_and_expiry_never_value(
    console: AdminConsole, henderson: Any, clock: Clock, environment: dict[str, Path]
) -> None:
    console.record_credential(
        "ANTHROPIC_API_KEY", "model access", expires_on="2026-09-20", who=WHO, reason="rotated"
    )
    report = console.check()
    cred = next(c for c in report.checks if c.id == "credentials")
    assert cred.status == "warn" and "within 30 days" in cred.failures[0].diagnostic.detail
    assert report.blocking(HEND) == (), "a warning blocks nothing"
    clock.advance(days=30)
    cred = next(c for c in console.check().checks if c.id == "credentials")
    assert cred.status == "fail" and cred.failures[0].diagnostic.code == "CONFIG.CREDENTIAL_EXPIRED"
    assert "not-a-real-key" not in report.report() + cred.detail + str(cred.failures)
    assert console.credential_present("ANTHROPIC_API_KEY") is True
    assert console.credential_present("NOT_THERE") is False


def test_unclaimed_folders_warn_and_never_guess(
    console: AdminConsole, henderson: Any, preflight: Preflight
) -> None:
    assert preflight.intake_store is not None
    preflight.intake_store.report_unclaimed(
        "w-val", "Pinecrest Holdings/2026 ESOP", 3, "2026-09-04T08:00:00Z"
    )
    report = console.check()
    check = next(c for c in report.checks if c.id == "unclaimed_folders")
    assert check.status == "warn" and "Pinecrest" in check.failures[0].diagnostic.detail
    assert check.failures[0].diagnostic.code == "INTAKE.NO_ENGAGEMENT"
    assert report.passed and report.blocking(HEND) == ()


def test_preflight_is_not_part_of_any_run(
    console: AdminConsole, henderson: Any, preflight: Preflight
) -> None:
    """It emits into no event stream: the store holds no run and no event after a
    full check, and the module never imports the bus."""
    import inspect

    import admin.preflight as module

    console.check(HEND)
    store = console.roster._store  # noqa: SLF001
    assert store.runs() == ()
    source = inspect.getsource(module)
    assert "EventBus" not in source and "emit(" not in source
