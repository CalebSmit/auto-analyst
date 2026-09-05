# Handoff

What changes on the work machine, and what does not.

The short version: **`.env` changes, and nothing else.** Everything that could have been
a fact about one laptop is behind a port or an environment variable, and this document is
the list. If something not on this list has to change to make the suite pass, that is a
defect in the portability claim, not a step to add here quietly.

---

## 1. Get it running

```
git clone <repo> automated-analyst
cd automated-analyst
cp .env.example .env          # then fill in the two values below
python -m uv sync --all-groups
python -m uv run pytest -q
python tools/gate.py status
```

Two values have to be filled in before anything runs for real:

| Variable | Why |
|---|---|
| `ANTHROPIC_API_KEY` | The firm's key. This is the one credential that changes at handoff. |
| `AA_VAULT_KEY` | The mask vault's encryption key. **Generate a new one on each machine** and never commit it. `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |

`AA_VAULT_KEY` is not copied across machines. The vault is the only store that can
re-identify anything; a key that has been in two places is a key nobody can reason about.
Generating a new one means the tokens issued on this machine cannot be resolved on that
one, which is the correct behaviour and not a problem to work around: mask tokens are
per engagement and are re-derived from the vault the run has.

The suite needs neither. The LLM adapter defaults to `fake`, which replays recorded
fixtures, so the whole suite runs with no API key and costs nothing.

---

## 2. In a container

The image holds no credential and no client data. Both arrive at runtime.

```
podman build -t automated-analyst:0.1.0 .
podman run --rm --env-file .env automated-analyst:0.1.0        # the suite
podman compose up --build                                      # app + Postgres
```

`docker`, `nerdctl` and Rancher Desktop's `nerdctl` take the same commands. Nothing in
the Dockerfile or `compose.yaml` is Docker Desktop's: no `desktop.` extension, no named
pipe, no host gateway, no mounted docker socket. That matters because **Docker Desktop is
not licensed here** and was never a dependency.

> **Which runtime was actually used.** None, on the build machine. No OCI runtime is
> installed on it — `docker`, `podman`, `nerdctl`, `finch` and `rancher` are all absent,
> and only WSL is present. The container files are written and statically checked by
> `tests/p28`, and the suite is run **with `--container`** on a machine that has a
> runtime. Until somebody does that, the image has never been built. The session summary
> says so on every run, in words, for the same reason the Postgres and Redis runs do:
> a claim nobody has executed is not evidence.
>
> Fill this in when you run it: _runtime used, version, date._

---

## 3. What is different about the work machine

Everything in this table is configuration. None of it is a code change.

| | This machine | The work machine |
|---|---|---|
| **Model key** | a personal key, or none — the fake adapter replays fixtures | the firm's `ANTHROPIC_API_KEY` |
| **Model access** | the Anthropic API directly | **the same.** Decided 2026-09-05: not Foundry. Hosting can move to Azure without model access moving with it — everything this build sends is GA on the first-party API, and the firm's account is already sanctioned for client data. Needs one thing from IT: egress from the container to `api.anthropic.com` |
| **Vault key** | generated locally, never committed | generated there, never copied |
| **Intake** | `AA_STORAGE_ADAPTER=local_folder`, a watched folder | `sharefile`, once the firm's connector is wired in |
| **Delivery** | `AA_DELIVERY_ADAPTER=local_folder`, `./outbox` | `box`, once the firm's connector is wired in |
| **State store** | SQLite at `AA_DB_URL=sqlite:///./runs/run_store.db` | Postgres — one URL, no other change |
| **Queue** | `in_process`, a bounded thread pool | `redis_rq` when runs outlive a process |
| **Concurrency** | `AA_MAX_PARALLELISM=1` | whatever the host allows; the Engagement Lock still serialises within a deal |
| **Postgres for tests** | portable binaries via `python tools/postgres.py start` | a server, or the compose file's |
| **Templates** | two synthetic masters, generated | the firm's real `.xlsx` masters, registered with input schemas |
| **Fixtures** | synthetic and masked | still synthetic and masked. **Client data never enters the repo** |
| **Container runtime** | none installed | podman, Rancher Desktop, or Docker Engine |

### What is the same

Python 3.12, `uv` and `uv.lock`, every registry and contract, the whole test suite, the
gate and the build state. The suite that passes here is the suite that has to pass there,
unchanged.

---

## 4. The three work repos

They are adapters to write, not dependencies to satisfy. Nothing in this repo imports
them, and the suite passes without them.

| Repo | Where it plugs in | What it has to satisfy |
|---|---|---|
| ShareFile connector | `ports/storage/sharefile.py` | `list` in a stable order, `read` or `INTAKE.UNREADABLE_FILE`, `stat` with a sha256 hash |
| Box connector | `ports/delivery/box.py` | `ensure_folder` idempotent, `put` that never silently overwrites, `version` |
| Model builder | `tools/write_template.py` | binding by **named range**, never by cell address |

Both adapter modules are registered and both refuse until wired, with
`SCOPE.ADAPTER_NOT_WIRED`. That is deliberate: selecting `sharefile` before the connector
exists must be a refusal somebody can read, not an unknown name and certainly not a
silent fallback to the local folder. Each module's docstring is the contract — read it
before writing the body, including the three things each connector must *not* do.

---

## 5. What is still owed

These are on P28 in `BUILD/PLAN.md` and need material that only exists at work. None of
them is a code change waiting to happen; each is evidence somebody has to produce.

1. **Timing normalization on real files.** Confirm the alignment on a real engagement and
   tailor the normalized table to the firm's Excel models. Deferred through P18–P25.
2. **The firm's chart of accounts.** Publish Chartwell's conventions as a new taxonomy
   version — never edit `coa-taxonomy@1.0.0` in place — measure the two-analyst baseline
   on 200 real line items, and rebuild `fixtures/skills/line-item-tagging` from it.
3. **Real add-backs.** An analyst confirms the add-backs proposed on a real engagement are
   defensible and that nothing material was auto-accepted; rebuild
   `fixtures/skills/ebitda-normalization`.
4. **The model builder.** Reconcile its named-range binding with `tools/write_template.py`
   and register the real templates with their input schemas under `templates/inputs/`.

Also open, from earlier phases:

- `CF_LBO_Model_v3` is bound at `corporate-finance/_group` with no master and no input
  schema. Preflight reports it as `CONFIG.TEMPLATE_UNREGISTERED`. Register it or unbind it.
- The human baseline override rate is unmeasured, so the analytics compare against
  "unmeasured" rather than against a number.
- The vault retention policy is a placeholder. Setting it is Risk / IT's decision.
- The materiality and auto-accept bars are per engagement and are the practice's to set.

---

## 6. Where things live

| | |
|---|---|
| The design of record | `docs/architecture.html` — edit here, commit, then `python tools/export_architecture.py` |
| Build state | `BUILD/STATE.md`, generated by `python tools/gate.py render` |
| Run artifacts | `runs/`, `artifacts/`, `vault/` — gitignored, they hold client data |
| Client material | `inbox/`, `outbox/` — gitignored |
| Governance drafts | `AA_SKILLS_INTAKE_ROOT`, outside the repo by default |
| Secrets | `.env`, gitignored, never leaves the machine it is on |

Every one of those paths is a variable. `.env.example` lists all twenty-seven the code
reads, and `tests/p28` derives that list from the source rather than trusting the file, so
a variable added without being documented fails the suite.
