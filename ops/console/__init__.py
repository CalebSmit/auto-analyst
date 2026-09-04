"""The Ops Console: the always-on dashboard. What is running, right now.

A **reader** of the event bus and the run store. It holds no pipeline state and nothing
depends on it: console down, runs continue; run stalled, the console says so. Getting
that dependency direction right is what makes it safe to leave running.

* `trace.py` - the reducer that paints the graph from the event stream; live and replay
  are the same fold.
* `app.py`   - FastAPI: the JSON surfaces, server-sent events per run, and the one-page
  browser client that subscribes to them.
"""

from ops.console.app import Console, create_app
from ops.console.trace import NodeState, Trace, TraceReducer, state_for

__all__ = ["Console", "NodeState", "Trace", "TraceReducer", "create_app", "state_for"]
