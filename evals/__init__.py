"""Assurance before a skill ships: the Evaluation Harness and the Replay Harness.

`harness.py` runs a skill over its golden fixtures and scores it against the named
numeric gates in `gates.yaml`; `coverage()` says which skills and guards have fixtures
and which do not. `replay.py` re-runs a candidate over the recorded inputs of a past run
and diffs the result against what was delivered and what a person later corrected.
`registration.py` is the only way a skill version is recorded as registered, and it
refuses a scorecard below its gate.
"""

from __future__ import annotations

from evals.harness import Coverage, EvalHarness, Gate, Metric, Scorecard
from evals.registration import RegisteredSkill, SkillRegistration
from evals.replay import Change, CorrectionCheck, Replay, ReplayHarness

__all__ = [
    "Change",
    "CorrectionCheck",
    "Coverage",
    "EvalHarness",
    "Gate",
    "Metric",
    "RegisteredSkill",
    "Replay",
    "ReplayHarness",
    "Scorecard",
    "SkillRegistration",
]
