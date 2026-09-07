"""The Admin Console: the setup surface, and what an admin may and may not change.

Reads and writes the Configuration Store and the Active Project Roster; every write
lands in the Config Change Log with who, what, when and why. Preflight runs on every
write, and activation is gated on it: a failing check blocks activating that engagement
rather than failing later inside a run.

What an admin can do is a method here. What an admin cannot do is not a method here -
and where a method could be pushed past the line, it refuses with
`CONFIG.ADMIN_FORBIDDEN`:

* a review level may be raised, never lowered;
* a per-run budget may be set at or below the firm ceiling, never above it;
* a credential's presence can be seen, never its value.

Nothing here reaches a skill definition, a guard, the mask vault or the release gate.
Those enter through the governance chain (invariant 23: configuration writes the
engagement record; guards read the run).
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from admin.preflight import Preflight, PreflightReport, resolve_model
from graph.recipes import load_recipe
from graph.resolve import TemplateBinding
from intake.config import CONTRACT, ConfigStore, Destination, Watch
from intake.roster import ProjectRoster, RosterEntry, RosterState
from registries.constraints import ConstraintRegistry
from registries.errors import ADMIN_FORBIDDEN, RECIPE_INVALID, DiagnosticError, diagnose
from registries.scopes import ScopePath

__all__ = ["REVIEW_LEVELS", "AdminConsole", "AdminRefused"]

# The per-engagement review level ladder, lowest first. Raising is an admin action;
# lowering is not one at all.
REVIEW_LEVELS: tuple[str, ...] = ("standard", "elevated")


class AdminRefused(DiagnosticError):
    """The console would not make that change. Carries every diagnostic behind it."""

    def __init__(self, diagnostics: tuple[Any, ...]) -> None:
        super().__init__(diagnostics[0])
        self.diagnostics = diagnostics


class AdminConsole:
    def __init__(
        self,
        config: ConfigStore,
        roster: ProjectRoster,
        preflight: Preflight,
        *,
        constraints: ConstraintRegistry | None = None,
    ) -> None:
        self.config = config
        self.roster = roster
        self.preflight = preflight
        self.constraints = constraints or ConstraintRegistry.load()

    # -- reading

    def setup(self) -> dict[str, Any]:
        """Everything the Admin tab shows, in one shape."""
        doc = self.config.document()
        return {
            "environment": self.config.environment,
            "version": self.config.version(),
            "watches": [w.__dict__ for w in self.config.watches()],
            "destinations": [d.__dict__ for d in self.config.destinations()],
            "model_bindings": [b.__dict__ for b in self.config.model_bindings().values()],
            "credentials": [
                {**c.__dict__, "present": self.preflight.secrets.has(c.name)}
                for c in self.config.credentials()
            ],
            "intake": dict(doc["intake"]),
            "roster": [self._entry_row(e) for e in self.roster.entries()],
            "firm_ceiling_usd": self.firm_ceiling,
            "can": CAN,
            "cannot": CANNOT,
        }

    @property
    def firm_ceiling(self) -> float:
        return float(self.constraints.ceilings["per_run"]["usd_max"])

    def scope_choices(self) -> dict[str, Any]:
        """Every scope an engagement can be given, and which of them mean anything yet.

        The dashboard offers these rather than asking somebody to type
        `valuation/esop/repeat` correctly. The registry is the source: adding a practice
        group is an entry there, and it shows up here without anything else changing.

        `defined` is the registry's own flag - a group scaffolded but not yet described.
        `firm_layer_only` is the consequence, measured by resolving the path rather than
        inferred from the flag, because those two can disagree and the resolver is the one
        that decides what a run actually gets.
        """
        registry = self.preflight._resolver().scopes  # noqa: SLF001
        paths = []
        for path in registry.combinations():
            practice = registry.practice(path.practice)
            segment = practice.segment(path.segment)
            resolved = self.preflight._resolver().resolve(path)  # noqa: SLF001
            paths.append(
                {
                    "scope_path": str(path),
                    "defined": practice.defined and bool(segment and segment.defined),
                    "skills": len(resolved),
                    "firm_layer_only": resolved.firm_layer_only,
                }
            )
        return {
            "layer_order": list(registry.layer_order),
            "practices": [
                {
                    "id": p.id,
                    "name": p.name,
                    "defined": p.defined,
                    "note": p.note,
                    "segments": [
                        {"id": s.id, "name": s.name, "defined": s.defined} for s in p.segments
                    ],
                }
                for p in registry.practices
            ],
            "dispositions": [
                {"id": d.id, "name": d.name, "precedent_scope": d.precedent_scope, "note": d.note}
                for d in registry.dispositions
            ],
            "paths": paths,
        }

    def methodology(self) -> dict[str, Any]:
        """Every methodology file, and what the register says about it.

        What a dashboard shows somebody before they clear anything: which files are
        cleared and by whom, which have never been read, and which were edited after they
        were cleared - the third being the case worth seeing, because it is the one that
        looks fine on disk.
        """
        register = self.preflight.methodology
        return {
            "root": register.root.name,
            "layers": list(register.layers()),
            "files": [
                {
                    "name": found.name,
                    "layer": found.name.rsplit("/", 1)[0],
                    "digest": found.digest,
                    "state": found.state,
                    "cleared_by": found.cleared_by,
                    "cleared_at": found.cleared_at,
                }
                for found in register.review()
            ],
        }

    def clear_methodology(self, name: str, *, who: str) -> dict[str, Any]:
        """Record that a person read this file and cleared this exact content.

        The scan runs here, and a refusal is the answer rather than a warning beside a
        success. `who` is required by the register itself; this passes it through rather
        than defaulting it, because a default is how "cleared by nobody" gets back in.
        """
        register = self.preflight.methodology
        path = next((p for p in register.files() if register.name_of(p) == name), None)
        if path is None:
            raise KeyError(f"{name} is not a methodology file in {register.root.name}/")
        record = register.clear(path, cleared_by=who)
        return {
            "name": record.name,
            "digest": record.digest,
            "cleared_by": record.cleared_by,
            "cleared_at": record.cleared_at,
            "size_bytes": record.size_bytes,
        }

    def resolve_model(self, scope_path: str) -> dict[str, Any]:
        """Which model this scope builds into and which layer said so - the same
        five-layer walk the skills use."""
        layers = self.preflight._resolver().scopes.layers_for(ScopePath.parse(scope_path))  # noqa: SLF001
        binding, walked = resolve_model(scope_path, self.config.model_bindings(), layers)
        return {
            "scope_path": scope_path,
            "layers": list(walked),
            "binding": binding.__dict__ if binding else None,
            "bound_at": binding.layer if binding else None,
        }

    def changes(self) -> tuple[Any, ...]:
        return self.config.changes()

    def check(self, engagement_id: str | None = None) -> PreflightReport:
        return self.preflight.run(engagement_id)

    # -- the roster

    def register_engagement(
        self,
        entry: RosterEntry,
        *,
        profile: dict[str, Any] | None,
        who: str,
        reason: str,
    ) -> RosterEntry:
        """Put an engagement on the roster with its profile. Registered paused unless
        asked for active - and active only past preflight."""
        wanted = entry.state
        recorded = self.roster.register(
            replace(entry, state=RosterState.PAUSED), who=who, reason=reason
        )
        if profile is not None:
            self.set_profile(entry.engagement_id, profile, who=who, reason=reason)
        if wanted is RosterState.ACTIVE:
            return self.activate(entry.engagement_id, who=who, reason=reason)
        if wanted is RosterState.ARCHIVED:
            return self.roster.set_state(entry.engagement_id, wanted, who=who, reason=reason)
        return recorded

    def activate(self, engagement_id: str, *, who: str, reason: str) -> RosterEntry:
        """Active only when preflight passes for this engagement. The refusal carries
        every failing check, each with a code, an owner and what to do."""
        report = self.preflight.run(engagement_id)
        blocking = report.blocking(engagement_id)
        if blocking:
            raise AdminRefused(tuple(f.diagnostic for f in blocking))
        return self.roster.set_state(engagement_id, RosterState.ACTIVE, who=who, reason=reason)

    def pause(self, engagement_id: str, *, who: str, reason: str, note: str = "") -> RosterEntry:
        return self.roster.set_state(
            engagement_id, RosterState.PAUSED, who=who, reason=reason, note=note
        )

    def archive(self, engagement_id: str, *, who: str, reason: str, note: str = "") -> RosterEntry:
        return self.roster.set_state(
            engagement_id, RosterState.ARCHIVED, who=who, reason=reason, note=note
        )

    def set_budget(self, engagement_id: str, usd: float, *, who: str, reason: str) -> RosterEntry:
        """At or below the firm ceiling. Above it is a governance change."""
        if usd > self.firm_ceiling:
            raise AdminRefused(
                (
                    diagnose(
                        ADMIN_FORBIDDEN,
                        f"a per-run budget of ${usd:.2f} is above the firm ceiling of "
                        f"${self.firm_ceiling:.2f}",
                        locator=f"roster/{engagement_id}/budget_usd",
                        expected=f"<= {self.firm_ceiling:.2f}",
                        found=f"{usd:.2f}",
                    ),
                )
            )
        return self.roster.update(engagement_id, who=who, reason=reason, budget_usd=float(usd))

    def set_review_level(
        self, engagement_id: str, level: str, *, who: str, reason: str
    ) -> RosterEntry:
        """Raise only. The review requirement on an engagement can go up above the
        skill's floor; it cannot come down through this surface."""
        entry = self.roster.get(engagement_id)
        if entry is None:
            raise KeyError(f"{engagement_id} is not on the roster")
        if level not in REVIEW_LEVELS:
            raise ValueError(f"{level!r} is not a review level; one of {REVIEW_LEVELS}")
        if REVIEW_LEVELS.index(level) < REVIEW_LEVELS.index(entry.review_level):
            raise AdminRefused(
                (
                    diagnose(
                        ADMIN_FORBIDDEN,
                        f"review level on {engagement_id} may be raised from "
                        f"{entry.review_level}, not lowered to {level}",
                        locator=f"roster/{engagement_id}/review_level",
                        expected=f">= {entry.review_level}",
                        found=level,
                    ),
                )
            )
        return self.roster.update(engagement_id, who=who, reason=reason, review_level=level)

    def set_recipe(self, engagement_id: str, recipe: str, *, who: str, reason: str) -> int:
        """Choose the recipe this engagement runs, or clear it back to the watch's.

        Refused if the recipe does not load. A name that resolves to nothing would sweep
        cleanly and then fail every run it released, at which point the person who typed
        it is somewhere else - so it is checked here, where they are still reading.

        An empty name is not an error: it means inherit, which is where every engagement
        started and is the right way to undo this.
        """
        entry = self.roster.get(engagement_id)
        if entry is None:
            raise KeyError(f"{engagement_id} is not on the roster")

        chosen = recipe.strip()
        if chosen:
            try:
                load_recipe(chosen)
            except Exception as unloadable:
                raise AdminRefused(
                    (
                        diagnose(
                            RECIPE_INVALID,
                            f"{engagement_id} cannot run recipe {chosen!r}: {unloadable}",
                            locator=f"engagements/{engagement_id}/recipe",
                            expected="a recipe that loads",
                            found=chosen,
                        ),
                    )
                ) from unloadable

        doc = self.config.document()
        engagements = dict(doc.get("engagements") or {})
        over = dict(engagements.get(engagement_id) or {})
        if chosen:
            over["recipe"] = chosen
        else:
            over.pop("recipe", None)
        engagements[engagement_id] = over
        doc["engagements"] = engagements

        # A recipe has no home in 1.1.0, so writing one upgrades the document. Nothing
        # else does: a configuration that names no recipe stays the version it was.
        if chosen and doc.get("schema_version") != CONTRACT:
            doc["schema_version"] = CONTRACT
        return self._write(doc, who, reason)

    def bind_engagement(
        self,
        engagement_id: str,
        *,
        who: str,
        reason: str,
        destination_id: str | None = None,
        template_pin: str | None = None,
        watch_id: str | None = None,
        folder: str | None = None,
    ) -> RosterEntry:
        """Point an engagement at a destination, a template, a watch or a folder."""
        fields = {
            k: v
            for k, v in {
                "destination_id": destination_id,
                "template_pin": template_pin,
                "watch_id": watch_id,
                "folder": folder,
            }.items()
            if v is not None
        }
        if not fields:
            raise ValueError("nothing to bind")
        return self.roster.update(engagement_id, who=who, reason=reason, **fields)

    # -- the configuration document

    def set_profile(
        self, engagement_id: str, profile: dict[str, Any], *, who: str, reason: str
    ) -> int:
        """The engagement record configuration writes. Validated against its contract
        on the way in; the store refuses an invalid one before anything is written."""
        return self._edit_engagement(engagement_id, {"profile": dict(profile)}, who, reason)

    def set_intake_override(
        self,
        engagement_id: str,
        *,
        who: str,
        reason: str,
        quiet_period_minutes: float | None = None,
        max_wait_hours: float | None = None,
    ) -> int:
        """Tighten an engagement's intake timing. The store's `timing` reads these as a
        floor, never as a way to lengthen the environment's lock timeout."""
        over = {
            k: v
            for k, v in {
                "quiet_period_minutes": quiet_period_minutes,
                "max_wait_hours": max_wait_hours,
            }.items()
            if v is not None
        }
        return self._edit_engagement(engagement_id, over, who, reason)

    def profile_template(self, engagement_id: str) -> dict[str, Any]:
        """A skeleton engagement profile, and what is still missing from the real one.

        Registering an engagement is easy and activating it is not: three skills read the
        profile as a required input, so preflight refuses until it is complete. Without a
        starting point that refusal is correct and unactionable - the person is told
        twelve fields are missing and left to find out their shapes.

        What comes back is filled in where the system already knows the answer - the
        engagement id, the practice, segment and disposition from the scope path it was
        registered under - and blank where the answer is a judgment. `gaps` is preflight's
        own list, so the page and the check cannot disagree about what is missing.
        """
        entry = self.roster.get(engagement_id)
        if entry is None:
            raise KeyError(f"no engagement {engagement_id}")
        practice, segment, disposition = entry.scope_path.split("/")
        current = self.config.document().get("engagements", {}).get(engagement_id) or {}
        existing = current.get("profile") or {}

        skeleton: dict[str, Any] = {
            "schema_version": "engagement_profile@1.0.0",
            "engagement_id": engagement_id,
            "practice": practice,
            "segment": segment,
            "disposition": disposition,
            "industry_classification": {"system": "NAICS", "code": "", "description": ""},
            "size_band": {"metric": "revenue", "band": "", "as_of": ""},
            "fiscal_calendar": {"basis": "calendar", "year_end_month": 12, "year_end_day": 31},
            "scale_convention": 1,
            "owner_compensation_baseline": {
                "amount": 0,
                "currency": "USD",
                "basis": "survey_median",
                "source": "",
                "as_of": "",
            },
            "materiality_threshold": {"amount": 0, "currency": "USD"},
            "checkpoint_policy": {
                "owner": "",
                "sla_hours": 24,
                "auto_accept_confidence": 0.85,
                "always_review_categories": ["owner_related"],
            },
            "recorded_by": "",
            "recorded_at": "",
        }
        skeleton.update(existing)

        from admin.preflight import _profile_gaps  # noqa: PLC0415 - one direction only

        return {
            "engagement_id": engagement_id,
            "scope_path": entry.scope_path,
            "profile": skeleton,
            "gaps": _profile_gaps(existing or None, entry.scope_path),
        }

    def initialise(self, *, who: str, reason: str) -> dict[str, Any]:
        """Write the first configuration document for this environment.

        Every other write here reads the current document first, so on a machine that has
        never been configured all of them fail and the dashboard is unusable on the one
        day somebody most needs it. This is the way in.

        What it writes is empty and valid: no watch, no destination, no engagement, and
        the two credentials the system always needs named as expected rather than
        supplied. Those are decisions, and a starter file that guessed at them would be
        recording choices nobody made - the same reason the methodology register ships
        with nothing cleared.

        Refuses when a document already exists. Overwriting a live configuration is not
        an initialisation, and the ordinary edits are the way to change one.
        """
        if self.config.version() > 0:
            raise ValueError(
                f"{self.config.environment} is already configured "
                f"(version {self.config.version()}); edit it rather than initialising it"
            )
        document: dict[str, Any] = {
            "schema_version": "config_document@1.1.0",
            "environment": self.config.environment,
            "watches": [],
            "intake": {"quiet_period_minutes": 30, "max_wait_hours": 24, "lock_timeout_hours": 6},
            "document_type_conventions": {
                "trial_balance": ["tb_", "trial balance"],
                "financial_statements": ["income statement", "balance sheet", "financials"],
            },
            "destinations": [],
            "credentials": [],
            "model_bindings": [],
            "engagements": {},
        }
        version = self._write(document, who, reason)

        # The model bindings come from `templates/bindings.yaml`, which is checked in and
        # is the firm's record of which model each layer builds into. Without them the
        # first engagement anybody registers cannot be activated - it resolves to no
        # template - and the refusal is correct and unactionable. Seeding a record that
        # already exists is not deciding anything; leaving it out was.
        from graph.resolve import ScopeResolver  # noqa: PLC0415

        bindings = ScopeResolver().bindings
        if bindings:
            version = self.seed_model_bindings(
                bindings, who=who, reason="the checked-in model bindings, at initialisation"
            )
        return {
            "environment": self.config.environment,
            "version": version,
            "model_bindings": len(bindings),
        }

    def add_watch(self, watch: Watch, *, who: str, reason: str) -> int:
        doc = self.config.document()
        if any(w["id"] == watch.id for w in doc["watches"]):
            raise ValueError(f"watch {watch.id} exists; edit it instead")
        doc["watches"] = [*doc["watches"], _watch_row(watch)]
        return self._write(doc, who, reason)

    def edit_watch(self, watch: Watch, *, who: str, reason: str) -> int:
        doc = self.config.document()
        if not any(w["id"] == watch.id for w in doc["watches"]):
            raise KeyError(f"no watch {watch.id}")
        doc["watches"] = [_watch_row(watch) if w["id"] == watch.id else w for w in doc["watches"]]
        return self._write(doc, who, reason)

    def add_destination(self, destination: Destination, *, who: str, reason: str) -> int:
        doc = self.config.document()
        rows = list(doc.get("destinations") or [])
        if any(d["id"] == destination.id for d in rows):
            raise ValueError(f"destination {destination.id} exists")
        doc["destinations"] = [*rows, _destination_row(destination)]
        return self._write(doc, who, reason)

    def bind_model(
        self,
        layer: str,
        file: str | None,
        template_version: str | None,
        *,
        why: str,
        who: str,
        reason: str,
    ) -> int:
        """Bind a model to a practice area, a segment or a leaf scope - written once at
        the shallowest layer where it is true. `file=None` declares the layer with
        nothing bound, which falls through to the layer above."""
        doc = self.config.document()
        rows = [b for b in (doc.get("model_bindings") or []) if b["layer"] != layer]
        rows.append(
            {
                "layer": layer,
                "file": file,
                "template_version": template_version,
                "why": why,
            }
        )
        doc["model_bindings"] = rows
        return self._write(doc, who, reason)

    def seed_model_bindings(
        self, bindings: dict[str, TemplateBinding], *, who: str, reason: str
    ) -> int:
        """Bring the checked-in `templates/bindings.yaml` into the configuration, once,
        so the store is the live record from then on."""
        doc = self.config.document()
        doc["model_bindings"] = [
            {
                "layer": b.layer,
                "file": b.file or None,
                "template_version": b.template_version or None,
                "why": b.why,
            }
            for b in bindings.values()
        ]
        return self._write(doc, who, reason)

    def record_credential(
        self,
        name: str,
        purpose: str,
        *,
        expires_on: str | None,
        who: str,
        reason: str,
    ) -> int:
        """Say that the environment expects a credential and when it expires. The value
        is rotated through the Secrets Port; nothing here can hold or show it."""
        doc = self.config.document()
        rows = [c for c in (doc.get("credentials") or []) if c["name"] != name]
        row: dict[str, Any] = {"name": name, "purpose": purpose}
        if expires_on:
            row["expires_on"] = expires_on
        doc["credentials"] = [*rows, row]
        return self._write(doc, who, reason)

    def credential_present(self, name: str) -> bool:
        """Presence, never the value."""
        present: bool = self.preflight.secrets.has(name)
        return present

    # -- plumbing

    def _edit_engagement(
        self, engagement_id: str, fields: dict[str, Any], who: str, reason: str
    ) -> int:
        doc = self.config.document()
        engagements = dict(doc.get("engagements") or {})
        engagements[engagement_id] = {**(engagements.get(engagement_id) or {}), **fields}
        doc["engagements"] = engagements
        return self._write(doc, who, reason)

    def _write(self, doc: dict[str, Any], who: str, reason: str) -> int:
        """Every write is validated by the store and logged field by field there."""
        return self.config.write(doc, who=who, reason=reason)

    def _entry_row(self, entry: RosterEntry) -> dict[str, Any]:
        return {
            "engagement_id": entry.engagement_id,
            "client": entry.client,
            "scope_path": entry.scope_path,
            "state": str(entry.state),
            "watch_id": entry.watch_id,
            "folder": entry.folder,
            "destination_id": entry.destination_id,
            "template_pin": entry.template_pin or self.preflight.template_pin_for(entry),
            "recipe": entry.recipe,
            "budget_usd": entry.budget_usd,
            "review_level": entry.review_level,
            "note": entry.note,
            "profile_recorded": self.config.profile(entry.engagement_id) is not None,
        }


CAN: tuple[str, ...] = (
    "Activate, pause and archive engagements - which decides the folders swept tonight",
    "Add and edit watch locations, subfolder patterns and delivery destinations",
    "Bind a model to a practice area, a segment or one engagement",
    "Raise the review requirement on an engagement above the skill's floor",
    "Set a per-run budget at or below the firm ceiling",
    "Rotate a credential, and see whether one is present - never its value",
    "Choose the delivery adapter per destination",
)
CANNOT: tuple[str, ...] = (
    "Disable a guard that fails closed, or move one out of the path",
    "Lower a skill's review floor - a scope overlay may only tighten, and so may this",
    "Turn off masking, or reach the mask vault",
    "Raise a budget above the firm ceiling - that is a governance change, not a setup one",
    "Edit a skill, a prompt or a schema - those enter through the governance chain",
    "Write into the live skills/ tree - the Registry is its only writer",
    "Release a deliverable, or bypass the release gate",
)


def _watch_row(watch: Watch) -> dict[str, Any]:
    row: dict[str, Any] = {
        "id": watch.id,
        "kind": watch.kind,
        "name": watch.name,
        "root": watch.root,
        "recipe": watch.recipe,
    }
    if watch.kind == "bound":
        row["engagement_id"] = watch.engagement_id
    else:
        row["depth"] = watch.depth
    return row


def _destination_row(destination: Destination) -> dict[str, Any]:
    row: dict[str, Any] = {
        "id": destination.id,
        "name": destination.name,
        "path": destination.path,
        "adapter": destination.adapter,
    }
    if destination.credential:
        row["credential"] = destination.credential
    return row
