"""An ephemeral run for evaluating a skill outside any engagement.

A procedure's mechanical half reaches its tools through the Guarded Tool Runtime and
nothing else, so evaluating one needs a run scope for the gate to decide against, a run
store for the events, and the real tools bound by name. This builds all of that over a
throwaway SQLite file and a synthetic engagement, so `gate eval` runs the same code path
a run does - the gate included - with nothing on disk afterwards.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from harness.policy import PolicyGate, RunScope
from harness.runtime import BoundTools, GuardedRuntime
from ops.events import EventBus
from ops.models import RunState
from ops.run_store import SqlRunStore, open_store
from ops.source_parse import Row, SourceParseStore
from precedent import PrecedentStore
from registries.constraints import ConstraintRegistry
from registries.contracts import ContractRegistry
from tools.coa import chart_of_accounts_lookup
from tools.normalize import timing_normalizer
from tools.precedent import precedent_lookup_tool
from tools.recompute import recompute
from tools.template_schema import template_schema_lookup

__all__ = ["EvalWorld"]

ENGAGEMENT = "EVAL-0000-00"
RUN_ID = "run_eval"
SCOPE_PATH = "valuation/esop/repeat"
TAXONOMY = "coa-taxonomy@1.0.0"
TEMPLATE_KEY = "Chartwell_ESOP_Model_v9@9.4"


class EvalWorld:
    def __init__(self, root: Path | None = None) -> None:
        self._tmp = None if root is not None else tempfile.TemporaryDirectory(prefix="aa-eval-")
        self.root = root if root is not None else Path(self._tmp.name)  # type: ignore[union-attr]
        self.contracts = ContractRegistry.load()
        self.constraints = ConstraintRegistry.load()
        self.store: SqlRunStore = open_store(f"sqlite:///{(self.root / 'eval.db').as_posix()}")
        self.bus = EventBus(self.store, contracts=self.contracts)
        self.parse_store = SourceParseStore(self.store)
        self.precedents = PrecedentStore(self.store)
        self.store.start_run(
            run_id=RUN_ID,
            engagement_id=ENGAGEMENT,
            plan_hash="sha256:" + "e" * 64,
            versions={
                "model_pin": "eval",
                "skills": [],
                "contracts": "1.0.0",
                "constraints": "1.0.0",
                "taxonomy": TAXONOMY,
            },
            tieout_tolerance=0.0,
        )
        self.store.transition(RUN_ID, RunState.RUNNING)
        self.runtime = GuardedRuntime(
            PolicyGate(self.constraints, self.bus),
            self.constraints,
            self.bus,
            {
                "timing_normalizer": timing_normalizer,
                "recompute": recompute,
                "chart_of_accounts_lookup": chart_of_accounts_lookup,
                "precedent_lookup": precedent_lookup_tool(self.precedents),
                "template_schema_lookup": template_schema_lookup,
            },
        )
        self.run_scope = RunScope(
            run_id=RUN_ID,
            engagement_id=ENGAGEMENT,
            engagement_root=f"engagements/{ENGAGEMENT}",
            scope_path=SCOPE_PATH,
            versions={
                "chart_of_accounts_lookup": TAXONOMY,
                "template_schema_lookup": TEMPLATE_KEY,
            },
            budget_remaining_usd=1_000.0,
        )
        self.run_id = RUN_ID
        self.engagement_id = ENGAGEMENT

    def tools_for(self, skill: str, step_id: str) -> BoundTools:
        return self.runtime.bound(self.run_scope, skill, step_id)

    def write_blocks(self, files: list[dict[str, Any]], run_id: str | None = None) -> str:
        """The readers' rows for one case, under their own run so two cases that reuse
        a source id never share a block. Returns the run id the guards should read."""
        run = run_id or self.run_id
        if run != self.run_id and run not in {r.run_id for r in self.store.runs()}:
            self.store.start_run(
                run_id=run,
                engagement_id=ENGAGEMENT,
                plan_hash="sha256:" + "e" * 64,
                versions={
                    "model_pin": "eval",
                    "skills": [],
                    "contracts": "1.0.0",
                    "constraints": "1.0.0",
                    "taxonomy": TAXONOMY,
                },
                tieout_tolerance=0.0,
            )
        for f in files:
            for locator, rows in f["blocks"].items():
                if not self.parse_store.exists(run, f["source_id"], locator):
                    self.parse_store.write(run, f["source_id"], locator, [Row(**r) for r in rows])
        return run

    def close(self) -> None:
        self.store.close()
        if self._tmp is not None:
            self._tmp.cleanup()
