"""The Template Registry: which version of the model template a deliverable was built from.

Registering a template introspects the workbook and asserts it declares every named
range the mapping requires, so a model missing two inputs fails at registration naming
the two, rather than delivering two empty cells. A required input that is a cell
address is refused outright: `B44` is not a contract, and one inserted row would shift
every mapping below it into a plausibly wrong deliverable.

The binding - which template a scope builds into - is the Scope Resolver's, read from
`templates/bindings.yaml` through the same five-layer walk as a skill. This registry
holds what a bound template actually declares, pinned by content hash, and answers
`template_schema_lookup`. A scope whose binding names a template nobody registered gets
`DELIVER.TEMPLATE_MISSING` and the fixed notice, never a guessed workbook.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace
from io import BytesIO
from pathlib import Path
from typing import Any

import yaml
from openpyxl import load_workbook

from graph.resolve import TemplateBinding
from registries.errors import (
    CELL_ADDRESS_BINDING,
    TEMPLATE_INPUTS_MISSING,
    TEMPLATE_MISSING,
    RegistryError,
    diagnose,
)

__all__ = [
    "CELL_ADDRESS",
    "INPUTS_DIR",
    "NAMED_RANGE",
    "RegisteredTemplate",
    "TemplateInput",
    "SOURCE_SUFFIX",
    "TemplateInputs",
    "TemplateRegistry",
    "TEMPLATES_DIR",
    "declared_names",
    "version_key",
]

TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates"
INPUTS_DIR = TEMPLATES_DIR / "inputs"

# The same rule the model-load contract states: a named range or a table reference,
# never a cell address. A1, B44, AA7 and $B$44 are all refused.
CELL_ADDRESS = re.compile(r"^\$?[A-Za-z]{1,3}\$?[0-9]+$")
NAMED_RANGE = re.compile(r"^(?![A-Za-z]{1,3}[0-9]+$)[A-Za-z_][A-Za-z0-9_.]*$")


def version_key(file: str, template_version: str) -> str:
    """`Chartwell_ESOP_Model_v9@9.4` - what a run pins and the gate checks."""
    return f"{Path(file).stem}@{template_version}"


@dataclass(frozen=True)
class TemplateInput:
    name: str
    line: str
    period: str
    required: bool

    def as_row(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "line": self.line,
            "period": self.period,
            "required": self.required,
        }


SOURCE_SUFFIX = "__Source"
"""What a source cell's named range is called: the input's name plus this.

A suffix rather than a parallel list, so the relationship between a figure and its
provenance is in the name and cannot be got wrong by filing them in a different order."""


@dataclass(frozen=True)
class TemplateInputs:
    """The mapping schema for one template version: what may be written, and what must."""

    file: str
    template_version: str
    scale: int
    currency: str
    stamps: tuple[str, ...]
    inputs: tuple[TemplateInput, ...]
    sources_beside_values: bool = False
    """Whether this template has a provenance cell beside each input.

    Declared per template and off by default, because it is not ours to add to the firm's
    own model. The Input Help workbook exists to be copied from and therefore to be
    checked, so it says where every figure came from; `Chartwell_Master_Model_v14` is a
    stand-in for a workbook Chartwell maintains, and putting a column in it that this
    build invented would be this build editing somebody else's model."""

    @property
    def key(self) -> str:
        return version_key(self.file, self.template_version)

    @property
    def required(self) -> tuple[str, ...]:
        return tuple(i.name for i in self.inputs if i.required)

    @property
    def optional(self) -> tuple[str, ...]:
        return tuple(i.name for i in self.inputs if not i.required)

    @property
    def declared(self) -> frozenset[str]:
        """Every destination the writer may write: the inputs. Stamps are the writer's."""
        return frozenset(i.name for i in self.inputs)

    @property
    def sources(self) -> tuple[str, ...]:
        """The cell beside each input that says where its figure came from.

        Derived rather than listed, because a schema that had to name forty-four of these
        by hand is a schema where one gets forgotten - and the one that gets forgotten is
        an input whose figure looks as checkable as the others and is not.

        They are **stamps**, not inputs: the writer owns them and the mapping may never
        name one. That is the same rule `Template_Version` and `Run_Id` are under, and for
        the same reason - a model that could route a figure into a provenance cell could
        write its own provenance.

        Empty for a template that does not declare the column."""
        if not self.sources_beside_values:
            return ()
        return tuple(f"{i.name}{SOURCE_SUFFIX}" for i in self.inputs)

    def get(self, name: str) -> TemplateInput | None:
        return next((i for i in self.inputs if i.name == name), None)

    @classmethod
    def load(cls, key: str, folder: Path = INPUTS_DIR) -> TemplateInputs:
        path = folder / f"{key}.yaml"
        if not path.is_file():
            have = ", ".join(p.stem for p in sorted(folder.glob("*.yaml"))) or "none"
            raise RegistryError(
                diagnose(
                    TEMPLATE_MISSING,
                    f"no input schema for template {key} (have: {have})",
                    locator=str(path),
                )
            )
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        inputs = [
            TemplateInput(str(e["name"]), str(e["line"]), str(e["period"]), required=True)
            for e in raw.get("required", [])
        ] + [
            TemplateInput(str(e["name"]), str(e["line"]), str(e["period"]), required=False)
            for e in raw.get("optional", [])
        ]
        schema = cls(
            file=str(raw["template"]),
            template_version=str(raw["template_version"]),
            scale=int(raw.get("scale", 1)),
            currency=str(raw.get("currency", "USD")),
            stamps=tuple(str(s) for s in raw.get("stamps", [])),
            inputs=tuple(inputs),
            sources_beside_values=bool(raw.get("sources_beside_values", False)),
        )
        # The source cells join the stamps here rather than in the file: they are one per
        # input and they follow the inputs exactly, so deriving them is the only version
        # of this that cannot fall out of step with the list it mirrors.
        schema = replace(schema, stamps=schema.stamps + schema.sources)
        if schema.key != key:
            raise RegistryError(
                diagnose(
                    TEMPLATE_MISSING,
                    f"{path.name} describes {schema.key}, not {key}",
                    locator=str(path),
                )
            )
        for name in (*schema.declared, *schema.stamps):
            _refuse_cell_address(name, str(path))
        return schema


@dataclass(frozen=True)
class RegisteredTemplate:
    """A template the registry accepted: the file, its hash, and what it declares."""

    file: str
    template_version: str
    content_hash: str
    named_ranges: frozenset[str]
    inputs: TemplateInputs
    path: Path
    binding_layer: str = ""

    @property
    def key(self) -> str:
        return version_key(self.file, self.template_version)

    def read(self) -> bytes:
        """The master's bytes, for the writer to open as a copy. The master itself is
        never opened for writing - the hash proves it."""
        data = self.path.read_bytes()
        digest = f"sha256:{hashlib.sha256(data).hexdigest()}"
        if digest != self.content_hash:
            raise RegistryError(
                diagnose(
                    TEMPLATE_MISSING,
                    f"{self.file} on disk is not the registered bytes ({digest[:19]}... "
                    f"vs {self.content_hash[:19]}...); a template that changed under "
                    f"its registration is not the template",
                    locator=str(self.path),
                )
            )
        return data


def declared_names(data: bytes) -> frozenset[str]:
    """Every defined name in a workbook, workbook-level and sheet-level, that points at
    a cell or range. Introspection, not trust: this is what the file says, not what its
    schema claims."""
    wb = load_workbook(BytesIO(data), read_only=False)
    names: set[str] = set()
    for name, defined in wb.defined_names.items():
        if defined.attr_text and "!" in str(defined.attr_text):
            names.add(str(name))
    for ws in wb.worksheets:
        for name in ws.defined_names:
            names.add(str(name))
    return frozenset(names)


class TemplateRegistry:
    def __init__(
        self,
        templates_dir: Path = TEMPLATES_DIR,
        inputs_dir: Path = INPUTS_DIR,
    ) -> None:
        self.templates_dir = templates_dir
        self.inputs_dir = inputs_dir
        self._registered: dict[str, RegisteredTemplate] = {}

    # -- registration

    def register(
        self,
        file: str,
        template_version: str,
        *,
        path: Path | None = None,
        inputs: TemplateInputs | None = None,
        bindings: Mapping[str, str] | None = None,
    ) -> RegisteredTemplate:
        """Introspect the workbook, list its named ranges, assert every required input
        is declared. Names the missing ones; refuses a cell address anywhere.

        `bindings` is an optional map of template input name -> the workbook name it is
        bound to, for a workbook whose names differ from the schema's. A binding to a
        cell address is refused before the workbook is opened.
        """
        key = version_key(file, template_version)
        schema = inputs or TemplateInputs.load(key, self.inputs_dir)
        aliases = dict(bindings or {})
        for target in aliases.values():
            _refuse_cell_address(target, key)
        for name in aliases:
            if name not in schema.declared:
                raise RegistryError(
                    diagnose(
                        TEMPLATE_INPUTS_MISSING,
                        f"{key}: binding names {name!r}, which the schema does not declare",
                        locator=key,
                    )
                )

        source = path or (self.templates_dir / file)
        if not source.is_file():
            raise RegistryError(
                diagnose(
                    TEMPLATE_MISSING,
                    # templates/*.xlsx is not in git. A clone has none until somebody
                    # runs the synthesizer, and a sentence that names the absence
                    # without the command left a fresh machine reading every practice
                    # group as having no model (P169).
                    f"{file} is not under {self.templates_dir}; "
                    "python -m uv run python tools/synthesize_templates.py writes it, "
                    "and start.cmd runs that on a clone",
                    locator=str(source),
                )
            )
        data = source.read_bytes()
        names = declared_names(data)
        for name in names:
            _refuse_cell_address(name, key)

        expected = [*schema.required]
        missing = [n for n in expected if aliases.get(n, n) not in names]
        stamps_missing = [s for s in schema.stamps if s not in names]
        if missing or stamps_missing:
            found = len(expected) - len(missing)
            raise RegistryError(
                diagnose(
                    TEMPLATE_INPUTS_MISSING,
                    f"{file} @ {template_version} declares {found} of {len(expected)} "
                    f"required inputs; missing {', '.join(missing)}"
                    + (f"; stamps missing {', '.join(stamps_missing)}" if stamps_missing else ""),
                    locator=key,
                    expected=len(expected),
                    found=found,
                    delta=", ".join([*missing, *stamps_missing]),
                )
            )

        registered = RegisteredTemplate(
            file=file,
            template_version=template_version,
            content_hash=f"sha256:{hashlib.sha256(data).hexdigest()}",
            named_ranges=names,
            inputs=schema,
            path=source,
        )
        self._registered[key] = registered
        return registered

    def register_bindings(
        self, bindings: Iterable[TemplateBinding]
    ) -> tuple[RegisteredTemplate, ...]:
        """Register every template the scope bindings name. A layer bound to nothing is
        skipped; a layer bound to a file that is not here fails, loudly."""
        done = []
        for b in bindings:
            if not b.file:
                continue
            registered = self.register(b.file, b.template_version)
            registered = RegisteredTemplate(**{**registered.__dict__, "binding_layer": b.layer})
            self._registered[registered.key] = registered
            done.append(registered)
        return tuple(done)

    # -- lookup

    def get(self, key: str) -> RegisteredTemplate:
        found = self._registered.get(key)
        if found is None:
            raise RegistryError(
                diagnose(
                    TEMPLATE_MISSING,
                    f"{key} is not registered "
                    f"(have: {', '.join(sorted(self._registered)) or 'none'})",
                    locator=key,
                )
            )
        return found

    def resolve(self, binding: TemplateBinding | None) -> RegisteredTemplate:
        """The registered template a resolved scope builds into, or the fixed refusal."""
        if binding is None or not binding.file:
            raise RegistryError(
                diagnose(
                    TEMPLATE_MISSING,
                    "the scope binds no template at any layer",
                    locator="templates/bindings.yaml",
                )
            )
        return self.get(version_key(binding.file, binding.template_version))

    def keys(self) -> tuple[str, ...]:
        return tuple(sorted(self._registered))


def _refuse_cell_address(name: str, locator: str) -> None:
    if CELL_ADDRESS.match(name) or not NAMED_RANGE.match(name):
        raise RegistryError(
            diagnose(
                CELL_ADDRESS_BINDING,
                f"{name!r} is a cell address, not a named range; B44 is not a contract",
                locator=locator,
                found=name,
                expected="a named range",
            )
        )
