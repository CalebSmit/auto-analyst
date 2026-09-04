# orchestrate/

**What belongs here.** The three orchestration nodes: `orchestrator.py` (the agent that
proposes a plan), `plan.py` (the Run Plan - a proposal becomes a recipe, is compiled and
asserted, and is written down), `triage.py` (the fallback when nothing fits).

**What does not.** Anything that executes. The planner produces a `CompiledGraph`; the
Step Executor runs it. Triage opens a review item and has no method that dispatches a
skill.

## The whole argument, in one sentence

A proposal is turned into a `Recipe` - the same dataclass `recipes/*.yaml` loads into -
so by the time anything is compiled there is nothing to tell a model-driven plan apart
from a named one. There is no second compiler, no second set of assertions and no path
that skips either.

## What the model supplies, and what it cannot

| The proposal carries | Where everything else comes from |
|---|---|
| which steps run, and what each needs | |
| a skill name, from the Skill Index | the version and the model pin: the resolved scope |
| a label and a failure policy | the output contract: the contract registry, pinned from the skill |
| a rationale, for the person reading | timeouts and retries: the recipe defaults |
| `match`: recipe, composed, or none | loop regions and their ceilings: `REQUIRED_LOOPS` here, with every maximum read from `constraints.yaml` |

`run_plan_proposal@1.0.0` has **no numeric property anywhere**. Not a figure, not a
confidence, not a timeout, not an iteration ceiling. The graph owns every loop, so the
ability to ask for another attempt is not withheld by a rule - there is no field for it.
"No confident match" is categorical for the same reason: `match: none` routes to triage,
rather than a number compared against a threshold nobody agreed.

## When a proposal does not survive

It is refused, the refusal is recorded with its diagnostic, and the named recipe runs.
Every way of being wrong ends the same way - a cycle nobody declared, a skill this
engagement does not have, an input nothing declared, a step that would write figures
after the tie-out gate. A model proposing a bad plan is not a way for a run to fail.

## The Run Plan artifact

`run_plan@1.0.0`, written to the content store and recorded on the run **before
execution begins**: steps, inputs, loop regions, order, plan hash, where it came from and
what was refused. `GET /api/runs/{id}/plan` reads it back, so "what is it doing?" is a
question with an answer before it finishes rather than after.

## Triage

High tier, deliberately: the cases that reach it are the ones where a classification
mistake costs most. `triage@1.0.0` has no numeric property and no open object, so a
plausible invented figure - the most damaging thing it could produce - has nowhere to go.
A suggested skill is checked against the index and recorded for a person; nothing here
dispatches it.

    python -m uv run pytest tests/p26 -q
