"""Fixtures for C58.

The vault chain is P12's and is reused rather than rebuilt: the key comes through the
Secrets Port from the environment the way it does in a run, because passing it in as a
parameter would be a second door.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from cryptography.fernet import Fernet

import ports
from privacy.mask import Masker
from privacy.vault import KEY_NAME, MaskVault, open_vault


@pytest.fixture
def key(monkeypatch: pytest.MonkeyPatch) -> str:
    fresh = Fernet.generate_key().decode()
    monkeypatch.setenv(KEY_NAME, fresh)
    ports.reset()
    return fresh


@pytest.fixture
def vault(key: str, tmp_path: Path) -> Iterator[MaskVault]:
    opened = open_vault(ports.get_secrets(), f"sqlite:///{(tmp_path / 'vault.db').as_posix()}")
    yield opened
    opened.close()


@pytest.fixture
def masker(vault: MaskVault) -> Masker:
    return Masker(vault)
