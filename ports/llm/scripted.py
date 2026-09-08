"""A scripted analyst: answers every skill from the request, for rehearsals only.

Reads the payload each procedure sends and writes a structurally right proposal: one
period per column, tags by taxonomy cue, add-backs for officer pay and the discretionary
lines, a binding for every template input it can find by name and period. Not clever
and not meant to be. What it is for is everything *around* the model - the guards on its
answers, the review queue, a person deciding, the run waking up, cost, precedent,
delivery - which a fixture-replaying fake cannot reach on files it has never seen.

A run under it would look like analysis and be nothing of the kind. The front door
(`tools/serve.py`) refuses to start on it unless `AA_REHEARSAL=1` is set beside
`AA_LLM_ADAPTER=scripted`, so the one way that could happen by accident is closed where
the system is assembled. The adapter itself builds like any other, so the port
conformance suite can hold it to the same shape.

A recorded fixture, where one exists for the request, is replayed exactly as the fake
adapter would replay it; the analyst answers only where nothing was recorded.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from ports.llm import LLMRequest, LLMResponse, Usage
from ports.llm.fake import FakeLLM, FixtureMissing

__all__ = ["REHEARSAL_VAR", "ScriptedAnalyst", "build"]

REHEARSAL_VAR = "AA_REHEARSAL"
KNOWN = ("files", "taxonomy", "verification", "lines", "template")


def payload_of(content: str) -> dict[str, Any]:
    """The JSON object a procedure put in the message: the one carrying a key a
    procedure sends, wherever it sits among the other sections."""
    decoder = json.JSONDecoder()
    for m in re.finditer(r"\{", content):
        try:
            body, _ = decoder.raw_decode(content, m.start())
        except ValueError:
            continue
        if isinstance(body, dict) and any(k in body for k in KNOWN):
            return body
    return {}


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


class ScriptedAnalyst:
    name = "scripted"

    def __init__(self, fixture_dir: Path | str | None = None) -> None:
        self.requests: list[LLMRequest] = []
        self.recorded = FakeLLM(fixture_dir)

    def __repr__(self) -> str:
        return f"ScriptedAnalyst(calls={len(self.requests)})"

    def record(self, request: LLMRequest, response: LLMResponse) -> None:
        """A recorded answer wins over the script, exactly as the fake replays it."""
        self.recorded.record(request, response)

    def complete(self, request: LLMRequest) -> LLMResponse:
        self.requests.append(request)
        try:
            return self.recorded.complete(request)
        except FixtureMissing:
            pass
        content = request.messages[-1].content
        body = payload_of(content)
        skill = request.metadata.get("skill", "unknown@0.0.0")
        answer = self.answer(body, skill)
        text = json.dumps(answer, indent=1)
        return LLMResponse(
            text=text,
            model=request.pin.model,
            stop_reason="end_turn",
            usage=Usage(input_tokens=len(content) // 4, output_tokens=len(text) // 4),
        )

    def answer(self, body: dict[str, Any], skill: str) -> dict[str, Any]:
        if "files" in body:
            answer = self.timing(body)
        elif "taxonomy" in body:
            answer = self.tagging(body)
        elif body.get("verification"):
            answer = self.verification(body)
        elif "lines" in body and "benchmark" in body:
            answer = self.ebitda(body)
        elif "template" in body:
            answer = self.model_load(body)
        else:
            answer = {}
        name = skill.split("@", 1)[0]
        answer["produced_by"] = skill
        answer["schema_version"] = (
            f"skills/{name}-verification-proposal@1.0.0"
            if body.get("verification")
            else f"skills/{name}-proposal@1.0.0"
        )
        return answer

    # -- timing: one period per block from its header, line items grouped by label

    def timing(self, body: dict[str, Any]) -> dict[str, Any]:
        periods: list[dict[str, Any]] = []
        groups: dict[str, dict[str, Any]] = {}
        for f in body["files"]:
            ends = [str(e) for e in (f.get("period_ends") or [])]
            for idx, (block, b) in enumerate(f["blocks"].items()):
                label, end = self.period(b.get("period_hint"), ends, idx)
                periods.append(
                    {
                        "label": label,
                        "type": "FY",
                        "end": end,
                        "source_id": f["source_id"],
                        "block": block,
                    }
                )
                for row in b["rows"]:
                    locator, _, text = row.partition(": ")
                    key = _norm(text)
                    entry = groups.setdefault(
                        key, {"canonical_label": text.strip(), "kind": "exact", "sources": []}
                    )
                    entry["sources"].append(
                        {"source_id": f["source_id"], "locator": locator, "label": text.strip()}
                    )
        return {"periods": periods, "line_items": list(groups.values()), "unmatched": []}

    @staticmethod
    def period(hint: Any, ends: list[str], idx: int) -> tuple[str, str]:
        text = str(hint or "")
        m = re.search(r"(20\d\d)-(\d\d)-(\d\d)", text)
        if m:
            return f"FY{m.group(1)}", m.group(0)
        m = re.search(r"(20\d\d)", text)
        if m:
            return f"FY{m.group(1)}", f"{m.group(1)}-12-31"
        m = re.search(r"'?(\d\d)\b", text)
        if m and text:
            year = f"20{m.group(1)}"
            return f"FY{year}", f"{year}-12-31"
        if idx < len(ends):
            return f"FY{ends[idx][:4]}", ends[idx]
        return f"P{idx + 1}", "2025-12-31"

    # -- tagging: the longest matching cue wins

    def tagging(self, body: dict[str, Any]) -> dict[str, Any]:
        categories = body["taxonomy"]["categories"]
        items = []
        for it in body["items"]:
            text = _norm(it["description"] + " " + " ".join(it.get("source_labels") or []))
            best, best_len = None, 0
            for c in categories:
                for cue in c.get("cues", ()):
                    if _norm(cue) in text and len(cue) > best_len:
                        best, best_len = c, len(cue)
            if best is None:
                hint = str(it.get("statement_hint") or "")
                wanted = "accounts_receivable" if hint == "BS" else "other_operating_expense"
                best = next((c for c in categories if c["id"] == wanted), categories[0])
            items.append(
                {
                    "line_item_ref": it["line_item_ref"],
                    "category": best["id"],
                    "excluded_from_al": bool(best["excluded_from_al"]),
                    "include_in_nwc": bool(best["include_in_nwc"]),
                    "confidence": 0.62 if best_len == 0 else 0.91,
                    "rationale": (
                        f"cue match on {best['label']!r}"
                        if best_len
                        else "no cue matched; nearest by statement"
                    ),
                }
            )
        return {"items": items}

    # -- add-backs: officer pay, and anything that reads as personal or one-off

    def ebitda(self, body: dict[str, Any]) -> dict[str, Any]:
        candidates = []
        for ln in body["lines"]:
            d = _norm(ln["description"])
            ref = ln["line_item_ref"]
            if ln.get("category") == "officer_compensation":
                candidates.append(
                    {
                        "candidate_id": f"ADD-officer-{ref[-6:]}",
                        "line_item_ref": ref,
                        "category": "owner_related",
                        "periods": list(ln["periods_present"]),
                        "officer_compensation": True,
                        "rationale": "officer pay, tested against the benchmark",
                        "confidence": 0.9,
                    }
                )
            elif re.search(r"life insurance|club|personal|one time|settlement|donation|charit", d):
                candidates.append(
                    {
                        "candidate_id": f"ADD-disc-{ref[-6:]}",
                        "line_item_ref": ref,
                        "category": "discretionary",
                        "periods": list(ln["periods_present"]),
                        "rationale": "discretionary owner expense",
                        "confidence": 0.8,
                    }
                )
        return {"candidates": candidates}

    def verification(self, body: dict[str, Any]) -> dict[str, Any]:
        return {
            "verdicts": [
                {
                    "candidate_id": i["candidate_id"],
                    "supported": True,
                    "reason": "the cited row carries the description and the amount",
                }
                for i in body["items"]
            ]
        }

    # -- model load: bind by name and period order, say what could not be bound

    SYNONYMS: dict[str, set[str]] = {
        "revenue": {"sales", "revenue"},
        "cost of sales": {"cost", "cogs"},
        "officer compensation": {"officer"},
        "depreciation": {"depreciation"},
        "interest expense": {"interest"},
        "cash": {"cash"},
        "accounts receivable": {"receivable"},
        "inventory": {"inventory"},
        "accounts payable": {"payable"},
    }

    def model_load(self, body: dict[str, Any]) -> dict[str, Any]:
        catalogue = body["catalogue"]
        by_ref = {c["figure_ref"]: c for c in catalogue}
        labels = sorted({str(c.get("period")) for c in catalogue if c.get("period")})
        order = {f"FY{i + 1}": lab for i, lab in enumerate(labels)}
        bindings, unmapped = [], []
        for inp in body["template"]["inputs"]:
            line, period = str(inp["line"]), str(inp["period"])
            want_period = order.get(period, period)
            want = f"timing:{line}:{want_period}"
            ref = want if want in by_ref else None
            if ref is None:
                keys = self.SYNONYMS.get(_norm(line), set(_norm(line).split()))
                ref = next(
                    (
                        c["figure_ref"]
                        for c in catalogue
                        if str(c.get("period")) == want_period
                        and keys & set(_norm(str(c.get("description"))).split())
                    ),
                    None,
                )
            baseline = "profile:owner_compensation_baseline"
            if (
                ref is None
                and baseline in by_ref
                and _norm(line) in ("owner compensation baseline", "owner compensation")
            ):
                ref = baseline
            if ref:
                bindings.append({"named_range": inp["name"], "figure_ref": ref})
            else:
                unmapped.append(
                    {
                        "named_range": inp["name"],
                        "why": f"no upstream figure for {line!r} in {period}",
                    }
                )
        bound = {b["figure_ref"] for b in bindings}
        return {
            "bindings": bindings,
            "unmapped_template_inputs": unmapped,
            "unrouted_upstream_figures": [
                {"figure_ref": c["figure_ref"], "why": "no template input takes it"}
                for c in catalogue
                if c["figure_ref"] not in bound
            ][:50],
        }


def build() -> ScriptedAnalyst:
    return ScriptedAnalyst()
