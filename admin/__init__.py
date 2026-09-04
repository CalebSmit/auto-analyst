"""The Admin tab: where a person actually sets this thing up.

Three nodes from the blueprint, one module each:

* `preflight.py` - Setup Preflight. Ten checks over a proposed or live configuration,
  each failure a standard diagnostic with the owner set to `config`. A failing check
  blocks activation of that engagement rather than failing later inside a run.
* `console.py`  - the Admin Console. Reads and writes the Configuration Store and the
  Active Project Roster, and every write lands in the Config Change Log with who, what,
  when and why. What an admin may and may not change is enforced here, not documented.
* `app.py`      - the FastAPI surface over the console.

The package cannot reach a skill definition, a guard, the mask vault or the release
gate: it imports none of them, and a test keeps it that way. Configuration writes the
engagement record; guards read the run (invariant 23).
"""

from admin.console import AdminConsole, AdminRefused
from admin.preflight import Check, Failure, Preflight, PreflightReport

__all__ = [
    "AdminConsole",
    "AdminRefused",
    "Check",
    "Failure",
    "Preflight",
    "PreflightReport",
]
