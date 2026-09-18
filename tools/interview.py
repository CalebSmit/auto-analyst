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
    python tools/interview.py suggest           # what in knowledge/ looks like a name
    python tools/interview.py register NAME     # put one in the register (--none if there are none)
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
        "# that contains one of them. Add to it the moment a name is mentioned:\n"
        "#\n"
        "#     python tools/interview.py suggest            what already looks like a name\n"
        "#     python tools/interview.py register NAME      add it\n"
        "#     python tools/interview.py register --none \"why\"\n"
        "#         if nobody has been named yet - records that a person looked, and\n"
        "#         stops counting the moment another session is logged\n"
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


SESSION_HEADER = (
    "Appended after every answer: the question, the answer as given, files provided,\n"
    "and what was recorded where. Never rewritten afterwards.\n"
)
"""What `start_session` writes before a single question has been asked. Named rather than
inlined because `_knowledge_has_answers` subtracts it: a log holding only this has learned
nothing, and the difference decides whether the leak scan has anything to check."""


def start_session(knowledge: Path = KNOWLEDGE, today: date | None = None) -> Path:
    """A new session log: `sessions/YYYY-MM-DD-N.md`, N counting today's sessions."""
    init(knowledge)
    stamp = (today or date.today()).isoformat()
    sessions = knowledge / "sessions"
    n = 1
    while (sessions / f"{stamp}-{n}.md").exists():
        n += 1
    path = sessions / f"{stamp}-{n}.md"
    path.write_text(f"# Session {stamp}-{n}\n\n" + SESSION_HEADER, encoding="utf-8")
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
    created = init(KNOWLEDGE)
    topics = load_topics()
    coverage = load_coverage(KNOWLEDGE)
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
    print(f"projects: {', '.join(projects(KNOWLEDGE)) or 'none yet'}")
    counts = backlog_counts(KNOWLEDGE)
    print("backlog: " + (", ".join(f"{n} {s}" for s, n in counts.items()) or "empty"))

    followups = open_followups(KNOWLEDGE)
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
    names = identifiers(KNOWLEDGE)
    print(f"identifiers kept inside knowledge/: {len(names)}")
    if not names and _knowledge_has_answers(KNOWLEDGE):
        # Step 6 of the protocol is where `scan` runs, and step 6 is after every answer has
        # been given. Saying it here, at step 2, is the difference between a note to act on
        # while asking and a wall at the end of the session.
        #
        # It also has to agree with `scan`, which reads the acknowledgement and this did not.
        # A person running both in one minute was told the close-out would refuse and that
        # the register was clean, about the same file, by the two commands the protocol
        # tells them to run.
        standing = reviewed_empty(KNOWLEDGE)
        if standing and _review_is_current(KNOWLEDGE, standing[0]):
            on, by = standing
            print(f"  An acknowledgement stands, made {on} by {by}, so `scan` passes now.")
            print("  It covers the sessions recorded before it and not this one: the first")
            print("  answer logged today makes it stale and the close-out refuses again.")
        else:
            print("  `interview.py scan` will refuse to close this session: knowledge/ holds")
            print("  answers and the register is empty.")
        print("  Add names as they come up rather than at the end:")
        print("      python tools/interview.py suggest     what already looks like a name")
        print("      python tools/interview.py register NAME [NAME ...]")
        print("      python tools/interview.py register --none \"...\"   if nobody was named")
    return 0


def _topics() -> int:
    coverage = load_coverage(KNOWLEDGE)
    for topic in sorted(load_topics(), key=lambda t: t.priority):
        state = coverage.get(topic.id, {}).get("status", "open")
        print(f"[{topic.id}] p{topic.priority} {state}: {topic.title}")
        for angle in topic.angles:
            print(f"    - {angle}")
    return 0


def _shown(path: Path) -> str:
    """A path as a person should read it: relative to the repository where it is inside it,
    and whole where it is not.

    `relative_to` raises rather than falling back, and this is the line that reports a
    client's name having reached a file outside `knowledge/` - so the one moment the check
    has something to say was the one moment it could raise instead of saying it. Nothing
    `committable_files()` returns is outside the repository today, which is why it never
    happened; a landmine that has not gone off is still a landmine (see P55).
    """
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _scan() -> int:
    names = identifiers(KNOWLEDGE)
    hits = scan(committable_files(), names)
    for path, line, name in hits:
        print(f"{_shown(path)}:{line}: {name!r}")
    if hits:
        print(f"FAIL: {len(hits)} identifier(s) outside knowledge/")
        return 1
    if not names:
        reviewed = reviewed_empty(KNOWLEDGE)
        if reviewed and _review_is_current(KNOWLEDGE, reviewed[0]):
            on, who = reviewed
            # Explicitly against the module's KNOWLEDGE rather than the parameter default:
            # a default is bound at definition and does not follow a patched module
            # attribute, which is how these checks came to read the machine's own register
            # instead of the one under test (see the note in tests/p54).
            over = _reviewed_over(KNOWLEDGE)
            print(f"clean: the register is empty on purpose - reviewed {on} by {who}.")
            print("       Nothing outside knowledge/ was searched, because nothing has been")
            print("       named to search for.")
            if over is None:
                print("       It names no sessions, so it covers only what was logged before")
                print(f"       {on}. Any session dated {on} or later makes it stale and the")
                print("       check refuses again.")
            else:
                print(f"       Made over {len(over)} session(s): {', '.join(over) or 'none'}.")
                print("       The next session is not among them, so it goes stale as soon as")
                print("       one is logged and the check refuses again.")
            return 0
        if _knowledge_has_answers(KNOWLEDGE):
            # `clean` over an empty register is the most dangerous thing this command can
            # print: it is the check CLAUDE.md names as the one that keeps client data inside
            # knowledge/, and it passed unconditionally for as long as nobody remembered to
            # write a name in the file. A check that cannot fail is worse than no check,
            # because the record says it ran.
            print("UNCHECKED: knowledge/ holds answers and knowledge/identifiers.txt is empty.")
            if reviewed is not None:
                print(f"           It was reviewed on {reviewed[0]}, and a session has been")
                print("           recorded since. An acknowledgement covers the answers that")
                print("           existed when it was written, not the ones that came after.")
            print("           Nothing was looked for, so nothing was found. Two ways out:")
            print("")
            print("             python tools/interview.py suggest")
            print("                 what in knowledge/ has the shape of a name, and where")
            print("             python tools/interview.py register NAME [NAME ...]")
            print("                 add them - every client, person, place and entity")
            print("             python tools/interview.py register --none \"...\"")
            print("                 record that you looked and there is nothing to register")
            print("")
            print("           This is the whole of what keeps those names out of a skill, a")
            print("           methodology file or a fixture. Do not work around it.")
            return 1
        # And the other empty case, which is not a failure and must not read like one: a
        # clone before its first interview has nothing to check for, and saying so is the
        # only honest answer. The first version of this refusal could not tell the two
        # apart, so it refused on a machine where nobody had been asked anything yet.
        print("clean: knowledge/ holds no answers yet, so there is nothing to check for.")
        return 0
    print(f"clean: {len(names)} identifiers checked against every file outside knowledge/")
    return 0


def _beyond_its_header(log: Path) -> bool:
    """Whether anything has been appended to a session log since it was opened.

    `interview.py session` runs at step 3 of the protocol - before the first question. A log
    that still holds only what `start_session` wrote is a session that has learned nothing.
    """
    try:
        text = log.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return True  # unreadable is not evidence of emptiness
    body = text.replace(SESSION_HEADER, "")
    return any(
        line.strip() and not line.startswith("# Session ") for line in body.splitlines()
    )


def _knowledge_has_answers(knowledge: Path = KNOWLEDGE) -> bool:
    """Whether there is anything in knowledge/ that could have named somebody.

    Two places, because those are the two ways a name first arrives. The interview appends
    every answer to its session log before it asks the next question, so no answer exists
    without a log carrying it; and `projects/<codename>/docs/` is where a client's own
    documents are allowed to live, which is a name whatever the logs say.

    What deliberately does not count is the skeleton `init()` lays down and the README that
    ships with the repo. The first version of this counted any `.md` over 400 bytes, and
    `knowledge/README.md` is committed at 522 - so a clone where no interview had happened
    was told to register names nobody had been given yet, and there was no state of the repo
    in which the scan could pass. An empty register is correct exactly until somebody is
    asked something.
    """
    if not knowledge.is_dir():
        return False
    if any(_beyond_its_header(log) for log in (knowledge / "sessions").glob("????-??-??-*.md")):
        return True
    return any(p.is_file() and p.name != "README.md" for p in (knowledge / "projects").rglob("*"))


# ------------------------------------------------------- proposing what to put in the register

# Shapes that are worth a person's attention. Each names what it found and where; none of
# them decides anything. Ordered most distinctive first, because that is the order somebody
# reading a list wants them in.
# Dotted forms first: alternation is ordered, and a bare `Co` would otherwise win over
# `Co.` and leave the dot behind. The trailing lookahead is `(?!\w)` rather than `(?![\w.])`
# because a company suffix at the end of a sentence is followed by a full stop, which is the
# common case and which the stricter lookahead silently refused.
_SUFFIX = (
    r"L\.L\.C\.|Inc\.|Ltd\.|Corp\.|Co\.|"
    r"LLC|Inc|Ltd|Corp|PLC|LLP|LP|PC|PA|Co|"
    r"Partners|Holdings|Group|Capital|Ventures|Industries|Enterprises|Associates|"
    r"Brands|Systems|Solutions|Technologies|Manufacturing|Properties|Realty|Trust|Foundation"
)
_PROPER = r"[A-Z][A-Za-z'&-]+"

CANDIDATE_SHAPES: tuple[tuple[str, str, re.Pattern[str]], ...] = (
    (
        "entity",
        "a proper name ending in a company suffix",
        # `(?!\s+[A-Z])` because a company suffix *ends* a name - that is what makes it a
        # suffix. Without it, `Capital` matched inside the firm template's "Applicable
        # Capital Gains" and the suggester proposed "Applicable Capital" as a company. The
        # `(?!\w)` before it does not help: a space satisfies it. Greedy matching means a
        # genuine multi-suffix name - "Northgate Dental Partners Inc" - still matches whole.
        re.compile(rf"\b(?:{_PROPER}\s+){{1,4}}(?:{_SUFFIX})(?!\w)(?!\s+[A-Z])"),
    ),
    (
        "person",
        "an initial and a surname",
        re.compile(r"\b(?:[A-Z]\.\s*){1,3}[A-Z][a-z]{2,}\b"),
    ),
    (
        "person",
        "an honorific and a surname",
        re.compile(r"\b(?:Mr|Mrs|Ms|Miss|Dr|Prof|Messrs|Sr|Jr)\.?\s+[A-Z][a-z]{2,}\b"),
    ),
    (
        "name-shaped",
        "two or more capitalised words together",
        re.compile(r"\b[A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,}){1,3}\b"),
    ),
)

# Words that start a sentence, name a month, or belong to this build rather than to a
# client. Deliberately short: the real filter is the one below it, which asks whether a
# phrase already appears in the repo's own committed text.
_NOT_A_NAME = {
    "January", "February", "March", "April", "May", "June", "July", "August",
    "September", "October", "November", "December",
    "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday",
    "The", "This", "That", "There", "These", "Those", "They", "Then", "When", "What",
    "Where", "Which", "While", "With", "Without", "From", "For", "And", "But", "Not",
    "One", "Two", "Three", "First", "Second", "Third", "Next", "Last", "Each", "Every",
    "Also", "After", "Before", "Once", "Only", "Both", "Either", "Neither", "Because",
    "Session", "Answer", "Question", "Notes", "Evidence", "Size", "Status", "Files",
    "Usually", "Often", "Always", "Never", "Sometimes", "Any", "Some", "Most", "All",
    "Generally", "Typically", "Normally", "Currently", "Today", "Yesterday", "Tomorrow",
    "If", "Unless", "Since", "Until", "During", "Between", "Above", "Below", "Per",
    "Yes", "No", "Maybe", "Probably", "Nothing", "Something", "Anything", "Everything",
    "It", "He", "She", "We", "You", "His", "Her", "Their", "Our", "Its",
}


@dataclass(frozen=True)
class Candidate:
    """Something in `knowledge/` that has the shape of a name. A proposal, never a verdict."""

    text: str
    kind: str
    shape: str
    count: int
    first_seen: str
    """`file:line` of the first place it appeared."""
    outside: bool
    """Whether it also appears in something git would commit. See `suggest()`."""


def suggest(knowledge: Path = KNOWLEDGE, root: Path = ROOT) -> list[Candidate]:
    """What in `knowledge/` looks like it belongs in the register.

    The register has been empty through three sessions, and the reason is not carelessness:
    filling it from memory means recalling every name mentioned across hours of conversation.
    The answers are on disk. This reads them.

    **It proposes and nothing else.** No file is written, the register is not touched, and a
    name enters it because a person put it there - the same reason `privacy/` is deterministic
    Python and no model performs re-identification. A shape is not a judgement about who
    somebody is.

    `outside` is the one piece of real information here rather than pattern-matching. A
    phrase that already appears in something git would commit is usually this build's own
    vocabulary - "Precedent Store", "Scope Resolver" - and not a client. But it is marked
    rather than dropped, because the other reading is that a client's name has already
    reached a committable file, which is precisely what the register exists to catch. A
    filter that silently removed those would hide the only case that matters.
    """
    answers = _answer_files(knowledge)
    known = {name.casefold() for name in identifiers(knowledge)}
    found: dict[str, dict[str, Any]] = {}

    for path in answers:
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        where = path.relative_to(knowledge).as_posix()
        for number, line in enumerate(text.splitlines(), start=1):
            if line.lstrip().startswith(("#", ">", "|", "-", "*")) and "`" in line:
                continue  # a heading or a table of the interview's own scaffolding
            for kind, shape, pattern in CANDIDATE_SHAPES:
                for match in pattern.finditer(line):
                    phrase = _trim(match.group(0).strip(" ,;:"))
                    if not _worth_proposing(phrase, known):
                        continue
                    entry = found.setdefault(
                        phrase,
                        {"kind": kind, "shape": shape, "count": 0, "first": f"{where}:{number}"},
                    )
                    entry["count"] += 1

    # "Brightwater Holdings LLC" and "Brightwater Holdings" are one name proposed twice, and
    # a list a person has to read is worth only as much as its signal. The longer, more
    # confident shape wins; the fragment inside it is dropped.
    stronger = {p for p, e in found.items() if e["kind"] != "name-shaped"}
    found = {
        phrase: e
        for phrase, e in found.items()
        if e["kind"] != "name-shaped" or not any(phrase in other for other in stronger)
    }

    committable = committable_files(root)
    return sorted(
        (
            Candidate(
                text=phrase,
                kind=str(e["kind"]),
                shape=str(e["shape"]),
                count=int(e["count"]),
                first_seen=str(e["first"]),
                outside=bool(scan(committable, [phrase])),
            )
            for phrase, e in found.items()
        ),
        key=lambda c: (c.kind != "entity", c.kind != "person", -c.count, c.text),
    )


def _answer_files(knowledge: Path) -> list[Path]:
    """Where an answer can have been written down. Not `backlog.md` or `coverage.yaml`,
    which are the build's own bookkeeping, and not `identifiers.txt`, which is the answer."""
    if not knowledge.is_dir():
        return []
    named = ("profile.md", "workflow.md", "decisions.md", "documents.md", "followups.md")
    files = [knowledge / name for name in named if (knowledge / name).is_file()]
    files += sorted((knowledge / "sessions").glob("????-??-??-*.md"))
    files += sorted(p for p in (knowledge / "projects").rglob("*.md") if p.name != "README.md")
    return files


# ----------------------------------------------- a register that is empty on purpose

_REVIEWED = re.compile(
    r"^#\s*reviewed\s+(\d{4}-\d{2}-\d{2})\s+by\s+([^:\[]+?)\s*(?:\[over:([^\]]*)\])?\s*:", re.I
)
"""`# reviewed <date> by <who> [over: <session stems>]: <note>`.

The `[over: ...]` part is what the acknowledgement was made against, and it is the whole
point of the line. Optional in the pattern because acknowledgements written before P64 do
not carry it, and those are read conservatively rather than trusted - see
`_review_is_current`."""


def reviewed_empty(knowledge: Path = KNOWLEDGE) -> tuple[str, str] | None:
    """`(date, who)` if somebody has recorded that they looked and there was nothing.

    The sessions it was made over are read separately by `_reviewed_over`, so that a caller
    wanting to print who and when does not have to know about coverage.

    An empty register does not have to mean nobody has checked. Three sessions of this
    interview named no client at all - they were about how the work is done, not about whose
    work it was - and a refusal that reads "answers exist, therefore names exist" is wrong in
    exactly that case. The way out is not a cleverer detector. It is the same move
    methodology clearance makes: a person reads something and records that they did, under
    their own name, and the record is what the check reads.

    It expires. An acknowledgement is about the answers that existed when it was written, so
    a session log recorded after it does not inherit it - see `_review_is_current`. Otherwise
    the first person to run this would have switched the check off permanently, which is the
    failure P53 and P54 were both about.
    """
    path = knowledge / "identifiers.txt"
    if not path.exists():
        return None
    for line in path.read_text(encoding="utf-8").splitlines():
        found = _REVIEWED.match(line.strip())
        if found:
            return found.group(1), found.group(2).strip()
    return None


def _reviewed_over(knowledge: Path = KNOWLEDGE) -> tuple[str, ...] | None:
    """The session stems an acknowledgement was made over, or None if it names none.

    None means the line was written before P64 and says only when it was made. That is not
    the same as "over nothing", and the two must not be confused: one is an old record, the
    other would be an acknowledgement covering no session at all.
    """
    path = knowledge / "identifiers.txt"
    if not path.exists():
        return None
    for line in path.read_text(encoding="utf-8").splitlines():
        found = _REVIEWED.match(line.strip())
        if found:
            over = found.group(3)
            return tuple(over.split()) if over is not None else None
    return None


def sessions_with_answers(knowledge: Path = KNOWLEDGE) -> tuple[str, ...]:
    """The session logs that got past their own header - the ones holding answers."""
    logs = sorted((knowledge / "sessions").glob("????-??-??-*.md"))
    return tuple(log.stem for log in logs if _beyond_its_header(log))


def _review_is_current(knowledge: Path, on: str) -> bool:
    """Whether the acknowledgement covers every session that holds answers.

    It used to ask whether every session *predated* the review, with the same day counting
    as covered. That was deliberate and it was wrong. The legitimate flow is to finish a
    session and then record that nobody was named, which happens on one day - so `<` would
    refuse the very case the acknowledgement exists for. But `<=` also covers a session that
    had not happened when the line was written, and a session begun an hour after an
    acknowledgement inherited it. That is the check CLAUDE.md names as what keeps client
    data inside `knowledge/` reporting `clean` over answers nobody looked at.

    A date cannot separate those two orderings, because both happen on the same date. What
    was looked at has to be recorded. So an acknowledgement now carries the sessions it was
    made over, and is current only while those are still all of them.

    An acknowledgement from before P64 carries no list. It is read conservatively - strictly
    before its date - rather than trusted, because the one thing not known about it is
    whether the same-day session came first. That expires the acknowledgement in the repo
    today against any session dated the same day, which is the safe direction: the cost is
    running `register --none` again, and the cost of the other direction is a client's name
    leaving `knowledge/` unnoticed.
    """
    answered = sessions_with_answers(knowledge)
    covered = _reviewed_over(knowledge)
    if covered is None:
        return all(stem[:10] < on for stem in answered)
    return set(answered) <= set(covered)


def add_identifiers(names: list[str], knowledge: Path = KNOWLEDGE) -> list[str]:
    """Append names to the register, skipping any already there. Returns what was added."""
    init(knowledge)
    path = knowledge / "identifiers.txt"
    known = {n.casefold() for n in identifiers(knowledge)}
    fresh = [n.strip() for n in names if n.strip() and n.strip().casefold() not in known]
    if fresh:
        body = path.read_text(encoding="utf-8")
        joined = "\n".join(fresh)
        path.write_text(
            body + ("" if body.endswith("\n") else "\n") + joined + "\n", encoding="utf-8"
        )
    return fresh


def record_review(who: str, note: str, knowledge: Path = KNOWLEDGE, on: str | None = None) -> str:
    """Write the acknowledgement that the register was looked at and is empty on purpose.

    It records the sessions that held answers at the moment it was written. That list is
    what makes the acknowledgement expire honestly: the next session is not in it, so the
    check refuses again, whether or not it falls on the same day.
    """
    init(knowledge)
    path = knowledge / "identifiers.txt"
    stamp = on or date.today().isoformat()
    over = " ".join(sessions_with_answers(knowledge))
    line = f"# reviewed {stamp} by {who} [over:{(' ' + over) if over else ''}]: {note}"
    body = path.read_text(encoding="utf-8")
    kept = [ln for ln in body.splitlines() if not _REVIEWED.match(ln.strip())]
    path.write_text("\n".join([*kept, line]) + "\n", encoding="utf-8")
    return line


def _trim(phrase: str) -> str:
    """Drop leading words that only start a sentence.

    "Usually Excel" and "Any Cursor" are one capitalised word with an adverb in front of it,
    picked up because the sentence began there. Stripping the opener and re-measuring is
    better than rejecting the phrase: it leaves "Excel", which is one word and falls below
    the threshold on its own, while "Usually Northgate Dental" keeps the part that matters.
    """
    words = phrase.split()
    while words and words[0].strip(".,") in _NOT_A_NAME:
        words.pop(0)
    return " ".join(words)


def _worth_proposing(phrase: str, known: set[str]) -> bool:
    if len(phrase) < 4 or phrase.casefold() in known:
        return False
    return len(phrase.split()) > 1 or "." in phrase


def _suggest() -> int:
    candidates = suggest(KNOWLEDGE, ROOT)
    registered = identifiers(KNOWLEDGE)
    print("# Candidates for knowledge/identifiers.txt\n")
    print("Read from the answers already in knowledge/. Nothing here has been written")
    print("anywhere: the register is changed by a person, one name per line. Reject freely -")
    print("a name that is not a client's costs nothing to leave out, and a shape is not a")
    print("judgement about who somebody is.\n")
    if registered:
        print(f"{len(registered)} already registered, and not proposed again.\n")
    if not candidates:
        print("Nothing in knowledge/ has the shape of a name.")
        return 0

    for kind in ("entity", "person", "name-shaped"):
        group = [c for c in candidates if c.kind == kind]
        if not group:
            continue
        print(f"## {kind} ({len(group)})")
        for c in group:
            times = "once" if c.count == 1 else f"{c.count} times"
            mark = "  <- ALSO OUTSIDE knowledge/" if c.outside else ""
            print(f"  {c.text}")
            print(f"      {c.shape}, {times}, first at {c.first_seen}{mark}")
        print()

    if any(c.outside for c in candidates):
        print("A candidate marked ALSO OUTSIDE already appears in a file git would commit.")
        print("Usually that means it is this build's own vocabulary rather than a client's")
        print("name - and if it is not, it is a name that has already left knowledge/, which")
        print("is the one case the register exists to catch. Worth looking at either way.\n")

    print(f"{len(candidates)} candidate(s). Add the real ones to knowledge/identifiers.txt,")
    print("then run `python tools/interview.py scan`.")
    return 0


def _register(names: list[str], none: str | None, who: str) -> int:
    if none is not None:
        if identifiers(KNOWLEDGE):
            print("The register is not empty; there is nothing to acknowledge.")
            return 1
        # The note is the decision. The code used to supply one when the person did not,
        # which records an acknowledgement in nobody's words - the same defect as a
        # methodology clearance nobody read the file for.
        if not none.strip():
            print("An acknowledgement needs words of your own: what you looked at, and why")
            print("there was nothing to register. Nothing has been recorded.")
            print('\n  python tools/interview.py register --none "checked the three sessions;')
            print('      no client, person or entity has been named"')
            return 2
        # Replacing one that still stands would destroy a record and put a second decision
        # in its place that changed nothing - which is what P57 refuses for a recipe already
        # approved at the same bytes. A stale one is different: renewing it is the act.
        standing = reviewed_empty(KNOWLEDGE)
        if standing and _review_is_current(KNOWLEDGE, standing[0]):
            on, by = standing
            print(f"An acknowledgement already stands, made {on} by {by}, and nothing has")
            print("been logged since that it does not cover. Recording another would replace")
            print("it with a decision that changed nothing.")
            print("\nIt goes stale by itself the moment a session with answers is logged.")
            return 1
        line = record_review(who, none, KNOWLEDGE)
        print(f"recorded in knowledge/identifiers.txt:\n  {line}")
        print("\nIt covers the sessions named in it. The next one makes it stale,")
        print("which is the point: an acknowledgement is not a way of switching the check off.")
        return 0
    if not names:
        print("Nothing to add. Give one or more names, or --none to record an empty register.")
        return 2
    added = add_identifiers(names, KNOWLEDGE)
    skipped = [n for n in names if n not in added]
    for name in added:
        print(f"added: {name}")
    for name in skipped:
        print(f"already registered: {name}")
    print(f"\n{len(identifiers(KNOWLEDGE))} identifier(s) in the register. Now: interview.py scan")
    return 0


def _who() -> str:
    """Whoever is at this machine. The same answer the identity adapter gives a run."""
    import getpass  # noqa: PLC0415

    try:
        return getpass.getuser()
    except Exception:  # noqa: BLE001
        return "unknown"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else "")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status", help="where the interview stands and what to ask next")
    sub.add_parser("session", help="start a session log and print its path")
    sub.add_parser("topics", help="the coverage map in asking order")
    sub.add_parser("scan", help="identifiers in anything git would commit")
    sub.add_parser("suggest", help="what in knowledge/ looks like it belongs in the register")
    reg = sub.add_parser("register", help="add a name to the register, or record it as empty")
    reg.add_argument("names", nargs="*", help="every client, person, place or entity name")
    reg.add_argument(
        "--none",
        nargs="?",
        const="",
        default=None,
        metavar="WHY",
        help="record that you looked and there is nothing to register",
    )
    reg.add_argument("--who", default="", help="who reviewed it; defaults to this machine's user")
    marker = sub.add_parser("mark", help="record a topic's coverage")
    marker.add_argument("topic")
    marker.add_argument("status", choices=STATUSES)
    marker.add_argument("--note", default="")
    marker.add_argument("--session", default="")
    args = parser.parse_args(argv)

    if args.command == "status":
        return _status()
    if args.command == "session":
        opened = start_session(KNOWLEDGE)
        # Relative while it is inside the repo, which is where it lives; absolute rather
        # than a traceback when it is not, which is the case a test points elsewhere.
        try:
            print(opened.relative_to(ROOT).as_posix())
        except ValueError:
            print(opened.as_posix())
        return 0
    if args.command == "topics":
        return _topics()
    if args.command == "scan":
        return _scan()
    if args.command == "suggest":
        return _suggest()
    if args.command == "register":
        return _register(args.names, args.none, args.who or _who())
    if args.command == "mark":
        # A traceback in the middle of an interview is noise a person has to read past to
        # find the one sentence that matters, and the sentence is already written.
        try:
            entry = mark(args.topic, args.status, args.note, args.session, KNOWLEDGE)
        except ValueError as refused:
            print(refused)
            print("\nThe topics are listed by: python tools/interview.py topics")
            return 2
        print(f"{args.topic}: {entry['status']}")
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
