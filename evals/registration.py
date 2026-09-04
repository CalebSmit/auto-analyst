"""Skill registration: the recorded act that makes a version live, and the one gate on it.

Approval is a decision; registration is a deployment. A SKILL.md sitting in a folder is
not live - registration is a separate, recorded act, and the only way in is through a
scorecard that clears every gate. A skill below its gate cannot be registered, whoever
approves it. Versions are immutable: registering the same version twice is refused,
because a change is a new version and a new review.

The governance chain that leads here - sandbox, submit, board, shadow - is P27's. This
is the last link, built now so the eval harness has a consequence.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from evals.harness import Scorecard
from registries.errors import BELOW_GATE, DiagnosticError, diagnose

__all__ = ["REGISTER_FILE", "RegisteredSkill", "RegistrationRefused", "SkillRegistration"]

REGISTER_FILE = Path(__file__).resolve().parents[1] / "skills" / "registered.yaml"


class RegistrationRefused(DiagnosticError):
    """The scorecard is below its gate, or the version is already registered."""


@dataclass(frozen=True)
class RegisteredSkill:
    skill: str
    version: str
    registered_at: str
    approved_by: str
    scorecard_hash: str
    gates: tuple[str, ...]
    owed: tuple[str, ...]

    @property
    def key(self) -> str:
        return f"{self.skill}@{self.version}"


class SkillRegistration:
    def __init__(self, path: Path = REGISTER_FILE) -> None:
        self.path = path

    def _load(self) -> list[dict[str, Any]]:
        if not self.path.is_file():
            return []
        raw = yaml.safe_load(self.path.read_text(encoding="utf-8")) or {}
        return list(raw.get("registered", []))

    def registered(self) -> tuple[RegisteredSkill, ...]:
        return tuple(_as_registered(r) for r in self._load())

    def is_registered(self, skill: str, version: str) -> bool:
        return any(r.skill == skill and r.version == version for r in self.registered())

    def register(self, scorecard: Scorecard, *, approved_by: str) -> RegisteredSkill:
        """Record a version as registered. Refuses below the gate, refuses a blank
        approver, refuses a version already registered."""
        if not approved_by.strip():
            raise ValueError("registration names the person who approved it")
        failing = [m for m in scorecard.metrics if m.passed is False]
        if scorecard.status != "shipped" or failing:
            detail = (
                f"{scorecard.key} is not shipped"
                if scorecard.status != "shipped"
                else f"{scorecard.key} is below its gate on "
                + ", ".join(
                    f"{m.gate.metric} ({m.value:g} {m.gate.op} {m.gate.threshold:g})"
                    for m in failing
                )
            )
            raise RegistrationRefused(
                diagnose(
                    BELOW_GATE,
                    detail,
                    locator=scorecard.key,
                    skill=scorecard.key,
                    expected="every gate holding",
                    found=", ".join(m.gate.metric for m in failing) or scorecard.status,
                )
            )
        if self.is_registered(scorecard.skill, scorecard.version):
            raise RegistrationRefused(
                diagnose(
                    BELOW_GATE,
                    f"{scorecard.key} is already registered; a change is a new version "
                    f"and a new review",
                    locator=scorecard.key,
                    skill=scorecard.key,
                )
            )
        body = json.dumps(scorecard.as_dict(), sort_keys=True).encode("utf-8")
        record = RegisteredSkill(
            skill=scorecard.skill,
            version=scorecard.version,
            registered_at=datetime.now(tz=UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
            approved_by=approved_by.strip(),
            scorecard_hash=f"sha256:{hashlib.sha256(body).hexdigest()}",
            gates=tuple(m.line() for m in scorecard.metrics if m.value is not None),
            owed=tuple(f"{g.metric} ({g.measured_by})" for g in scorecard.owed),
        )
        rows = self._load()
        rows.append(
            {
                "skill": record.skill,
                "version": record.version,
                "registered_at": record.registered_at,
                "approved_by": record.approved_by,
                "scorecard_hash": record.scorecard_hash,
                "gates": list(record.gates),
                "owed": list(record.owed),
            }
        )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            "# Registered skill versions. Written only by evals/registration.py, only from a\n"
            "# scorecard that cleared every gate. Append-only: a version is never edited or\n"
            "# removed here; a change is a new version and a new review.\n"
            + yaml.safe_dump({"registered": rows}, sort_keys=False),
            encoding="utf-8",
        )
        return record


def _as_registered(row: dict[str, Any]) -> RegisteredSkill:
    return RegisteredSkill(
        skill=str(row["skill"]),
        version=str(row["version"]),
        registered_at=str(row["registered_at"]),
        approved_by=str(row["approved_by"]),
        scorecard_hash=str(row["scorecard_hash"]),
        gates=tuple(str(g) for g in row.get("gates", [])),
        owed=tuple(str(o) for o in row.get("owed", [])),
    )
