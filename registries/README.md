# registries/

**What belongs here.** The loaders for the three registries the blueprint names —
contracts, constraints and (from P07) diagnostics. Each one reads its declarative
source, pins a version, and refuses anything it was not told about. Nothing here knows
what EBITDA is.

**What does not.** No schema content and no predicate content — those live in
`contracts/` and `constraints/` as data. No evaluation either: this package hands the
Policy Gate its predicates, it does not decide anything.

## Why this directory exists

The blueprint's repo listing places the *data* — `contracts/figure.schema.json`,
`constraints/constraints.yaml` — and never names a home for the code that loads it.
`contracts/` cannot hold it (a schema that needs code to be understood is not a
contract), and `harness/`, `graph/`, `guards/` and `ops/` are all wrong for a thing
that all four of them read. So the three registries got their own package, which is
what the blueprint calls them anyway: "the third registry ... alongside the contracts
and constraints".

Recorded as a deliberate divergence in [AMENDMENTS.md](../BUILD/AMENDMENTS.md).

## What "pins a version" means here

`ContractRegistry.get("figure")` is refused. `get("figure@1.0.0")` resolves.
`get("figure@9.9.9")` is refused. A schema file sitting in `contracts/` that
`contracts/registry.yaml` does not list is an error, and so is an index entry with no
file behind it. "Whatever is in the folder" is not a version, and a run that cannot
name the contract version it validated against cannot be reproduced.
