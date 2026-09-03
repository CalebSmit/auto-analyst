# recipes/

**What belongs here.** Named, versioned job recipes: an ordered list of steps with their
dependencies, the loop regions in force, and what happens when a step fails.

**What does not.** Domain logic. A recipe composes skills; nothing here says what EBITDA
is. That lives in a SKILL.md, at the scope layer where it is true.

## Why recipes rather than a model, until P26

Most deal work is not novel. When the shape of a job is already known, having the
orchestrator rediscover it every time is wasted tokens and a wasted chance at variance.

The sharper reason is about debugging: bringing up plan compilation and a model's plan
proposal at the same time means trusting neither when something is wrong. Recipes make
the routine case deterministic first. The orchestrator arrives later, into a compiler
that is already known to work.

## Every loop is declared here

A recipe's `loops:` block names the region, the step iteration restarts at, its members,
and an integer ceiling. The compiler checks that ceiling against `constraints.yaml` -
raising one is a change there, deliberately, never in the recipe that wants the extra go.

Then it refuses any cycle that is not one of these. The dependency graph on its own must
be acyclic; a `needs:` that closes a loop has nothing bounding it, and a loop with no
ceiling is how a run spends its whole budget on one step.

A step can be inside more than one region - self-verification applies to every EBITDA
output, guard repair applies when that output fails its schema check - so regions may
nest. What they may not do is overlap partially, or declare members that do not lie on
the path the back edge returns over.
