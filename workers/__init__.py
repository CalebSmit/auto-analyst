"""Workers: the bounded pool behind the Job Queue Port.

One module, `pool.py`. Several engagements at once, one run at a time within each; a run
becomes running when a worker holds it and not before; a worker that dies leaves a run
that resumes from the ledger. Which queue answers is configuration - nothing here names
an adapter.
"""

from workers.pool import PASS_KINDS, PassRunner, Placement, Pressure, Stranded, WorkerPool

__all__ = ["PASS_KINDS", "PassRunner", "Placement", "Pressure", "Stranded", "WorkerPool"]
