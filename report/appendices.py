"""Which appendices exist, and what each one binds to.

**Data, not code.** The real report has not been seen by anything in this repo, and the
first one to arrive will not match a guess - a heading will be worded differently, an
appendix will have been renamed, the firm will add one. So an appendix is four values and
adding or correcting one is a config change on the work machine, not a phase here.

The default registry is what the analyst named in the fifth interview session:

> "I will point to appendix c, economic condition (info to pull into the report template),
> then the appendix e (summary of major market indices), then appendix f (summary of M&A
> markets), then appendix g (assumptions & limiting conditions), appendix h:
> certification, appendix I: qualifications of Chartwell & Staff."

Six named, and **three of them have no button and no code path**: "appendix g, h, and [i]
can stay the same as the prior years. Don't need to be updated." Setting up a report
begins by copying last year's, so G, H and I arrive in that copy untouched. They are still
listed here, with `updated=False`, for one reason: an appendix that is *deliberately* not
updated and an appendix somebody forgot to add look identical in an empty registry, and
the first person to wonder "why is there no button for the certification" deserves an
answer in the place they will look.

That also settles the hardest non-negotiable in the blueprint without a guard. Appendix H
is the certification. Nothing here writes to it - not because a check refuses, but because
there is no code path that reaches it. *Nothing concludes, signs or certifies* is
satisfied by construction.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from registries.errors import (
    APPENDIX_REGISTRY_INVALID,
    UNKNOWN_APPENDIX,
    RegistryError,
    diagnose,
)

__all__ = ["APPENDICES", "Appendix", "appendix", "registry_from", "updatable"]


@dataclass(frozen=True)
class Appendix:
    """One appendix: what it is called, where it goes, and whether anything updates it."""

    id: str
    """Short and stable - `economic`, `indices`, `ma`. The button's name in the code, not
    the letter: letters move when the firm adds an appendix, and a rename should not
    silently re-point a button at different content."""

    letter: str
    title: str

    anchor: str
    """The bookmark or heading to bind to. Never a paragraph index - see
    `report/anchors.py` for why that is the rule rather than a preference."""

    updated: bool = True
    """False for the three that carry forward. Listed rather than omitted, so "there is no
    button for this" is an answer rather than a gap."""

    note: str = ""


APPENDICES: tuple[Appendix, ...] = (
    Appendix(
        "economic",
        "C",
        "Economic Conditions",
        "Appendix C - Economic Conditions",
        note="Per period. The economic commentary, which is ready at its own moment - "
        "which is why there is a button per appendix rather than one for the report.",
    ),
    Appendix(
        "indices",
        "E",
        "Summary of Major Market Indices",
        "Appendix E - Summary of Major Market Indices",
        note="Per period.",
    ),
    Appendix(
        "ma",
        "F",
        "Summary of M&A Markets",
        "Appendix F - Summary of M&A Markets",
        note="Per period.",
    ),
    Appendix(
        "assumptions",
        "G",
        "Assumptions & Limiting Conditions",
        "Appendix G - Assumptions & Limiting Conditions",
        updated=False,
        note="Carries forward in the copy of last year's report. Firm boilerplate; "
        "changing it is a person's job in Word.",
    ),
    Appendix(
        "certification",
        "H",
        "Certification",
        "Appendix H - Certification",
        updated=False,
        note="Carries forward, and nothing here writes to it. The appraiser signs, "
        "outside this system - which is true by there being no code path rather than by "
        "a guard refusing one.",
    ),
    Appendix(
        "qualifications",
        "I",
        "Qualifications of Chartwell & Staff",
        "Appendix I - Qualifications of Chartwell & Staff",
        updated=False,
        note="Carries forward.",
    ),
)


def updatable(registry: tuple[Appendix, ...] = APPENDICES) -> tuple[Appendix, ...]:
    """The ones with a button. Three, not six."""
    return tuple(a for a in registry if a.updated)


def appendix(appendix_id: str, registry: tuple[Appendix, ...] = APPENDICES) -> Appendix:
    """One by id, or a refusal that names what exists.

    A refusal rather than None, and it names the three that *can* be updated separately
    from the three that cannot - because "there is no appendix called that" and "that
    appendix is not one anything updates" send a person to different places.
    """
    for entry in registry:
        if entry.id == appendix_id:
            return entry
    carried = ", ".join(f"{a.id} (appendix {a.letter})" for a in registry if not a.updated)
    raise RegistryError(
        diagnose(
            UNKNOWN_APPENDIX,
            f"there is no appendix called {appendix_id!r}. The ones with an update are "
            f"{', '.join(a.id for a in updatable(registry))}"
            + (f"; {carried} carry forward and nothing updates them" if carried else ""),
            locator=f"report/appendix/{appendix_id}",
        )
    )


def registry_from(rows: Any) -> tuple[Appendix, ...]:
    """Build a registry from configuration.

    The reason this exists: the real report has not been seen, so the default above is an
    informed guess at six anchor strings. When the first real one arrives and a heading
    turns out to be worded differently, correcting it has to be a setting somebody edits -
    not an edit to this file, and certainly not a phase.
    """
    built: list[Appendix] = []
    for row in rows:
        data = dict(row)
        missing = [key for key in ("id", "letter", "title", "anchor") if not data.get(key)]
        if missing:
            raise RegistryError(
                diagnose(
                    APPENDIX_REGISTRY_INVALID,
                    f"an appendix entry is missing {', '.join(missing)}. Every appendix "
                    f"needs an id, a letter, a title and the anchor it binds to; an entry "
                    f"without an anchor would have nowhere to put its content.",
                    locator="report/appendices",
                )
            )
        built.append(
            Appendix(
                id=str(data["id"]),
                letter=str(data["letter"]),
                title=str(data["title"]),
                anchor=str(data["anchor"]),
                updated=bool(data.get("updated", True)),
                note=str(data.get("note", "")),
            )
        )
    ids = [a.id for a in built]
    if len(set(ids)) != len(ids):
        raise RegistryError(
            diagnose(
                APPENDIX_REGISTRY_INVALID,
                f"two appendices share an id: {sorted({i for i in ids if ids.count(i) > 1})}. "
                f"The id is what a button names, so a duplicate would make one of them "
                f"unreachable and the other ambiguous.",
                locator="report/appendices",
            )
        )
    return tuple(built)
