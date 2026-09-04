# deliver/

The way out. Everything above this package exists so that building the deliverable is
boring: by the time a figure arrives here it has a source, has been recomputed, has been
re-identified and has been locked.

| file | node | what it does |
|---|---|---|
| `registry.py` | Template Registry | Registers a template by introspecting the workbook: every required named range must be declared, a cell address is refused, the bytes are pinned by hash. Answers `template_schema_lookup`. |
| `builder.py` | Model Builder | Resolves the validated mapping to values, hands them to the Template Writer (`tools/write_template.py`), reads the workbook back, and the Numeric Integrity Lock says nothing changed. Refuses to build with a required input unmapped. |
| `qc.py` | Deliverable QC Gate | Opens the produced file: loads, no `#REF!`, formulas resolve, no external link, no residual mask token, version stamped, every written range holds its value. Fails closed. |
| `release.py` | Single Release Gate + Idempotency Ledger | One inbound edge, from QC. Records run id, artifact hash and destination in the same transaction as the release event; a replayed release returns the original location and never writes twice. |
| `workpaper.py` | Workpaper Narrative | Renders the summary from locked data, counts in words, and checks that every number in the prose is a locked figure. |

## What the tests prove

- A binding to a cell address is rejected at registration.
- A template declaring 41 of 43 required inputs fails registration naming the two.
- A produced workbook opens with no `#REF!`, no broken link, no residual token, and the
  stamp and every written range as the mapping said.
- A replayed release does not deliver a second time.

## Templates

`templates/*.xlsx` are synthetic, built by `tools/synthesize_templates.py` from the input
schemas under `templates/inputs/`. The firm's own models register under new versions at
the P24 pilot. The master is never opened for writing: the writer works on the
registered bytes, and the registry refuses a master whose bytes changed.
