# privacy/

**What belongs here.** mask.py, vault.py, unmask.py, verify.py, payload_scan.py. All
deterministic Python.

**What does not.** No model call, ever. Re-identification is the one step where a
plausible mistake is indistinguishable from correctness, and `tests/p12` walks the import
graph to prove nothing here reaches a port to a model.

## Why masking exists at all

Not as a security boundary - the firm's Claude account is sanctioned for client data.
Two other reasons, both of which survive that. **Cross-client isolation:** a token issued
under one engagement resolves under no other, and the boundary is a `WHERE` clause rather
than a check somebody remembers. **Precedent portability:** the Precedent Store can reuse
one client's approved decisions on another's engagement only if the descriptions in it
name no one.

## The vault

The only store in the system that can re-identify anything. Scoped per engagement,
encrypted at rest with a key from the Secrets Port (`AA_VAULT_KEY`), two edges only: the
masker writes, the unmasker reads. Invariant 1 in `graph/architecture_assertions.py`
proves no model node has an edge to it. The strongest isolation available is absence.

**Tokens are stable.** The same account under the same engagement gets the same token
across every file and every run, for as long as the entry is retained - period alignment
weeks apart depends on it. Achieved by looking up a keyed hash of the plaintext before
issuing, so the lookup never decrypts anything and a vault dump reveals no
cross-engagement equalities.

**Retention is a field, not yet a policy.** `retention_until` and `purge_expired` exist;
the number is a placeholder until Risk / IT set it, which the blueprint lists as their
decision before phase 1.

## The three assertions

`verify.py` is a separate node from the masker on purpose - a masker that silently no-ops
and a checker that silently passes are the same bug, and splitting them makes it
findable. Every token in the input resolved; no token survives into the output; no token
resolved that was never issued for this engagement. The third is the one that matters:
a token resolving to another client's value is the failure this whole band exists to
prevent.

## Setting up

    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

into `.env` as `AA_VAULT_KEY`. It never leaves this machine, and losing it loses every
token it protects - the vault says so rather than returning garbage that looks like a name.
