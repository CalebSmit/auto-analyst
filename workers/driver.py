"""What carries a released run to an ending.

The worker pool takes a `PassRunner` - a callable that runs one pass of one run and says
what happened - and until now nothing ever gave it one outside a test. Intake created runs
and took their locks; the pool would have run them if anybody had handed it the means; the
executor would have walked their plans. Between those three there was nothing, so a run
released by a watched folder sat with its lock taken and no process to move it.

This is that means, and it is a composition root rather than a component: it holds no
guarantee of its own, and every line of it is picking up something built elsewhere and
handing it to something else built elsewhere.

**What one pass does.** Read the run and its engagement, resolve the scope, compile the
plan, read the source documents through the readers into the parse store, build the run's
facts, and hand the whole thing to the `StepExecutor` with a runner that knows both kinds
of step. The executor decides what is executed, satisfied from the ledger, quarantined or
blocked; this decides nothing about that.

**A pass is not a run.** The executor returns when a step blocks on a person, quarantines,
or the plan is finished - all three are ordinary endings for a pass. The pool asks again
when the run is ready to move, which is why this is idempotent and why nothing here holds
state between calls.

**Two skills in the shipped recipes have no mechanical half yet** - `qc-tieout` and
`ddr-tagging`. A run reaching one of those stops there with the step named, which is the
system saying what it cannot do rather than delivering something nobody checked. Writing
those procedures is skill work, recorded on the open register, and this needs no change
when it lands.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from typing import Any

from graph.compile import PlanContext, compile_recipe
from graph.execute import Attempt, ExecutionReport, StepExecutor
from graph.recipes import load_recipe
from graph.resolve import ScopeResolver
from harness.inputs import InputsUnavailable, RunFacts
from harness.procedures.timing_normalization import SourceFile
from harness.runner import RunContext, SkillStepRunner
from intake.readers import read_source
from ops.blobs import ContentRef, ContentStore, put_json
from ports.llm import ModelPin
from ports.storage import FileRef
from review import CheckpointPolicy

__all__ = ["RunDriver", "RunWiring"]

READ_STEP = "intake"
MASK_STEP = "mask"
RELEASE_STEP = "release"


@dataclass
class RunWiring:
    """Everything a pass needs that is the same for every run on this machine.

    Separated from the run's own facts because these are the environment - the stores, the
    registries, the ports - and a driver that rebuilt them per run would open a vault and
    reload a registry for every pass.
    """

    store: Any
    bus: Any
    blobs: ContentStore
    contracts: Any
    constraints: Any
    config: Any
    roster: Any
    intake_store: Any
    parse_store: Any
    dispatcher_for: Any
    """`(run_id) -> SkillDispatcher`. A factory rather than an instance, because a
    dispatcher carries the masker and the budget governor for one run."""
    templates: Any
    precedents: Any
    """The precedent store, for the snapshot a plan has to name. A plan without one is
    refused, and rightly: two runs sharing a hash while seeing different examples would
    legitimately disagree."""
    delivery: Any
    storage: Any
    boundary: Any
    tier: str = "mid"


class RunDriver:
    """One pass of one run. Satisfies `workers.pool.PassRunner`."""

    def __init__(self, wiring: RunWiring) -> None:
        self.wiring = wiring

    # -- the pass

    def __call__(self, run_id: str) -> ExecutionReport:
        w = self.wiring
        run = w.store.run(run_id)
        entry = w.roster.get(run.engagement_id)
        if entry is None:
            raise InputsUnavailable(
                f"{run_id} belongs to {run.engagement_id}, which is not on the roster"
            )

        resolver = ScopeResolver(bindings=w.config.model_bindings())
        scope = resolver.resolve(entry.scope_path)
        watch = next(x for x in w.config.watches() if x.id == entry.watch_id)
        plan = compile_recipe(
            load_recipe(entry.recipe or watch.recipe),
            PlanContext(
                engagement_id=run.engagement_id,
                scope=scope,
                taxonomy_version=str(run.versions.get("taxonomy", "coa-taxonomy@1.0.0")),
                precedent_snapshot=self._snapshot(run),
            ),
        )

        profile = w.config.profile(run.engagement_id) or {}
        facts = self._facts(run_id, run.engagement_id, scope, profile)
        profile_ref = put_json(w.blobs, profile, name="engagement_profile")

        context = RunContext(
            run_id=run_id,
            engagement_id=run.engagement_id,
            client_id=entry.client,
            scope=scope,
            engagement_profile=profile_ref,
            identifiers=self._identifiers(entry, profile),
            run_scope=self._run_scope(run_id, entry, scope),
            pin=ModelPin.for_tier(w.tier),
            facts=facts,
        )
        skills = SkillStepRunner(w.dispatcher_for(run_id), w.blobs, context)

        executor = StepExecutor(
            w.store, w.bus, self._route(skills, context), blobs=w.blobs,
            constraints=w.constraints,
        )
        return executor.execute(
            plan,
            run_id,
            run_inputs={
                "engagement_profile": profile_ref,
                "source_documents": put_json(w.blobs, 
                    {"source_ids": [f.source_id for f in facts.sources]}, name="sources"
                ),
            },
        )

    def _snapshot(self, run: Any) -> str:
        """The precedent snapshot this run compiles against.

        The one it already names, when it names one, so a resumed run recompiles to the
        hash it started with rather than to whatever the store holds today. Otherwise the
        store's current snapshot - intake creates a run before anything has asked.
        """
        named = str(run.versions.get("precedent_snapshot") or "")
        return named or str(self.wiring.precedents.snapshot_id())

    # -- the two kinds of step

    def _route(self, skills: SkillStepRunner, context: RunContext) -> Any:
        """Skill steps to the harness; io steps to the thing that does them.

        The plan says which is which - `kind` is compiled, not guessed - so this is a
        lookup rather than a decision.
        """

        def run(attempt: Attempt) -> ContentRef:
            if attempt.step.kind == "skill":
                return skills(attempt)
            return self._io(attempt, context)

        return run

    def _io(self, attempt: Attempt, context: RunContext) -> ContentRef:
        w = self.wiring
        step = attempt.step
        if step.id == READ_STEP:
            return put_json(w.blobs, 
                {
                    "sources": [
                        {"source_id": f.source_id, "filename": f.filename, "kind": f.document_type}
                        for f in context.facts.sources
                    ],
                    "locators": sum(len(f.blocks) for f in context.facts.sources),
                },
                name="intake",
            )
        if step.id == MASK_STEP:
            # The masking itself happens per step, inside the dispatcher, where the
            # payload is built - masking here would mask nothing, because nothing has been
            # assembled yet. What this records is what the masker will be looking for.
            return put_json(w.blobs, 
                {"identifiers": [i.kind for i in context.identifiers]}, name="mask"
            )
        if step.id == RELEASE_STEP:
            return self._release(attempt, context)
        raise InputsUnavailable(
            f"{step.id} is an io step this driver does not know how to run"
        )

    def _release(self, attempt: Attempt, context: RunContext) -> ContentRef:
        """Build the workbook from the mapping the model proposed, and deliver it once.

        Reachable only when every step before it produced something, which today means
        never on the shipped recipes: both end in `qc-tieout`, which has no mechanical
        half. Written and exercised anyway, because the alternative is a path that is
        wired and has never run - which is the thing this whole block is fixing.
        """
        from deliver.builder import ModelBuilder

        w = self.wiring
        mapping = self._output(attempt, "model")
        template = w.templates.resolve(context.scope.template)
        built = ModelBuilder(w.bus).build(
            mapping,
            self._figures(attempt, context),
            template,
            run_id=context.run_id,
            engagement_id=context.engagement_id,
        )
        released = w.delivery and w.release_gate.release(  # type: ignore[attr-defined]
            context.run_id,
            context.engagement_id,
            built.name,
            built.data,
            template_version=template.template_version,
            expected=built.writes,
        )
        return put_json(w.blobs, 
            {
                "delivered": built.name,
                "writes": len(built.writes),
                "already_released": bool(getattr(released, "already_released", False)),
            },
            name="release",
        )

    # -- what the run knows about itself

    def _facts(
        self, run_id: str, engagement_id: str, scope: Any, profile: dict[str, Any]
    ) -> RunFacts:
        sources = self._read_sources(run_id, engagement_id)
        template = None
        if scope.template is not None:
            try:
                template = self.wiring.templates.resolve(scope.template)
            except Exception:  # noqa: BLE001 - preflight reports an unbound template
                template = None
        return RunFacts(
            profile=profile,
            policy=CheckpointPolicy.from_profile(profile, self.wiring.constraints),
            taxonomy_version="coa-taxonomy@1.0.0",
            sources=sources,
            blocks={f.source_id: f.blocks for f in sources},
            template=template,
            periods=("FY1", "FY2", "FY3"),
        )

    def _read_sources(self, run_id: str, engagement_id: str) -> tuple[SourceFile, ...]:
        """Every file in the run's intake set, read once into the parse store.

        Idempotent by the parse store, which versions what it is given, so a second pass
        over a resumed run re-reads without inventing a second version of a row.
        """
        w = self.wiring
        out: list[SourceFile] = []
        for row in self._intake_set(run_id, engagement_id):
            already = w.parse_store.locators(run_id, row.source_id)
            if already:
                out.append(self._from_store(run_id, row, already))
                continue
            data = w.storage.read(FileRef(row.path))
            report = read_source(
                run_id,
                engagement_id,
                row,
                data,
                store=w.store,
                parse_store=w.parse_store,
                boundary=w.boundary,
                bus=w.bus,
                step_id=READ_STEP,
            )
            periods = report.periods
            out.append(
                SourceFile(
                    source_id=report.source_id,
                    filename=report.filename,
                    document_type=(
                        report.classification.document_type if report.classification else "other"
                    ),
                    # The rows, from the store the readers wrote them to. The report says
                    # how many went in; a second copy of them travelling beside the store
                    # would be a second thing to keep true.
                    blocks={
                        locator: [dataclasses.asdict(r) for r in w.parse_store.rows(
                            run_id, report.source_id, locator
                        )]
                        for locator in report.blocks
                    },
                    scale=periods.scale if periods else None,
                    currency=periods.currency if periods else None,
                    period_type=periods.period_type if periods else None,
                    period_ends=tuple(periods.period_ends) if periods else (),
                    ambiguous=tuple(periods.ambiguous) if periods else (),
                    source_version=row.source_version,
                )
            )
        return tuple(out)

    def _from_store(self, run_id: str, row: Any, locators: tuple[str, ...]) -> SourceFile:
        """A source this run has already read, rebuilt from what was recorded.

        The classification and the period detection are not re-derived: they were part of
        reading, and re-deriving them on a resume would mean a run could change its mind
        about what a file is between passes.
        """
        w = self.wiring
        return SourceFile(
            source_id=row.source_id,
            filename=row.filename,
            document_type=row.document_type or "other",
            blocks={
                locator: [
                    dataclasses.asdict(r)
                    for r in w.parse_store.rows(run_id, row.source_id, locator)
                ]
                for locator in locators
            },
            scale=None,
            currency=None,
            period_type=None,
            period_ends=(),
            source_version=row.source_version,
        )

    def _intake_set(self, run_id: str, engagement_id: str) -> tuple[Any, ...]:
        """The files this run consumed.

        Taken from what the intake store marked against the run rather than from what the
        engagement currently holds: a run reads the set it was released for, and files
        that landed afterwards belong to the next one. That is the whole reason intake
        marks them.
        """
        w = self.wiring
        consumed = tuple(
            row
            for row in w.intake_store.files(engagement_id)
            if getattr(row, "consumed_by", None) == run_id
        )
        return consumed or w.intake_store.current_set(engagement_id)

    def _identifiers(self, entry: Any, profile: dict[str, Any]) -> tuple[Any, ...]:
        """What the masker must not let through, built once for the run.

        From the engagement rather than from a step, because a step that assembled its own
        would be a step that could miss one - and the one it missed would be the one that
        reached a model.
        """
        from privacy.mask import Identifier

        found = [Identifier("CLIENT", entry.client)]
        owner = (profile.get("checkpoint_policy") or {}).get("owner")
        if owner:
            found.append(Identifier("PERSON", str(owner)))
        return tuple(found)

    def _run_scope(self, run_id: str, entry: Any, scope: Any) -> Any:
        from harness.policy import RunScope

        return RunScope(
            run_id=run_id,
            engagement_id=entry.engagement_id,
            engagement_root=f"engagements/{entry.engagement_id}",
            scope_path=entry.scope_path,
            versions={},
            budget_remaining_usd=entry.budget_usd or 0.0,
        )

    def _output(self, attempt: Attempt, name: str) -> dict[str, Any]:
        import json

        if name not in attempt.inputs:
            raise InputsUnavailable(
                f"{attempt.step.id} needs the output of {name!r}, which this run does not have"
            )
        loaded = json.loads(self.wiring.blobs.get(attempt.inputs[name]).decode("utf-8"))
        if not isinstance(loaded, dict):
            raise InputsUnavailable(f"{name} is not a step output")
        return loaded

    def _figures(self, attempt: Attempt, context: RunContext) -> Any:
        from harness.inputs import build_inputs

        loaded = build_inputs(
            "model-load", attempt.step.id, dict(attempt.inputs), context.facts, self.wiring.blobs
        )
        return loaded.figures()
