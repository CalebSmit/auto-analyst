# docs/

**What belongs here.** The architecture blueprint that travels with the repo, and the
original project-context note it grew out of. `architecture.html` is a self-contained
single file: 118 nodes, 240 edges, 25 executable invariants, 67 failure modes. Open it in
a browser; it needs nothing else and makes no network requests.

**What does not.** Generated documentation, and anything that duplicates BUILD/. The plan
lives in BUILD/; this is the design the plan is built from.

## This file is the source of truth

`architecture.html` is edited **here**, and the edit is committed alongside whatever
prompted it. It is the copy the work machine has after the handoff, the copy the tests in
`tests/p02` read when they check that the blueprint still describes what is built, and the
only copy with a history you can read.

It used to be the other way round — the authoritative copy lived in OneDrive and this one
was refreshed from it. That made every blueprint correction a two-step operation where
forgetting the first step reverted the second without saying so. The reason for the change
is in [AMENDMENTS.md](../BUILD/AMENDMENTS.md).

## The OneDrive mirror

A copy is published to OneDrive so the design can be opened on another device. It is a
mirror. Nothing reads it, and editing it there is not how the blueprint changes.

```
python tools/sync_blueprint.py            publish this copy to the mirror
python tools/sync_blueprint.py --check    report drift, change nothing
python tools/sync_blueprint.py --pull     mirror wins - for an edit made over there
python tools/sync_blueprint.py --force    publish over a mirror that has diverged
```

Publishing refuses if the mirror has changed since it was last published, because that
means somebody edited it there and a publish would discard the work. `--pull` brings such
an edit back into the repo, where it gets committed with a reason like anything else.

On a machine with no OneDrive path — the work machine — every one of these is a harmless
no-op.

## When the blueprint and the code disagree

That is a **finding**, not a preference. Resolve it explicitly, correct whichever side is
wrong, and record the resolution with `gate amend`. Four tests in `tests/p02` read this
file directly and fail when it stops describing what is actually built.
