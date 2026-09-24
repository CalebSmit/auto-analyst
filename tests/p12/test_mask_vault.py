"""The masker and the vault: stable tokens, one engagement at a time, encrypted at rest.

The first exit criterion - the same account masks to the same token across runs weeks
apart - is the one period alignment depends on, and it is tested by closing the vault
and opening the same database again as a different process would.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

import ports
from privacy.mask import ACCOUNT_NUMBER, Identifier, Masker
from privacy.payload_scan import PayloadScan
from privacy.vault import KEY_NAME, MaskVault, open_vault
from registries.errors import RegistryError
from tests.p12.conftest import ENGAGEMENT, HENDERSON, OTHER, TRIAL_BALANCE

# ------------------------------------------------------------------ masking


def test_declared_identifiers_are_substituted(masker: Masker) -> None:
    masked = masker.mask(TRIAL_BALANCE, ENGAGEMENT, HENDERSON, run_id="r1")
    for ident in HENDERSON:
        assert ident.value not in masked.text
        assert ident.value.lower() not in masked.text.lower()
    assert "[[CLIENT_1]]" in masked.text
    assert "[[PERSON_1]]" in masked.text
    assert "[[ACCOUNT_1]]" in masked.text and "[[ACCOUNT_2]]" in masked.text


def test_the_amounts_survive(masker: Masker) -> None:
    """Masking names, not numbers. The figures are the work."""
    masked = masker.mask(TRIAL_BALANCE, ENGAGEMENT, HENDERSON)
    for amount in ("48,231.00", "112,904.55", "36,000.00"):
        assert amount in masked.text


def test_an_account_number_nobody_declared_is_caught_by_shape(masker: Masker) -> None:
    masked = masker.mask(TRIAL_BALANCE, ENGAGEMENT, HENDERSON)
    assert "1234-5678-9012" not in masked.text
    assert "[[NUMBER_1]]" in masked.text
    assert "1234-5678-9012" in masked.substitutions


def test_the_number_pattern_does_not_eat_amounts_or_years() -> None:
    assert not ACCOUNT_NUMBER.search("FY2025 total 1,234,567.89")
    assert not ACCOUNT_NUMBER.search("48231.00")
    assert ACCOUNT_NUMBER.search("acct 12345678")
    assert ACCOUNT_NUMBER.search("IBAN 1234-5678-9012-3456")


def test_the_longest_identifier_wins(masker: Masker) -> None:
    """"Bob Henderson" is masked before "Bob" could split it into a token and a name."""
    idents = (Identifier("PERSON", "Bob"), Identifier("PERSON", "Bob Henderson"))
    masked = masker.mask("paid to Bob Henderson and to Bob", ENGAGEMENT, idents)
    assert masked.text == "paid to [[PERSON_1]] and to [[PERSON_2]]"


def test_masking_is_case_insensitive(masker: Masker) -> None:
    shouted = "HENDERSON MANUFACTURING / henderson manufacturing"
    masked = masker.mask(shouted, ENGAGEMENT, HENDERSON)
    assert masked.text == "[[CLIENT_1]] / [[CLIENT_1]]"


def test_the_masker_hands_the_scan_what_to_check(masker: Masker) -> None:
    """The masker and the scan agree by construction: the identifiers that must be
    absent and the tokens that must be present come from the same call."""
    masked = masker.mask(TRIAL_BALANCE, ENGAGEMENT, HENDERSON)
    result = PayloadScan().check(masked.text, masked.identifiers)
    assert result.passed
    assert set(masked.identifiers.expected_tokens) == set(masked.tokens)


def test_a_no_op_masker_would_be_caught_by_the_scan(masker: Masker) -> None:
    """P11's exit criterion, closed from this side: the identifier list the real masker
    produces, checked against the text it did *not* mask."""
    masked = masker.mask(TRIAL_BALANCE, ENGAGEMENT, HENDERSON)
    result = PayloadScan().check(TRIAL_BALANCE, masked.identifiers)
    assert not result.passed
    assert len(result.hits) == len(HENDERSON) + 1


def test_an_unknown_kind_is_refused() -> None:
    with pytest.raises(ValueError, match="token kind"):
        Identifier("SECRET", "x")


# ------------------------------------------------------------- stability


def test_the_same_account_masks_to_the_same_token_across_runs_weeks_apart(
    key: str, vault_url: str
) -> None:
    """The exit criterion. Two processes, weeks apart, over the same vault: the same
    token. Period alignment across runs depends on exactly this."""
    march = open_vault(ports.get_secrets(), vault_url)
    first = Masker(march).mask(TRIAL_BALANCE, ENGAGEMENT, HENDERSON, run_id="march")
    march.close()

    june = open_vault(ports.get_secrets(), vault_url)
    second = Masker(june).mask(
        "Bob's LLC Checking closing balance; Operating Account opened", ENGAGEMENT, HENDERSON,
        run_id="june",
    )
    june.close()

    assert first.substitutions["Bob's LLC Checking"] == second.substitutions["Bob's LLC Checking"]
    assert first.substitutions["Operating Account"] == second.substitutions["Operating Account"]


def test_a_new_value_gets_the_next_number_not_a_reused_one(
    masker: Masker, vault: MaskVault
) -> None:
    masker.mask("Bob's LLC Checking", ENGAGEMENT, HENDERSON)
    masker.mask("Operating Account", ENGAGEMENT, HENDERSON)
    later = masker.mask("Payroll Account", ENGAGEMENT, (Identifier("ACCOUNT", "Payroll Account"),))
    assert later.substitutions["Payroll Account"] == "[[ACCOUNT_3]]"
    assert vault.kinds_issued(ENGAGEMENT) == {"ACCOUNT": 3}


def test_case_and_whitespace_do_not_make_a_second_token(vault: MaskVault) -> None:
    a = vault.issue(ENGAGEMENT, "ACCOUNT", "Operating Account")
    b = vault.issue(ENGAGEMENT, "ACCOUNT", "  operating account ")
    assert a == b


# ------------------------------------------------------------ per engagement


def test_the_same_value_under_two_engagements_is_two_tokens_two_entries(vault: MaskVault) -> None:
    """Scoped per engagement. The number happens to match - each starts at 1 - and the
    entries do not: resolving under the other engagement finds nothing."""
    a = vault.issue(ENGAGEMENT, "PERSON", "Bob Henderson")
    b = vault.issue(OTHER, "PERSON", "Bob Henderson")
    assert a == b == "[[PERSON_1]]"
    assert vault.resolve(ENGAGEMENT, a) == "Bob Henderson"
    assert vault.resolve(OTHER, b) == "Bob Henderson"
    assert vault.issued(ENGAGEMENT) == vault.issued(OTHER) == frozenset({"[[PERSON_1]]"})


def test_a_token_is_resolved_only_under_its_own_engagement(vault: MaskVault) -> None:
    """The cross-client boundary is a WHERE clause, not a check somebody remembers."""
    token = vault.issue(ENGAGEMENT, "ACCOUNT", "Bob's LLC Checking")
    assert vault.resolve(ENGAGEMENT, token) == "Bob's LLC Checking"
    assert vault.resolve(OTHER, token) is None


def test_the_value_hash_is_salted_by_engagement(vault: MaskVault, vault_url: str) -> None:
    """One vault dump reveals no cross-engagement equalities."""
    vault.issue(ENGAGEMENT, "PERSON", "Bob Henderson")
    vault.issue(OTHER, "PERSON", "Bob Henderson")
    with create_engine(vault_url).connect() as conn:
        hashes = [r[0] for r in conn.execute(text("SELECT value_hash FROM vault")).fetchall()]
    assert len(set(hashes)) == 2


# ------------------------------------------------------- encrypted at rest


def test_the_plaintext_is_not_in_the_database(vault: MaskVault, vault_url: str) -> None:
    vault.issue(ENGAGEMENT, "PERSON", "Bob Henderson")
    with create_engine(vault_url).connect() as conn:
        rows = conn.execute(text("SELECT ciphertext, value_hash FROM vault")).fetchall()
    for ciphertext, value_hash in rows:
        assert "Henderson" not in ciphertext
        assert "Henderson" not in value_hash
        assert "Bob" not in ciphertext


def test_a_changed_key_cannot_read_the_vault(
    vault: MaskVault, vault_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Losing the key loses every token it protects - and says so, rather than returning
    garbage that looks like a name."""
    from cryptography.fernet import Fernet

    token = vault.issue(ENGAGEMENT, "PERSON", "Bob Henderson")
    monkeypatch.setenv(KEY_NAME, Fernet.generate_key().decode())
    ports.reset()
    other_key = open_vault(ports.get_secrets(), vault_url)
    with pytest.raises(RegistryError) as raised:
        other_key.resolve(ENGAGEMENT, token)
    assert raised.value.diagnostic.code == "PRIVACY.VAULT_UNAVAILABLE"


def test_no_key_no_vault(
    vault_url: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A run does not proceed on unmasked payloads because the vault was down.

    The secrets adapter reads **`.env` as well as the environment**, so deleting the
    variable is not enough to describe a machine with no key - the file still supplies one.
    This passed for the whole build's life only because no machine had ever put
    `AA_VAULT_KEY` in `.env`; the first one that did, on 2026-09-22, turned it red. The
    environment was deciding the result, which is the same defect `tests/p75` carried and
    the third place it has been found.

    So the adapter is pointed at an empty file *and* the variable is unset, which is the
    only way to say "there is no key here" to something that reads two places.
    """
    from ports.secrets.dotenv import DotenvSecrets

    monkeypatch.delenv(KEY_NAME, raising=False)
    ports.reset()
    nothing = DotenvSecrets(env_file=tmp_path / "absent.env")
    with pytest.raises(RegistryError) as raised:
        open_vault(nothing, vault_url)
    assert raised.value.diagnostic.code == "PRIVACY.VAULT_UNAVAILABLE"
    assert "generate_key" in str(raised.value)


def test_the_key_comes_through_the_secrets_port(vault: MaskVault) -> None:
    """Not from os.environ directly, and not as a parameter. The port is the one door
    for credentials, the way the model door is for models.

    Walked rather than grepped. This asserted `"os.environ.get(KEY_NAME" not in source`,
    which blocks exactly one spelling: `os.getenv(KEY_NAME)` and `os.environ[KEY_NAME]`
    both sail through, and the string it requires survives in a docstring."""
    import ast
    import inspect

    from privacy import vault as module

    source = inspect.getsource(module)

    def reads_the_environment(node: ast.AST) -> bool:
        """`os.environ.get(x)`, `os.environ[x]` or `os.getenv(x)`, however spelled."""
        if isinstance(node, ast.Subscript):
            target = node.value
            return isinstance(target, ast.Attribute) and target.attr == "environ"
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute) and func.attr == "getenv":
                return True
            return (
                isinstance(func, ast.Attribute)
                and func.attr == "get"
                and isinstance(func.value, ast.Attribute)
                and func.value.attr == "environ"
            )
        return False

    def names_the_key(node: ast.AST) -> bool:
        """Whether `KEY_NAME` is what is being looked up. The module may read a *setting*
        from the environment - the retention window is one - and that is not what this
        invariant is about: the credential is the port's, and nothing else is."""
        return any(
            isinstance(inner, ast.Name) and inner.id == "KEY_NAME" for inner in ast.walk(node)
        )

    for node in ast.walk(ast.parse(source)):
        if reads_the_environment(node) and names_the_key(node):
            raise AssertionError(f"privacy/vault.py reads the key from os: {ast.dump(node)}")
    assert "secrets.get(KEY_NAME)" in source, "and it does go through the port"
    del vault

def test_retention_is_a_field_on_every_entry(vault: MaskVault, vault_url: str) -> None:
    vault.issue(ENGAGEMENT, "PERSON", "Bob Henderson")
    with create_engine(vault_url).connect() as conn:
        until = conn.execute(text("SELECT retention_until FROM vault")).scalar_one()
    assert until.endswith("Z")
    assert datetime.fromisoformat(until.replace("Z", "+00:00")) > datetime.now(tz=UTC)


def test_expired_entries_are_purged_and_cannot_resolve(key: str, vault_url: str) -> None:
    short = open_vault(ports.get_secrets(), vault_url, retention_days=1)
    token = short.issue(ENGAGEMENT, "PERSON", "Bob Henderson")
    assert short.resolve(ENGAGEMENT, token) == "Bob Henderson"

    purged = short.purge_expired(now=datetime.now(tz=UTC) + timedelta(days=2))
    assert purged == 1
    assert short.resolve(ENGAGEMENT, token) is None
    assert short.issued(ENGAGEMENT) == frozenset()
    short.close()


def test_the_default_retention_is_a_stated_placeholder() -> None:
    from privacy.vault import DEFAULT_RETENTION_DAYS

    assert DEFAULT_RETENTION_DAYS == 730
    source = open(  # noqa: PTH123, SIM115 - a one-line read of our own module
        __import__("privacy.vault", fromlist=["x"]).__file__, encoding="utf-8"
    ).read()
    assert "Risk / IT" in source
