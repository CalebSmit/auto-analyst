"""C93 - day one, before anyone has done anything.

P166, P167 and P168 were built for the same morning: the one when this repository is
cloned onto the work laptop and a person tries to use it. Each phase passes alone. This
asks what that machine looks like when all three are in place and nothing has been set up -
no `.env`, nothing cleared, the default adapters - because that is the state the guide has
to be true for.

* The readiness report says where the record will be, before there is one (P168).
* Preflight's new check warns on the default model adapter and says which switch to set
  (P168), and the methodology check sees ten uncleared files, six of them the knowledge
  P167 put there - against a register in a temp directory, because a clearance is a
  person's act and a test must not make one.
* The three superseded skills are not in version 1's recipe and nothing can dispatch them
  (P167), so the retirement cost the recipe nothing.
* A client file of the kind P166 learned to name is still refused with the true sentence
  when the readers are reached the way a run reaches them.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import ports
from registries.methodology import MethodologyRegister

ROOT = Path(__file__).resolve().parents[3]
FOUNDATIONS = ROOT / "foundations"


def test_the_readiness_report_names_the_record_before_there_is_one(monkeypatch, tmp_path) -> None:
    from tools.serve import readiness

    monkeypatch.setenv("AA_DB_URL", f"sqlite:///{(tmp_path / 'runs' / 'run_store.db').as_posix()}")
    seams = {s.name: s for s in readiness()}
    assert "the record" in seams
    assert (tmp_path / "runs" / "run_store.db").as_posix() in seams["the record"].detail
    assert not (tmp_path / "runs" / "run_store.db").exists(), "naming it does not create it"


def test_preflight_on_the_default_adapter_warns_in_the_way_a_person_can_act_on(
    monkeypatch,
) -> None:
    from admin.preflight import Preflight

    monkeypatch.delenv("AA_LLM_ADAPTER", raising=False)
    ports.reset()
    preflight = Preflight.__new__(Preflight)
    preflight.secrets = type("NoSecrets", (), {"has": staticmethod(lambda name: False)})()
    said = preflight._model_answers()
    assert said.status == "warn", "the default adapter is the fixture replayer: a warning"
    assert "AA_LLM_ADAPTER" in said.detail
    assert "on a work laptop set it to one that answers" in said.detail
    assert "anthropic_messages" in said.detail
    assert said.failures == (), "a warning does not refuse activation"


def test_a_fresh_register_has_ten_uncleared_files_six_of_them_the_new_knowledge(tmp_path) -> None:
    register = MethodologyRegister(path=tmp_path / "cleared.yaml", root=FOUNDATIONS)
    found = register.review()
    assert len(found) == 10, [f.name for f in found]
    assert all(f.state == "uncleared" for f in found)
    group = [f.name for f in found if f.name.startswith("valuation/_group/")]
    assert len(group) == 6
    # And every one of the six would clear if a person read it: the scan has nothing to say.
    for name in group:
        path = FOUNDATIONS / name
        assert register.scan(path.read_bytes(), name) == (), name


def test_version_one_runs_without_the_superseded_skills() -> None:
    import yaml

    from harness.procedures import PROCEDURES
    from registries.skills import SkillTree

    recipe = yaml.safe_load(
        (ROOT / "recipes" / "valuation-input-prep.yaml").read_text(encoding="utf-8")
    )
    named = {s.get("skill") for s in recipe.get("steps", []) if s.get("skill")}
    superseded = {s.name for s in SkillTree.load().all() if s.status == "superseded"}
    assert superseded == {"cost-of-capital", "dcf-build", "gpc-scrub"}
    assert not named & superseded
    unbuilt = named - set(PROCEDURES)
    assert not unbuilt, f"version one names a skill with no procedure: {unbuilt}"


@pytest.mark.parametrize(
    ("filename", "data", "says"),
    [
        (
            "Trial balance.xlsx",
            bytes.fromhex("d0cf11e0a1b11ae1") + bytes(512),
            "protected with a password",
        ),
        ("TB.csv", b"PK\x03\x04" + bytes(64), "under a text name"),
    ],
)
def test_the_first_wrong_file_gets_the_true_sentence(
    filename: str, data: bytes, says: str, kit: dict
) -> None:
    from registries.errors import DiagnosticError
    from tests.p156.test_a_file_that_will_not_open import read

    with pytest.raises(DiagnosticError) as refused:
        read("spreadsheet", filename, data, **kit)
    assert refused.value.diagnostic.code == "INTAKE.FORMAT_NOT_READ"
    assert says in refused.value.diagnostic.detail
    assert "readable copy" not in refused.value.diagnostic.detail
