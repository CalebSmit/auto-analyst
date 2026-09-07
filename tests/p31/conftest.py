"""Fixtures for P31: a methodology tree with three layers that belong to two groups.

Everything else comes from P30, which built the register, and through it from P09 and
P24/P29. Only the shape of the folder changes here: a firm layer, one practice group with
methodology of its own, and a second group that has written none - because "a group with
nothing of its own still carries the firm's" is a claim about a folder that is not there.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.p30 import conftest as p30

Sourced = p30.Sourced
blobs = p30.blobs
builder = p30.builder
cleared = p30.cleared
clock = p30.clock
config = p30.config
console = p30.console
constraints = p30.constraints
contracts = p30.contracts
entry = p30.entry
environment = p30.environment
henderson = p30.henderson
payload = p30.payload
plan = p30.plan
preflight = p30.preflight
profile = p30.profile
profile_for = p30.profile_for
register = p30.register
request_for = p30.request_for
roster = p30.roster
scope = p30.scope
source = p30.source
started = p30.started
store = p30.store
templates = p30.templates
tree = p30.tree
bus = p30.bus

HEND = p30.HEND
WHO = p30.WHO

FIRM = "# Firm QC\n\nEvery engagement gets a scope memo before fieldwork starts.\n"
VALUATION = "# How valuation works here\n\nWe reconcile to the trial balance first.\n"
CONSULTING = "# How consulting works here\n\nWe scope the question before the model.\n"


@pytest.fixture
def foundations(tmp_path: Path) -> Path:
    """Three layers across two practice groups, and one group with nothing of its own.

    Corporate Finance is deliberately absent from the folder: it is declared in the scope
    registry and has written no methodology, which is the ordinary state of a new practice
    group and the case that has to keep working.
    """
    root = tmp_path / "foundations"
    for layer, body in (
        ("_firm", FIRM),
        ("valuation/_group", VALUATION),
        ("consulting/_group", CONSULTING),
    ):
        directory = root / layer
        directory.mkdir(parents=True)
        (directory / "how-we-work.md").write_text(body, encoding="utf-8")
    (root / "README.md").write_text("# What this folder is\n", encoding="utf-8")
    return root
