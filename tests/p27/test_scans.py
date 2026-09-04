"""The conformance check and the adaptation bench: what a draft is scanned for, what the
gap report says, and the one thing the bench may never produce."""

from __future__ import annotations

import inspect
from pathlib import Path
from typing import Any

import pytest

from governance import AdaptationBench, ConformanceCheck, DraftHeld, GovernanceChain
from governance.candidate import Stage
from registries.errors import RegistryError
from tests.p27.conftest import (
    DRAFT_WITH_CLIENT_DATA,
    DRAFT_WITH_INJECTION,
    DROPPER,
    LAYER,
    OWNER,
    ROUGH_DRAFT,
    SKILL,
    ScriptedPort,
    adapted_answer,
    drop_draft,
)

GOVERNANCE_MODULES = (
    "governance.record",
    "governance.candidate",
    "governance.drop",
    "governance.conformance",
    "governance.adapt",
    "governance.sandbox",
    "governance.board",
    "governance.shadow",
    "governance.registry",
    "governance.chain",
)


def test_a_draft_carrying_client_data_is_held_and_reaches_nothing(
    chain: GovernanceChain, root: Path
) -> None:
    """Somebody will paste a real trial balance into an example sooner or later, and that
    must not quietly become a file in the repo."""
    dropped = chain.take(drop_draft(root, DRAFT_WITH_CLIENT_DATA), DROPPER)
    with pytest.raises(DraftHeld) as held:
        chain.scan(dropped, "skill_conformance")

    d = held.value.diagnostic
    assert d.code == "SKILL.CLIENT_DATA_IN_DRAFT"
    assert d.owner == "client-data" and "synthetic" in d.what_now
    assert "account number" in d.detail and "money over a thousand" in d.detail

    candidate = chain.candidate(dropped.candidate_id)
    assert not candidate.has(Stage.SCANNED), "a held draft has no scan behind it"
    assert candidate.stage is Stage.DROPPED
    held_entry = [e for e in chain.record.entries(dropped.candidate_id) if e.stage == "held"]
    assert len(held_entry) == 1
    assert "4100-01" in " ".join(held_entry[0].detail["client_data"])
    assert "hendersonmfg.com" in " ".join(held_entry[0].detail["client_data"])


def test_a_draft_carrying_an_instruction_to_a_model_is_held(
    chain: GovernanceChain, root: Path
) -> None:
    """A rough draft is a document from outside the system and meets the same boundary a
    client PDF meets."""
    dropped = chain.take(drop_draft(root, DRAFT_WITH_INJECTION), DROPPER)
    with pytest.raises(DraftHeld) as held:
        chain.scan(dropped, "skill_conformance")
    assert held.value.diagnostic.code == "INTAKE.INJECTION_DETECTED"
    assert "instruction aimed at a model" in held.value.diagnostic.detail
    assert not chain.candidate(dropped.candidate_id).has(Stage.SCANNED)


def test_the_gap_report_is_a_checklist_and_fixtures_are_not_on_the_benchs_half(
    chain: GovernanceChain, root: Path
) -> None:
    """It turns "make this fit" into a list. And it separates what a model can fill from
    what only a person can supply."""
    dropped = chain.take(drop_draft(root, ROUGH_DRAFT), DROPPER)
    report = chain.scan(dropped, "skill_conformance")

    assert not report.conforms
    named = {g.field for g in report.gaps}
    assert {"name", "version", "scope", "tools", "output_contract", "hitl"} <= named
    assert "fixtures" in named and "when not to use" in named

    (fixtures,) = [g for g in report.gaps if g.field == "fixtures"]
    assert fixtures.fixable_by_bench is False
    assert report.for_a_person == (fixtures,)
    assert len(report.for_the_bench) == len(report.gaps) - 1
    assert "[person] fixtures" in report.report()

    recorded = chain.record.entries(dropped.candidate_id)[-1]
    assert recorded.stage == str(Stage.SCANNED)
    assert recorded.detail["gap_report"]["conforms"] is False


def test_a_gap_report_names_a_tool_and_a_contract_that_do_not_exist(
    chain: GovernanceChain, root: Path
) -> None:
    draft = (
        "---\n"
        "name: invented\nversion: 0.1.0\nstatus: draft\nscope: valuation/atlantis\n"
        "title: Invented\ndescription: x\ntier: mid\ninputs: [a]\noutputs: [b]\n"
        "tools: [make_it_up]\ndata_sensitivity: whatever\nhitl: none\n"
        "output_contract: skills/invented@9.9.9\nfixtures: fixtures/skills/invented\n"
        "---\n\nWhen not to use: never. Escalate when unsure.\n"
    )
    dropped = chain.take(drop_draft(root, draft, "invented.md"), DROPPER)
    report = chain.scan(dropped, "skill_conformance")
    by_field = {g.field: g.why for g in report.gaps}
    assert "make_it_up" in by_field["tools"]
    assert "not pinned in the contract registry" in by_field["output_contract"]
    assert "valuation/atlantis" in by_field["scope"]
    assert "whatever" in by_field["data_sensitivity"]
    assert "fixtures" not in by_field, "this draft names a fixture set"


def test_the_bench_fills_the_gaps_and_asks_for_evidence(
    chain: GovernanceChain, root: Path, port: ScriptedPort
) -> None:
    dropped = chain.take(drop_draft(root), DROPPER)
    report = chain.scan(dropped, "skill_conformance")
    adapted = chain.adapt(report, OWNER)

    assert adapted.name == SKILL and adapted.layer == LAYER
    assert adapted.frontmatter["tools"] == ["timing_normalizer"]
    assert "shallowest layer" in adapted.scope_reasoning
    assert adapted.fixture_request.what and adapted.fixture_request.who
    assert adapted.skill_md().startswith("---\n")

    # What the bench was shown: the gaps, the contract and the tool namespace. Never a
    # client file, and the draft body arrives as data rather than as instruction.
    sent = port.sent()
    assert "## Gaps to fill" in sent and "output_contract" in sent
    assert "timing_normalizer" in sent
    assert "UNTRUSTED" in sent.upper()

    entry = chain.record.entries(dropped.candidate_id)[-1]
    assert entry.stage == str(Stage.ADAPTED)
    assert entry.detail["fixture_request"].startswith("three statements")


def test_the_bench_cannot_return_a_conforming_skill_without_a_fixture_request(
    chain: GovernanceChain, root: Path, port: ScriptedPort
) -> None:
    """The limit that matters. Without it the drop folder plus a helpful model is the
    route by which unvalidated logic reaches client work."""
    port.answers = [__import__("json").dumps(adapted_answer(fixture_request={}))]
    dropped = chain.take(drop_draft(root), DROPPER)
    report = chain.scan(dropped, "skill_conformance")

    with pytest.raises(RegistryError) as refused:
        chain.adapt(report, OWNER)
    assert "no fixture request" in refused.value.diagnostic.detail
    assert "may never produce" in refused.value.diagnostic.detail
    assert not chain.candidate(dropped.candidate_id).has(Stage.ADAPTED)


def test_the_bench_cannot_declare_a_tool_the_constraints_do_not_have(
    chain: GovernanceChain, root: Path, port: ScriptedPort
) -> None:
    answer = adapted_answer()
    answer["frontmatter"] = {**answer["frontmatter"], "tools": ["timing_normalizer", "shell"]}
    port.answers = [__import__("json").dumps(answer)]
    dropped = chain.take(drop_draft(root), DROPPER)
    report = chain.scan(dropped, "skill_conformance")

    with pytest.raises(RegistryError) as refused:
        chain.adapt(report, OWNER)
    assert "'shell'" in refused.value.diagnostic.detail
    assert "constraint registry" in refused.value.diagnostic.detail


def test_nothing_in_governance_writes_a_fixture(chain: GovernanceChain) -> None:
    """Evidence cannot be authored by the thing it vouches for.

    Structural rather than a promise: every call in the package that writes anything is
    found in the syntax tree, and there are exactly four modules that write - the record,
    the triage copy, the sandbox and the registry. None of them writes a fixture, and no
    callable in the package has one to write.
    """
    import ast

    writes = {"write_text", "write_bytes", "copy2", "open", "mkdir"}
    writers: dict[str, set[str]] = {}
    for name in GOVERNANCE_MODULES:
        module = __import__(name, fromlist=["x"])
        for node in ast.walk(ast.parse(inspect.getsource(module))):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in writes
            ):
                writers.setdefault(name, set()).add(node.func.attr)

    assert set(writers) == {
        "governance.record",
        "governance.drop",
        "governance.sandbox",
        "governance.registry",
    }, writers
    assert writers["governance.drop"] == {"copy2", "mkdir"}, "it copies; it moves nothing"

    # And nothing anywhere in the package is named for producing one.
    import governance

    named = [n for n in governance.__all__ if "fixture" in n.lower()]
    assert named == ["FixtureRequest"], named
    assert not [n for n in dir(AdaptationBench) if "fixture" in n.lower()]
    assert not [n for n in dir(ConformanceCheck) if "write" in n.lower()]


def test_governance_has_no_way_to_reach_client_data(chain: GovernanceChain) -> None:
    """The exit criterion. The isolation is that the connection does not exist: no vault,
    no engagement store, no storage port, no delivery. What governance sees is a draft, a
    registry and a masked payload."""
    forbidden = (
        "privacy.vault",
        "privacy.mask",
        "privacy.unmask",
        "intake.",
        "ports.storage",
        "ports.delivery",
        "deliver.",
        "precedent.",
    )
    for name in GOVERNANCE_MODULES:
        module = __import__(name, fromlist=["x"])
        imports = [
            line
            for line in inspect.getsource(module).splitlines()
            if line.startswith(("import ", "from "))
        ]
        for banned in forbidden:
            assert not [line for line in imports if banned in line], (name, banned)

    # And the graph says the same thing about the design.
    from graph.architecture_assertions import (
        assert_governance_never_reads_client_data,
        load_graph,
    )

    assert_governance_never_reads_client_data(load_graph())


def test_the_governance_scope_is_not_an_engagement(chain: GovernanceChain, store: Any) -> None:
    """A governance model call is metered under a run of its own, so its cost never lands
    on a client's engagement."""
    from governance.adapt import GOVERNANCE_RUN, GOVERNANCE_SCOPE

    run = store.run(GOVERNANCE_RUN)
    assert run.engagement_id == GOVERNANCE_SCOPE
    assert not GOVERNANCE_SCOPE[0].isupper(), "not shaped like an engagement id"
    assert "-" not in GOVERNANCE_SCOPE
