# foundations/

**What belongs here.** How the firm does this work, and how each practice group does it.
Valuation standards, QC conventions, tagging policy, house rules at the firm layer; a
group's own way of working at its own. Attached by the Context Builder rather than
referenced per skill, so it cannot be omitted by whoever writes the next skill.

**What does not.** Anything specific to one skill - that is a reference file under the
skill's own folder. Anything specific to one engagement - that is the engagement profile.
Anything carrying a real engagement's numbers, names or identifiers - see *Cleared once*
below, which refuses it rather than trusting nobody will.

## The layers

The same five-layer tree as `skills/`, walked the same way, so methodology and skills
cannot disagree about what a practice group is:

```
foundations/_firm/                        every run there is
foundations/valuation/_group/             every valuation run
foundations/valuation/_repeat/            valuation, returning clients
foundations/valuation/esop/_segment/      ESOP work
foundations/valuation/esop/repeat/        the leaf
```

A valuation run carries the firm's methodology and valuation's, and never consulting's. A
group that has written nothing of its own still carries the firm's: a missing layer
contributes nothing rather than failing, so a new practice group works from the day it is
declared.

Only `_firm/` exists today. The rest is written when a practice group writes it - the
system does not invent firm standards.

## Cleared once, checked every run

Methodology reaches **every model call for every client**, and the outbound scan only
knows the current engagement's identifiers. A worked example quoting a real deal, pasted
in here by somebody being helpful, would travel to every prompt and trip nothing.

So a file is read by a person and cleared before it is attached to anything:

    POST /api/admin/methodology/{layer}/{name}/clear    {"who": "your name"}

Clearing scans for client data and for anything shaped like an instruction to the model
reading it, and records the file's digest against the name of whoever cleared it. At run
time the check is a hash lookup - never a scan, because one broad pattern would otherwise
take a practice group offline in the middle of the afternoon.

**An edit loses its clearance automatically**, because the digest changes. There is no
path where a file is cleared, edited, and still attached. Preflight reports anything
uncleared or edited at setup rather than leaving a run to find it.

`cleared.yaml` is not committed. A clearance records that somebody read a file, so
shipping one would record a decision nobody made - a fresh clone starts with nothing
cleared, and says so.

## A size ceiling

`constraints.yaml` caps bytes per layer, and preflight reports it. This is content on
every call: methodology that grows unchecked is a standing cost on every run and a step
closer to the per-run ceiling, attributable to nothing in particular months later. The
ceiling makes growth a decision.

`BUILD/surfaces.json` carries a digest per layer, so a change to what every prompt
carries shows up as a line in a diff rather than as nothing at all.
