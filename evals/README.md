# evals/

Assurance before a skill ships. Two harnesses and the one gate on registration.

| file | node | what it does |
|---|---|---|
| `gates.yaml` | - | The per-skill acceptance gates: a named metric, an operator and a number, beside the blueprint's sentence for it. |
| `metrics.py` | - | One function per shipped skill that runs the skill's mechanical half over its golden fixtures, through the gated runtime, and returns the numbers. |
| `harness.py` | Evaluation Harness | `evaluate(skill)` scores every gate; `coverage()` reports which skills and guards have fixtures and which do not. |
| `replay.py` | Replay Harness | Restores a past step's recorded inputs, runs a candidate over them, and diffs against what was delivered and what a person later corrected. |
| `registration.py` | Skill Registry (the last link) | Records a version as registered from a scorecard that cleared every gate. Below the gate, no registration. |
| `world.py` | - | An ephemeral run for evaluating outside any engagement: a throwaway store, the real tools, the real gate. |

## The command

    python tools/gate.py eval timing-normalization        # the scorecard
    python tools/gate.py eval --all                        # every shipped skill
    python tools/gate.py eval --coverage                   # what is and is not covered
    python tools/gate.py eval line-item-tagging --register "Caleb"   # register on pass

## What is measured, and what is owed

A gate the offline harness cannot measure - shadow disagreement over real runs - is
listed in `gates.yaml` with `measured_by` and reported as owed, on the scorecard, in
the coverage report and on the registration record. It neither passes nor fails a skill
here; it is a debt the later control pays, and the report says so rather than leaving
the row out.

## Replay reads masked payloads only

The dispatcher records three blobs per skill step - the inputs the procedure was given,
the proposal the model returned, the output the step emitted - and names them on the
`skill.completed` event. Replay reads those and the run store. It never opens the vault
and never touches a released artifact, so a candidate sees exactly what the original
skill saw and nothing a person re-identified afterwards.
