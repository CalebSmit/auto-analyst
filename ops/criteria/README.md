# ops/criteria/

The acceptance criteria a run is scored against, one file per version.

`run_criteria@1.0.0.yaml` is the blueprint's ten-row scorecard table as data: an id, the
words, the guard events it reads, and how many failures the bar tolerates (none, on every
row). `ops/scorecard.py` measures each id from the record and pins the current version;
the manifest records which version judged the run.

**Never edit a published version.** A changed bar is a new file beside the old one. The
old one stays for as long as any manifest cites it, which is the only way "what counted
as working" stays answerable for a run from six months ago.

A version that names a criterion the scorecard cannot measure is refused at load. The
alternative - skipping it - would let a criterion quietly stop being applied.
