# taxonomy/

**What belongs here.** The firm chart-of-accounts taxonomy, one file per version:
`coa-taxonomy@<version>.yaml`. The canonical category list, the default A/L and NWC
flags per category, and the rules in prose. Data rather than prompt text, so the people
who own the convention can review and version it without touching a skill.

**What does not.** Anything client-specific. A client's chart of accounts is intake; this
is the firm's map of where any client's lines land.

## How it is reached

Through `chart_of_accounts_lookup` (`tools/coa.py`), by name, through the Guarded Tool
Runtime. The run pins a version in its manifest; the Policy Gate refuses a lookup that
asks for any other. The tagging procedure loads the pinned version once per step and
puts the category list in the payload, so the model sees exactly the version the run
recorded - not whichever file happens to be newest.

## Changing it

Bump the version and add a file; never edit one in place. A recorded run cites its
version, and a version that changes underneath it makes the manifest a lie. Old
versions stay for as long as any run cites them. The synthetic defaults in 1.0.0 are
replaced by Chartwell's own conventions at the P24 pilot, as 1.1.0 or 2.0.0.
