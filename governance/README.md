# governance/

**What belongs here.** The eleven-stage chain a skill has to survive: `record.py`,
`candidate.py`, `drop.py`, `conformance.py`, `adapt.py`, `sandbox.py`, `board.py`,
`shadow.py`, `registry.py`, `chain.py`.

**What does not.** Anything that runs client work, and anything that could reach it. No
vault, no engagement store, no storage port, no delivery. The eval harness and the replay
harness are P22's and live in `evals/`; this package uses them.

## The chain

    drop -> conformance -> bench -> sandbox -> sandbox test -> eval harness
         -> replay -> submit -> board -> shadow run -> registry -> the live tree

Linear, and each stage requires the evidence of every stage before it. Remove any one and
the path breaks rather than routing around it - `tests/p27` takes each gate away in turn
and asserts the refusal names it. The blueprint's invariant 21 says the same thing about
the design; this is the same claim about the code.

## The record is the state

`GovernanceRecord` is an append-only JSONL file in a governance scope, outside the repo,
with each entry carrying the hash of the one before it. A candidate's position is folded
from it, so nothing advances because an object in memory said it had, and an edit made
outside this module leaves a break that `verify()` finds and names. The run store gets
that guarantee from database triggers; a file gets it from the chain of hashes.

## The two limits that matter

**The bench cannot produce fixtures.** It fits a draft to the contract and writes a
fixture *request*. Four modules in this package write anything at all - the record, the
triage copy, the sandbox and the registry - and a test walks the syntax tree to prove it.
Without that limit, the drop folder plus a helpful model is the route by which unvalidated
logic reaches client work.

**Governance sees masked payloads or it sees nothing.** The isolation is that the
connection does not exist: no engagement credential, no vault, no storage binding. The
client-data scan is therefore pattern-based, and its patterns live here rather than being
imported from `privacy/`, which would give this package a reason to reach the masking
layer.

## Where things are

| | |
|---|---|
| Drafts and the record | `AA_SKILLS_INTAKE_ROOT`, default `~/.automated-analyst/skills-intake` |
| Never | inside the repo. A draft is untrusted content, and the scan runs *after* the drop |
| The live tree | `skills/`, written only by `governance/registry.py` |
| The version ledger | `skills/registered.yaml`, written only by `evals/registration.py` |

## Promotion

`shadow_disagreement` in `evals/gates.yaml` carries both halves of its gate: the rate and
the number of real runs it has to hold over. Promotion needs the rate inside the threshold
over every observation *and* over the most recent window of that size, so a candidate that
was fine for eighteen runs and has disagreed since does not promote on its average.

    python -m uv run pytest tests/p27 -q
    python -m uv run pytest tests/checkpoints/c09 -q
