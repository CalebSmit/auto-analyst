"""The deterministic half of `/improve-agent`: where the interview stands, and what leaked.

The slash command is a model asking one question at a time. What it must not do is decide
from memory what has been covered, or trust itself that a client's name stayed inside
`knowledge/` rather than reaching a skill, methodology file or fixture. Both of those are
answered here, from files, so they are the same answer in Cursor on the work laptop as in
Claude Code on this machine.

    python tools/interview.py status            # coverage, follow-ups, backlog, code gaps
    python tools/interview.py session           # open today's session log, print its path
    python tools/interview.py mark <topic> covered --note "..."
    python tools/interview.py scan              # any identifier outside knowledge/
    python tools/interview.py topics            # the whole coverage map, in asking order

Everything the interview learns lives under `knowledge/`, committed so it travels with the
private repo. The map of what to ask about is `interview/topics.yaml`. The protocol the command
follows is `interview/PROTOCOL.md`.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

KNOWLEDGE = ROOT / "knowledge"
TOPICS_FILE = ROOT / "interview" / "topics.yaml"

STATUSES = ("open", "partial", "covered", "skipped")

# The skeleton `init` lays down. Each file says what it is for in its first lines, because
# the reader six months from now is a model that has never seen this conversation.
SKELETON: dict[str, str] = {
    "profile.md": (
        "# Profile\n\nWho the analyst is: role, team, who reviews their work, the tools and\n"
        "AI models they use today and which are firm-approved. One fact per line, each\n"
        "ending with the session it came from, e.g. `(2026-09-16-1)`.\n"
    ),
    "workflow.md": (
        "# The workflow, as currently understood\n\nThe non-ESOP engagement from first "
        "contact to delivered model, step by step.\nEach step: what happens, who does it, "
        "what it needs, what it produces, how long it\ntakes, and the session it came from. "
        "Rewrite a step when an answer changes it; the\nsession logs keep the history.\n"
    ),
    "decisions.md": (
        "# Judgment rules\n\n`When <situation>, I <do this>, because <reason>.` One per "
        "entry, with the project\ncodename and session it came from. These are the raw "
        "material for skills: a rule\nwith no reason is a follow-up, not a rule.\n"
    ),
    "documents.md": (
        "# Documents and the order they arrive in\n\nEach document type: what it is, the "
        "formats it comes in, when it usually arrives,\nwhat it feeds, and what to do when "
        "it is late, missing, revised or out of order.\n"
    ),
    "followups.md": (
        "# Follow-ups\n\nQuestions an earlier answer raised. `- [ ]` open, `- [x]` asked. "
        "Asked before\nany new topic.\n"
    ),
    "backlog.md": (
        "# Build backlog\n\nChanges the interview has proposed. Each: `## B-NNN title`, then "
        "`status:` one of\nproposed, approved, declined, built; what it changes, the files, "
        "and the answers\nbehind it.\n"
    ),
    "identifiers.txt": (
        "# Client names, people, places, account and entity names that appeared in answers\n"
        "# or documents. One per line. `interview.py scan` refuses any file outside knowledge/\n"
        "# that contains one of them. Add to it the moment a name is mentioned.\n"
    ),
    "coverage.yaml": "topics: {}\n",
    "projects/README.md": (
        "# Projects\n\nOne folder per project, named by a codename rather than the client: "
        "`projects/<codename>/notes.md`\nand `projects/<codename>/docs/`. The codename is "
        "what committed text may cite.\n"
    ),
    "sessions/README.md": "# Sessions\n\nOne log per session, appended after every answer.\n",
}


@dataclass(frozen=True)
class Topic:
    id: str
    title: str
    priority: int
    why: str
    angles: tuple[str, ...]
    done_when: str
    feeds: tuple[str, ...]


# -------------------------------------------------------------------- the map


def load_topics(path: Path = TOPICS_FILE) -> list[Topic]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    topics: list[Topic] = []
    seen: set[str] = set()
    for entry in raw["topics"]:
        topic = Topic(
            id=str(entry["id"]),
            title=str(entry["title"]),
            priority=int(entry["priority"]),
            why=str(entry["why"]).strip(),
            angles=tuple(str(a) for a in entry.get("angles", [])),
            done_when=str(entry["done_when"]).strip(),
            feeds=tuple(str(f) for f in entry.get("feeds", [])),
        )
        if topic.id in seen:
            raise ValueError(f"topic {topic.id!r} is declared twice in {path.name}")
        if topic.priority not in (1, 2, 3):
            raise ValueError(f"topic {topic.id!r} has priority {topic.priority}; use 1, 2 or 3")
        if not topic.angles:
            raise ValueError(f"topic {topic.id!r} gives the interviewer nothing to ask")
        seen.add(topic.id)
        topics.append(topic)
    return topics


# ------------------------------------------------------------ the knowledge folder


def init(knowledge: Path = KNOWLEDGE) -> list[Path]:
    """Lay down whatever of the skeleton is missing. Never overwrites."""
    created: list[Path] = []
    for name, body in SKELETON.items():
        target = knowledge / name
        if target.exists():
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding="utf-8")
        created.append(target)
    return created


def load_coverage(knowledge: Path = KNOWLEDGE) -> dict[str, dict[str, Any]]:
    path = knowledge / "coverage.yaml"
    if not path.exists():
        return {}
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    topics = raw.get("topics") or {}
    return {str(k): dict(v or {}) for k, v in topics.items()}


def mark(
    topic_id: str,
    status: str,
    note: str = "",
    session: str = "",
    knowledge: Path = KNOWLEDGE,
    topics_file: Path = TOPICS_FILE,
) -> dict[str, Any]:
    if status not in STATUSES:
        raise ValueError(f"status must be one of {', '.join(STATUSES)}")
    known = {t.id for t in load_topics(topics_file)}
    if topic_id not in known:
        raise ValueError(f"{topic_id!r} is not in {topics_file.name}; add it there first")
    init(knowledge)
    coverage = load_coverage(knowledge)
    entry = coverage.get(topic_id, {})
    entry["status"] = status
    if note:
        entry.setdefault("notes", []).append(note)
    if session:
        sessions = entry.setdefault("sessions", [])
        if session not in sessions:
            sessions.append(session)
    coverage[topic_id] = entry
    (knowledge / "coverage.yaml").write_text(
        yaml.safe_dump({"topics": coverage}, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    return entry


def next_topics(
    topics: list[Topic], coverage: dict[str, dict[str, Any]], limit: int = 3
) -> list[tuple[Topic, str]]:
    """Open before partial, higher priority first, declaration order otherwise."""
    rank = {"open": 0, "partial": 1}
    waiting = [
        (t, coverage.get(t.id, {}).get("status", "open"))
        for t in topics
        if coverage.get(t.id, {}).get("status", "open") in rank
    ]
    order = {t.id: i for i, t in enumerate(topics)}
    waiting.sort(key=lambda pair: (pair[0].priority, rank[pair[1]], order[pair[0].id]))
    return waiting[:limit]


def open_followups(knowledge: Path = KNOWLEDGE) -> list[str]:
    path = knowledge / "followups.md"
    if not path.exists():
        return []
    return [
        line.strip()[6:].strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip().startswith("- [ ] ")
    ]


def backlog_counts(knowledge: Path = KNOWLEDGE) -> dict[str, int]:
    path = knowledge / "backlog.md"
    counts: dict[str, int] = {}
    if not path.exists():
        return counts
    for match in re.finditer(r"^status:\s*(\w+)", path.read_text(encoding="utf-8"), re.M):
        counts[match.group(1)] = counts.get(match.group(1), 0) + 1
    return counts


def start_session(knowledge: Path = KNOWLEDGE, today: date | None = None) -> Path:
    """A new session log: `sessions/YYYY-MM-DD-N.md`, N counting today's sessions."""
    init(knowledge)
    stamp = (today or date.today()).isoformat()
    sessions = knowledge / "sessions"
    n = 1
    while (sessions / f"{stamp}-{n}.md").exists():
        n += 1
    path = sessions / f"{stamp}-{n}.md"
    path.write_text(
        f"# Session {stamp}-{n}\n\n"
        "Appended after every answer: the question, the answer as given, files provided,\n"
        "and what was recorded where. Never rewritten afterwards.\n",
        encoding="utf-8",
    )
    return path


def projects(knowledge: Path = KNOWLEDGE) -> list[str]:
    folder = knowledge / "projects"
    if not folder.exists():
        return []
    return sorted(p.name for p in folder.iterdir() if p.is_dir())


# ---------------------------------------------------------------- the code's side


def code_gaps() -> list[str]:
    """What the code says is missing for the focus division. Asked, never remembered.

    Each question is asked separately and a failure to answer is reported as such, so a
    half-configured clone still gets an interview rather than a stack trace.
    """
    lines: list[str] = []
    try:
        from registries.scopes import ScopePath, ScopeRegistry  # noqa: PLC0415

        registry = ScopeRegistry.load()
    except Exception as exc:  # noqa: BLE001
        return [f"could not read the scope registry: {exc}"]
    if registry.focus is None:
        return ["no focus is declared in scope/scopes.yaml"]
    practice, segment = registry.focus
    lines.append(f"focus: {practice}/{segment}")

    layers_dir = ROOT / "skills"
    for sub in ("_segment", "repeat", "non-repeat"):
        folder = layers_dir / practice / segment / sub
        own = [p for p in folder.iterdir() if p.is_dir()] if folder.exists() else []
        if not own:
            lines.append(f"skills/{practice}/{segment}/{sub}: empty - nothing of its own yet")
    foundations = ROOT / "foundations" / practice / segment
    if not foundations.exists():
        lines.append(f"foundations/{practice}/{segment}: no methodology written for it")

    try:
        from graph.resolve import ScopeResolver  # noqa: PLC0415
        from harness.procedures import PROCEDURES  # noqa: PLC0415

        resolver = ScopeResolver()
        for disposition in registry.dispositions:
            resolved = resolver.resolve(ScopePath(practice, segment, disposition.id))
            template = resolved.template
            bound = f"{template.file} (from {template.layer})" if template else "none"
            lines.append(
                f"{resolved.scope}: {len(resolved)} skills, template {bound}"
            )
            unproceduralised = [r.name for r in resolved.skills if r.name not in PROCEDURES]
            if unproceduralised:
                lines.append(
                    "  no mechanical half (cannot run): " + ", ".join(sorted(unproceduralised))
                )
    except Exception as exc:  # noqa: BLE001
        lines.append(f"could not resolve the focus: {exc}")

    try:
        from tools.serve import readiness  # noqa: PLC0415

        for seam in readiness():
            if not seam.ready:
                lines.append(f"not joined: {seam.name} - {seam.detail}")
    except Exception as exc:  # noqa: BLE001
        lines.append(f"could not ask serve.readiness(): {exc}")
    return lines


# ---------------------------------------------------------------- the leak scan


def identifiers(knowledge: Path = KNOWLEDGE) -> list[str]:
    path = knowledge / "identifiers.txt"
    if not path.exists():
        return []
    names = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and len(line) >= 3:
            names.append(line)
    return names


def committable_files(root: Path = ROOT) -> list[Path]:
    """Every file git would commit outside `knowledge/`: tracked, plus untracked and not
    ignored. Knowledge may name a client; a skill, methodology file or fixture reaches every
    prompt for every client, and must not."""
    out = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=root,
        capture_output=True,
        check=True,
    ).stdout.decode("utf-8", "replace")
    names = [name for name in out.split("\0") if name]
    return [root / name for name in names if not name.startswith("knowledge/")]


def scan(files: list[Path], names: list[str]) -> list[tuple[Path, int, str]]:
    """(file, line, identifier) for every identifier found, case-insensitively, whole words."""
    if not names:
        return []
    alternatives = "|".join(re.escape(n) for n in sorted(names, key=len, reverse=True))
    pattern = re.compile(r"(?<!\w)(" + alternatives + r")(?!\w)", re.IGNORECASE)
    hits: list[tuple[Path, int, str]] = []
    for path in files:
        if not path.is_file() or path.stat().st_size > 2_000_000:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for number, line in enumerate(text.splitlines(), start=1):
            for match in pattern.finditer(line):
                hits.append((path, number, match.group(1)))
    return hits


# ------------------------------------------------------------------------- CLI


def _status() -> int:
    created = init()
    topics = load_topics()
    coverage = load_coverage()
    sessions = sorted((KNOWLEDGE / "sessions").glob("????-??-??-*.md"))
    print("# Interview status\n")
    if created:
        print(f"knowledge/ initialised ({len(created)} files) - this is the first session.\n")
    last = f" (last: {sessions[-1].stem})" if sessions else ""
    print(f"sessions so far: {len(sessions)}{last}")
    tally = {s: 0 for s in STATUSES}
    for t in topics:
        tally[coverage.get(t.id, {}).get("status", "open")] += 1
    print("topics: " + ", ".join(f"{n} {s}" for s, n in tally.items()))
    print(f"projects: {', '.join(projects()) or 'none yet'}")
    counts = backlog_counts()
    print("backlog: " + (", ".join(f"{n} {s}" for s, n in counts.items()) or "empty"))

    followups = open_followups()
    print(f"\n## Open follow-ups ({len(followups)}) - ask these first")
    for item in followups[:5]:
        print(f"- {item}")

    print("\n## Next topics")
    for topic, state in next_topics(topics, coverage):
        print(f"- [{topic.id}] {topic.title} (priority {topic.priority}, {state})")
        print(f"  why: {topic.why}")
        print(f"  done when: {topic.done_when}")

    print("\n## What the code says is missing")
    for line in code_gaps():
        print(f"- {line}")

    print("\n## Boundary")
    print(f"identifiers kept inside knowledge/: {len(identifiers())}")
    return 0


def _topics() -> int:
    coverage = load_coverage()
    for topic in sorted(load_topics(), key=lambda t: t.priority):
        state = coverage.get(topic.id, {}).get("status", "open")
        print(f"[{topic.id}] p{topic.priority} {state}: {topic.title}")
        for angle in topic.angles:
            print(f"    - {angle}")
    return 0


def _scan() -> int:
    names = identifiers()
    hits = scan(committable_files(), names)
    for path, line, name in hits:
        print(f"{path.relative_to(ROOT)}:{line}: {name!r}")
    if hits:
        print(f"FAIL: {len(hits)} identifier(s) outside knowledge/")
        return 1
    print(f"clean: {len(names)} identifiers checked against every file outside knowledge/")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else "")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status", help="where the interview stands and what to ask next")
    sub.add_parser("session", help="start a session log and print its path")
    sub.add_parser("topics", help="the coverage map in asking order")
    sub.add_parser("scan", help="identifiers in anything git would commit")
    marker = sub.add_parser("mark", help="record a topic's coverage")
    marker.add_argument("topic")
    marker.add_argument("status", choices=STATUSES)
    marker.add_argument("--note", default="")
    marker.add_argument("--session", default="")
    args = parser.parse_args(argv)

    if args.command == "status":
        return _status()
    if args.command == "session":
        print(start_session().relative_to(ROOT).as_posix())
        return 0
    if args.command == "topics":
        return _topics()
    if args.command == "scan":
        return _scan()
    if args.command == "mark":
        entry = mark(args.topic, args.status, args.note, args.session)
        print(f"{args.topic}: {entry['status']}")
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
