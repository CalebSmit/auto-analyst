# workers/

**What belongs here.** The Worker Pool: `pool.py`. Runs go to the Job Queue Port as
data and a bounded pool behind the port executes them, several engagements at once.

**What does not.** Nothing that decides what a run does. The pool runs passes; the
executor, the harness and the guards decide everything about them. And nothing that
names a queue adapter - `AA_QUEUE_ADAPTER` chooses, and the import-boundary test in
`tests/p03` fails on a direct import.

## Two bounds, one pool

Cross-engagement concurrency comes from the Compute Target: `max_parallelism` is asked
for, never assumed, and the in-process adapter's thread pool and the number of `rq
worker` processes are both sized by it. Within one engagement the Engagement Lock still
serialises: only a lock holder is ever handed to a worker, and the in-process adapter
refuses to run two jobs of one engagement together even if asked.

## Running means a worker holds it

The blueprint's run states say *queued* is "nothing is allocated; position is visible"
and *running* is "a worker holds it". P25 made the code say the same: the lock grants
and the review surface re-enqueues, but neither moves a run to running any more. The
executor's pass does, as its first act. So a run with the lock and no free worker shows
as queued with a position, its wall clock has not started, and the stall detector does
not mistake a starved pool for a silent run.

## After every pass, the lock is released

A pass ends four ways - finished, blocked on a person, quarantined, or the worker died -
and the first three hold no process afterwards, so none of them holds the lock. The next
run queued on that engagement takes it and is enqueued in turn. A blocked run comes back
through the Review Surface's `run.resume` job, which the pool handles like any pass.

## A worker that dies

The in-process adapter records a thread that died as `worker lost:`; RQ moves a job
whose worker vanished to its failed registry. `WorkerPool.stranded()` reads both the
record (a step started and never ended) and the port (a job that ended without a
result), raises `worker.lost` once with `PROCESS.WORKER_LOST`, and `resume()` retries the
job under the same id. The executor's ledger does the rest: every completed step is
satisfied from it, and the lost step is re-attempted as attempt two.

    python -m uv run pytest tests/p25 -q          # in-process, and Redis over a fake
    python -m uv run pytest tests/p03 tests/p25 -q --redis   # the RQ adapter for real
