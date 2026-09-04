"""The Template Registry: introspects the workbook, names what is missing, refuses a cell."""

from __future__ import annotations

from pathlib import Path

import pytest

from deliver.registry import TemplateInputs, TemplateRegistry, declared_names
from graph.resolve import ResolvedScope, TemplateBinding
from harness.notice import notice_for
from registries.errors import RegistryError
from tests.p21.conftest import ROOT, TEMPLATE_FILE, TEMPLATE_KEY, TEMPLATE_VERSION, workbook_with


def test_the_template_on_disk_declares_every_required_input_and_registers(
    registry: TemplateRegistry,
) -> None:
    template = registry.get(TEMPLATE_KEY)
    assert template.content_hash.startswith("sha256:")
    assert set(template.inputs.required) <= template.named_ranges
    assert {"Template_Version", "Run_Id"} <= template.named_ranges
    assert len(template.inputs.required) == 43
    assert template.inputs.optional == ("WACC_Terminal", "NWC_Target", "EV_EBITDA_Multiple")


def test_a_template_declaring_41_of_43_required_inputs_fails_naming_the_two(
    tmp_path: Path, schema: TemplateInputs
) -> None:
    """The exit criterion, as the blueprint's own example: expected 43, found 41, and
    the two missing ranges named in the diagnostic - not discovered as empty cells."""
    names = {n: f"Inputs!$B${i + 5}" for i, n in enumerate(schema.required)}
    del names["Owner_Comp_Benchmark"]
    del names["Other_Opex_FY3"]
    names["Template_Version"] = "Inputs!$B$2"
    names["Run_Id"] = "Inputs!$B$3"
    path = tmp_path / TEMPLATE_FILE
    path.write_bytes(workbook_with(names))

    with pytest.raises(RegistryError) as refused:
        TemplateRegistry(templates_dir=tmp_path).register(TEMPLATE_FILE, TEMPLATE_VERSION)
    d = refused.value.diagnostic
    assert d.code == "CONFIG.TEMPLATE_INPUTS_MISSING"
    assert d.owner == "config"
    assert d.expected == "43" and d.found == "41"
    assert "Other_Opex_FY3" in d.delta and "Owner_Comp_Benchmark" in d.delta
    assert "Add the named ranges" in d.what_now or "add the named ranges" in d.what_now
    fixed = notice_for(d, step="Template Registry", engagement="HEND-2026-04")
    assert fixed.kind == "config_error"


@pytest.mark.parametrize("address", ["B44", "$B$44", "AA7", "a1"])
def test_a_binding_to_a_cell_address_is_rejected_at_registration(
    address: str, tmp_path: Path, schema: TemplateInputs
) -> None:
    """The exit criterion. B44 is not a contract: one inserted row shifts every mapping
    below it into a plausibly wrong deliverable, so the address never gets that far."""
    names = {n: f"Inputs!$B${i + 5}" for i, n in enumerate(schema.required)}
    names.update({"Template_Version": "Inputs!$B$2", "Run_Id": "Inputs!$B$3"})
    (tmp_path / TEMPLATE_FILE).write_bytes(workbook_with(names))
    with pytest.raises(RegistryError) as refused:
        TemplateRegistry(templates_dir=tmp_path).register(
            TEMPLATE_FILE, TEMPLATE_VERSION, bindings={"Revenue_FY1": address}
        )
    assert refused.value.diagnostic.code == "CONFIG.CELL_ADDRESS_BINDING"
    assert refused.value.diagnostic.owner == "config"


def test_a_workbook_whose_own_name_is_a_cell_address_is_refused(
    tmp_path: Path, schema: TemplateInputs
) -> None:
    names = {n: f"Inputs!$B${i + 5}" for i, n in enumerate(schema.required)}
    names.update({"Template_Version": "Inputs!$B$2", "Run_Id": "Inputs!$B$3", "C9": "Inputs!$C$9"})
    (tmp_path / TEMPLATE_FILE).write_bytes(workbook_with(names))
    with pytest.raises(RegistryError) as refused:
        TemplateRegistry(templates_dir=tmp_path).register(TEMPLATE_FILE, TEMPLATE_VERSION)
    assert refused.value.diagnostic.code == "CONFIG.CELL_ADDRESS_BINDING"


def test_introspection_reads_the_workbook_not_the_schema() -> None:
    data = (ROOT / "templates" / TEMPLATE_FILE).read_bytes()
    names = declared_names(data)
    assert "Revenue_FY1" in names and "Template_Version" in names
    assert "Nothing_Like_This" not in names


def test_the_scope_binding_resolves_to_the_registered_template(
    registry: TemplateRegistry, scope: ResolvedScope
) -> None:
    """The five-layer walk bound the ESOP segment to its own model; the registry hands
    back what that binding names, pinned by hash."""
    assert scope.template is not None and scope.template.file == TEMPLATE_FILE
    template = registry.resolve(scope.template)
    assert template.key == TEMPLATE_KEY
    assert template.read() == (ROOT / "templates" / TEMPLATE_FILE).read_bytes()


def test_an_unregistered_or_unbound_template_is_the_fixed_refusal(
    registry: TemplateRegistry,
) -> None:
    with pytest.raises(RegistryError) as missing:
        registry.resolve(TemplateBinding("corporate-finance/_group", "CF_LBO_Model_v3.xlsx", "3.1"))
    assert missing.value.diagnostic.code == "DELIVER.TEMPLATE_MISSING"
    with pytest.raises(RegistryError) as unbound:
        registry.resolve(None)
    assert unbound.value.diagnostic.code == "DELIVER.TEMPLATE_MISSING"


def test_a_master_that_changed_under_its_registration_is_refused(
    tmp_path: Path, schema: TemplateInputs
) -> None:
    names = {n: f"Inputs!$B${i + 5}" for i, n in enumerate(schema.required)}
    names.update({"Template_Version": "Inputs!$B$2", "Run_Id": "Inputs!$B$3"})
    path = tmp_path / TEMPLATE_FILE
    path.write_bytes(workbook_with(names))
    reg = TemplateRegistry(templates_dir=tmp_path)
    template = reg.register(TEMPLATE_FILE, TEMPLATE_VERSION)
    path.write_bytes(workbook_with(names, {"Inputs!D1": "edited after registration"}))
    with pytest.raises(RegistryError) as refused:
        template.read()
    assert refused.value.diagnostic.code == "DELIVER.TEMPLATE_MISSING"


def test_the_synthetic_templates_match_their_schemas() -> None:
    """The committed workbooks are what the generator makes from the input schemas."""
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "synthesize_templates.py"), "--check"],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    assert result.returncode == 0, result.stdout + result.stderr
