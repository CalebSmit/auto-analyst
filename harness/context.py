"""The Context Builder: everything a model is shown, assembled in one place and recorded.

Nothing calls a model without going through here, so "what exactly was in context?" is
a hash lookup rather than an archaeology exercise. The assembled whole is content-hashed
into `context_ref`, stored, and the hash goes into the step's idempotency key - which is
why a changed precedent changes the key, and why a resumed run can never return a cached
result the current context would no longer produce.

**What goes in, in this order, every time.** The skill body. The references it declares,
including the ones an overlay added. The firm's foundations, unconditionally. Retrieved
precedents. The engagement profile. The masked payload. On a repair pass, the guard
failure that sent it back. The order is fixed because the hash is an identity, and two
contexts that differed only in section order would be two keys for one question.

**Progressive disclosure is enforced here, not hoped for.** The tree holds frontmatter for
every skill and the body for none. This builder asks the tree for exactly one body - the
step's own - and exactly the references that skill declares. A test wraps the tree to
prove it. A skill body loaded for a skill the plan did not select is not a waste, it is a
leak: procedures the orchestrator was never meant to see, in context.

**Precedent retrieval is scope-built.** The query is constructed from the engagement's
resolved scope and nothing else can construct one, so a Corporate Finance decision is
never available to an ESOP valuation. What comes back is checked, not trusted: a
precedent from another practice group, or one that is not masked, refuses the whole
batch. For a returning client, that client's own prior decisions are placed first.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from graph.compile import Step
from graph.resolve import ResolvedScope, ResolvedSkill
from ops.blobs import ContentRef, ContentStore
from ops.events import EventBus
from ops.run_store import RunStore
from registries.errors import (
    METHODOLOGY_UNCLEARED,
    PRECEDENT_OUT_OF_SCOPE,
    RECIPE_INVALID,
    UNMASKED_PRECEDENT,
    RegistryError,
    diagnose,
)
from registries.methodology import MethodologyRegister, digest_of
from registries.skills import SkillTree

REPO_ROOT = Path(__file__).resolve().parents[1]
FOUNDATIONS_DIR = REPO_ROOT / "foundations"

# The framing between sections of the assembled context. Fixed, and part of the bytes
# that are hashed: the hash covers what the model was shown, framing included.
FRAME = "\n=== {kind}: {name} ({digest}) ===\n"
PRECEDENTS_PER_CALL = 24
"""The most examples one call is shown. The blueprint's cost model tags twenty items per
call; one example each plus a few from the scope is the whole budget."""

__all__ = [
    "AssembledContext",
    "ContextBuilder",
    "ContextRequest",
    "NoPrecedents",
    "Precedent",
    "PrecedentQuery",
    "PrecedentSource",
    "Section",
]


# --------------------------------------------------------------- precedents


@dataclass(frozen=True)
class Precedent:
    """One approved, masked example from a past engagement."""

    precedent_id: str
    engagement_id: str
    client_id: str
    scope: str
    """The scope path it was decided under: practice/segment/disposition."""
    masked: bool
    example: dict[str, Any]
    """A masked line-item description, its approved category, and the rationale."""

    @property
    def practice(self) -> str:
        return self.scope.split("/", 1)[0]


@dataclass(frozen=True)
class PrecedentQuery:
    """What the store is asked. Built from a resolved scope, and from nothing else.

    There is no constructor that takes a free-text scope: `ContextBuilder.query_for`
    derives every field from the engagement's `ResolvedScope`, which is what "scope-built"
    means and why a query cannot be widened by a caller.
    """

    engagement_id: str
    client_id: str
    practice: str
    segment: str
    disposition: str
    precedent_scope: str
    """`client_first` or `scope_only` - from the disposition, possibly narrowed by an
    overlay. Never wider than the scope resolved."""
    skill: str
    limit: int = 8
    terms: tuple[str, ...] = ()
    """Masked line-item descriptions the step is about, for ranking within the scope.
    Ranking only: a term cannot widen where the store looks, because the scope fields
    above are what the store's WHERE clause is built from and the terms are not."""

    @property
    def scope_path(self) -> str:
        return f"{self.practice}/{self.segment}/{self.disposition}"


@runtime_checkable
class PrecedentSource(Protocol):
    """Where approved precedents come from. The Precedent Store proper is P19's."""

    def retrieve(self, query: PrecedentQuery) -> tuple[Precedent, ...]: ...


class NoPrecedents:
    """The source until P19 exists. Answers every query with nothing, honestly."""

    def retrieve(self, query: PrecedentQuery) -> tuple[Precedent, ...]:
        return ()


# ------------------------------------------------------------------ request


@dataclass(frozen=True)
class ContextRequest:
    """What one model call is about. Refs, not values - the builder fetches."""

    run_id: str
    engagement_id: str
    client_id: str
    step: Step
    scope: ResolvedScope
    engagement_profile: ContentRef
    payload: ContentRef
    """The masked payload, as cleared by the payload scan. The type that only the scan can
    produce is P12's; until then this is a ref and the scan is the caller's promise."""
    repair_feedback: ContentRef | None = None
    """On a repair pass, the guard's structured failure. The changed input that makes an
    iteration count as one."""
    tool_results: tuple[ContentRef, ...] = ()
    precedent_terms: tuple[str, ...] = ()
    """Masked descriptions the precedent query ranks by. From the dispatcher, after the
    masker; a value the masker has not seen does not belong here."""


@dataclass(frozen=True)
class Section:
    """One part of the assembled context, and the hash of just that part."""

    kind: str
    name: str
    content_hash: str
    size_bytes: int


@dataclass(frozen=True)
class AssembledContext:
    """The whole, its hash, and an account of what went in."""

    context_ref: str
    ref: ContentRef
    manifest_ref: ContentRef
    skill: str
    sections: tuple[Section, ...]
    precedent_ids: tuple[str, ...]

    def section(self, kind: str, name: str | None = None) -> tuple[Section, ...]:
        return tuple(
            s for s in self.sections if s.kind == kind and (name is None or s.name == name)
        )


# ------------------------------------------------------------------ builder


class ContextBuilder:
    """The single place a model call's input is put together."""

    def __init__(
        self,
        tree: SkillTree,
        blobs: ContentStore,
        bus: EventBus,
        store: RunStore | None = None,
        precedents: PrecedentSource | None = None,
        foundations_dir: Path = FOUNDATIONS_DIR,
        methodology: MethodologyRegister | None = None,
    ) -> None:
        self.tree = tree
        self.blobs = blobs
        self.bus = bus
        self.store = store
        self.precedents: PrecedentSource = precedents or NoPrecedents()
        self.foundations_dir = foundations_dir
        self.methodology = methodology or MethodologyRegister(root=foundations_dir)

    def build(self, request: ContextRequest) -> AssembledContext:
        step = request.step
        if step.kind != "skill" or not step.skill:
            raise RegistryError(
                diagnose(
                    RECIPE_INVALID,
                    f"{step.id} is a {step.kind} step; only a skill step has a context",
                    locator=step.id,
                )
            )
        name = step.skill.split("@", 1)[0]
        resolved = request.scope.skill(name)

        parts: list[tuple[str, str, bytes]] = []

        # 1. The skill body. Exactly one, exactly this one.
        parts.append(("skill", resolved.skill.key, self.tree.body(resolved.skill).encode("utf-8")))

        # 2. Its references, as resolved - the overlay-added ones included.
        for ref_name in resolved.references:
            text = self.tree.reference(
                resolved.skill,
                ref_name,
                declared=resolved.references,
                layers=request.scope.layers,
            )
            parts.append(("reference", ref_name, text.encode("utf-8")))

        # 3. Foundations, unconditionally - and only ever the cleared version.
        #
        # Unconditional is what makes methodology worth checking: it is the one input that
        # reaches every call for every client, and the outbound scan knows only the
        # current engagement's identifiers, so a worked example from a real deal pasted in
        # here would travel everywhere and trip nothing. It is read by a person once and
        # recorded by digest; this is the lookup, and it refuses rather than dropping the
        # file, because a run silently missing half its methodology answers a different
        # question from the one that was asked.
        cleared = self.methodology.digests()
        for path in self.methodology.files():
            body = path.read_bytes()
            digest = digest_of(body)
            if digest not in cleared:
                raise RegistryError(
                    diagnose(
                        METHODOLOGY_UNCLEARED,
                        f"{path.name} is not cleared methodology"
                        + (
                            " - it was cleared once, but not this version of it"
                            if any(row.name == path.name for row in self.methodology.cleared())
                            else ""
                        ),
                        locator=path.name,
                        expected="a digest recorded in the methodology register",
                        found=digest,
                    )
                )
            parts.append(("foundations", path.name, body))

        # 4. Precedents, from a scope-built query, checked on the way in.
        query = self.query_for(request, resolved)
        precedents = self._checked(self.precedents.retrieve(query), query)
        for precedent in precedents:
            parts.append(("precedent", precedent.precedent_id, _canonical(precedent.example)))

        # 5. The engagement profile and 6. the masked payload, by ref.
        parts.append(
            (
                "engagement_profile",
                request.engagement_profile.content_hash,
                self.blobs.get(request.engagement_profile),
            )
        )
        parts.append(("payload", request.payload.content_hash, self.blobs.get(request.payload)))

        # 7. On a repair pass, what the guard said. The changed input.
        if request.repair_feedback is not None:
            parts.append(
                (
                    "repair_feedback",
                    request.repair_feedback.content_hash,
                    self.blobs.get(request.repair_feedback),
                )
            )
        for result in request.tool_results:
            parts.append(("tool_result", result.content_hash, self.blobs.get(result)))

        assembled, sections = _assemble(parts)
        ref = self.blobs.put(assembled, media_type="text/plain", name=f"context:{step.id}")

        manifest = {
            "schema": "context_manifest@1.0.0",
            "run_id": request.run_id,
            "engagement_id": request.engagement_id,
            "step_id": step.id,
            "skill": resolved.skill.key,
            "context_ref": ref.content_hash,
            "sections": [
                {
                    "kind": s.kind,
                    "name": s.name,
                    "content_hash": s.content_hash,
                    "size_bytes": s.size_bytes,
                }
                for s in sections
            ],
            "precedents": [p.precedent_id for p in precedents],
            "precedent_query": {
                "scope": query.scope_path,
                "precedent_scope": query.precedent_scope,
                "client_first": query.precedent_scope == "client_first",
            },
        }
        manifest_ref = self.blobs.put(_canonical(manifest), name=f"context_manifest:{step.id}")

        self._record(request, ref, manifest_ref, sections, precedents)
        return AssembledContext(
            context_ref=ref.content_hash,
            ref=ref,
            manifest_ref=manifest_ref,
            skill=resolved.skill.key,
            sections=sections,
            precedent_ids=tuple(p.precedent_id for p in precedents),
        )

    # -- the query

    def query_for(self, request: ContextRequest, resolved: ResolvedSkill) -> PrecedentQuery:
        """A query derived from the resolved scope, and from nothing else.

        The precedent scope comes from the disposition, narrowed by an overlay if one
        applied to this skill. It is never wider than what resolution produced, because
        there is no field here a caller could widen it through.
        """
        scope = request.scope.scope
        terms = tuple(t for t in request.precedent_terms if t.strip())
        query = PrecedentQuery(
            engagement_id=request.engagement_id,
            client_id=request.client_id,
            practice=scope.practice,
            segment=scope.segment,
            disposition=scope.disposition,
            precedent_scope=resolved.precedent_scope or request.scope.precedent_scope,
            skill=resolved.skill.key,
        )
        if terms:
            # Room for one example per item, within a ceiling; never fewer than the
            # default, so a short batch still sees the scope's best examples.
            limit = min(PRECEDENTS_PER_CALL, max(query.limit, len(terms)))
            query = dataclasses.replace(query, terms=terms, limit=limit)
        return query

    def _checked(
        self, precedents: tuple[Precedent, ...], query: PrecedentQuery
    ) -> tuple[Precedent, ...]:
        """Refuse the batch, not the offending item.

        A source that returns one precedent from the wrong practice group is a broken
        source, and quietly dropping that item would leave it broken and unnoticed.
        """
        for precedent in precedents:
            if precedent.practice != query.practice:
                raise RegistryError(
                    diagnose(
                        PRECEDENT_OUT_OF_SCOPE,
                        f"{precedent.precedent_id} was decided under {precedent.scope}; "
                        f"this engagement is {query.scope_path}",
                        locator=query.engagement_id,
                    )
                )
            if not precedent.masked:
                raise RegistryError(
                    diagnose(
                        UNMASKED_PRECEDENT,
                        f"{precedent.precedent_id} is not masked",
                        locator=query.engagement_id,
                    )
                )
        if query.precedent_scope == "client_first":
            # Stable, so the store's own ranking survives within each half.
            own = tuple(p for p in precedents if p.client_id == query.client_id)
            rest = tuple(p for p in precedents if p.client_id != query.client_id)
            return own + rest
        return precedents

    # -- the record

    def _record(
        self,
        request: ContextRequest,
        ref: ContentRef,
        manifest_ref: ContentRef,
        sections: tuple[Section, ...],
        precedents: tuple[Precedent, ...],
    ) -> None:
        if self.store is not None:
            self.store.record_artifact(
                request.run_id, f"context/{request.step.id}", ref.content_hash
            )
        self.bus.emit(
            run_id=request.run_id,
            engagement_id=request.engagement_id,
            node_id="context_builder",
            type="context.assembled",
            message=f"{request.step.id}: {len(sections)} sections, {ref.size_bytes} bytes",
            step_id=request.step.id,
            payload={
                "context_ref": ref.content_hash,
                "manifest_ref": manifest_ref.content_hash,
                "sections": [f"{s.kind}:{s.name}" for s in sections],
                "precedents": len(precedents),
            },
        )


# ------------------------------------------------------------------ helpers


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _assemble(parts: list[tuple[str, str, bytes]]) -> tuple[bytes, tuple[Section, ...]]:
    """Frame each part and concatenate. The frame carries the part's own hash, so the
    manifest and the bytes agree by construction."""
    out = bytearray()
    sections: list[Section] = []
    for kind, name, body in parts:
        digest = f"sha256:{hashlib.sha256(body).hexdigest()}"
        out += FRAME.format(kind=kind, name=name, digest=digest).encode("utf-8")
        out += body
        if not body.endswith(b"\n"):
            out += b"\n"
        sections.append(Section(kind=kind, name=name, content_hash=digest, size_bytes=len(body)))
    return bytes(out), tuple(sections)
