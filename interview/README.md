# interview/

**What belongs here.** The committed half of `/improve-agent`: the protocol the command
follows (`PROTOCOL.md`) and the map of what it has to learn (`topics.yaml`). Generic by
rule - no client, no project, no figure.

**What does not.** Anything learned. Answers, documents, projects and the coverage state
live in `knowledge/`, committed so the interview travels with the private repo. `tools/interview.py` is the deterministic half:
status, session logs, coverage, and the scan that keeps identifiers out of committed files.

## Running it

| Where | How |
|---|---|
| Claude Code | `/improve-agent` (from `.claude/commands/improve-agent.md`) |
| Cursor | `/improve-agent` in the agent chat (from `.cursor/commands/improve-agent.md`) |

Both are one-line wrappers that point at `PROTOCOL.md`, so the behaviour cannot drift
between the two tools. Type anything after the command to steer the first question, e.g.
`/improve-agent the Oakmont project` or `/improve-agent add-backs`. Say **stop** when you
are done; it will propose what to build from the session and ask which items to build.

## Pointing it at another division

Change `focus:` in `scope/scopes.yaml`, and add or adjust topics here for what differs.
Nothing else in the command is division-specific.

## Moving machines

`knowledge/` is committed, so a clone picks the interview up where it left off. Commit and
push at the end of a session, and pull before starting one on the other machine. The repo
must stay private: `knowledge/` can hold client names and documents.
