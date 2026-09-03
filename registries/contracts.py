"""The Contract Registry: load the schemas, pin their versions, refuse the rest.

Every typed object that crosses an edge is validated here — the figure envelope, one
output schema per skill, events, the run manifest, the engagement profile and the one
intake document type that carries a contract. Schema versions are pinned per run and
recorded in the plan hash, which is only meaningful if the registry can refuse a
version it was not told about. That refusal is the whole feature.

References between schemas resolve from the loaded set, never over the network: a
contract that needs the internet to be understood is not a contract either.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator
from jsonschema import exceptions as js_exceptions
from referencing import Registry, Resource

from registries.errors import (
    CONTRACT_INDEX_INVALID,
    FABRICATED_SOURCE,
    NO_PROVENANCE,
    SCHEMA_INVALID,
    UNKNOWN_CONTRACT,
    ContractViolation,
    Diagnostic,
    RegistryError,
    diagnose,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
CONTRACTS_DIR = REPO_ROOT / "contracts"
INDEX_FILE = CONTRACTS_DIR / "registry.yaml"

# The fields that make a figure sourced. A failure touching any of them is a provenance
# failure and reads as one, rather than as a generic shape complaint.
PROVENANCE_FIELDS = frozenset({"source_id", "locator", "source_version"})


@dataclass(frozen=True)
class ContractEntry:
    """One registered contract: what it is, where it lives, and at which version."""

    id: str
    version: str
    file: str
    kind: str
    note: str = ""

    @property
    def key(self) -> str:
        """The pinned name a compiled step and the run manifest both carry."""
        return f"{self.id}@{self.version}"


@dataclass(frozen=True)
class IntakeDocumentType:
    """A document type intake may bind an arriving file to.

    Declared centrally so a skill can require one as an input and so the binder has a
    closed vocabulary. A file that binds to nothing is never processed to figure out
    later what it is.
    """

    id: str
    contract: str | None
    supplied_by: str
    privacy_class: str
    required_by: tuple[str, ...]


class ContractRegistry:
    """The loaded, version-pinned set of contracts.

    Construct it with :meth:`load`. Ask for a schema by its pinned key — ``figure@1.0.0``,
    ``skills/ebitda-normalization@1.0.0`` — and nothing else resolves.
    """

    def __init__(
        self,
        version: str,
        base_uri: str,
        entries: dict[str, ContractEntry],
        schemas: dict[str, dict[str, Any]],
        intake_types: dict[str, IntakeDocumentType],
    ) -> None:
        self.version = version
        self.base_uri = base_uri
        self._entries = entries
        self._schemas = schemas
        self._intake_types = intake_types
        self._refs = Registry().with_resources(  # type: ignore[var-annotated]
            (schema["$id"], Resource.from_contents(schema)) for schema in schemas.values()
        )
        self._validators: dict[str, Draft202012Validator] = {}

    # ------------------------------------------------------------------ loading

    @classmethod
    def load(cls, index_file: Path = INDEX_FILE) -> ContractRegistry:
        """Read the index, then read exactly what it lists and nothing else."""
        index = yaml.safe_load(index_file.read_text(encoding="utf-8"))
        root = index_file.parent
        base_uri = index["base_uri"]

        entries: dict[str, ContractEntry] = {}
        schemas: dict[str, dict[str, Any]] = {}
        listed_files: set[Path] = set()

        for row in index["contracts"]:
            entry = ContractEntry(
                id=row["id"],
                version=row["version"],
                file=row["file"],
                kind=row["kind"],
                note=row.get("note", ""),
            )
            if entry.key in entries:
                raise RegistryError(
                    diagnose(CONTRACT_INDEX_INVALID, f"{entry.key} is listed twice")
                )
            path = root / entry.file
            if not path.is_file():
                raise RegistryError(
                    diagnose(
                        CONTRACT_INDEX_INVALID,
                        f"{entry.key} lists a missing file {entry.file}",
                    )
                )
            schema = json.loads(path.read_text(encoding="utf-8"))
            expected_id = f"{base_uri}{entry.id}@{entry.version}"
            if schema.get("$id") != expected_id:
                raise RegistryError(
                    diagnose(
                        CONTRACT_INDEX_INVALID,
                        f"{entry.file} declares $id {schema.get('$id')!r}, "
                        f"index says {expected_id!r}",
                    )
                )
            entries[entry.key] = entry
            schemas[entry.key] = schema
            listed_files.add(path.resolve())

        # A schema on disk that the index does not list is not a contract. Left
        # unchecked, this is how a second copy of the envelope quietly appears.
        for path in sorted(root.rglob("*.schema.json")):
            if path.resolve() not in listed_files:
                raise RegistryError(
                    diagnose(
                        CONTRACT_INDEX_INVALID,
                        f"{path.relative_to(root).as_posix()} is on disk but not in the index",
                    )
                )

        intake_types = {
            row["id"]: IntakeDocumentType(
                id=row["id"],
                contract=row.get("contract"),
                supplied_by=row["supplied_by"],
                privacy_class=row["privacy_class"],
                required_by=tuple(row.get("required_by") or ()),
            )
            for row in index.get("intake_document_types") or ()
        }
        for doc_type in intake_types.values():
            if doc_type.contract is not None and doc_type.contract not in entries:
                raise RegistryError(
                    diagnose(
                        CONTRACT_INDEX_INVALID,
                        f"intake type {doc_type.id} cites unregistered contract "
                        f"{doc_type.contract}",
                    )
                )

        return cls(index["version"], base_uri, entries, schemas, intake_types)

    # ------------------------------------------------------------------ lookup

    def ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._entries))

    def entries(self) -> tuple[ContractEntry, ...]:
        return tuple(self._entries[k] for k in self.ids())

    def entry(self, key: str) -> ContractEntry:
        self._require_pinned(key)
        return self._entries[key]

    def get(self, key: str) -> dict[str, Any]:
        """Return a schema by pinned key. An unpinned or unknown key is refused."""
        self._require_pinned(key)
        return self._schemas[key]

    def skill_output_key(self, skill: str, version: str = "1.0.0") -> str:
        return f"skills/{skill}@{version}"

    def intake_document_types(self) -> tuple[IntakeDocumentType, ...]:
        return tuple(self._intake_types[k] for k in sorted(self._intake_types))

    def intake_document_type(self, doc_type_id: str) -> IntakeDocumentType:
        if doc_type_id not in self._intake_types:
            raise RegistryError(
                diagnose(
                    UNKNOWN_CONTRACT,
                    f"{doc_type_id!r} is not a declared intake document type",
                )
            )
        return self._intake_types[doc_type_id]

    def _require_pinned(self, key: str) -> None:
        if "@" not in key:
            raise RegistryError(
                diagnose(
                    UNKNOWN_CONTRACT,
                    f"{key!r} names no version. Ask for {key}@<version> - the registry does "
                    "not pick one for you.",
                )
            )
        if key not in self._entries:
            raise RegistryError(
                diagnose(UNKNOWN_CONTRACT, f"{key!r} is not registered in contracts/registry.yaml")
            )

    # ------------------------------------------------------------------ validation

    def validator(self, key: str) -> Draft202012Validator:
        self._require_pinned(key)
        if key not in self._validators:
            self._validators[key] = Draft202012Validator(self._schemas[key], registry=self._refs)
        return self._validators[key]

    def check(self, key: str, instance: object) -> tuple[Diagnostic, ...]:
        """Validate and return diagnostics. Empty means it passed."""
        errors = sorted(
            self.validator(key).iter_errors(instance), key=lambda e: list(e.absolute_path)
        )
        found: list[Diagnostic] = []
        for error in _flatten(errors):
            found.append(
                diagnose(
                    _classify(error),
                    detail=error.message,
                    locator=_locator(error) or key,
                )
            )
        return tuple(_dedupe(found))

    def validate(self, key: str, instance: object) -> None:
        """Validate, or raise the most specific violation found."""
        found = self.check(key, instance)
        if found:
            raise ContractViolation(_worst(found), found)

    def self_check(self) -> tuple[str, ...]:
        """Assert every registered schema is itself a valid schema. Returns the keys."""
        for key, schema in self._schemas.items():
            Draft202012Validator.check_schema(schema)
            if "title" not in schema or "description" not in schema:
                raise RegistryError(
                    diagnose(CONTRACT_INDEX_INVALID, f"{key} does not say what it is")
                )
        return self.ids()


# ---------------------------------------------------------------------- helpers


def _flatten(
    errors: list[js_exceptions.ValidationError],
) -> Iterator[js_exceptions.ValidationError]:
    """Walk into oneOf/anyOf branches, where the interesting failure usually hides."""
    for error in errors:
        if error.context:
            yield from _flatten(sorted(error.context, key=lambda e: list(e.absolute_path)))
        else:
            yield error


def _classify(error: js_exceptions.ValidationError) -> str:
    """Name the failure. Fabricated provenance is never merely a shape complaint."""
    if error.validator == "not":
        subschema = error.validator_value
        title = FABRICATED_SOURCE.split(".")[1]
        if isinstance(subschema, dict) and subschema.get("title") == title:
            return FABRICATED_SOURCE
    path = [str(p) for p in error.absolute_path]
    if path and path[-1] in PROVENANCE_FIELDS:
        return NO_PROVENANCE
    if error.validator == "required":
        missing = error.message.split("'")[1] if "'" in error.message else ""
        if missing in PROVENANCE_FIELDS:
            return NO_PROVENANCE
    return SCHEMA_INVALID


def _locator(error: js_exceptions.ValidationError) -> str:
    return "/".join(str(p) for p in error.absolute_path)


def _dedupe(found: list[Diagnostic]) -> Iterator[Diagnostic]:
    seen: set[tuple[str, str, str]] = set()
    for d in found:
        marker = (d.code, d.locator, d.detail)
        if marker not in seen:
            seen.add(marker)
            yield d


def _worst(found: tuple[Diagnostic, ...]) -> Diagnostic:
    """Fabricated provenance outranks a missing source, which outranks a bad shape."""
    order = {FABRICATED_SOURCE: 0, NO_PROVENANCE: 1, SCHEMA_INVALID: 2}
    return min(found, key=lambda d: order.get(d.code, 3))
