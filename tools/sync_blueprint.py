"""Copy the working blueprint into docs/, and say whether it had drifted.

The repo copy is what exists after the handoff to the work machine, so it is the one
that matters. On this machine the working copy lives in OneDrive.
"""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "docs" / "architecture.html"
SRC = Path(
    "c:/Users/smitc/OneDrive/Documents/Chartwell/Automated Analyst/"
    "Chartwell_Automated_Analyst_Architecture.html"
)


def digest(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()[:12]


def main() -> int:
    if not SRC.exists():
        print(f"no working copy at {SRC} - docs/architecture.html is the only copy, which is fine")
        return 0
    before = digest(DEST) if DEST.exists() else None
    after = digest(SRC)
    if before == after:
        print(f"in sync ({after})")
        return 0
    shutil.copy2(SRC, DEST)
    print(f"updated docs/architecture.html  {before} -> {after}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
