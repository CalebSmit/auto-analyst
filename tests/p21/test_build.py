"""Model-load emits a mapping; the builder resolves it; the writer performs every write;
the lock brackets it; QC opens the result."""

from __future__ import annotations

import copy
from typing import Any

import pytest

from graph.compile import Step
from graph.execute import Blocked
from graph.resolve import ResolvedScope
from guards.numeric_lock import numeric_tokens
from harness.policy import PolicyDenied
from harness.procedures.model_load import ProposalRefused
from ops.run_store import SqlRunStore
from registries.contracts import ContractRegistry
from registries.errors import RegistryError
from registries.skills import SkillTree
from tests.p21.conftest import (
    TEMPLATE_KEY,
    TEMPLATE_VERSION,
    ProposalPort,
    build,
    dispatch,
    events_of,
    mapping_for,
    named_values,
    sheet_values,
)
from tools.write_template import write_template

CONTRACT = "skills/model-load@1.0.0"


# ------------------------------------------------------------- the skill


def test_model_load_emits_a_mapping_through_the_dispatcher_and_writes_nothing(
    world: dict[str, Any],
    model_step: Step,
    scope: ResolvedScope,
    store: SqlRunStore,
    contracts: ContractRegistry,
) -> None:
    port = ProposalPort(world["proposal"])
    done = dispatch(world, model_step, scope, port)
    assert done.skill == "model-load@0.1.0"
    assert contracts.check(CONTRACT, done.output) == ()
    mapping = done.output["template_mapping"]
    assert mapping["template_version"] == TEMPLATE_VERSION
    assert len(mapping["bindings"]) == 43 and mapping["unmapped_template_inputs"] == []
    assert {u["figure_ref"] for u in mapping["unrouted_upstream_figures"]} >= {
        "timing:Officer bonus:FY2023",
        "timing:Legal settlement:FY2024",
    }
    called = [e.payload["tool"] for e in events_of(store, world["run_id"], "tool.called")]
    assert called == ["template_schema_lookup"], "one gated read of the pinned schema"
    user = port.requests[0].messages[0].content
    payload = user.split("=== payload:", 1)[1]
    assert '"Revenue_FY1"' in payload and "timing:Revenue:FY2023" in payload
    assert '"value"' not in payload and "4020000" not in payload


def test_the_schema_lookup_is_pinned_to_the_runs_template(world: dict[str, Any]) -> None:
    tools = world["tools_for"]()
    assert tools.names() == ("template_schema_lookup",)
    with pytest.raises(PolicyDenied) as denied:
        tools["template_schema_lookup"](
            engagement_id=tools.engagement_id, version="Chartwell_Master_Model_v14@14.2"
        )
    assert denied.value.decision.predicate == "pinned_versions_only"


@pytest.mark.parametrize("how", ["undeclared_input", "unknown_ref", "bound_twice"])
def test_a_routing_the_template_or_the_catalogue_does_not_know_is_refused(
    world: dict[str, Any], how: str
) -> None:
    proposal = copy.deepcopy(world["proposal"])
    if how == "undeclared_input":
        proposal["bindings"][0]["named_range"] = "Nothing_Like_This"
    elif how == "unknown_ref":
        proposal["bindings"][0]["figure_ref"] = "timing:Invented:FY2023"
    else:
        proposal["bindings"][1]["named_range"] = proposal["bindings"][0]["named_range"]
    with pytest.raises(ProposalRefused):
        world["procedure"].apply(proposal, world["tools_for"](), world["inputs"], "pin")


def test_a_required_input_the_proposal_forgot_is_listed_as_unmapped(world: dict[str, Any]) -> None:
    proposal = copy.deepcopy(world["proposal"])
    dropped = proposal["bindings"].pop()
    out = world["procedure"].apply(proposal, world["tools_for"](), world["inputs"], "pin")
    unmapped = out["template_mapping"]["unmapped_template_inputs"]
    assert unmapped == [{"named_range": dropped["named_range"], "why": "not in the proposal"}]


def test_a_cell_address_destination_is_refused_by_the_contract_before_any_tool_runs(
    world: dict[str, Any], model_step: Step, scope: ResolvedScope, store: SqlRunStore
) -> None:
    from guards import GuardFailed

    proposal = copy.deepcopy(world["proposal"])
    proposal["bindings"][0]["named_range"] = "B44"
    with pytest.raises(GuardFailed) as refused:
        dispatch(world, model_step, scope, ProposalPort(proposal))
    assert refused.value.diagnostic.code == "SKILL.SCHEMA_INVALID"
    assert events_of(store, world["run_id"], "tool.called") == []


# ------------------------------------------------------------- the builder and the writer


def test_the_builder_writes_every_binding_by_named_range_and_the_lock_holds(
    world: dict[str, Any], store: SqlRunStore
) -> None:
    built = build(world)
    assert built.template_key == TEMPLATE_KEY and built.lock.passed
    assert len(built.writes) == 43
    values = named_values(built.data, list(built.writes))
    for name, value in built.writes.items():
        assert values[name] == value, name
    assert values["Revenue_FY1"] == 4_020_000.0
    assert values["Officer_Comp_FY3"] == 256_620.0
    assert values["Owner_Comp_Benchmark"] == 285_000.0
    stamps = named_values(built.data, ["Template_Version", "Run_Id"])
    assert stamps == {"Template_Version": TEMPLATE_VERSION, "Run_Id": world["run_id"]}
    assert numeric_tokens(built.locked_text)
    assert [e for e in store.events(world["run_id"]) if e.node_id == "numeric_lock"]
    assert events_of(store, world["run_id"], "model.built")


def test_formulas_names_and_the_master_survive_the_write(world: dict[str, Any]) -> None:
    built = build(world)
    hist = sheet_values(built.data, "Historicals")
    assert hist["B2"] == "=Revenue_FY1" and hist["D16"] == "=Revenue_FY3-COGS_FY3"
    assert world["template"].read() == world["template"].path.read_bytes(), (
        "the master is untouched"
    )
    assert built.data != world["template"].read()


def test_the_writer_refuses_a_destination_the_mapping_schema_does_not_declare(
    world: dict[str, Any],
) -> None:
    template = world["template"]
    with pytest.raises(RegistryError) as refused:
        write_template(
            template.read(),
            {"Revenue_FY1": 1.0, "Hallucinated_Range": 2.0},
            template.inputs.declared,
            {"Template_Version": "x", "Run_Id": "y"},
        )
    assert refused.value.diagnostic.code == "DELIVER.WRITE_FAILED"
    with pytest.raises(RegistryError) as cell:
        write_template(template.read(), {"B44": 1.0}, {"B44"}, {})
    assert cell.value.diagnostic.code == "CONFIG.CELL_ADDRESS_BINDING"
    with pytest.raises(RegistryError) as stamp:
        write_template(
            template.read(),
            {"Template_Version": "9.9"},
            template.inputs.declared | {"Template_Version"},
            {"Template_Version": "9.4"},
        )
    assert "stamp" in stamp.value.diagnostic.detail


def test_a_required_input_left_unmapped_stops_the_build_for_a_person(world: dict[str, Any]) -> None:
    mapping = mapping_for(world)
    mapping["template_mapping"]["bindings"] = [
        b for b in mapping["template_mapping"]["bindings"] if b["named_range"] != "Rent_FY2"
    ]
    mapping["template_mapping"]["unmapped_template_inputs"].append(
        {"named_range": "Rent_FY2", "why": "test"}
    )
    with pytest.raises(Blocked) as blocked:
        build(world, mapping)
    assert blocked.value.kind == "unmapped_inputs_require_review"
    assert "Rent_FY2" in blocked.value.subject


def test_a_figure_at_the_wrong_scale_is_refused_not_restated(world: dict[str, Any]) -> None:
    figures = dict(world["inputs"].figures())
    original = figures["timing:Revenue:FY2023"]
    assert isinstance(original, dict)
    figure = dict(original)
    figure["scale"] = 1000
    figures["timing:Revenue:FY2023"] = figure
    with pytest.raises(RegistryError) as refused:
        world["builder"].build(
            mapping_for(world),
            figures,
            world["template"],
            run_id=world["run_id"],
            engagement_id="X",
        )
    assert "restating is arithmetic" in refused.value.diagnostic.detail


# ------------------------------------------------------------- the skill file


def test_the_skill_file_is_written_and_never_writes_a_cell(tree: SkillTree) -> None:
    skill = next(s for s in tree.all() if s.name == "model-load")
    assert skill.status == "draft" and skill.scripts == ()
    body = tree.body(skill)
    flat = " ".join(body.lower().split())
    assert "you emit a mapping; you never write a cell and you never state a value" in flat
    assert "## Procedure" in body and "Skeleton" not in body
    reference = tree.reference(skill, "template-input-map.md")
    assert "Placeholder" not in reference and "Officer_Comp" in reference
