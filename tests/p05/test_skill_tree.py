"""The Skill Tree: thirteen skeletons, laid out the way the blueprint lays them out.

Half of these compare the tree against something outside it - the blueprint, the
constraint registry, the contract registry. That is the point. A skill tree that agrees
only with itself is a tree that has quietly diverged from every other part of the system
that has an opinion about it.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from registries.constraints import ConstraintRegistry
from registries.contracts import ContractRegistry
from registries.errors import RegistryError
from registries.skills import REQUIRED_FRONTMATTER, SkillTree
from tests.p05.conftest import skill as make_skill

ROOT = Path(__file__).resolve().parents[2]
SKILLS_DIR = ROOT / "skills"


def test_the_tree_holds_the_thirteen_skills_the_blueprint_declares(
    tree: SkillTree, blueprint_skill_scopes: dict[str, str]
) -> None:
    assert len(tree) == 13
    assert {s.name for s in tree.all()} == set(blueprint_skill_scopes)


def test_every_skill_sits_at_the_layer_the_blueprint_puts_it_at(
    tree: SkillTree, blueprint_skill_scopes: dict[str, str]
) -> None:
    """The layer is the whole design. A skill written one level too deep is invisible to
    every scope that should have had it, and nothing else fails."""
    assert {s.name: s.layer for s in tree.all()} == blueprint_skill_scopes


def test_the_layers_in_use_are_the_five_the_order_admits(tree: SkillTree) -> None:
    assert set(tree.layers()) == {
        "_firm",
        "valuation/_group",
        "valuation/_repeat",
        "valuation/_non-repeat",
        "valuation/esop/_segment",
    }


def test_every_skill_declares_everything_it_must(tree: SkillTree) -> None:
    """Each required field is something the Policy Gate or the dispatcher enforces
    later. A skill missing one is not a skill with a gap - it is a skill nothing can be
    enforced against."""
    for skill in tree.all():
        for field in REQUIRED_FRONTMATTER:
            assert getattr(skill, "layer" if field == "scope" else field), (
                f"{skill.name} declares no {field}"
            )


def test_every_skill_is_masked_only(tree: SkillTree) -> None:
    """`masked_only` unless there is a stated reason for anything else. There is no
    stated reason anywhere in the tree today, so this is a real assertion rather than a
    restatement of the default."""
    assert {s.data_sensitivity for s in tree.all()} == {"masked_only"}


def test_the_tools_a_skill_declares_are_the_ones_the_constraints_allow(
    tree: SkillTree, constraints: ConstraintRegistry
) -> None:
    """Two files, written in two phases, that have to agree. The SKILL.md is what a
    reader believes; constraints.yaml is what the Policy Gate enforces. A divergence
    means a skill that reads as though it may call something it cannot."""
    for skill in tree.all():
        assert set(skill.tools) == set(constraints.tools_for(skill.name)), (
            f"{skill.name}: SKILL.md says {skill.tools}, constraints.yaml says "
            f"{constraints.tools_for(skill.name)}"
        )


def test_every_skill_names_a_registered_output_contract(
    tree: SkillTree, contracts: ContractRegistry
) -> None:
    for skill in tree.all():
        assert skill.output_contract in contracts.ids(), (
            f"{skill.name} names {skill.output_contract}, which the contract registry "
            f"does not pin"
        )


def test_every_declared_reference_exists_on_disk(tree: SkillTree) -> None:
    """A reference the frontmatter names and the disk does not have is a skill that
    fails on dispatch, in P18, rather than here."""
    for skill in tree.all():
        folder = ROOT / Path(skill.path).parent
        for ref in skill.references:
            assert (folder / "references" / ref).is_file(), f"{skill.name} -> {ref}"


# The skills a phase has written a procedure for. Everything else is a skeleton until
# its phase lands, and a skeleton that claimed otherwise would be dispatchable with no
# procedure to run.
WRITTEN = {"timing-normalization": "P18"}


def test_every_skill_is_a_skeleton_and_says_so_until_its_phase_writes_it(tree: SkillTree) -> None:
    for skill in tree.all():
        body = (ROOT / skill.path).read_text(encoding="utf-8").split("---", 2)[2]
        if skill.name in WRITTEN:
            assert skill.status == "draft", f"{skill.name} was written in {WRITTEN[skill.name]}"
            assert "Skeleton" not in body and "## Procedure" in body
        else:
            assert skill.status == "skeleton", skill.name
            assert "Skeleton" in body


# ---------------------------------------------------------------- overlays


def test_the_three_blueprint_overlays_are_declared(tree: SkillTree) -> None:
    assert {(o.layer, o.target) for o in tree.overlays()} == {
        ("valuation/_repeat", "line-item-tagging"),
        ("valuation/esop/_segment", "ebitda-normalization"),
        ("valuation/esop/_segment", "qc-tieout"),
    }


def test_every_overlay_gives_a_reason(tree: SkillTree) -> None:
    """An overlay without one is indistinguishable from a mistake six months later."""
    for overlay in tree.overlays():
        assert len(overlay.why) > 40, f"{overlay.layer} -> {overlay.target}"


def test_an_overlay_targeting_a_skill_nobody_declares_is_refused(tmp_path: Path) -> None:
    _one_skill(tmp_path)
    layer = tmp_path / "_firm"
    (layer / "overlays.yaml").write_text(
        yaml.safe_dump(
            {
                "version": "1.0.0",
                "scope": "_firm",
                "overlays": [{"target": "nonexistent", "why": "x" * 50}],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(RegistryError) as raised:
        SkillTree.load(tmp_path)
    assert raised.value.diagnostic.code == "SCOPE.SKILL_INVALID"


# ------------------------------------------------------------- the refusals


def test_a_skill_that_declares_a_layer_it_does_not_sit_at_is_refused(tmp_path: Path) -> None:
    """A skill moved without updating its declaration would resolve from one layer and
    claim another, and the manifest would record the claim."""
    _one_skill(tmp_path, scope="valuation/_group")
    with pytest.raises(RegistryError) as raised:
        SkillTree.load(tmp_path)
    assert raised.value.diagnostic.code == "SCOPE.SKILL_INVALID"
    assert "sits at" in str(raised.value)


def test_a_skill_missing_a_required_field_is_refused(tmp_path: Path) -> None:
    _one_skill(tmp_path, drop="hitl")
    with pytest.raises(RegistryError) as raised:
        SkillTree.load(tmp_path)
    assert "hitl" in str(raised.value)


def test_a_file_with_no_frontmatter_is_refused(tmp_path: Path) -> None:
    folder = tmp_path / "_firm" / "thing"
    folder.mkdir(parents=True)
    (folder / "SKILL.md").write_text("# Just a document\n", encoding="utf-8")
    with pytest.raises(RegistryError, match="frontmatter"):
        SkillTree.load(tmp_path)


def test_the_same_skill_twice_at_one_layer_is_refused() -> None:
    """Resolution is by depth. Two skills of one name at one layer have no deepest
    answer, and picking either would be arbitrary.

    The folder layout makes this unreachable from disk today, because the folder name is
    the skill name. Checked on a tree built in memory, against the day that changes.
    """
    duplicated = SkillTree((make_skill("a", "_firm"), make_skill("a", "_firm")), ())
    with pytest.raises(RegistryError) as raised:
        duplicated.self_check()
    assert raised.value.diagnostic.code == "SCOPE.AMBIGUOUS_SKILL"


def _one_skill(root: Path, scope: str = "_firm", drop: str = "") -> Path:
    folder = root / "_firm" / "thing"
    folder.mkdir(parents=True)
    frontmatter = {
        "name": "thing",
        "version": "0.1.0",
        "status": "skeleton",
        "scope": scope,
        "title": "Thing",
        "description": "Does a thing.",
        "tier": "mid",
        "inputs": ["a"],
        "outputs": ["b"],
        "tools": ["recompute"],
        "data_sensitivity": "masked_only",
        "hitl": "always_surfaces_to_reviewer",
        "output_contract": "skills/thing@1.0.0",
    }
    frontmatter.pop(drop, None)
    (folder / "SKILL.md").write_text(
        "---\n" + yaml.safe_dump(frontmatter) + "---\n\n# Thing\n", encoding="utf-8"
    )
    return folder
