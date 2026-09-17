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

## Deterministic engines no skill can reach yet

| file | what it does | what reaching it takes |
|---|---|---|
| `statement_checks.py` | The analyst's model checks - net income ties to the client's, the balance sheet balances, cash flow ending cash equals balance sheet cash - plus period-over-period movement flags. Every total through `recompute`; a failure keeps both numbers; no stated figure is `could_not_evaluate`, never a pass. Output fits the `qc-tieout` contract. | A qc-tieout procedure, the tool named in `constraints.yaml` and in the skill's `tools:` - the last through the governance chain. Backlog B-004. |
| `forecast_drivers.py` | Forecast driver baselines for a firm-built forecast: revenue growth, cost of sales and operating expenses as shares of revenue, per period, last year and 2/3/5-year trailing averages, each through `recompute` with its source lines. Chooses no baseline and projects no year. | A forecast skill (backlog B-006) that proposes the baseline and step path, through the governance chain. |
| `beta.py` | Unlever and relever a beta under a formula the caller must name (Hamada or Harris-Pringle; no default until the firm's is confirmed), and the comps' median unlevered beta naming every company used and left out. Through `recompute`. | A cost-of-capital procedure, through the governance chain. |
