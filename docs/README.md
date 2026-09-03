# docs/

**What belongs here.** The architecture blueprint that travels with the repo, and the
original project-context note it grew out of. `architecture.html` is a self-contained
single file: 118 nodes, 240 edges, 25 executable invariants, 67 failure modes. Open it in
a browser; it needs nothing else and makes no network requests.

**What does not.** Generated documentation, and anything that duplicates BUILD/. The plan
lives in BUILD/; this is the design the plan is built from.

## Keeping it current

On this machine the working copy is at:

    c:/Users/smitc/OneDrive/Documents/Chartwell/Automated Analyst/Chartwell_Automated_Analyst_Architecture.html

`python tools/sync_blueprint.py` copies it here and reports whether it had drifted. The
copy in this directory is the one that exists on the work machine, so it is the one that
matters after the handoff.
