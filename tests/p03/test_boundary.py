"""Nothing outside ports/ imports a concrete adapter.

This is the test the whole ports arrangement rests on. Six interfaces are worth exactly
as much as their weakest import statement: one `from ports.storage.local_folder import
LocalFolderStorage` in the pipeline and moving to ShareFile stops being a config line
and becomes a search-and-replace with a deadline attached.

Enforced by walking the import graph rather than by asking people to remember, because
the failure is invisible - the code works perfectly until the day it has to be swapped.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

import ports

ROOT = Path(__file__).resolve().parents[2]

# Where the rule applies. tests/ is exempt: the conformance suite has to construct the
# adapters it tests, and the P03 tests are the one place that is legitimate.
SCANNED = [
    "harness", "graph", "privacy", "guards", "ops", "tools", "registries", "skills",
    "review", "intake",
]

ADAPTER_MODULES = {
    module for spec in ports.PORTS.values() for module in spec.adapters.values()
}


def python_files() -> list[Path]:
    found: list[Path] = []
    for package in SCANNED:
        found.extend(sorted((ROOT / package).rglob("*.py")))
    return found


def imported_modules(tree: ast.AST) -> set[str]:
    """Every module named by an import in this file, in dotted form.

    `from ports.storage.local_folder import X` and `import ports.storage.local_folder`
    both resolve to the same string, so one rule covers both spellings.
    """
    named: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            named.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            named.add(node.module)
            named.update(f"{node.module}.{alias.name}" for alias in node.names)
    return named


def test_there_is_something_to_scan() -> None:
    """A boundary test that silently scans nothing passes forever."""
    assert len(python_files()) >= 10


@pytest.mark.parametrize("path", python_files(), ids=lambda p: str(p.relative_to(ROOT)))
def test_no_module_outside_ports_imports_an_adapter(path: Path) -> None:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    offending = imported_modules(tree) & ADAPTER_MODULES
    assert not offending, (
        f"{path.relative_to(ROOT)} imports {sorted(offending)} directly. "
        f"Use ports.get_{'|'.join(sorted(ports.PORTS))}() and the Protocol instead - "
        f"a direct adapter import is what turns a config change into a refactor."
    )


@pytest.mark.parametrize("path", python_files(), ids=lambda p: str(p.relative_to(ROOT)))
def test_no_module_outside_ports_reaches_a_provider_sdk(path: Path) -> None:
    """The provider SDK lives behind the LLM port and nowhere else, because that is what
    makes one door to a model true - and one door is what lets the payload scan sit in
    exactly one place."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    named = imported_modules(tree)
    forbidden = {"anthropic", "boto3", "google.cloud.aiplatform", "openai"}
    assert not named & forbidden, (
        f"{path.relative_to(ROOT)} imports a provider SDK. It belongs behind ports/llm/."
    )


def test_every_registered_adapter_module_exists_and_builds() -> None:
    """An entry in the registry that names a module nobody wrote would make the
    boundary test scan for something that cannot be imported."""
    import importlib

    for port, spec in ports.PORTS.items():
        for adapter, module_path in spec.adapters.items():
            module = importlib.import_module(module_path)
            assert hasattr(module, "build"), f"{module_path} has no build()"
            assert module.build().name == adapter, f"{port}/{adapter} misnames itself"


def test_the_adapter_set_is_not_empty() -> None:
    assert len(ADAPTER_MODULES) >= 6
