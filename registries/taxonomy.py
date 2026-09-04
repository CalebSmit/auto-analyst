"""The Chart of Accounts Taxonomy: the firm's categories, versioned.

A versioned reference document. The version a run uses is pinned in its manifest and
checked by the Policy Gate (`pinned_versions_only`) on every `chart_of_accounts_lookup`
call, so the categories a step tagged against are the categories the record says it did.

This is the loader - a registry over data under taxonomy/, like the others in this
package. The tool that reaches it through the Guarded Tool Runtime is `tools/coa.py`;
the tagging procedure reads it here directly to build the payload, because a procedure
is code and the payload is built before any tool is bound. Pure Python, no model.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from registries.errors import UNKNOWN_TAXONOMY, RegistryError, diagnose

__all__ = [
    "Category",
    "Taxonomy",
    "TAXONOMY_DIR",
    "UNMAPPED",
    "load_taxonomy",
    "taxonomy_versions",
]

TAXONOMY_DIR = Path(__file__).resolve().parents[1] / "taxonomy"
UNMAPPED = "unmapped"
STATEMENTS = ("IS", "BS", "NA")
VERSION_KEY = re.compile(r"^coa-taxonomy@(\d+\.\d+\.\d+)$")


@dataclass(frozen=True)
class Category:
    id: str
    label: str
    statement: str
    section: str
    excluded_from_al: bool
    include_in_nwc: bool
    cues: tuple[str, ...]
    note: str = ""

    def as_row(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "statement": self.statement,
            "section": self.section,
            "excluded_from_al": self.excluded_from_al,
            "include_in_nwc": self.include_in_nwc,
            "cues": list(self.cues),
            **({"note": self.note} if self.note else {}),
        }


@dataclass(frozen=True)
class Taxonomy:
    version: str
    """`coa-taxonomy@1.0.0` - the key a run pins and the gate checks."""
    title: str
    effective: str
    rules: dict[str, str]
    categories: dict[str, Category]

    def get(self, category_id: str) -> Category | None:
        return self.categories.get(category_id)

    def __contains__(self, category_id: object) -> bool:
        return category_id in self.categories

    def rows(self, ids: Iterable[str] | None = None) -> list[dict[str, Any]]:
        if ids is None:
            return [c.as_row() for c in self.categories.values()]
        return [self.categories[i].as_row() for i in ids if i in self.categories]


def taxonomy_versions(folder: Path = TAXONOMY_DIR) -> tuple[str, ...]:
    """Every version on disk, as `coa-taxonomy@x.y.z`. None of them is 'the' taxonomy;
    a run names one."""
    found = []
    for path in sorted(folder.glob("coa-taxonomy@*.yaml")):
        key = path.name[: -len(".yaml")]
        if VERSION_KEY.match(key):
            found.append(key)
    return tuple(found)


@lru_cache(maxsize=8)
def _load(path: Path) -> Taxonomy:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    key = path.name[: -len(".yaml")]
    if f"coa-taxonomy@{raw.get('version')}" != key:
        raise RegistryError(
            diagnose(
                UNKNOWN_TAXONOMY,
                f"{path.name} says version {raw.get('version')!r}; the file name says {key}",
                locator=str(path),
            )
        )
    categories: dict[str, Category] = {}
    for entry in raw["categories"]:
        category = Category(
            id=str(entry["id"]),
            label=str(entry["label"]),
            statement=str(entry["statement"]),
            section=str(entry["section"]),
            excluded_from_al=bool(entry["excluded_from_al"]),
            include_in_nwc=bool(entry["include_in_nwc"]),
            cues=tuple(str(c) for c in entry.get("cues", ())),
            note=str(entry.get("note", "")).strip(),
        )
        if category.id in categories:
            raise RegistryError(
                diagnose(UNKNOWN_TAXONOMY, f"{key} lists {category.id} twice", locator=str(path))
            )
        if category.statement not in STATEMENTS:
            raise RegistryError(
                diagnose(
                    UNKNOWN_TAXONOMY,
                    f"{key}: {category.id} is on statement {category.statement!r}",
                    locator=str(path),
                )
            )
        if category.statement == "IS" and (category.excluded_from_al or category.include_in_nwc):
            raise RegistryError(
                diagnose(
                    UNKNOWN_TAXONOMY,
                    f"{key}: {category.id} is an income statement line with a balance sheet flag",
                    locator=str(path),
                )
            )
        categories[category.id] = category
    if UNMAPPED not in categories:
        raise RegistryError(
            diagnose(
                UNKNOWN_TAXONOMY,
                f"{key} has no {UNMAPPED!r} category; a taxonomy without an honest answer "
                f"forces a guess",
                locator=str(path),
            )
        )
    return Taxonomy(
        version=key,
        title=str(raw.get("title", key)),
        effective=str(raw.get("effective", "")),
        rules={str(k): str(v).strip() for k, v in (raw.get("rules") or {}).items()},
        categories=categories,
    )


def load_taxonomy(version: str, folder: Path = TAXONOMY_DIR) -> Taxonomy:
    """The taxonomy at exactly this version. There is no 'latest'."""
    if not VERSION_KEY.match(version):
        raise RegistryError(
            diagnose(
                UNKNOWN_TAXONOMY,
                f"{version!r} is not a taxonomy version key (coa-taxonomy@x.y.z)",
                locator=str(folder),
            )
        )
    path = folder / f"{version}.yaml"
    if not path.is_file():
        have = ", ".join(taxonomy_versions(folder)) or "none"
        raise RegistryError(
            diagnose(
                UNKNOWN_TAXONOMY,
                f"{version} is not on disk (have: {have})",
                locator=str(path),
            )
        )
    return _load(path)
