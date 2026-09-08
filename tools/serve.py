"""The front door: one command that starts the system and says what it can do.

Everything in this repo was built as a component and proved as a component. Nothing
composed them. There were app factories nobody called, a worker pool nobody started, and
a sweep loop that only ran inside tests - so the honest state of the build was that every
part worked and the whole could not be started. This is the composition root that was
missing, and `readiness()` is the part of it that refuses to overstate what it started.

    python tools/serve.py                  # the consoles, and a sweep every 60 seconds
    python tools/serve.py --no-sweep       # the consoles only
    python tools/serve.py --check          # build everything, start nothing, report

`--check` is the useful one on a machine nobody has configured yet: it wires the whole
system together and prints what is ready and what is not, without opening a port.

**What this starts and what it does not.** Intake is joined: a file landing in a watched
folder is bound to an engagement, fingerprinted, held through its quiet period and released
as a run with the engagement lock taken. A step of a compiled plan runs through the harness
- context, masking, the model door, the guards. What is missing is the half between them:
nothing takes a released run and carries it to an ending, because the worker pool takes a
`PassRunner` it has never been given.

`readiness()` derives each of those by asking the code rather than asserting it, so a seam
stops being reported as open the day somebody writes the missing piece. That is not a
hypothetical: "step execution" flipped to joined on its own the moment the runner existed,
while "run execution" did not.
"""

from __future__ import annotations

import argparse
import sys
import threading
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000
DEFAULT_SWEEP_SECONDS = 60

__all__ = ["Seam", "Served", "build", "main", "readiness", "sweep_forever"]


@dataclass(frozen=True)
class Seam:
    """One join between two halves of the system, and whether it is made.

    A seam is not a feature. It is the place two finished components meet, and it is
    where an unfinished system is unfinished - each half tested, nothing between them.
    """

    name: str
    ready: bool
    detail: str

    def line(self) -> str:
        return f"  [{'ok' if self.ready else 'NOT WIRED'}] {self.name}: {self.detail}"


def steps_are_wired() -> bool:
    """Whether anything in the harness implements `graph.execute.StepRunner`.

    Derived by import rather than declared by a constant, so this answer changes when the
    code does. A constant here would be a claim somebody has to remember to update, which
    is the failure this whole build tries not to have.
    """
    import importlib  # noqa: PLC0415

    from graph.execute import StepRunner  # noqa: PLC0415

    try:
        runner = importlib.import_module("harness.runner")
    except ModuleNotFoundError:
        return False
    return any(
        isinstance(found, type) and issubclass(found, StepRunner)
        for found in (getattr(runner, name) for name in dir(runner) if not name.startswith("_"))
    )


def runs_are_wired() -> bool:
    """Whether anything drives a released run: a `PassRunner` the pool can be given.

    Asked the same way and for the same reason - a step running through the harness and a
    run being carried to an ending are two different claims, and the first was true for a
    while before the second was.
    """
    import importlib  # noqa: PLC0415

    try:
        driver = importlib.import_module("workers.driver")
    except ModuleNotFoundError:
        return False
    return hasattr(driver, "RunDriver")


def readiness() -> tuple[Seam, ...]:
    """What is joined, in the order a piece of work passes through it."""
    steps = steps_are_wired()
    runs = runs_are_wired()
    return (
        Seam(
            "admin",
            True,
            "engagements, folder labels, methodology clearance, preflight - at /admin",
        ),
        Seam("ops console", True, "runs, steps, cost, review queue - at /"),
        Seam(
            "intake",
            True,
            "a watched folder is swept, files are bound to engagements and held through "
            "their quiet period, and a complete set is released as a run",
        ),
        Seam(
            "step execution",
            steps,
            "a step of a compiled plan runs through the harness - context, masking, the "
            "model door, the guards"
            if steps
            else "nothing implements graph.execute.StepRunner, so no step can run. See "
            "BUILD/OPEN.md",
        ),
        Seam(
            "run execution",
            runs,
            "a released run is picked up and driven to an ending"
            if runs
            else "nothing drives a run: the worker pool takes a PassRunner it has never "
            "been given, so a run released by intake sits with its lock taken. The step "
            "half of this is joined; what is missing is the half that carries a whole "
            "run. See BUILD/OPEN.md",
        ),
    )


@dataclass
class Served:
    """The assembled system. Held together so a test can build it without a port."""

    app: Any
    admin: Any
    ops: Any
    intake: Any
    store: Any
    config: Any
    roster: Any
    pool: Any = None
    """The worker pool, or None on a machine where the driver could not be built - most
    often a vault with no key yet. `readiness()` says which."""

    def close(self) -> None:
        self.store.close()


def _bindings(config: Any) -> dict[str, Any] | None:
    """The model bindings, or none at all on a machine nobody has configured yet.

    A fresh clone has no configuration document, and `--check` on a fresh clone is the
    case this command most needs to survive: somebody wants to know what they have before
    they set anything up. An empty binding set resolves to the firm default, which is what
    an unconfigured machine should say rather than a traceback.
    """
    try:
        bindings: dict[str, Any] = config.model_bindings()
    except KeyError:
        return None
    return bindings


def build(*, environment: str = "local", db_url: str | None = None) -> Served:
    """Wire every component together. No server, no threads, no side effects beyond the
    store the environment already points at - which is what makes it testable."""
    from fastapi import FastAPI

    import ports
    from admin import AdminConsole, Preflight
    from admin.app import create_admin_app, install_identity
    from deliver.registry import TemplateRegistry
    from graph.resolve import ScopeResolver
    from intake import Intake
    from intake.config import ConfigStore
    from intake.launch import RunLauncher
    from intake.lock import EngagementLock
    from intake.roster import ProjectRoster
    from intake.store import IntakeStore
    from ops.console import Console
    from ops.console.app import create_app
    from ops.events import EventBus
    from ops.run_store import open_store
    from registries.constraints import ConstraintRegistry
    from registries.contracts import ContractRegistry

    store = open_store(db_url)
    contracts = ContractRegistry.load()
    constraints = ConstraintRegistry.load()
    bus = EventBus(store, contracts=contracts)

    config = ConfigStore(store, contracts, environment=environment)
    roster = ProjectRoster(store, config)
    intake_store = IntakeStore(store)

    # Register the templates the scope bindings name. Without this the registry is empty,
    # every engagement resolves to an unregistered template, and preflight refuses to
    # activate anything - which is correct, and reads like the system is broken rather
    # than unconfigured. A missing workbook is left to preflight to report in words: the
    # masters are generated rather than committed, so absent is an ordinary first-day
    # state and not a reason the process should fail to start.
    templates = TemplateRegistry()
    for binding in ScopeResolver(bindings=_bindings(config)).bindings.values():
        if not binding.file:
            continue  # a layer bound to nothing falls through to a higher one
        try:
            templates.register_bindings([binding])
        except Exception as unregistered:  # noqa: BLE001, PERF203 - one bad binding is one
            # One at a time on purpose. Registering them as a batch means the first
            # template without an input schema stops the rest from registering, and one
            # practice group being unfinished should not make every other group's
            # engagements unactivatable.
            print(f"  {binding.layer}: {unregistered}")

    preflight = Preflight(
        config,
        roster,
        storage=ports.get_storage(),
        delivery=ports.get_delivery(),
        secrets=ports.get_secrets(),
        templates=templates,
        resolver=ScopeResolver(bindings=_bindings(config)),
        intake_store=intake_store,
        constraints=constraints,
    )
    admin = AdminConsole(config, roster, preflight, constraints=constraints)
    ops = Console(store, bus, constraints=constraints)
    def planner(engagement_id: str, recipe: Any) -> dict[str, Any]:
        """What a launch records on the run: the plan hash it will execute under, and the
        version pins. Computed by the same function the driver compiles with, so the two
        cannot disagree."""
        from precedent.store import PrecedentStore  # noqa: PLC0415
        from workers.driver import plan_for  # noqa: PLC0415

        entry = roster.get(engagement_id)
        plan, versions = plan_for(
            entry, recipe, config=config, precedents=PrecedentStore(store),
            contracts=contracts, constraints=constraints,
        )
        return {"plan_hash": plan.plan_hash, "versions": versions}

    intake = Intake(
        ports.get_storage(),
        roster,
        config,
        intake_store,
        RunLauncher(store, bus, EngagementLock(store, bus), intake_store),
        launch_planner=planner,
    )

    # One app carrying both routers rather than two mounted sub-applications: mounting
    # would move every admin path under a prefix, and the paths are the contract the
    # dashboard and every test are written against.
    app = FastAPI(title="Chartwell Automated Analyst", docs_url=None, redoc_url=None)
    # On the app that is served, not on the one whose routes it borrows: a router does not
    # carry its application's middleware, so installing it there would leave this one with
    # no check at all.
    install_identity(app)
    app.include_router(create_admin_app(admin).router)
    app.include_router(create_app(ops).router)

    @app.get("/api/readiness")
    def _readiness() -> dict[str, Any]:
        seams = readiness()
        return {
            "ready": all(s.ready for s in seams),
            "seams": [{"name": s.name, "ready": s.ready, "detail": s.detail} for s in seams],
        }

    pool = _pool(store, bus, config, roster, intake_store, templates, contracts, constraints)

    return Served(app=app, admin=admin, ops=ops, intake=intake, store=store,
                  config=config, roster=roster, pool=pool)


def _pool(
    store: Any,
    bus: Any,
    config: Any,
    roster: Any,
    intake_store: Any,
    templates: Any,
    contracts: Any,
    constraints: Any,
) -> Any:
    """The worker pool, with the driver that carries a run.

    Returns None rather than raising when something the driver needs is absent - a vault
    that cannot be opened without a key, most often, on a machine where nobody has written
    a `.env` yet. The readiness report says so, which is more use than a traceback at
    startup on the one command somebody runs to find out what they have.
    """
    import ports  # noqa: PLC0415
    from guards.untrusted import UntrustedBoundary  # noqa: PLC0415
    from harness.budget import BudgetGovernor  # noqa: PLC0415
    from harness.context import ContextBuilder  # noqa: PLC0415
    from harness.dispatch import SkillDispatcher  # noqa: PLC0415
    from harness.door import ModelDoor  # noqa: PLC0415
    from harness.policy import PolicyGate  # noqa: PLC0415
    from harness.runtime import GuardedRuntime  # noqa: PLC0415
    from intake.lock import EngagementLock  # noqa: PLC0415
    from ops.blobs import LocalContentStore  # noqa: PLC0415
    from ops.cost import CostMeter  # noqa: PLC0415
    from ops.source_parse import SourceParseStore  # noqa: PLC0415
    from precedent.store import PrecedentStore  # noqa: PLC0415
    from privacy.mask import Masker  # noqa: PLC0415
    from privacy.payload_scan import PayloadScan  # noqa: PLC0415
    from privacy.vault import open_vault  # noqa: PLC0415
    from registries.skills import SkillTree  # noqa: PLC0415
    from workers.driver import RunDriver, RunWiring  # noqa: PLC0415
    from workers.pool import WorkerPool  # noqa: PLC0415

    try:
        vault = open_vault(ports.get_secrets())
    except Exception as unopened:  # noqa: BLE001 - reported, not raised
        print(f"  the pool did not start: {unopened.__class__.__name__}: {unopened}")
        return None

    blobs = LocalContentStore()
    meter = CostMeter(store)
    governor = BudgetGovernor(constraints, meter, bus, store)
    tree = SkillTree.load()
    runtime = GuardedRuntime(PolicyGate(constraints, bus), constraints, bus, {})
    boundary = UntrustedBoundary(bus)

    def dispatcher_for(_run_id: str) -> SkillDispatcher:
        return SkillDispatcher(
            tree=tree,
            context=ContextBuilder(tree, blobs, bus, store=store),
            door=ModelDoor(ports.get_llm(), PayloadScan(bus), governor, meter, bus),
            runtime=runtime,
            contracts=contracts,
            boundary=boundary,
            masker=Masker(vault),
            bus=bus,
            blobs=blobs,
        )

    driver = RunDriver(
        RunWiring(
            store=store,
            bus=bus,
            blobs=blobs,
            contracts=contracts,
            constraints=constraints,
            config=config,
            roster=roster,
            intake_store=intake_store,
            parse_store=SourceParseStore(store),
            dispatcher_for=dispatcher_for,
            templates=templates,
            precedents=PrecedentStore(store),
            delivery=ports.get_delivery(),
            storage=ports.get_storage(),
            boundary=boundary,
        )
    )
    return WorkerPool(store, bus, EngagementLock(store, bus), driver)


def sweep_forever(served: Served, seconds: int, stop: threading.Event) -> None:
    """Sweep the watched folders on an interval until asked to stop.

    Errors are printed and the loop continues. A sweep that fails because somebody
    unplugged a network drive should not take the consoles down with it - and the
    consoles are how anybody would find out what happened.
    """
    while not stop.wait(seconds):
        try:
            result = served.intake.sweep()
        except Exception as failed:  # noqa: BLE001 - a bad sweep is not a dead process
            print(f"  sweep failed: {failed.__class__.__name__}: {failed}", flush=True)
            continue
        for engagement_id, why in getattr(result, "not_launched", ()):
            print(f"  {engagement_id} did not launch: {why[:160]}", flush=True)
        if not result.runs:
            continue
        when = datetime.now(tz=UTC).strftime("%H:%M:%S")
        print(f"  {when} released {len(result.runs)} run(s): {', '.join(result.runs)}", flush=True)
        if served.pool is None:
            print("  nothing to drive them: see the readiness report", flush=True)
            continue
        try:
            served.pool.submit_all(result.runs)
            served.pool.work()
        except Exception as failed:  # noqa: BLE001 - one bad run is not a dead process
            print(f"  a run did not finish: {failed.__class__.__name__}: {failed}", flush=True)


def report(served: Served) -> int:
    """What was built, what is ready, and what setup still needs. The return code is
    whether the system could take work, not whether it started."""
    seams = readiness()
    print("\n  Chartwell Automated Analyst\n")
    for seam in seams:
        print(seam.line())

    print("\n  Configuration:")
    try:
        document = served.config.document()
        watches = len(document.get("watches", []))
        active = len(list(served.roster.active()))
        print(f"    environment {served.config.environment}, "
              f"{watches} watch(es), {active} active engagement(s)")
    except Exception as unread:  # noqa: BLE001 - an unconfigured machine is the usual case
        print(f"    no configuration document yet ({unread.__class__.__name__}).")
        print("    Set one up at /admin, or see docs/USING.md.")
        return 1

    check = served.admin.check()
    print(f"    preflight: {'PASS' if check.passed else 'FAIL'}")
    for line in check.report().splitlines()[1:]:
        print(f"    {line}")
    return 0 if check.passed and all(s.ready for s in seams) else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--environment", default="local")
    parser.add_argument("--sweep-seconds", type=int, default=DEFAULT_SWEEP_SECONDS)
    parser.add_argument("--no-sweep", action="store_true", help="do not watch any folder")
    parser.add_argument("--check", action="store_true",
                        help="wire everything, start nothing, and report")
    args = parser.parse_args(argv)

    served = build(environment=args.environment)
    code = report(served)
    if args.check:
        served.close()
        return code

    stop = threading.Event()
    if not args.no_sweep:
        threading.Thread(
            target=sweep_forever, args=(served, args.sweep_seconds, stop), daemon=True
        ).start()
        print(f"\n  Sweeping every {args.sweep_seconds}s.")

    print(f"\n  http://{args.host}:{args.port}/        the ops console")
    print(f"  http://{args.host}:{args.port}/admin   setup and engagements\n")

    import uvicorn

    try:
        uvicorn.run(served.app, host=args.host, port=args.port, log_level="warning")
    finally:
        stop.set()
        time.sleep(0)
        served.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
