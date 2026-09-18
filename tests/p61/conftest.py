"""Fixtures for P61: an admin console with a recipe register and a board of its own.

Nothing here touches `recipes/registered.yaml` in the repo. An approval records that
somebody approved a workflow, and a test that wrote one into the firm's own register would
be recording a decision nobody made - the same reason P33's fixtures are arranged this way.
"""

from __future__ import annotations

from tests.p33.conftest import (  # noqa: F401
    blobs,
    board,
    recipes,
    record,
    register,
    root,
)
