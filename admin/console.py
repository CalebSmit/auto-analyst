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

import hashlib
from dataclasses import replace
from pathlib import Path
from typing import Any

from admin.preflight import Preflight, PreflightReport, resolve_model
from graph.recipes import load_recipe
from graph.resolve import TemplateBinding
from intake.config import CONTRACT, ConfigStore, Destination, Watch
from intake.roster import ProjectRoster, RosterEntry, RosterState
from registries.constraints import ConstraintRegistry
from registries.errors import (
    ADMIN_FORBIDDEN,
    RECIPE_INVALID,
    UNKNOWN_ADAPTER,
    UNKNOWN_CRITERIA,
    DiagnosticError,
    diagnose,
)
from registries.scopes import ScopePath

__all__ = ["REVIEW_LEVELS", "AdminConsole", "AdminRefused", "AlreadyApproved"]

# How long a started sign-in stays acceptable. Long enough for an MFA prompt on a phone
# somebody has to go and find; short enough that a state left lying around is not a value
# that would still be honoured tomorrow.
LOGIN_WINDOW_SECONDS = 15 * 60


def _now() -> float:
    import time

    return time.monotonic()


# The per-engagement review level ladder, lowest first. Raising is an admin action;
# lowering is not one at all.
REVIEW_LEVELS: tuple[str, ...] = ("standard", "elevated")

# The largest file the Setup page will place in a watched folder. A client's statements,
# schedules and exports are well under it; a data room is not a thing to upload one file at a
# time through a browser.
MAX_UPLOAD_BYTES = 50 * 1024 * 1024


class AlreadyApproved(Exception):
    """This exact file is already approved, so approving it again would record nothing.

    Not a refusal of the kind `AdminRefused` carries - nothing was attempted that an admin
    may not do. It is the surface answering a question: the answer is "somebody already
    did, here is who and when".
    """


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
        self._logins: dict[str, float] = {}
        """Sign-ins started and not yet finished, state -> when. In memory, so a restart
        invalidates them - see start_sharefile_login."""

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
            "inbox_root": _local_root(self.preflight.storage),
            "outbox_root": _local_root(self.preflight.delivery),
            "review_levels": list(REVIEW_LEVELS),
            # Which *AI* model answers, which no screen said anywhere. The word "model"
            # means the Excel template in three other places on this page, so somebody
            # looking for this found three controls named model and none of them was it.
            # Read from the ports rather than declared, so it cannot drift from the run.
            "ai_model": self._ai_model(),
            "can": CAN,
            "cannot": CANNOT,
        }

    # -- an engagement's files, for the person who has them

    def _folder_of(self, engagement_id: str) -> tuple[RosterEntry, str]:
        entry = self.roster.get(engagement_id)
        if entry is None:
            raise KeyError(f"{engagement_id} is not on the roster")
        watch = next((w for w in self.config.watches() if w.id == entry.watch_id), None)
        if watch is None:
            raise KeyError(f"{engagement_id} names watch {entry.watch_id!r}, which is not set up")
        if watch.is_bound:
            return entry, watch.root
        if not entry.folder:
            raise ValueError(f"{engagement_id} has no folder under watch {watch.id}")
        return entry, f"{watch.root}/{entry.folder}" if watch.root else entry.folder

    def engagement_files(self, engagement_id: str) -> dict[str, Any]:
        """Where an engagement's files go, and what is there now.

        What the Setup page shows so nobody has to work out a folder path: the path under the
        watch, the whole path on this machine when storage is a local folder, and every file
        the sweep would see.
        """
        entry, relative = self._folder_of(engagement_id)
        storage = self.preflight.storage
        base = _local_root(storage)
        files = []
        for ref in storage.list(relative):
            stat = storage.stat(ref)
            inside = ref.path.startswith(relative + "/")
            files.append(
                {
                    "path": ref.path[len(relative) + 1 :] if inside else ref.path,
                    "bytes": stat.size_bytes,
                    "modified": stat.modified_at.isoformat(),
                }
            )
        return {
            "engagement_id": entry.engagement_id,
            "client": entry.client,
            "state": str(entry.state),
            "relative": relative,
            "absolute": str(Path(base) / relative) if base else None,
            "can_add": base is not None and entry.state is not RosterState.ARCHIVED,
            "files": files,
            "quiet_period_minutes": self.config.timing(engagement_id).quiet_period_minutes,
        }

    def add_file(
        self, engagement_id: str, name: str, data: bytes, *, who: str, reason: str
    ) -> dict[str, Any]:
        """Place one file in the engagement's watched folder - what a person dropping it there
        would do, and nothing more. The sweep finds it, holds it through the quiet period and
        fingerprints it like any other file; nothing here reads it.

        Only where storage is a folder on this machine. Recorded against the person, with the
        file's size and digest, so "who put this file here" has an answer.
        """
        base = _local_root(self.preflight.storage)
        if base is None:
            raise ValueError(
                "files can be added from the page only when storage is a local folder; "
                "put them where the storage port reads from"
            )
        entry, relative = self._folder_of(engagement_id)
        if entry.state is RosterState.ARCHIVED:
            raise ValueError(f"{engagement_id} is archived; nothing more is read for it")
        clean = _safe_filename(name)
        if not data:
            raise ValueError(f"{clean} is empty")
        if len(data) > MAX_UPLOAD_BYTES:
            raise ValueError(f"{clean} is larger than {MAX_UPLOAD_BYTES // (1024 * 1024)} MB")
        if not who.strip() or not reason.strip():
            raise ValueError("adding a file names a person and gives a reason")
        folder = Path(base) / relative
        target = (folder / clean).resolve()
        if Path(base).resolve() not in target.parents:
            raise ValueError(f"{clean} would land outside the watched folder")
        replaced = target.exists()
        folder.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        digest = "sha256:" + hashlib.sha256(data).hexdigest()
        self.config.log_change(
            who=who,
            field=f"files/{engagement_id}",
            old={},
            new=(placed := {
                "file": f"{relative}/{clean}",
                "bytes": len(data),
                "digest": digest,
                "replaced": replaced,
            }),
            reason=reason,
        )
        return placed

    def methodology_text(self, name: str) -> dict[str, Any]:
        """A methodology file's text, so it can be read on the page it is cleared from."""
        register = self.preflight.methodology
        found = next((p for p in register.files() if register.name_of(p) == name), None)
        if found is None:
            raise KeyError(f"no methodology file {name!r}")
        return {"name": name, "text": found.read_text(encoding="utf-8")}

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
        groups: dict[str, dict[str, Any]] = {}
        for path in registry.combinations():
            practice = registry.practice(path.practice)
            segment = practice.segment(path.segment)
            resolved = self.preflight._resolver().resolve(path)  # noqa: SLF001
            paths.append(
                {
                    "scope_path": str(path),
                    "focus": registry.in_focus(path),
                    "parked": bool(segment and segment.parked),
                    "defined": practice.defined and bool(segment and segment.defined),
                    "skills": len(resolved),
                    "firm_layer_only": resolved.firm_layer_only,
                }
            )
            # A practice group is the path without its disposition, and the page asks for
            # the two separately because they are two questions. Built here from the parts
            # the registry already has rather than by splitting the joined string on the
            # page: which segment means what is this module's business, and a page that
            # sliced the path would be a second place to be wrong about it - which is what
            # C47 holds the page to.
            group = f"{path.practice}/{path.segment}"
            groups.setdefault(
                group,
                {
                    "group": group,
                    "name": f"{practice.name} - {segment.name}" if segment else practice.name,
                    "focus": registry.in_focus(path),
                    "parked": bool(segment and segment.parked),
                    "defined": practice.defined and bool(segment and segment.defined),
                },
            )
        # The focus first, parked last; declaration order otherwise. Sorting is stable.
        paths.sort(key=lambda p: (not p["focus"], p["parked"]))
        ordered = sorted(groups.values(), key=lambda g: (not g["focus"], g["parked"]))
        return {
            "focus": "/".join(registry.focus) if registry.focus else None,
            "layer_order": list(registry.layer_order),
            "groups": ordered,
            "practices": [
                {
                    "id": p.id,
                    "name": p.name,
                    "defined": p.defined,
                    "note": p.note,
                    "segments": [
                        {"id": s.id, "name": s.name, "defined": s.defined, "parked": s.parked}
                        for s in p.segments
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

    def approve_recipe(
        self,
        name: str,
        *,
        who: str,
        reason: str,
        register: Any | None = None,
        board: Any | None = None,
    ) -> dict[str, Any]:
        """Record that a person approved this exact version of a workflow.

        The register was unwritable outside the test suite, which is not the same thing as
        being protected: on a clean clone no recipe loaded, preflight check 10 failed, no
        engagement activated and no run started, and there was nothing anywhere to click.
        Refusing to do it badly had become refusing to do it.

        So this goes *through* `SkillBoard.register_recipe` rather than around it. The board
        is still the only writer, it still refuses anything that is not an approval, and the
        chain still records who approved what and why. What changed is that a person can now
        perform the approval instead of only a test being able to.

        `reason` is required and not defaulted. A registration with no reason is the shape
        of a decision without the decision in it, and this record outlives everybody who
        remembers the conversation.

        `register` and `board` default to the real ones and are injectable, the way
        `SkillBoard.register_recipe` already takes its register - so a test can prove this
        refuses what it should without writing to the machine's own governance chain.
        """
        from pathlib import Path  # noqa: PLC0415

        from governance.board import Decision, SkillBoard  # noqa: PLC0415
        from governance.record import GovernanceRecord  # noqa: PLC0415
        from ops.blobs import LocalContentStore  # noqa: PLC0415
        from registries.recipes import RecipeRegister  # noqa: PLC0415

        if not who.strip():
            raise ValueError("an approval names a person; nothing here defaults that")
        if not reason.strip():
            raise ValueError(f"{name} needs a reason for approval, recorded with it")

        from registries.recipes import digest_of_recipe  # noqa: PLC0415

        register = register or RecipeRegister()
        path = Path(register.root) / f"{name}.yaml"
        if not path.is_file():
            raise KeyError(f"{name} is not a recipe in {Path(register.root).name}/")

        # Already approved, at exactly these bytes. The register is write-once per digest -
        # the same file is the same approval, which is right - so `register` would return the
        # existing row and write nothing. P57 sent it through the board anyway, which
        # appended a REGISTERED entry to the governance chain naming a person whose approval
        # produced no registration, beside a register still naming whoever approved it first.
        # A chain that records approvals which changed nothing is a chain nobody can audit.
        settled = register.entry(digest_of_recipe(path))
        if settled is not None:
            raise AlreadyApproved(
                f"{name} is already approved at these exact bytes, by "
                f"{settled.approved_by} on {settled.registered_at[:10]}. Editing the file "
                f"un-approves it; approving it again without changing it would record a "
                f"decision that changed nothing."
            )

        # A re-approval after an edit is the next version, not the same one again: the
        # register keeps every approval, and two rows for "version 1" of one workflow would
        # make "which file did they read" unanswerable. `RecipeState` carries no version -
        # it describes the file on disk - so the number comes from what has been registered.
        approved = [r.version for r in register.registered() if r.name == name]
        version = max(approved) + 1 if approved else 1

        # The board takes a content store for skill submissions; registering a recipe never
        # touches it. Built here rather than carried on the console because nothing else on
        # this surface writes to the governance chain.
        board = board or SkillBoard(GovernanceRecord(), LocalContentStore())
        recorded = board.register_recipe(
            path,
            version=version,
            decision=Decision(
                candidate_id=f"recipe:{name}",
                decision="approved",
                reviewer=who,
                reason=reason,
                # Empty, and not a practice group. `routed_to` records which reviewer
                # group a *submission* was routed to by its scope - the board derives it
                # from the scope registry for a skill drop. A recipe approved here was
                # routed to nobody: a named person at this console performed the approval
                # directly, and writing a group name in would claim a routing that did not
                # happen. It would also put a practice group's name in `admin/`, which
                # P29 forbids precisely so that adding a group stays an entry in
                # scopes.yaml rather than a code change.
                routed_to="",
            ),
            register=register,
        )
        return {
            "name": recorded.name,
            "version": recorded.version,
            "digest": recorded.digest,
            "approved_by": who,
            "reason": reason,
        }

    def recipes(self) -> dict[str, Any]:
        """Every recipe on disk, and whether the board approved this version of it.

        Reading is separate from approving on purpose. `approve_recipe` is the write, and it
        goes through the board: a button here that wrote the register directly would be the
        shortcut P33 exists to close. What this is for is answering "why did that engagement
        not run" without anybody having to read a register by hand.
        """
        from registries.recipes import RecipeRegister

        register = RecipeRegister()
        return {
            "recipes": [
                {
                    "name": found.name,
                    "state": found.state,
                    "approved_by": found.approved_by,
                    "registered_at": found.registered_at,
                    "digest": found.digest,
                }
                for found in register.review()
            ]
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

    def set_prior_model(
        self, engagement_id: str, path: str, *, who: str, reason: str
    ) -> int:
        """Where last year's model is, for an engagement that has a last year.

        The analyst asked for exactly this and said exactly where it comes from: *"In the
        set up, I would point it to the right box file location."* Three quarters of this
        practice's engagements are repeat clients, and for those the work begins by opening
        last year's workbook - the historicals are copied forward, the years shifted, the
        WS line items carried across as this year's schema. Without this the roll-forward
        has nothing to roll forward from.

        **Checked here, while the person is still reading.** A path that does not resolve
        is the failure this surface keeps producing in other forms: the engagement
        registers, everything looks right, and nothing ever happens. By the time a run
        needs the file, whoever typed the path is somewhere else. Box Drive presents a
        local path, so this is an ordinary file that either exists or does not.

        An empty path clears it, which is how a mistake is undone and how an engagement
        that turns out not to have a usable prior year says so.
        """
        entry = self.roster.get(engagement_id)
        if entry is None:
            raise KeyError(f"{engagement_id} is not on the roster")

        chosen = path.strip().strip('"')
        if chosen:
            from pathlib import Path as _Path  # noqa: PLC0415

            where = _Path(chosen).expanduser()
            if not where.is_file():
                raise AdminRefused(
                    (
                        diagnose(
                            ADMIN_FORBIDDEN,
                            f"no file at {chosen!r}. Last year's model has to be a file "
                            "this machine can open - a Box or OneDrive folder that is "
                            "synced locally, not a web link.",
                            locator=f"engagements/{engagement_id}/prior_model",
                            expected="a path to an existing workbook",
                            found=chosen,
                        ),
                    )
                )
            chosen = str(where.resolve())

        doc = self.config.document()
        engagements = dict(doc.get("engagements") or {})
        over = dict(engagements.get(engagement_id) or {})
        if chosen:
            over["prior_model"] = chosen
        else:
            over.pop("prior_model", None)
        engagements[engagement_id] = over
        doc["engagements"] = engagements

        # `prior_model` has no home before 1.3.0, so writing one upgrades the document -
        # the same move the recipe made at 1.2.0. Nothing else does: a configuration that
        # names no prior model stays the version it was, and an older document written
        # before this existed still means exactly what it meant.
        if chosen and doc.get("schema_version") != CONTRACT:
            doc["schema_version"] = CONTRACT
        return self._write(doc, who, reason)

    def prior_model(self, engagement_id: str) -> str:
        """The recorded path, or empty. Read from the configuration like the recipe."""
        doc = self.config.document()
        over = (doc.get("engagements") or {}).get(engagement_id) or {}
        return str(over.get("prior_model") or "")

    def needs_a_prior_model(self, engagement_id: str) -> bool:
        """Whether this engagement is one that should have been pointed at last year.

        Only a repeat engagement. A first-year client has no last year, and asking for one
        would be demanding a file that does not exist - which is how a checklist teaches
        somebody to ignore it.
        """
        entry = self.roster.get(engagement_id)
        if entry is None:
            return False
        return entry.scope_path.rsplit("/", 1)[-1] == "repeat" and not self.prior_model(
            engagement_id
        )

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
                # A working bar, set 2026-09-18 and revisitable - the conservative end of
                # what was agreed, because nothing has measured what a safe one is yet. The
                # sampling audit the blueprint names as the only defence against a
                # confidently wrong, internally consistent classification does not exist,
                # and until it does a bar is a judgement rather than a finding. The practice
                # lead and QC own the real number; see BUILD/OPEN.md.
                "auto_accept_confidence": 0.90,
                # Never auto-accepted whatever the confidence. A bar only ever lets through
                # what no rule forces to review, and materiality forces it separately.
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
            # What people actually name files. Short tokens match as whole words only
            # (the binder's rule), so `is` claims `IS 2025.xlsx` and not `analysis.xlsx`.
            "document_type_conventions": {
                "trial_balance": [
                    "tb",
                    "tb_",
                    "trial balance",
                    "trial_balance",
                    "trialbalance",
                    "susa",
                ],
                "financial_statements": [
                    "income statement",
                    "balance sheet",
                    "financials",
                    "financial statements",
                    "profit and loss",
                    "p&l",
                    "statement of income",
                    "statement of operations",
                    "statement of financial position",
                    "is",
                    "bs",
                    "fs",
                    "guv",
                    "bilanz",
                ],
                # A forecast is named like the statements it projects, so a file such as
                # "Income Statement Forecast.xlsx" matches both types - and a filename that
                # matches two types is held for a person rather than read as history (P38).
                "forecast": [
                    "forecast",
                    "projection",
                    "projections",
                    "projected",
                    "budget",
                    "pro forma",
                    "proforma",
                ],
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

    # -- the ShareFile login, which is a person with a browser

    def start_sharefile_login(self, redirect_uri: str) -> dict[str, Any]:
        """Where the browser has to go, and the one-time value that ties it back here.

        The state is kept in memory on purpose. A server restart between pressing Sign in
        and finishing the login means starting again, which costs ten seconds; a state
        persisted to disk would be a replayable value sitting in a file, which is the
        thing it exists to prevent.
        """
        import ports

        url, state = ports.build_port("storage", "sharefile").begin_login(redirect_uri)
        self._forget_stale_logins()
        self._logins[state] = _now()
        return {"url": url, "state": state, "redirect_uri": redirect_uri}

    def finish_sharefile_login(self, code: str, state: str, redirect_uri: str) -> dict[str, Any]:
        """Turn the code into a stored refresh token, if this callback is ours.

        **The state check is not a formality.** This server answers to anything that can
        make a browser navigate to 127.0.0.1, and an OAuth callback is a plain GET with no
        Origin header - so the request gate cannot tell this redirect from one another site
        arranged. Without a state that was issued here and is accepted exactly once, a page
        could hand the tool an authorization code for somebody else's ShareFile account,
        and every later sweep would read that account's folders.
        """
        import ports

        if not state or self._logins.pop(state, None) is None:
            raise AdminRefused(
                (
                    diagnose(
                        ADMIN_FORBIDDEN,
                        "this ShareFile callback does not match a sign-in started here. "
                        "It is either stale - the server restarted, or it took too long - "
                        "or it came from somewhere else. Press Sign in again.",
                        locator="sharefile:state",
                        expected="a state issued by this server, used once",
                        found="unknown state",
                    ),
                )
            )
        adapter = ports.build_port("storage", "sharefile")
        stored = adapter.finish_login(code, redirect_uri)
        return {
            "service": stored.service,
            "subdomain": stored.subdomain,
            "obtained_at": stored.obtained_at,
            # Never the token. This dict is rendered into a page.
            "signed_in": True,
        }

    def sharefile_sign_in_state(self) -> str:
        import ports

        state: str = ports.build_port("storage", "sharefile").sign_in_state()
        return state

    def forget_sharefile_login(self) -> bool:
        """Drop the stored token. For when it was revoked at the other end and a person
        would rather say so than wait for a confusing refusal."""
        import ports

        adapter = ports.build_port("storage", "sharefile")
        dropped: bool = adapter.store().forget("sharefile")
        return dropped

    def _forget_stale_logins(self) -> None:
        """A state nobody came back with is dead weight and, kept forever, a growing list
        of values that would still be accepted."""
        cutoff = _now() - LOGIN_WINDOW_SECONDS
        for state, started in list(self._logins.items()):
            if started < cutoff:
                del self._logins[state]

    # -- the due-diligence tracker

    def dd_tracker(
        self, engagement_id: str, tracker_path: str = "", *, dry_run: bool = False
    ) -> dict[str, Any]:
        """Read the engagement's folder and update its request-list tracker.

        The list comes from the engagement's scope when there is no tracker yet, which is
        the ordinary state of a new engagement and the one he will be testing in. What a
        person has already written in an existing tracker is read back in first and
        written out unchanged - see `intake/tracker.py` for why that matters more than the
        matching does.
        """
        from intake.request_list import for_scope
        from intake.tracker import Tracker, look_at, read_tracker, write_tracker

        entry, relative = self._folder_of(engagement_id)
        scope_path = getattr(entry, "scope_path", "") or self.config.document().get(
            "default_scope", ""
        )

        target = Path(tracker_path) if tracker_path else self._tracker_beside(relative)
        held = read_tracker(target)

        listing = for_scope(str(scope_path))
        if listing is None:
            raise AdminRefused(
                (
                    diagnose(
                        UNKNOWN_CRITERIA,
                        f"there is no request list for {scope_path!r}, and none was "
                        f"supplied. A list is what the client was asked for; the tool "
                        f"does not borrow another division's.",
                        locator=f"request-list/{scope_path}",
                    ),
                )
            )

        tracker = Tracker(listing, look_at(self.preflight.storage, relative), held)
        report = tracker.report()
        report["tracker"] = str(target)
        report["dry_run"] = dry_run
        if not dry_run:
            write_tracker(tracker, target)
        return report

    @staticmethod
    def _tracker_beside(relative: str) -> Path:
        return Path(relative) / "DD request list.xlsx"

    # -- setting up the report, one appendix at a time

    def report_appendices(self, report: str) -> dict[str, Any]:
        """Each appendix with a button, and whether its anchor is even in that report.

        Asked on load rather than on press: an anchor that does not resolve is worth
        knowing about while there is still time to bookmark it, not at the moment somebody
        is trying to get a report out.
        """
        from report import what_would_change

        return {"report": report, "appendices": what_would_change(report)}

    def start_report(self, last_year: str, into: str) -> dict[str, Any]:
        """This period's report begins as a copy of last year's.

        Everything that carries forward does so by being copied - the boilerplate,
        Appendix G, the certification, the qualifications. Nothing is regenerated that
        nobody asked to change.
        """
        from report import set_up

        return {"report": str(set_up(last_year, into))}

    def update_appendix(
        self, report: str, appendix_id: str, source: str, *, dry_run: bool = False
    ) -> dict[str, Any]:
        """Press one appendix's button, or ask what it would do.

        `dry_run` takes the same path and stops before the write, so a preview and the
        update it previews cannot disagree.
        """
        from report import preview, update

        if dry_run:
            return preview(report, appendix_id, source).as_dict()
        return update(report, appendix_id, source).as_dict()

    def relay_to_box(self, prefix: str = "") -> dict[str, Any]:
        """Press Update: copy what is in ShareFile into Box.

        Built fresh for the same reason the connection test is, and pointed at the two
        adapters by name rather than at the configured storage port - the relay has a
        direction, and "whichever adapter is selected" has none.
        """
        import ports
        from intake.relay import relay

        return relay(
            ports.build_port("storage", "sharefile"),
            ports.build_port("storage", "box"),
            prefix,
        ).as_dict()

    def test_connection(self, service: str) -> dict[str, Any]:
        """Press the button: does this actually connect, and if not, which part.

        The adapter is built fresh rather than the configured storage port being used,
        because the whole point is to test a connection *before* switching a sweep over to
        it - and because this button gets pressed immediately after somebody edits `.env`.
        The report carries `in_use` so a green result cannot be mistaken for "runs are now
        reading Box" when `AA_STORAGE_ADAPTER` still says otherwise.
        """
        import ports
        from admin.connection import probe_box, probe_sharefile

        probes = {"box": probe_box, "sharefile": probe_sharefile}
        if service not in probes:
            raise AdminRefused(
                (
                    diagnose(
                        UNKNOWN_ADAPTER,
                        f"there is no connection test for {service!r}. The ones that "
                        f"exist are {', '.join(sorted(probes))}.",
                        locator="admin/connection.py",
                    ),
                )
            )
        return probes[service](
            ports.build_port("storage", service),
            self.preflight.secrets,
            in_use=ports.selected("storage") == service,
        ).as_dict()

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

    def _ai_model(self) -> dict[str, Any]:
        """Which adapter answers a skill, and what it costs to ask.

        Not settable here on purpose: the adapter is an environment choice and the concrete
        model comes from the skill's own tier, which is a budgeting decision made per skill
        rather than per client. What was missing was not a control - it was the answer to
        "which AI is this using", which the page could not give at all.
        """
        import ports  # noqa: PLC0415
        from ports.llm import TIER_MODELS  # noqa: PLC0415

        adapter = ports.selected("llm")
        says = {
            "fake": "replays recorded fixtures - no API call, no spend",
            "scripted": "a stand-in answering for the model, for a rehearsal",
            "anthropic_messages": "the Anthropic API, with the firm's key",
        }
        return {
            "adapter": adapter,
            "means": says.get(adapter, "an adapter this page does not recognise"),
            "reaches_a_model": adapter not in ("fake", "scripted"),
            "tiers": dict(TIER_MODELS),
        }

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
            "profile_gaps": self._gaps(entry),
            # A repeat engagement's work starts by opening last year's workbook, so the
            # roster says whether it has been pointed at one. `is_repeat` rather than the
            # page parsing the scope path: which segment means repeat is this module's
            # business, and a page that split the string would be a second place to be
            # wrong about it.
            "is_repeat": entry.scope_path.rsplit("/", 1)[-1] == "repeat",
            "prior_model": self.prior_model(entry.engagement_id),
        }

    def _gaps(self, entry: RosterEntry) -> list[str]:
        """What the engagement's profile still lacks before a run can read it - shown beside
        the engagement, so a missing judgement is found at setup rather than mid-run."""
        from admin.preflight import _profile_gaps  # noqa: PLC0415 - one direction only

        return _profile_gaps(self.config.profile(entry.engagement_id), entry.scope_path)


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


def _local_root(port: Any) -> str | None:
    """The folder on this machine a port reads or writes, when it is a local folder."""
    found = getattr(port, "root", None)
    return str(found) if found is not None and getattr(port, "name", "") == "local_folder" else None


def _safe_filename(name: str) -> str:
    """A file name, and only a name: no folders, no parent references, nothing hidden."""
    clean = str(name or "").replace("\\", "/").rsplit("/", 1)[-1].strip()
    if not clean or clean in {".", ".."} or clean.startswith("."):
        raise ValueError(f"{name!r} is not a file name")
    if any(ch in clean for ch in '<>:"|?*') or any(ord(ch) < 32 for ch in clean):
        raise ValueError(f"{name!r} has a character a file name cannot carry")
    return clean
