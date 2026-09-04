# tools/

**What belongs here.** The deterministic tools a skill may propose calling, plus gate.py. All arithmetic in the system happens here.

**What does not.** No model calls, and nothing importable from skills/ - tools are reached through the Guarded Tool Runtime by name, never by import.

| name | file | kind | what it does |
|---|---|---|---|
| `recompute` | recompute.py | computes | Re-derives a stated figure from the rows behind it. |
| `timing_normalizer` | normalize.py | computes | Executes a proposed alignment; every sum, none of the judgment. |
| `chart_of_accounts_lookup` | coa.py | reads | The firm taxonomy at the version the run pinned (`registries/taxonomy.py` loads it). |
| `precedent_lookup` | precedent.py | reads | Prior approved decisions, scope-built from the run's own scope; by id or ranked by description. |

The two reads pass the Policy Gate exactly as the two computes do: the taxonomy call
names the pinned version or is refused, the precedent call names the run's practice or
is refused. Reading the wrong engagement's precedents would return perfectly valid data,
which is why a read is not the cheap case.
