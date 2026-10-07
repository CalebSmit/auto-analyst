# knowledge/

Everything `/improve-agent` learns: answers, documents, project walk-throughs, judgment
rules, coverage. **Committed**, so it travels between machines with the repo - which is
why the repo must stay private. It is excluded from the container image.

Nothing identifying in here may be copied into a skill, methodology file or fixture;
`python -m uv run python tools/interview.py scan` checks everything outside this folder against
`identifiers.txt`.

The layout is created by `python -m uv run python tools/interview.py status` on first use.

`model-setup/` is the exception to that: it is made here, for the worked examples, prior
models and engagement notes behind the model-setup skill the work laptop brings - the part
of that skill that names clients and so can never live under `skills/`. See
[`model-setup/README.md`](model-setup/README.md) and section 8 of
[`docs/WORK-LAPTOP.md`](../docs/WORK-LAPTOP.md).
