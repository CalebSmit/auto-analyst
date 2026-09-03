"""Job Recipes: named, versioned sequences of skills, loaded from YAML.

A recipe composes skills; it contains no domain logic. Nothing in `recipes/` says what
EBITDA is - that lives in a SKILL.md, at the scope layer where it is true.

Recipes rather than a model produce the plan until P26, and that is deliberate: debugging
plan compilation and a model's plan proposal at the same time means trusting neither. A
recipe makes the routine case deterministic and leaves the orchestrator for the cases
that actually need judgement.

This module only reads and shapes. Everything that can be wrong about a recipe *as a
graph* - a step naming a producer that does not exist, a cycle nobody declared, a loop
asking for more iterations than the constraints allow - is the compiler's to refuse, in
`graph.compile`, because those are properties of the compiled whole rather than of the
file.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from registries.errors import RECIPE_INVALID, RegistryError, diagnose

REPO_ROOT = Path(__file__).resolve().parents[1]
RECIPES_DIR = REPO_ROOT / "recipes"

KINDS = ("skill", "tool", "guard", "human", "io")
ON_FAILURE = ("halt", "quarantine", "review")

# Defaults a recipe does not have to restate. `max_turns` is the one that matters: a
# skill invocation is one model turn, so 1 is not a default anybody should have to
# choose - it is what you get unless you deliberately ask for trouble, and the compiler
# refuses the ask.
DEFAULT_TIMEOUT_S = 300
DEFAULT_RETRIES = 0
DEFAULT_MAX_TURNS = 1

__all__ = [
    "LoopDeclaration",
    "Recipe",
    "RecipeInput",
    "RecipeStep",
    "load_recipe",
    "recipe_names",
]


@dataclass(frozen=True)
class RecipeInput:
    """Something that arrives from outside the plan."""

    name: str
    schema: str | None = None
    note: str = ""


@dataclass(frozen=True)
class RecipeStep:
    """One line of a recipe, before it becomes a compiled Step."""

    id: str
    kind: str
    label: str
    skill: str | None = None
    needs: tuple[str, ...] = ()
    run_inputs: tuple[str, ...] = ()
    output_schema: str | None = None
    on_failure: str = "quarantine"
    timeout_s: int = DEFAULT_TIMEOUT_S
    retries: int = DEFAULT_RETRIES
    max_turns: int = DEFAULT_MAX_TURNS


@dataclass(frozen=True)
class LoopDeclaration:
    """A loop region, declared with a ceiling before anything can iterate."""

    loop: str
    head: str
    members: tuple[str, ...]
    max_iterations: int
    why: str = ""


@dataclass(frozen=True)
class Recipe:
    name: str
    version: int
    title: str
    description: str
    steps: tuple[RecipeStep, ...]
    inputs: tuple[RecipeInput, ...] = ()
    loops: tuple[LoopDeclaration, ...] = ()
    path: str = ""
    _by_id: dict[str, RecipeStep] = field(default_factory=dict, repr=False, compare=False)

    @property
    def key(self) -> str:
        """How a run names the recipe it was seeded from."""
        return f"{self.name}@v{self.version}"

    def step(self, step_id: str) -> RecipeStep:
        return self._by_id[step_id]

    def input(self, name: str) -> RecipeInput | None:
        return next((i for i in self.inputs if i.name == name), None)


def recipe_names(recipes_dir: Path = RECIPES_DIR) -> tuple[str, ...]:
    return tuple(sorted(p.stem for p in recipes_dir.glob("*.yaml")))


def load_recipe(name: str, recipes_dir: Path = RECIPES_DIR) -> Recipe:
    """Load one recipe by name. Shape only; the graph is the compiler's business."""
    path = recipes_dir / f"{name}.yaml"
    if not path.is_file():
        raise RegistryError(
            diagnose(
                RECIPE_INVALID,
                f"no recipe called {name!r} (have: {', '.join(recipe_names(recipes_dir))})",
                locator=str(path),
            )
        )
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise RegistryError(diagnose(RECIPE_INVALID, "not a mapping", locator=str(path)))

    locator = f"{recipes_dir.name}/{path.name}"
    steps = tuple(_step(entry, locator) for entry in raw.get("steps") or ())
    if not steps:
        raise RegistryError(diagnose(RECIPE_INVALID, "declares no steps", locator=locator))

    seen: set[str] = set()
    for step in steps:
        if step.id in seen:
            raise RegistryError(
                diagnose(RECIPE_INVALID, f"step id {step.id!r} appears twice", locator=locator)
            )
        seen.add(step.id)

    recipe = Recipe(
        name=str(raw.get("name") or path.stem),
        version=int(raw.get("version", 1)),
        title=str(raw.get("title") or path.stem),
        description=" ".join(str(raw.get("description", "")).split()),
        steps=steps,
        inputs=tuple(
            RecipeInput(
                name=i["name"],
                schema=i.get("schema"),
                note=" ".join(str(i.get("note", "")).split()),
            )
            for i in raw.get("inputs") or ()
        ),
        loops=tuple(_loop(entry, locator) for entry in raw.get("loops") or ()),
        path=locator,
        _by_id={s.id: s for s in steps},
    )
    if recipe.name != path.stem:
        raise RegistryError(
            diagnose(
                RECIPE_INVALID,
                f"declares name {recipe.name!r} in a file called {path.name!r}",
                locator=locator,
            )
        )
    return recipe


def _step(entry: dict[str, Any], locator: str) -> RecipeStep:
    for required in ("id", "kind"):
        if not entry.get(required):
            raise RegistryError(
                diagnose(RECIPE_INVALID, f"a step declares no {required}", locator=locator)
            )
    step_id = str(entry["id"])
    kind = str(entry["kind"])
    if kind not in KINDS:
        raise RegistryError(
            diagnose(
                RECIPE_INVALID,
                f"{step_id}: kind {kind!r} is not one of {', '.join(KINDS)}",
                locator=locator,
            )
        )
    on_failure = str(entry.get("on_failure", "quarantine"))
    if on_failure not in ON_FAILURE:
        raise RegistryError(
            diagnose(
                RECIPE_INVALID,
                f"{step_id}: on_failure {on_failure!r} is not one of {', '.join(ON_FAILURE)}. "
                f"Every step says what happens when it fails; there is no implicit "
                f"'carry on regardless'.",
                locator=locator,
            )
        )
    if kind == "skill" and not entry.get("skill"):
        raise RegistryError(
            diagnose(RECIPE_INVALID, f"{step_id}: a skill step names no skill", locator=locator)
        )
    if kind != "skill" and entry.get("skill"):
        raise RegistryError(
            diagnose(
                RECIPE_INVALID,
                f"{step_id}: only a skill step may name a skill",
                locator=locator,
            )
        )
    return RecipeStep(
        id=step_id,
        kind=kind,
        label=str(entry.get("label") or step_id),
        skill=entry.get("skill"),
        needs=tuple(entry.get("needs") or ()),
        run_inputs=tuple(entry.get("run_inputs") or ()),
        output_schema=entry.get("output_schema"),
        on_failure=on_failure,
        timeout_s=int(entry.get("timeout_s", DEFAULT_TIMEOUT_S)),
        retries=int(entry.get("retries", DEFAULT_RETRIES)),
        max_turns=int(entry.get("max_turns", DEFAULT_MAX_TURNS)),
    )


def _loop(entry: dict[str, Any], locator: str) -> LoopDeclaration:
    for required in ("loop", "head", "members", "max_iterations"):
        if entry.get(required) in (None, "", []):
            raise RegistryError(
                diagnose(
                    RECIPE_INVALID,
                    f"a loop declaration is missing {required}. A region without a "
                    f"ceiling is not a declared loop, it is a cycle with a name.",
                    locator=locator,
                )
            )
    return LoopDeclaration(
        loop=str(entry["loop"]),
        head=str(entry["head"]),
        members=tuple(entry["members"]),
        max_iterations=int(entry["max_iterations"]),
        why=" ".join(str(entry.get("why", "")).split()),
    )
