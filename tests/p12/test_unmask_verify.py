"""Unmask, the three integrity assertions, and the graph assertion that no model is near.

Three exit criteria. A token from another engagement fails the integrity check; zero
residual tokens survive into anything released; and a graph assertion proves no llm-exec
node reaches the vault. The last one already exists as invariant 1 - here it is named,
run, and shown to be the invariant that fires when the graph is broken in that place.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from ops.run_store import SqlRunStore
from privacy.mask import Masker
from privacy.unmask import Unmasked, Unmasker
from privacy.vault import MaskVault
from privacy.verify import IntegrityFailed, UnmaskVerify
from tests.p12.conftest import ENGAGEMENT, HENDERSON, OTHER, TRIAL_BALANCE

ROOT = Path(__file__).resolve().parents[2]


# ----------------------------------------------------------------- unmask


def test_a_masked_payload_round_trips(masker: Masker, unmasker: Unmasker) -> None:
    masked = masker.mask(TRIAL_BALANCE, ENGAGEMENT, HENDERSON)
    back = unmasker.unmask(masked.text, ENGAGEMENT)
    assert back.text.lower() == TRIAL_BALANCE.lower()
    assert back.found == back.resolved == frozenset(masked.tokens)
    assert back.unresolved == frozenset()


def test_unmasking_is_deterministic_python() -> None:
    """No model performs re-identification. Nothing in privacy/ imports a port to one."""
    for name in ("mask", "vault", "unmask", "verify", "payload_scan"):
        tree = ast.parse((ROOT / "privacy" / f"{name}.py").read_text(encoding="utf-8"))
        imported = {
            (n.module or "") if isinstance(n, ast.ImportFrom) else n.names[0].name
            for n in ast.walk(tree) if isinstance(n, ast.Import | ast.ImportFrom)
        }
        for forbidden in ("ports.llm", "harness.door", "anthropic"):
            assert not any(i.startswith(forbidden) for i in imported), f"{name} imports {forbidden}"


def test_no_skill_has_an_unmask_tool() -> None:
    """The six-name namespace has no `lookup_real_name`, and neither does any allowlist."""
    from registries.constraints import ConstraintRegistry

    constraints = ConstraintRegistry.load()
    for name in constraints.tools:
        assert "unmask" not in name and "real" not in name and "vault" not in name
    for tools in constraints.tool_allowlists.values():
        assert not any("unmask" in t or "vault" in t for t in tools)


def test_a_token_from_another_engagement_is_left_in_place(
    masker: Masker, unmasker: Unmasker
) -> None:
    """The unmasker resolves only what the vault holds for this engagement. A foreign
    token stays exactly as found and is reported, so the check that follows can name it."""
    foreign = masker.mask("Bob Henderson", OTHER, HENDERSON)
    token = foreign.substitutions["Bob Henderson"]
    back = unmasker.unmask(f"owner draw {token}", ENGAGEMENT)
    assert token in back.text
    assert back.unresolved == frozenset({token})


# ------------------------------------------------------ the three assertions


def test_a_clean_unmask_passes_and_is_recorded(
    masker: Masker, unmasker: Unmasker, verifier: UnmaskVerify, vault: MaskVault,
    started: str, store: SqlRunStore,
) -> None:
    masked = masker.mask(TRIAL_BALANCE, ENGAGEMENT, HENDERSON, run_id=started)
    back = unmasker.unmask(masked.text, ENGAGEMENT)
    result = verifier.verify(back, vault.issued(ENGAGEMENT), run_id=started, step_id="release")
    assert result.passed
    assert result.checked == 2 * len(masked.tokens)
    events = [e for e in store.events(started) if e.type == "guard.unmask_verify.pass"]
    assert len(events) == 1
    assert events[0].payload["checked"] == result.checked


def test_a_token_issued_under_a_different_engagement_fails_the_integrity_check(
    masker: Masker, unmasker: Unmasker, verifier: UnmaskVerify, vault: MaskVault,
    started: str, store: SqlRunStore,
) -> None:
    """The exit criterion, and the assertion that matters most: a token resolving to a
    value from another engagement is the cross-client failure this whole band exists to
    prevent."""
    own = masker.mask("Operating Account", ENGAGEMENT, HENDERSON, run_id=started)
    foreign = masker.mask("Bob Henderson", OTHER, HENDERSON)
    stray = foreign.substitutions["Bob Henderson"]

    back = unmasker.unmask(f"{own.text} paid to {stray}", ENGAGEMENT)
    with pytest.raises(IntegrityFailed) as raised:
        verifier.verify(back, vault.issued(ENGAGEMENT), run_id=started)

    assert raised.value.diagnostic.code == "PRIVACY.TOKEN_CROSS_ENGAGEMENT"
    assert raised.value.result.foreign == (stray,)
    fails = [e for e in store.events(started) if e.type == "guard.unmask_verify.fail"]
    assert fails[0].diagnostic_code == "PRIVACY.TOKEN_CROSS_ENGAGEMENT"


def test_a_value_resolved_that_was_never_issued_here_fails_even_if_it_looks_fine(
    verifier: UnmaskVerify,
) -> None:
    """The third assertion on its own, which is why the check is a separate node: hand
    it an Unmasked that claims to have resolved a token this engagement never issued, and
    it refuses regardless of what the text looks like."""
    claimed = Unmasked(
        text="owner draw 36,000.00", engagement_id=ENGAGEMENT,
        found=frozenset({"[[PERSON_1]]"}), resolved=frozenset({"[[PERSON_1]]"}),
    )
    result = UnmaskVerify.check(claimed, issued=())
    assert not result.passed
    assert result.code == "PRIVACY.TOKEN_CROSS_ENGAGEMENT"
    assert result.foreign == ("[[PERSON_1]]",)


def test_a_residual_token_in_the_output_fails(
    masker: Masker, verifier: UnmaskVerify, vault: MaskVault, started: str
) -> None:
    """The exit criterion: zero residual mask tokens in any released artifact. An
    Unmasked whose text still carries a token did not finish, and does not release."""
    masked = masker.mask(TRIAL_BALANCE, ENGAGEMENT, HENDERSON, run_id=started)
    half_done = Unmasked(
        text=masked.text, engagement_id=ENGAGEMENT,
        found=frozenset(masked.tokens), resolved=frozenset(masked.tokens),
    )
    with pytest.raises(IntegrityFailed) as raised:
        verifier.verify(half_done, vault.issued(ENGAGEMENT), run_id=started)
    assert raised.value.diagnostic.code == "GUARD.UNMASK_RESIDUAL"
    assert set(raised.value.result.residual) == set(masked.tokens)


def test_a_purged_token_fails_as_unresolved(
    masker: Masker, unmasker: Unmasker, verifier: UnmaskVerify, vault: MaskVault, started: str
) -> None:
    """Retention ran, the entry is gone, the token is still in a document. Not a
    cross-engagement failure - it was issued here - but it never resolved, and the check
    says which of the three it is."""
    from datetime import UTC, datetime, timedelta

    masked = masker.mask("Operating Account", ENGAGEMENT, HENDERSON, run_id=started)
    issued_before = vault.issued(ENGAGEMENT)
    vault.purge_expired(now=datetime.now(tz=UTC) + timedelta(days=10_000))

    back = unmasker.unmask(masked.text, ENGAGEMENT)
    with pytest.raises(IntegrityFailed) as raised:
        verifier.verify(back, issued_before, run_id=started)
    assert raised.value.diagnostic.code == "GUARD.UNMASK_RESIDUAL"
    assert raised.value.result.unresolved == tuple(masked.tokens)


def test_the_check_reads_sets_not_the_masker(verifier: UnmaskVerify) -> None:
    """Separate from the masker on purpose: a masker that silently no-ops and a checker
    that silently passes are the same bug. The checker takes sets and a string, and can
    be handed a wrong set - which the tests above do."""
    import inspect

    params = set(inspect.signature(UnmaskVerify.check).parameters)
    assert params == {"unmasked", "issued"}


def test_a_verify_over_nothing_says_it_checked_nothing(verifier: UnmaskVerify) -> None:
    empty = Unmasked(text="no tokens here", engagement_id=ENGAGEMENT,
                     found=frozenset(), resolved=frozenset())
    result = UnmaskVerify.check(empty, issued=())
    assert result.passed and result.checked == 0


# ----------------------------------------------------- the graph assertion


def test_a_graph_assertion_proves_no_llm_node_reaches_the_vault() -> None:
    """The exit criterion. Invariant 1 in P07's suite, run here against the current
    graph, and shown to be the one that fires when a model node is put next to the
    vault."""
    import copy

    from graph.architecture_assertions import ALL, ArchGraph, check_all, load_graph

    graph = load_graph()
    first = ALL[0]
    assert first.name == "assert_no_model_reaches_the_vault"
    first.check(graph)

    for neighbour in graph.neighbours("mask_vault"):
        assert graph[neighbour]["exec"] == "code", f"{neighbour} touches the vault"
    assert set(graph.neighbours("mask_vault")) == {"mask_engine", "secrets_port", "unmask_engine"}

    broken = ArchGraph(nodes=copy.deepcopy(graph.nodes), edges=graph.edges)
    broken.nodes["unmask_engine"]["exec"] = "llm"
    assert 1 in {inv.number for inv, _ in check_all(broken)}


def test_the_vault_has_exactly_the_two_edges_the_blueprint_says() -> None:
    """The Masking Engine writes it, the Unmasking Engine reads it, the Secrets Port
    keys it. Nothing else."""
    from graph.architecture_assertions import load_graph

    graph = load_graph()
    assert {e.src for e in graph.inbound("mask_vault")} == {"mask_engine", "secrets_port"}
    assert {e.dst for e in graph.out("mask_vault")} == {"unmask_engine"}
