"""Setup Preflight: checks a setup before anyone relies on it, and says exactly what is
wrong.

Eleven checks over the live configuration, the roster and the ports:

 1. every watch root is readable through the Storage Port
 2. every credential the environment expects is present and unexpired - presence and
    dates only, never a value
 3. no two watches claim one path
 4. every swept subfolder maps to an engagement (unclaimed ones are a warning, routed
    to a person, never guessed)
 5. every active engagement's scope resolves to at least one skill
 6. every active engagement's practice group and segment are defined, rather than
    resolving to the firm layer only - a warning, because that is correct and not
    useful, and silence would make a short list look like a considered answer
 7. every active engagement has a complete engagement profile, with a checkpoint
    policy naming an owner and an SLA (finding F1)
 8. every active engagement resolves to exactly one destination and exactly one
    template pin, and that template is registered
 9. the template on disk is the bytes the registry pinned, and declares every
    required input
10. every destination is writable through the Delivery Port
11. every watch names a recipe that exists, and every run budget sits at or under the
    firm ceiling

A setup error found here costs a minute. The same error found at run time costs a
halted run, a diagnostic somebody has to read, and a client waiting. Preflight is a
setup-time activity: it is not part of any run, emits into no run's event stream, and
colours no node on the trace. It returns diagnostics; the console decides what they
block.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any

from deliver.registry import TemplateRegistry, version_key
from graph.recipes import load_recipe
from graph.resolve import ScopeResolver, TemplateBinding
from intake.config import ConfigStore
from intake.roster import ProjectRoster, RosterEntry
from intake.store import IntakeStore
from registries.constraints import ConstraintRegistry
from registries.errors import (
    BINDING_MISSING,
    BUDGET_ABOVE_CEILING,
    CREDENTIAL_EXPIRED,
    DESTINATION_UNWRITABLE,
    GROUP_UNDEFINED,
    METHODOLOGY_TOO_LARGE,
    METHODOLOGY_UNCLEARED,
    MISSING_CREDENTIAL,
    NO_ENGAGEMENT,
    PATH_UNREADABLE,
    PROFILE_INCOMPLETE,
    RECIPE_INVALID,
    TEMPLATE_HASH_MISMATCH,
    TEMPLATE_INPUTS_MISSING,
    TEMPLATE_UNREGISTERED,
    UNRESOLVED_SCOPE,
    Diagnostic,
    DiagnosticError,
    diagnose,
)
from registries.methodology import MethodologyRegister
from registries.scopes import ScopePath

__all__ = ["CHECKS", "Check", "Failure", "Preflight", "PreflightReport", "resolve_model"]

EXPIRY_WARNING_DAYS = 30
PROBE_NAME = "_preflight/probe.txt"

CHECKS: tuple[tuple[str, str], ...] = (
    ("watch_paths", "Watch paths readable"),
    ("credentials", "Credentials present and unexpired"),
    ("watch_overlap", "No two watches claim the same path"),
    ("unclaimed_folders", "Every swept subfolder maps to an engagement"),
    ("scope_resolves", "Every active engagement resolves to at least one skill"),
    ("scope_defined", "Every active engagement's practice group and segment are defined"),
    ("profile_complete", "Every active engagement has a complete engagement profile"),
    ("bindings", "Every active engagement resolves to one destination and one template"),
    ("template_intact", "Template hashes match and every required input is declared"),
    ("destinations_writable", "Delivery destinations writable"),
    ("recipes_and_budgets", "Named recipes exist and budgets are at or under the ceiling"),
    ("methodology_cleared", "Every methodology file is cleared, and is the cleared version"),
    ("methodology_size", "No layer of methodology is past its size ceiling"),
)


@dataclass(frozen=True)
class Failure:
    check: str
    diagnostic: Diagnostic
    engagement_ids: tuple[str, ...] = ()
    """Which engagements this failure blocks. Empty means the environment as a whole,
    which blocks every activation."""
    severity: str = "fail"
    """`fail` blocks; `warn` is shown and blocks nothing."""

    @property
    def blocks_everything(self) -> bool:
        return self.severity == "fail" and not self.engagement_ids


@dataclass(frozen=True)
class Check:
    id: str
    label: str
    status: str
    """`pass`, `warn` or `fail`."""
    detail: str
    failures: tuple[Failure, ...] = ()

    def line(self) -> str:
        return f"[{self.status.upper():<4}] {self.label}: {self.detail}"


@dataclass(frozen=True)
class PreflightReport:
    ran_at: str
    checks: tuple[Check, ...]
    engagement_id: str | None = None
    """Set when the report was run for one engagement's activation."""

    @property
    def failures(self) -> tuple[Failure, ...]:
        return tuple(f for c in self.checks for f in c.failures)

    @property
    def passed(self) -> bool:
        return all(c.status != "fail" for c in self.checks)

    def blocking(self, engagement_id: str) -> tuple[Failure, ...]:
        """Every failure that stops this engagement being activated: its own, and any
        that fails the environment it would run in."""
        return tuple(
            f
            for f in self.failures
            if f.severity == "fail" and (not f.engagement_ids or engagement_id in f.engagement_ids)
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "ran_at": self.ran_at,
            "engagement_id": self.engagement_id,
            "passed": self.passed,
            "checks": [
                {
                    "id": c.id,
                    "label": c.label,
                    "status": c.status,
                    "detail": c.detail,
                    "failures": [
                        {
                            "engagement_ids": list(f.engagement_ids),
                            "severity": f.severity,
                            **f.diagnostic.as_dict(),
                        }
                        for f in c.failures
                    ],
                }
                for c in self.checks
            ],
        }

    def report(self) -> str:
        head = f"preflight {'PASS' if self.passed else 'FAIL'} at {self.ran_at}"
        if self.engagement_id:
            head += f" for {self.engagement_id}"
        return "\n".join([head, *(f"  {c.line()}" for c in self.checks)])


def resolve_model(
    scope_path: str, bindings: dict[str, TemplateBinding], layers: tuple[str, ...]
) -> tuple[TemplateBinding | None, tuple[str, ...]]:
    """The model a scope builds into: the same five-layer walk the skills use, deepest
    binding wins, a layer bound to nothing falls through. Returns the binding and the
    layers walked, so the console can show where it came from."""
    found: TemplateBinding | None = None
    for layer in layers:
        binding = bindings.get(layer)
        if binding is not None and binding.file:
            found = binding
    return found, layers


class Preflight:
    def __init__(
        self,
        config: ConfigStore,
        roster: ProjectRoster,
        *,
        storage: Any,
        delivery: Any,
        secrets: Any,
        templates: TemplateRegistry,
        resolver: ScopeResolver | None = None,
        intake_store: IntakeStore | None = None,
        constraints: ConstraintRegistry | None = None,
        methodology: MethodologyRegister | None = None,
        recipes: Callable[[str], Any] = load_recipe,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.config = config
        self.roster = roster
        self.storage = storage
        self.delivery = delivery
        self.secrets = secrets
        self.templates = templates
        self.resolver = resolver
        self.intake_store = intake_store
        self.constraints = constraints or ConstraintRegistry.load()
        self.methodology = methodology or MethodologyRegister()
        self._recipes = recipes
        self._clock = clock or (lambda: datetime.now(tz=UTC))

    # -- running

    def run(self, engagement_id: str | None = None) -> PreflightReport:
        """Every check, over the live configuration. With `engagement_id`, the
        per-engagement checks consider that engagement whatever its roster state - it
        is the one about to be activated."""
        entries = self._entries(engagement_id)
        checks = (
            self._watch_paths(),
            self._credentials(),
            self._watch_overlap(),
            self._unclaimed(),
            self._scopes(entries),
            self._scope_defined(entries),
            self._profiles(entries),
            self._bindings(entries),
            self._templates(entries),
            self._destinations(),
            self._recipes_and_budgets(entries),
            self._methodology(),
            self._methodology_size(),
        )
        return PreflightReport(
            ran_at=self._clock().isoformat(timespec="seconds").replace("+00:00", "Z"),
            checks=checks,
            engagement_id=engagement_id,
        )

    def _entries(self, engagement_id: str | None) -> tuple[RosterEntry, ...]:
        active = list(self.roster.active())
        if engagement_id and engagement_id not in {e.engagement_id for e in active}:
            extra = self.roster.get(engagement_id)
            if extra is None:
                raise KeyError(f"{engagement_id} is not on the roster")
            active.append(extra)
        return tuple(active)

    # -- 1. watch paths

    def _watch_paths(self) -> Check:
        failures = []
        watches = self.config.watches()
        for watch in watches:
            try:
                self.storage.list(watch.root)
                root = getattr(self.storage, "root", None)
                if root is not None and watch.root and not (root / watch.root).is_dir():
                    raise FileNotFoundError(f"{watch.root} is not a folder under {root}")
            except Exception as failure:  # noqa: BLE001 - the port said no; that is the finding
                failures.append(
                    Failure(
                        "watch_paths",
                        diagnose(
                            PATH_UNREADABLE,
                            f"watch {watch.id} ({watch.name}) root {watch.root or '/'}: {failure}",
                            locator=f"config/watches/{watch.id}",
                        ),
                        engagement_ids=self._engagements_on_watch(watch.id),
                    )
                )
        return _check(
            "watch_paths",
            failures,
            f"{len(watches) - len(failures)} of {len(watches)} readable",
        )

    # -- 2. credentials

    def _credentials(self) -> Check:
        failures = []
        warnings = []
        today = self._clock().date()
        expected = self.config.credentials()
        for cred in expected:
            if not self.secrets.has(cred.name):
                failures.append(
                    Failure(
                        "credentials",
                        diagnose(
                            MISSING_CREDENTIAL,
                            f"{cred.name} ({cred.purpose}) is not in the Secrets Port",
                            locator=f"config/credentials/{cred.name}",
                        ),
                    )
                )
                continue
            if cred.expires_on:
                expires = date.fromisoformat(cred.expires_on)
                if expires <= today:
                    failures.append(
                        Failure(
                            "credentials",
                            diagnose(
                                CREDENTIAL_EXPIRED,
                                f"{cred.name} expired on {cred.expires_on}",
                                locator=f"config/credentials/{cred.name}",
                                expected=f"after {today.isoformat()}",
                                found=cred.expires_on,
                            ),
                        )
                    )
                elif expires <= today + timedelta(days=EXPIRY_WARNING_DAYS):
                    warnings.append(
                        Failure(
                            "credentials",
                            diagnose(
                                CREDENTIAL_EXPIRED,
                                f"{cred.name} expires on {cred.expires_on}, within "
                                f"{EXPIRY_WARNING_DAYS} days",
                                locator=f"config/credentials/{cred.name}",
                            ),
                            severity="warn",
                        )
                    )
        return _check(
            "credentials",
            failures + warnings,
            f"{len(expected)} expected, {len(expected) - len(failures)} present - "
            f"presence only, never the value",
        )

    # -- 3. overlap

    def _watch_overlap(self) -> Check:
        from intake.config import _check_no_overlap

        try:
            _check_no_overlap(self.config.watches())
        except DiagnosticError as refused:
            return _check(
                "watch_overlap",
                [Failure("watch_overlap", refused.diagnostic)],
                "overlap",
            )
        return _check("watch_overlap", [], f"{len(self.config.watches())} watches, no overlap")

    # -- 4. unclaimed

    def _unclaimed(self) -> Check:
        rows = self.intake_store.unclaimed() if self.intake_store is not None else ()
        warnings = [
            Failure(
                "unclaimed_folders",
                diagnose(
                    NO_ENGAGEMENT,
                    f"{row.location} under watch {row.watch_id}: {row.files} file(s), "
                    f"no engagement claims it",
                    locator=f"{row.watch_id}/{row.location}",
                ),
                severity="warn",
            )
            for row in rows
        ]
        return _check(
            "unclaimed_folders",
            warnings,
            f"{len(rows)} unclaimed - routed to a person, never guessed"
            if rows
            else "every swept folder maps to an engagement",
        )

    # -- 5. scopes

    def _scopes(self, entries: tuple[RosterEntry, ...]) -> Check:
        failures = []
        resolver = self._resolver()
        counts = []
        for entry in entries:
            try:
                resolved = resolver.resolve(entry.scope_path)
                if len(resolved) == 0:
                    raise DiagnosticError(
                        diagnose(
                            UNRESOLVED_SCOPE,
                            f"{entry.scope_path} resolves to no skills",
                            locator=entry.engagement_id,
                        )
                    )
                counts.append(len(resolved))
            except DiagnosticError as refused:
                failures.append(
                    Failure(
                        "scope_resolves",
                        refused.diagnostic,
                        engagement_ids=(entry.engagement_id,),
                    )
                )
        spread = f"{min(counts)}-{max(counts)} skills each" if counts else "none"
        return _check(
            "scope_resolves",
            failures,
            f"{len(entries) - len(failures)} of {len(entries)} resolve, {spread}",
        )

    def _scope_defined(self, entries: tuple[RosterEntry, ...]) -> Check:
        """Which engagements are scoped to a group nothing has been written for yet.

        Measured by resolving, not by reading the registry's `defined` flag: the flag is
        what somebody declared and the resolver is what a run actually gets, and when
        those two disagree the second one is the truth.
        """
        failures = []
        resolver = self._resolver()
        for entry in entries:
            try:
                resolved = resolver.resolve(entry.scope_path)
            except DiagnosticError:
                continue  # scope_resolves owns that failure; this check does not repeat it
            if not resolved.firm_layer_only:
                continue
            failures.append(
                Failure(
                    "scope_defined",
                    diagnose(
                        GROUP_UNDEFINED,
                        f"{entry.engagement_id} is scoped to {entry.scope_path}, which "
                        f"resolves to the firm layer only: {len(resolved)} firm skills and "
                        f"nothing of its group's. The group is scaffolded and nobody has "
                        f"named its segments yet.",
                        locator=entry.engagement_id,
                    ),
                    engagement_ids=(entry.engagement_id,),
                    severity="warn",
                )
            )
        named = len(entries) - len(failures)
        return _check(
            "scope_defined",
            failures,
            f"{named} of {len(entries)} scoped to a defined group",
        )

    # -- 6. profiles

    def _profiles(self, entries: tuple[RosterEntry, ...]) -> Check:
        failures = []
        for entry in entries:
            profile = self.config.profile(entry.engagement_id)
            missing = _profile_gaps(profile, entry.scope_path)
            if missing:
                failures.append(
                    Failure(
                        "profile_complete",
                        diagnose(
                            PROFILE_INCOMPLETE,
                            f"{entry.engagement_id}: {'; '.join(missing)}",
                            locator=f"config/engagements/{entry.engagement_id}/profile",
                        ),
                        engagement_ids=(entry.engagement_id,),
                    )
                )
        return _check(
            "profile_complete",
            failures,
            f"{len(entries) - len(failures)} of {len(entries)} complete",
        )

    # -- 7. bindings

    def _bindings(self, entries: tuple[RosterEntry, ...]) -> Check:
        failures = []
        destinations = {d.id for d in self.config.destinations()}
        for entry in entries:
            problems = []
            if entry.destination_id not in destinations:
                problems.append(f"destination {entry.destination_id!r} is not configured")
            pin = self.template_pin_for(entry)
            if pin is None:
                problems.append("no template at any layer of its scope and no pin on the roster")
            elif pin not in self.templates.keys():  # noqa: SIM118 - a method, not a dict
                failures.append(
                    Failure(
                        "bindings",
                        diagnose(
                            TEMPLATE_UNREGISTERED,
                            f"{entry.engagement_id} builds into {pin}, which the Template "
                            f"Registry has not registered",
                            locator=pin,
                        ),
                        engagement_ids=(entry.engagement_id,),
                    )
                )
            if problems:
                failures.append(
                    Failure(
                        "bindings",
                        diagnose(
                            BINDING_MISSING,
                            f"{entry.engagement_id}: {'; '.join(problems)}",
                            locator=f"roster/{entry.engagement_id}",
                        ),
                        engagement_ids=(entry.engagement_id,),
                    )
                )
        return _check(
            "bindings",
            failures,
            f"{len(entries) - len({e for f in failures for e in f.engagement_ids})} of "
            f"{len(entries)} bound to one destination and one template",
        )

    def template_pin_for(self, entry: RosterEntry) -> str | None:
        """The roster's pin if it has one, else the scope's binding through the same
        five-layer walk the skills use."""
        if entry.template_pin:
            return entry.template_pin
        try:
            layers = self._resolver().scopes.layers_for(ScopePath.parse(entry.scope_path))
        except DiagnosticError:
            return None
        binding, _ = resolve_model(entry.scope_path, self.config.model_bindings(), layers)
        return version_key(binding.file, binding.template_version) if binding else None

    # -- 8. templates

    def _templates(self, entries: tuple[RosterEntry, ...]) -> Check:
        failures = []
        checked: set[str] = set()
        for entry in entries:
            pin = self.template_pin_for(entry)
            if pin is None or pin in checked or pin not in self.templates.keys():  # noqa: SIM118
                continue
            checked.add(pin)
            registered = self.templates.get(pin)
            try:
                registered.read()
            except DiagnosticError as refused:
                failures.append(
                    Failure(
                        "template_intact",
                        diagnose(
                            TEMPLATE_HASH_MISMATCH,
                            refused.diagnostic.detail,
                            locator=pin,
                            expected=registered.content_hash,
                        ),
                        engagement_ids=self._engagements_on_pin(entries, pin),
                    )
                )
                continue
            missing = [n for n in registered.inputs.required if n not in registered.named_ranges]
            if missing:
                failures.append(
                    Failure(
                        "template_intact",
                        diagnose(
                            TEMPLATE_INPUTS_MISSING,
                            f"{pin} declares {len(registered.inputs.required) - len(missing)} of "
                            f"{len(registered.inputs.required)} required inputs",
                            locator=pin,
                            delta=", ".join(missing),
                        ),
                        engagement_ids=self._engagements_on_pin(entries, pin),
                    )
                )
        return _check(
            "template_intact",
            failures,
            f"{len(checked) - len(failures)} of {len(checked)} templates intact and complete",
        )

    # -- 9. destinations

    def _destinations(self) -> Check:
        failures = []
        destinations = self.config.destinations()
        for dest in destinations:
            try:
                self.delivery.ensure_folder(dest.path)
                self.delivery.put(f"{dest.path}/{PROBE_NAME}", b"preflight probe\n")
            except Exception as failure:  # noqa: BLE001 - the port said no
                failures.append(
                    Failure(
                        "destinations_writable",
                        diagnose(
                            DESTINATION_UNWRITABLE,
                            f"{dest.id} ({dest.name}) at {dest.path}: {failure}",
                            locator=f"config/destinations/{dest.id}",
                        ),
                        engagement_ids=self._engagements_on_destination(dest.id),
                    )
                )
        return _check(
            "destinations_writable",
            failures,
            f"{len(destinations) - len(failures)} of {len(destinations)} writable - probe written",
        )

    # -- 10. recipes and budgets

    def _recipes_and_budgets(self, entries: tuple[RosterEntry, ...]) -> Check:
        failures = []
        for watch in self.config.watches():
            try:
                self._recipes(watch.recipe)
            except Exception as failure:  # noqa: BLE001 - a recipe that does not load
                failures.append(
                    Failure(
                        "recipes_and_budgets",
                        diagnose(
                            RECIPE_INVALID,
                            f"watch {watch.id} names recipe {watch.recipe!r}: {failure}",
                            locator=f"config/watches/{watch.id}",
                        ),
                        engagement_ids=self._engagements_on_watch(watch.id),
                    )
                )
        ceiling = float(self.constraints.ceilings["per_run"]["usd_max"])
        for entry in entries:
            if entry.budget_usd is not None and entry.budget_usd > ceiling:
                failures.append(
                    Failure(
                        "recipes_and_budgets",
                        diagnose(
                            BUDGET_ABOVE_CEILING,
                            f"{entry.engagement_id} budget ${entry.budget_usd:.2f} against a "
                            f"firm ceiling of ${ceiling:.2f}",
                            locator=f"roster/{entry.engagement_id}/budget_usd",
                            expected=f"<= {ceiling:.2f}",
                            found=f"{entry.budget_usd:.2f}",
                        ),
                        engagement_ids=(entry.engagement_id,),
                    )
                )
        budgets = [e.budget_usd for e in entries if e.budget_usd is not None]
        return _check(
            "recipes_and_budgets",
            failures,
            f"{len(self.config.watches())} recipes, {len(budgets)} run budgets, "
            f"max ${max(budgets) if budgets else 0:.2f}, firm ceiling ${ceiling:.2f}",
        )

    # -- plumbing

    def _resolver(self) -> ScopeResolver:
        if self.resolver is None:
            self.resolver = ScopeResolver(bindings=self.config.model_bindings())
        return self.resolver

    def _engagements_on_watch(self, watch_id: str) -> tuple[str, ...]:
        return tuple(e.engagement_id for e in self.roster.entries() if e.watch_id == watch_id)

    def _engagements_on_destination(self, destination_id: str) -> tuple[str, ...]:
        return tuple(
            e.engagement_id for e in self.roster.entries() if e.destination_id == destination_id
        )

    def _engagements_on_pin(self, entries: tuple[RosterEntry, ...], pin: str) -> tuple[str, ...]:
        return tuple(e.engagement_id for e in entries if self.template_pin_for(e) == pin)


    def _methodology(self) -> Check:
        """Whether the firm's reference material is cleared, and is what was cleared.

        Environment-level rather than per-engagement: `foundations/` reaches every model
        call, so an uncleared file there stops every run, not one. Reported at setup
        because the alternative is finding out from a run - and the person who finds out
        that way is an analyst waiting on a deliverable, not the person who edited the
        file.
        """
        failures = []
        for found in self.methodology.review():
            if found.attachable:
                continue
            detail = (
                f"{found.name} was cleared once, but not this version of it - somebody "
                f"edited it after it was read"
                if found.state == "edited"
                else f"{found.name} has never been cleared"
            )
            failures.append(
                Failure(
                    "methodology_cleared",
                    diagnose(
                        METHODOLOGY_UNCLEARED,
                        f"{detail}. It reaches every model call, so until somebody reads "
                        f"it and clears it, every run stops here.",
                        locator=found.name,
                        expected="a digest in the methodology register",
                        found=found.digest,
                    ),
                )
            )
        files = self.methodology.review()
        return _check(
            "methodology_cleared",
            failures,
            f"{len(files) - len(failures)} of {len(files)} methodology files cleared",
        )


    def _methodology_size(self) -> Check:
        """What each layer adds to every prompt of every run that walks through it.

        A standing cost, not a one-off: the firm layer is on every run there is, and a
        practice group layer is on every run of that group. Found at setup, because the
        alternative is finding it in a bill and not knowing which document caused it.
        """
        ceiling = self.constraints.methodology_ceiling()
        failures = []
        largest = 0
        for layer in self.methodology.layers():
            size = self.methodology.bytes_at(layer)
            largest = max(largest, size)
            if size <= ceiling:
                continue
            failures.append(
                Failure(
                    "methodology_size",
                    diagnose(
                        METHODOLOGY_TOO_LARGE,
                        f"foundations/{layer} is {size:,} bytes against a ceiling of "
                        f"{ceiling:,}. Every run resolving through this layer carries all "
                        f"of it, on every model call.",
                        locator=layer,
                        expected=f"{ceiling:,} bytes or fewer",
                        found=f"{size:,} bytes",
                    ),
                )
            )
        layers = self.methodology.layers()
        return _check(
            "methodology_size",
            failures,
            f"{len(layers)} layer(s), largest {largest:,} of {ceiling:,} bytes",
        )


def _profile_gaps(profile: dict[str, Any] | None, scope_path: str) -> list[str]:
    """What a profile is missing before three skills can read it. The contract holds
    the shape; this holds the three things a run stops on."""
    if profile is None:
        return ["no engagement profile recorded"]
    gaps = []
    policy = profile.get("checkpoint_policy") or {}
    if not str(policy.get("owner", "")).strip():
        gaps.append("checkpoint policy names no owner")
    if not policy.get("sla_hours"):
        gaps.append("checkpoint policy sets no review SLA")
    baseline = profile.get("owner_compensation_baseline") or {}
    if not baseline.get("amount"):
        gaps.append("no owner-compensation baseline, so EBITDA Normalization cannot run")
    declared = "/".join(str(profile.get(k, "")) for k in ("practice", "segment", "disposition"))
    if declared != scope_path:
        gaps.append(f"profile scope {declared} is not the roster's {scope_path}")
    return gaps


def _check(check_id: str, failures: list[Failure], detail: str) -> Check:
    label = dict(CHECKS)[check_id]
    if any(f.severity == "fail" for f in failures):
        status = "fail"
    elif failures:
        status = "warn"
    else:
        status = "pass"
    return Check(check_id, label, status, detail, tuple(failures))
