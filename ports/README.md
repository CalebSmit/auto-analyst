# ports/

**What belongs here.** Six interfaces and their adapters: storage, delivery, secrets,
queue, llm, compute. Each port has a Protocol and a conformance suite every adapter must
pass.

**What does not.** Nothing outside this package imports a concrete adapter. Import
`ports.get_storage()` and the Protocol; never `ports.storage.local_folder`.

## The rule, and why it is a test

Six interfaces are worth exactly as much as their weakest import statement. One
`from ports.storage.local_folder import LocalFolderStorage` in the pipeline and moving to
ShareFile stops being a config line and becomes a search-and-replace with a deadline
attached — and nothing looks wrong until that day.

So `tests/p03/test_boundary.py` walks the import graph of every package outside `ports/`
and fails on a direct adapter import, or on any module reaching a provider SDK. `tests/`
is exempt, because the conformance suite has to construct the adapters it tests.

## Choosing an adapter

Configuration, read fresh on every call:

| Port | Variable | Default | Adapters |
|---|---|---|---|
| storage | `AA_STORAGE_ADAPTER` | `local_folder` | local_folder |
| delivery | `AA_DELIVERY_ADAPTER` | `local_folder` | local_folder |
| secrets | `AA_SECRETS_ADAPTER` | `dotenv` | dotenv |
| queue | `AA_QUEUE_ADAPTER` | `in_process` | in_process |
| llm | `AA_LLM_ADAPTER` | `fake` | fake, anthropic_messages |
| compute | `AA_COMPUTE_ADAPTER` | `local_process` | local_process |

An unknown name is `SCOPE.UNKNOWN_ADAPTER`, never a silent fallback to the default: a run
reading from somewhere nobody chose is the failure this arrangement exists to prevent.

The LLM default is the **fake** adapter, which replays recorded fixtures. Phases 4–10
build the entire engine against it, so the suite needs no API key and costs nothing —
a test suite that costs money per run is a test suite people stop running. A run that
means to reach a model says so.

## Two that are not obvious

**compute** is a port rather than an assumption. It reports where a run executed (into
the manifest) and how much concurrency exists (to the worker pool). Both would otherwise
be places where "we always run locally" quietly hard-codes itself.

**secrets** answers `has()` without producing the value, so preflight and config-audit
code can report "the Box credential is missing" with no code path that could print one
that is not. `Secret` redacts itself in `repr` and in f-strings — the two places a
credential reaches a log line by accident.
