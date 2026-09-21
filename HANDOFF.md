# Handoff

What changes on the work machine, and what does not.

The short version: **`.env` changes, and nothing else.** Everything that could have been
a fact about one laptop is behind a port or an environment variable, and this document is
the list. If something not on this list has to change to make the suite pass, that is a
defect in the portability claim, not a step to add here quietly.

**That claim is about the build, and there is one thing the *work* needs beyond it: an OCR
engine.** The suite passes without one and the system starts without one, so this is not a
portability exception - it is an operational dependency, the way Postgres is for the
production store. But every PDF this firm's clients send is a scan with no text layer, and
they send a lot of them. Without an engine the reader reports those pages rather than
inventing content for them, which is correct and also means most of the inbound path
arrives empty. **That failure looks like nothing happening**, which is the hardest kind to
diagnose on a first evening. `python -m uv run python tools/serve.py --check` says whether
it is working, and reports it as NOT INSTALLED rather than NOT WIRED - software to add,
not a join this build has left unmade.

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

Then the OCR engine, which is the one thing that is software rather than a setting:

```
python -m uv pip install pypdfium2 rapidocr-onnxruntime   # a wheel; no administrator
```

and set `AA_OCR_ADAPTER=rapidocr` in `.env`. `tesseract` is the alternative and reads as
well, but it needs the Tesseract executable on PATH, which on a managed laptop is a request
to somebody. Neither package is a project dependency: an ONNX runtime in every clone that
never reads a scan is a cost nobody asked for.

To check it took, and to measure it:

```
python -m uv run python tools/serve.py --check        # the "reading a scan" seam
python -m uv run pytest tests/p76 --ocr               # accuracy on a real public filing
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

> **Which runtime was actually used.** Podman 6.1.1 on Windows 11, 2026-09-05, client
> and server both 6.1.1, in a `podman machine` VM with 6 CPUs. Not Docker Desktop, which
> is not licensed here and is not a dependency. The image builds in about 80 seconds cold
> and 12 warm, and the whole suite passes inside it on the image's own interpreter with
> no host Python involved.
>
> Running it there is what proved portability, rather than the static checks alone. It
> found two real bugs and one bad test: file-type detection fell through to the host's
> MIME registry, which answers differently on Debian than on Windows; the Excel templates
> are generated rather than tracked, so a clean clone had none; and one test asserted the
> compute target had no image tag, which is true on a laptop and false in a container.
> All three are fixed, and P28 now carries the exit criterion that would have caught them.
>
> Three suites still say what they did not run, on every invocation and in words: Postgres
> conformance, the real Redis queue, and the container build itself when no runtime is on
> the path. That is deliberate. A claim nobody has executed is not evidence, and the run
> should say which kind it is.

---

## 2a. Before it is reachable by anybody else

Two things are true on this laptop that stop being acceptable the moment the system is on
a network the firm can reach, and both are phases rather than settings:

- **Nothing executes yet.** `graph.execute.StepRunner` has no production implementation, so
  a run released by intake sits with its lock taken. `python tools/serve.py --check` says
  so. Phases P34 and P35.
- **Neither surface has authentication**, and the `who` recorded against every change is a
  string the caller supplies. Bound to `127.0.0.1` that is correct; bound to anything else
  it makes the change log unverifiable. Phase P36, and it needs a decision from the firm
  about which identity provider before it can be built.

Neither is a surprise waiting to be found: both are on the open register, in
[`docs/USING.md`](docs/USING.md), and reported by the command that starts the system.

---

## 3. What is different about the work machine

Everything in this table is configuration. None of it is a code change.

| | This machine | The work machine |
|---|---|---|
| **Model key** | a personal key, or none — the fake adapter replays fixtures | the firm's `ANTHROPIC_API_KEY` |
| **Model access** | the Anthropic API directly | **the same.** Decided 2026-09-05: not Foundry. Hosting can move to Azure without model access moving with it — everything this build sends is GA on the first-party API, and the firm's account is already sanctioned for client data. Needs one thing from IT: egress from the container to `api.anthropic.com` |
| **Vault key** | generated locally, never committed | generated there, never copied |
| **Intake** | `AA_STORAGE_ADAPTER=local_folder`, a watched folder | `box` - written and tested against a replayed transport, never against a real tenant. Needs `BOX_CLIENT_ID`, `BOX_CLIENT_SECRET`, `BOX_USER_ID` and `AA_BOX_INBOX_FOLDER_ID`, and the Box app needs **Generate User Access Tokens** enabled. This is the read side because that is where work arrives: the client uploads to ShareFile, the files move to Box, and this reads Box |
| **Delivery** | `AA_DELIVERY_ADAPTER=local_folder`, `./outbox` | `box`, once the firm's connector is wired in |
| **State store** | SQLite at `AA_DB_URL=sqlite:///./runs/run_store.db` | Postgres — one URL, no other change |
| **Queue** | `in_process`, a bounded thread pool | `redis_rq` when runs outlive a process |
| **Reading a scan** | `AA_OCR_ADAPTER=none` — a scanned page is reported, not read | `tesseract`, with the Tesseract executable on PATH plus `pypdfium2` and `pytesseract`. Every PDF this firm's clients send is a scan, so without it most of the inbound path reads nothing. It must be a **local** engine: masking needs text, text from a scan needs OCR, and OCR by a vision model would put the unmasked client document in front of a model before masking could happen |
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
| ~~ShareFile connector~~ | `ports/storage/sharefile.py` | **Written in P89.** Not three env vars: an account with MFA cannot use a password grant, so a person presses Sign in once and everything after runs on a rotating refresh token. The app registration needs the local callback URL and offline access |
| Box connector | `ports/delivery/box.py` | `ensure_folder` idempotent, `put` that never silently overwrites, `version` |
| Model builder | `tools/write_template.py` | binding by **named range**, never by cell address |

Both adapter modules are registered and both refuse until wired, with
`SCOPE.ADAPTER_NOT_WIRED`. That is deliberate: selecting `sharefile` before the connector
exists must be a refusal somebody can read, not an unknown name and certainly not a
silent fallback to the local folder. Each module's docstring is the contract — read it
before writing the body, including the three things each connector must *not* do.

**Neither `ports/storage/box.py` nor `ports/storage/sharefile.py` is one of them any
more.** P87 wrote it, and it runs the same
conformance suite as the local folder through a transport that replays Box's documented
shapes. What that proves is the adapter's use of the API — pagination, ordering, the
sha256 it computes because Box only offers sha1, and the difference between a credential
nobody set and one the service refused. What it does not prove is that a real tenant
answers. So it reports as **NOT INSTALLED** rather than NOT WIRED: what is missing is
credentials on a machine, not a join this build left unmade. The first real evidence is
the connection test, pressed at work, which is what P93 is for.

Two things to expect the first time. Box refuses the token with `unauthorized_client`
when the app has not been granted **Generate User Access Tokens**; the adapter names that
setting in the refusal, because it is the most likely thing to be wrong. And ShareFile
refuses the login if the app registration does not list the callback this server actually
answers on - `http://127.0.0.1:8000/api/admin/sharefile/callback` - or does not ask for
offline access, in which case the login works for an hour and then stops.

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

**And from the fourth interview session (2026-09-18), which redefined what version 1 is
for** — it gathers and organises data into an *input-help workbook* the analyst types from,
and does not run the model:

5. **`Model Template - MASTER 2026` itself.** The input-help workbook has to match its
   input format, and the roll-forward's Excel half has to bind its named ranges. The tab
   strip and the Input, WS, IS and D structures are recorded in
   `knowledge/sessions/2026-09-18-1.md` from photographs; the named ranges are not knowable
   from a photograph. This is the largest single thing waiting, and everything about the
   repeat-client path waits behind it.
6. **The per-engagement request items.** The seven request-list sections are stable and are
   in `intake/request_list.py`; the numbered items inside them are written per engagement,
   and the only example in hand belongs to a client. There are many on the work computer.
7. **What OCR actually reads on a real scan.** `pytest tests/p76 --ocr` measures an engine
   against a public SEC filing, and it read 98.5%, 100% and 100% of the figures on three
   statement pages. Those pages were born digital and rendered to images - no skew, no
   scanner noise, no photocopy generation loss. **That is an upper bound, not a forecast.**
   The real number needs one hand-keyed engagement as ground truth (B-011).
8. **A local OCR engine, installed.** Confirmed possible on the work machine; see section 1.

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
