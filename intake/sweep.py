"""The Sweep Planner: decides which folders get looked at tonight - and skips every folder
that is not live work.

Reads the Active Project Roster and the watch definitions, and produces the list of
(location, engagement_id) pairs to sweep. Two kinds of watch: a **bound watch** is one
folder to one engagement, explicit; a **pattern watch** is a parent client folder plus a
rule that maps each subfolder to an engagement through the roster's `folder` binding -
one row covering forty clients.

A subfolder that matches no active engagement is never guessed at: it is reported
unclaimed and routed to a person. A paused engagement's folder is known and skipped; an
archived one is not swept at all. And no two watches may claim the same path, which is
checked before anything is swept.

Folder-level resolution is configuration and can be wrong; file-level binding fails
closed and cannot. Both exist deliberately.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime

from intake.config import ConfigStore, Watch
from intake.roster import ProjectRoster, RosterEntry, RosterState
from intake.store import IntakeStore
from ports.storage import StoragePort
from registries.errors import WATCH_OVERLAP, RegistryError, diagnose

__all__ = ["Skipped", "SweepPlan", "SweepPlanner", "SweepTarget", "Unclaimed"]


@dataclass(frozen=True)
class SweepTarget:
    location: str
    """A prefix relative to the storage port root: the folder to list."""
    engagement_id: str
    watch_id: str
    recipe: str


@dataclass(frozen=True)
class Skipped:
    location: str
    engagement_id: str
    state: RosterState


@dataclass(frozen=True)
class Unclaimed:
    location: str
    watch_id: str
    files: int


@dataclass(frozen=True)
class SweepPlan:
    targets: tuple[SweepTarget, ...]
    skipped: tuple[Skipped, ...] = ()
    unclaimed: tuple[Unclaimed, ...] = ()
    watches: tuple[Watch, ...] = field(default_factory=tuple)

    def locations(self) -> tuple[str, ...]:
        return tuple(t.location for t in self.targets)


class SweepPlanner:
    def __init__(
        self,
        roster: ProjectRoster,
        config: ConfigStore,
        port: StoragePort,
        intake_store: IntakeStore | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.roster = roster
        self.config = config
        self.port = port
        self.intake_store = intake_store
        self._clock = clock or (lambda: datetime.now(tz=UTC))

    def plan(self) -> SweepPlan:
        watches = self.config.watches()
        entries = self.roster.entries()
        _no_two_entries_claim_one_folder(entries)
        targets: list[SweepTarget] = []
        skipped: list[Skipped] = []
        unclaimed: list[Unclaimed] = []

        for watch in watches:
            if watch.is_bound:
                assert watch.engagement_id is not None
                entry = self.roster.get(watch.engagement_id)
                if entry is None or entry.state is RosterState.ARCHIVED:
                    continue  # not swept at all; the binding stays in the config for the record
                if entry.state is RosterState.PAUSED:
                    skipped.append(Skipped(watch.root, entry.engagement_id, entry.state))
                    continue
                targets.append(SweepTarget(watch.root, entry.engagement_id, watch.id, watch.recipe))
                continue

            by_folder = {e.folder: e for e in entries if e.watch_id == watch.id and e.folder}
            for folder, count in self._subfolders(watch).items():
                location = f"{watch.root}/{folder}" if watch.root else folder
                entry = by_folder.get(folder)
                if entry is None:
                    unclaimed.append(Unclaimed(location, watch.id, count))
                    if self.intake_store is not None:
                        self.intake_store.report_unclaimed(
                            watch.id, location, count, _stamp(self._clock())
                        )
                elif entry.state is RosterState.ACTIVE:
                    targets.append(
                        SweepTarget(location, entry.engagement_id, watch.id, watch.recipe)
                    )
                elif entry.state is RosterState.PAUSED:
                    skipped.append(Skipped(location, entry.engagement_id, entry.state))
                # archived: known, not swept, not unclaimed.

        return SweepPlan(
            targets=tuple(targets),
            skipped=tuple(skipped),
            unclaimed=tuple(unclaimed),
            watches=watches,
        )

    def _subfolders(self, watch: Watch) -> dict[str, int]:
        """Engagement-level folders under a pattern watch's root, with a file count each.
        Derived from the listing, never from anything read."""
        found: dict[str, int] = {}
        prefix = f"{watch.root}/" if watch.root else ""
        for ref in self.port.list(watch.root):
            relative = ref.path[len(prefix) :] if ref.path.startswith(prefix) else ref.path
            parts = relative.split("/")
            if len(parts) <= watch.depth:
                continue  # a file above engagement depth belongs to nobody in particular
            key = "/".join(parts[: watch.depth])
            found[key] = found.get(key, 0) + 1
        return found


def _no_two_entries_claim_one_folder(entries: tuple[RosterEntry, ...]) -> None:
    seen: dict[tuple[str, str], str] = {}
    for entry in entries:
        if not entry.folder or entry.state is RosterState.ARCHIVED:
            continue
        key = (entry.watch_id, entry.folder)
        if key in seen:
            raise RegistryError(
                diagnose(
                    WATCH_OVERLAP,
                    f"{seen[key]} and {entry.engagement_id} both claim {entry.folder!r} under "
                    f"watch {entry.watch_id}",
                    locator=f"roster/{entry.engagement_id}",
                )
            )
        seen[key] = entry.engagement_id


def _stamp(at: datetime) -> str:
    return at.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")
