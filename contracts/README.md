# contracts/

**What belongs here.** JSON Schemas for every shape the system passes around: the figure
envelope, one output schema per skill, events, the run manifest, engagement_profile and
participant_census. Each carries a version in its id. Plus `registry.yaml`, the index
that pins them — the loader reads only what it lists, at exactly the version it lists,
and a schema file the index does not name is an error rather than a contract.

**What does not.** No Python. A schema that needs code to be understood is not a
contract. The loader lives in [`registries/`](../registries/).

## The one that matters

`figure.schema.json` is load-bearing. Every guard on the map is really an assertion
about it, which is why it is defined once here and referenced by `$ref` rather than
restated per skill. Two of its fields exist because of specific failures:

- **`scale`** is required and has no default anywhere. A default is inference with a
  friendly name, and a trial balance in thousands read as units is a halt-at-tie-out
  failure the blueprint names explicitly.
- **`source_id`** must be a content hash, and an id naming the system's own reasoning —
  `derived`, `model`, `analysis` — is rejected as fabricated provenance, as hard as a
  missing one and with its own diagnostic, because "does not match a pattern" would send
  somebody to fix the wrong thing.

## Two conventions worth knowing

`x-emits-figures` on a skill output says whether that schema can originate a figure. It
is what P07's plan assertion reads, and a test checks it against whether the schema
actually references the envelope, so it cannot quietly become a lie.

`x-open-by-design` marks the only object in the registry that does not close itself —
`event.payload` — and carries the reason. Everything else sets
`additionalProperties: false`, because "the skill wrote a conclusion into a field that
should not exist" is caught structurally or it is not caught at all.
