# admin/

Where a person actually sets this thing up. Three blueprint nodes:

- **preflight.py** — Setup Preflight. Ten checks over the live configuration, the
  roster and the ports. Every failure is a standard diagnostic with the owner set to
  `config`, and the report says which engagements it blocks. Not part of any run: it
  emits into no event stream and colours no node on the trace.
- **console.py** — the Admin Console. Reads and writes the Configuration Store and the
  Active Project Roster; every write lands in the Config Change Log with who, what,
  when and why. `activate` runs preflight for that engagement first and refuses on a
  failing check, so a setup error costs a minute rather than a halted run.
- **app.py** — the FastAPI surface. Every write carries `who` and `reason`.

## What an admin may and may not do

May: activate, pause and archive; add and edit watches and destinations; bind a model
to a layer through the same five-layer walk the skills use; raise a review level; set a
per-run budget at or below the firm ceiling; record that a credential exists and when
it expires.

May not, and there is no method for it: lower a review level; raise a budget above the
firm ceiling (`CONFIG.ADMIN_FORBIDDEN`); see a credential's value; touch a guard, the
mask vault, a skill, a schema or the release gate. The package imports none of those,
and a test keeps it that way. Invariant 23 is checked over the graph:
configuration writes the engagement record, guards read the run.

## The record

`config_document@1.1.0` holds watches, intake timing, destinations (with adapter and
credential name), model bindings per layer, expected credentials (name and expiry,
never a value), and per-engagement overrides including the engagement profile, which is
validated against `engagement_profile@1.0.0` on every write. `templates/bindings.yaml`
stays as the checked-in seed; `seed_model_bindings` brings it into the store once.
