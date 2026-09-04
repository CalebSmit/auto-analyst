"""The way out: template registry, model builder, deliverable QC, the single release gate.

Everything above this package exists so that building the deliverable is boring. By the
time a figure reaches here it has a source, has been recomputed, has been re-identified
and has been locked. This package writes it into a copy of a pinned template by named
range, opens the result and checks it, and releases it exactly once.
"""

from __future__ import annotations

from deliver.builder import Built, ModelBuilder
from deliver.qc import DeliverableQC
from deliver.registry import RegisteredTemplate, TemplateInputs, TemplateRegistry
from deliver.release import Released, ReleaseGate, ReleaseRefused
from deliver.workpaper import WorkpaperNarrative

__all__ = [
    "Built",
    "DeliverableQC",
    "ModelBuilder",
    "RegisteredTemplate",
    "ReleaseGate",
    "ReleaseRefused",
    "Released",
    "TemplateInputs",
    "TemplateRegistry",
    "WorkpaperNarrative",
]
