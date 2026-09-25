"""C70 - the same payload, spelled smaller.

P124 took the indentation out of every procedure's payload at once. Each procedure's own
tests pass on its own module, and what none of them can see is the thing that actually
broke: a payload does not reach a model on its own. It is one section of an assembled
context, wrapped in untrusted-content markers beside the skill body, the methodology and
the precedent, and whatever reads it back has to find it among the others.

That is exactly where the change did break something. `tests/p19` asserted
`'"id": "officer_compensation"' in user` - a test about *whether the taxonomy reaches the
model*, which failed over a removed space after a colon. It was asking the message's
spelling for an answer about its content, and the answer stopped being true while the
content never changed.

So what this checkpoint proves is the property that survives the spelling: for every
procedure the register holds, the payload it sends is still **found and parsed** by the
reader that has to find it, when it sits where it really sits. And that the one thing the
change was for - headroom under the ceiling that refuses a run - is measurably there.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from guards.untrusted import BEGIN, END
from harness.procedures import PROCEDURES
from harness.procedures.ebitda_normalization import (
    EbitdaNormalization,
    EbitdaVerification,
    VerificationInputs,
)
from harness.procedures.line_item_tagging import LineItemTagging, TaggingInputs
from harness.procedures.model_load import (
    ModelLoad,
    ModelLoadInputs,
    TemplateInput,
    catalogue_from,
)
from harness.procedures.timing_normalization import SourceFile, TimingInputs, TimingNormalization
from ports.llm.scripted import payload_of
from registries.constraints import ConstraintRegistry
from review import CheckpointPolicy
from tests.p20.conftest import blocks_of, inputs_for, load_case, profile, timing_output

ROOT = Path(__file__).resolve().parents[3]
TAXONOMY = "coa-taxonomy@1.0.0"
SLOTS = ("FY1", "FY2", "FY3")


# ---------------------------------------------------------------- one case, four payloads


def a_policy() -> CheckpointPolicy:
    return CheckpointPolicy.from_profile(profile(), ConstraintRegistry.load())


def payloads() -> dict[str, str]:
    """What each procedure would send, built from one client's documents.

    The same case the EBITDA phase uses, carried through the chain the way a run carries
    it: the readers' blocks become timing's files, timing's table becomes tagging's items
    and model-load's catalogue, and the two together become EBITDA's lines.
    """
    case = load_case()
    blocks = blocks_of(case)
    table = timing_output(case)

    files = tuple(
        SourceFile(
            source_id=source_id,
            filename=f"{source_id[:8]}.xlsx",
            document_type="financial_statements",
            blocks={loc: list(rows) for loc, rows in by_locator.items()},
            scale=1000,
            currency="USD",
            period_type="annual",
            period_ends=("2025-12-31",),
            block_periods={loc: "FY2025" for loc in by_locator},
        )
        for source_id, by_locator in blocks.items()
    )

    tagging = TaggingInputs.from_normalized(
        table["normalized_historicals"], taxonomy_version=TAXONOMY, auto_accept_confidence=0.85
    )

    catalogue = catalogue_from(table, {}, period_slots={"FY2025": "FY1"})
    loaded = ModelLoadInputs(
        template_key="Chartwell_Input_Help_v1@1.0",
        template_version="1.0",
        inputs=(TemplateInput(name="Revenue_FY1", line="Revenue", period="FY1", required=True),),
        catalogue=catalogue,
        periods=SLOTS,
        period_slots=(("FY2025", "FY1"),),
    )

    ebitda = inputs_for(case, a_policy())

    return {
        "timing-normalization": TimingNormalization().payload(TimingInputs(files=files)),
        "line-item-tagging": LineItemTagging().payload(tagging),
        "model-load": ModelLoad().payload(loaded),
        "ebitda-normalization": EbitdaNormalization().payload(ebitda),
    }


@pytest.fixture(scope="module")
def sent() -> dict[str, str]:
    return payloads()


def assembled(payload: str) -> str:
    """A payload where it really sits: one wrapped section among others, which is what
    made the `p19` assertion fail and what a payload test on its own never sees."""
    other = json.dumps({"precedent": [{"decided": "officer comp is an addback"}]})
    return (
        f"{BEGIN} label=context:methodology\nsome prose about how this firm works\n{END}\n\n"
        f"{BEGIN} label=context:precedent\n{other}\n{END}\n\n"
        f"{BEGIN} label=context:payload\n{payload}\n{END}\n"
    )


# ---------------------------------------------------------------- still found, still read


def test_every_procedure_in_the_register_is_covered_here() -> None:
    """Derived from the register rather than from a list typed above, so a skill added
    later cannot quietly go unchecked (B-066)."""
    assert set(payloads()) == set(PROCEDURES)


def test_each_payload_is_still_valid_json(sent: dict[str, str]) -> None:
    for name, text in sent.items():
        assert isinstance(json.loads(text), dict), f"{name} no longer sends an object"


def test_each_payload_is_still_found_among_the_other_sections(sent: dict[str, str]) -> None:
    """Through `payload_of`, which is production's own reader - the scripted analyst uses
    it on every rehearsal run. It scans for a decodable object carrying a key a procedure
    sends, so it never depended on the spelling; proving that is the point."""
    for name, text in sent.items():
        found = payload_of(assembled(text))
        assert found, f"{name}'s payload was not found in an assembled context"
        assert found == json.loads(text), f"{name} was found but read back differently"


def test_and_the_wrapper_is_not_what_gets_parsed(sent: dict[str, str]) -> None:
    """The neighbouring section is also a JSON object. A reader that took the first one it
    saw would answer with the precedent every time."""
    found = payload_of(assembled(sent["line-item-tagging"]))
    assert "precedent" not in found
    assert "taxonomy" in found and "items" in found


def test_the_taxonomy_still_reaches_the_model(sent: dict[str, str]) -> None:
    """The assertion `tests/p19` was making, asked of the content this time. A category
    the model is meant to choose from has to be in what it is handed, and no spelling of
    the payload changes whether that is true."""
    body = payload_of(assembled(sent["line-item-tagging"]))
    ids = {c.get("id") for c in body["taxonomy"]["categories"]}
    assert "officer_compensation" in ids


def test_the_verification_pass_sends_a_readable_payload_too(sent: dict[str, str]) -> None:
    """The second invocation of EBITDA has its own payload and its own call site, and it
    was the fifth one the phase changed."""
    ebitda = inputs_for(load_case(), a_policy())
    schedule = {"addback_schedule": [], "periods": list(ebitda.periods)}
    text = EbitdaVerification().payload(VerificationInputs.from_pass(schedule, ebitda))
    assert json.loads(text)["verification"] is True
    assert payload_of(assembled(text))


# ---------------------------------------------------------------- and it is smaller


def test_every_payload_got_smaller_and_none_changed(sent: dict[str, str]) -> None:
    """Both halves of the claim in one assertion, per procedure: fewer bytes, same
    object. Either alone would be the wrong test - a smaller payload that says something
    different is the failure this phase was most able to cause."""
    for name, text in sent.items():
        body = json.loads(text)
        padded = json.dumps(body, indent=1)
        assert json.loads(padded) == body, f"{name} does not round-trip"
        assert len(text) < len(padded), f"{name} is not smaller than it was"


def test_the_context_nearest_the_ceiling_has_measurably_more_room() -> None:
    """Model-load on a real-sized catalogue is the step closest to the limit that refuses
    a run outright, and how close it comes is a function of how many line items the client
    has. The saving is stated against the ceiling because that is what it is for - not
    against the bill, where whitespace was never worth anything."""
    from tests.p124.test_a_payload_with_the_padding_taken_out import a_catalogue

    ceiling = ConstraintRegistry.load().context_ceiling()
    text = ModelLoad().payload(a_catalogue(370))
    padded = json.dumps(json.loads(text), indent=1)

    assert len(padded) > 0.6 * ceiling, "the shape under test is no longer a tight one"
    assert (len(padded) - len(text)) > 0.05 * ceiling


def test_no_procedure_anywhere_pretty_prints(sent: dict[str, str]) -> None:
    """Swept over the package rather than over the four modules this checkpoint builds
    payloads for, and asked of the code rather than of its comments - the module that
    explains why this must not happen contains the phrase a grep would match."""
    for module in sorted((ROOT / "harness" / "procedures").glob("*.py")):
        tree = ast.parse(module.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "dumps"
                and any(kw.arg == "indent" for kw in node.keywords)
            ):
                pytest.fail(f"{module.name} pretty-prints a payload again")
