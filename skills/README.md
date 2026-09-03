# skills/

**What belongs here.** One directory per scope layer, each holding SKILL.md files and
their reference documents. Deeper layers shadow shallower ones and may only tighten.

**What does not.** Nothing writes here except the Skill Registry. A hand-edited skill has
not been through fixtures, review or a shadow run.

## The layout

    <layer>/<skill-name>/SKILL.md          frontmatter + body
    <layer>/<skill-name>/references/       loaded on dispatch, never into the index
    <layer>/overlays.yaml                  changes to skills inherited from above

A skill is written once at the shallowest layer where it is true. The alternative - a
flat library, or a full copy per practice group - fails the same way every time: the same
EBITDA procedure ends up in six places and they drift apart within a year.

An empty layer folder is not a missing one. It is declared, contributes nothing, and the
resolver says so; that is how "Consulting has named no skills yet" stays visible instead
of looking like a resolution that went wrong.

## Skeletons

Every skill here is `status: skeleton`. The frontmatter is complete - it is what the
Skill Index reads and what the Policy Gate will enforce - and the body is a placeholder
until the phase that writes it. A skeleton is not a skill: nothing dispatches one, and
the Skill Registry is what makes a skill live.

## Three tiers, and the line between them

Tier 0 is the Scope Resolver. **Tier 1 is the Skill Index: name and description only**,
about forty tokens each, and it is the entire skill footprint in the orchestrator's
context. Tier 2 is the body, loaded on dispatch.

`tests/p05/test_skill_index.py` takes every distinctive line out of every body and
reference file and proves none of them can be reached through the index. The boundary is
worth that because the failure is invisible: an index that quietly grew a `body` field
would work perfectly and cost more on every run.
