# tools/

**What belongs here.** The deterministic tools a skill may propose calling, plus gate.py. All arithmetic in the system happens here.

**What does not.** No model calls, and nothing importable from skills/ - tools are reached through the Guarded Tool Runtime by name, never by import.
