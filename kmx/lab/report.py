"""Lesesichten auf das Labor: Zusammenfassung für die Prompts (inkl. widerlegter Ideen
und Gegenbeispiele) und der Bericht von `lab status`."""

from __future__ import annotations

import os
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from kmx.lab.claims import (
    EV_CRITIQUE,
    EV_EVALUATION,
    EV_LAB,
    EV_NOTE,
    EXPERIMENTAL,
    HYPOTHESIS,
    REFUTED,
    STATUSES,
    VERIFIED,
    Claim,
    official_passed,
    official_pinned,
)
from kmx.lab.registry import Event, Registry

PROMPT_CLAIMS_PER_STATUS = 8
PROMPT_CLAIM_CHARS = 300
RECENT_COUNTEREXAMPLES = 6
STATUS_CLAIM_CHARS = 110
FEEDBACK_ITEM_CHARS = 400
TEAM_AUTHOR_PREFIX = "team:"
PARSER_NOTE_PREFIX = "Parser: "
REFUTED_BY_PREFIX = "refuted by:"
UNPINNED_MARKER = "(Verifier nicht gepinnt)"
TOOL_HASH_PREFIX = 12
QC_ROWS_SHOWN = 8
MAX_QC_QUBITS = 4096  # wie MAX_CANDIDATE_QUBITS des Richters
BASELINE_LABEL = "Basis"


def _short(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 3] + "..."


def counterexample_line(cx: dict[str, Any]) -> str:
    where = cx.get("where") or (f"x={cx['x']}" if cx.get("x") is not None else "-")
    return f"[{cx.get('property', '?')}] {where}: {cx.get('detail', '')}"


def evaluations(events: Iterable[Event]) -> list[Event]:
    return [e for e in events if e.get("kind") == EV_EVALUATION]


def vetoes(events: Iterable[Event]) -> dict[str, str]:
    """Kennung -> Begründung aller (beratenden) Kritiker-Vetos."""
    return {
        str(e.get("claim_id")): str(e.get("reason", ""))
        for e in events
        if e.get("kind") == EV_CRITIQUE and e.get("veto")
    }


def evaluation_line(e: Event) -> str:
    """Kurzurteil des Richters aus einem Protokollereignis."""
    if e.get("no_change"):
        return (
            "judge: identical to the baseline (no change; not judged, no score) - "
            "transform the baseline ops before writing them"
        )
    if e.get("counterexample"):
        return "judge: " + counterexample_line(e["counterexample"])
    score, delta = e.get("score"), e.get("score_delta")
    text = f"judge: passed ({e.get('contract')})"
    if isinstance(score, (int, float)):
        text += f", score {score:,.2f}"
    if isinstance(delta, (int, float)):
        text += f", delta {delta:+,.2f}"
    return text


def _feedback_item(e: Event) -> str | None:
    kind = e.get("kind")
    if kind == EV_EVALUATION:
        return evaluation_line(e)
    notes = e.get("notes") if isinstance(e.get("notes"), list) else []
    if kind == EV_CRITIQUE and (e.get("veto") or e.get("counterexample") or notes):
        tag = "critic VETO (advisory)" if e.get("veto") else "critic"
        parts = [e.get("reason", ""), e.get("counterexample", ""), *map(str, notes)]
        return f"{tag}: " + " | ".join(str(p) for p in parts if p)
    text = str(e.get("text", ""))
    if kind == EV_NOTE and text.startswith(PARSER_NOTE_PREFIX):
        return text
    return None


def team_feedback(registry: Registry, teams: Iterable[str]) -> dict[str, list[str]]:
    """Rückmeldungen je Team aus dem Protokoll (Richter, Kritiker, Parser) in
    zeitlicher Reihenfolge; überlebt damit auch einen neuen `lab run`."""
    out: dict[str, list[str]] = {t: [] for t in teams}
    owner: dict[str, str] = {}
    for e in registry.events():
        cid = e.get("claim_id")
        if not isinstance(cid, str):
            continue
        author = str(e.get("introduced_by", ""))
        if e.get("kind") == "claim" and author.startswith(TEAM_AUTHOR_PREFIX):
            owner.setdefault(cid, author[len(TEAM_AUTHOR_PREFIX) :])
        team = owner.get(cid)
        item = _feedback_item(e) if team in out else None
        if team is not None and item:
            out[team].append(f"{cid}: {item}"[:FEEDBACK_ITEM_CHARS])
    return out


def _score_text(c: Claim, baseline: float | None) -> str:
    if c.best_score is None:
        return ""
    text = f" score={c.best_score:,.2f}"
    if baseline is not None:
        delta = c.best_score - baseline
        text += f" (Delta {delta:+,.2f}{'' if delta < 0 else ', keine Verbesserung'})"
    return text


def _claim_line(
    c: Claim,
    baseline: float | None,
    vetoed: dict[str, str],
    limit: int,
    marker: str = "",
) -> str:
    refuted_by = [a for a in c.assumptions if a.startswith(REFUTED_BY_PREFIX)]
    extra = f" [{refuted_by[0]}]" if c.status == REFUTED and refuted_by else ""
    veto = " [critic VETO, advisory]" if c.claim_id in vetoed else ""
    body = _short(c.claim + extra, limit)
    return f"{c.claim_id}{_score_text(c, baseline)}{marker}{veto}: {body}"


def verifier_pin_line(pin: Mapping[str, str] | None) -> str:
    """Pin des offiziellen Verifiers (lab.json) als eine Zeile."""
    if not pin:
        return (
            "Verifier nicht gepinnt: ein offizielles PASS zählt nur als experimental "
            "(lab init --verify-cmd ...)"
        )
    return "Verifier gepinnt: " + ", ".join(
        f"{os.path.basename(p)} {sha[:TOOL_HASH_PREFIX]}" for p, sha in pin.items()
    )


def official_markers(
    evals: Iterable[Event], claims: dict[str, Claim], pin: Mapping[str, str] | None
) -> dict[str, str]:
    """Kennung -> Zusatz der Statuszeile: Hash-Präfixe des gepinnten Verifiers bei
    verified, UNPINNED_MARKER bei experimental trotz offiziellem PASS."""
    out: dict[str, str] = {}
    for e in evals:
        cid, off = str(e.get("claim_id")), e.get("official")
        c = claims.get(cid)
        if c is None or not isinstance(off, dict) or not official_passed(off):
            continue
        if c.status == VERIFIED and official_pinned(
            off, e.get("candidate_sha256"), pin
        ):
            tools = off.get("tool_sha256") or {}
            hashes = ",".join(sorted(str(v)[:TOOL_HASH_PREFIX] for v in tools.values()))
            out[cid] = f" [Verifier sha256 {hashes}]"
        elif c.status == EXPERIMENTAL and cid not in out:
            out[cid] = " " + UNPINNED_MARKER
    return out


QCPoint = tuple[int, float, str]  # (Q, C, Kennung oder BASELINE_LABEL)


def qc_points(evals: Iterable[Event]) -> list[tuple[int, float, str, float]]:
    """(Q, C = Score/Q, Kennung, Score) je bestandenem Kandidaten (erster je Hash);
    nur vom Richter berechnete, begrenzte Werte."""
    seen: set[str] = set()
    out = []
    for e in evals:
        q = (e.get("metrics") or {}).get("q")
        score, sha = e.get("score"), str(e.get("candidate_sha256"))
        if not e.get("passed") or e.get("no_change") or sha in seen:
            continue
        if not isinstance(q, int) or not 0 < q <= MAX_QC_QUBITS:
            continue
        if not isinstance(score, (int, float)):
            continue
        seen.add(sha)
        out.append((q, score / q, str(e.get("claim_id")), float(score)))
    return out


def pareto_front(points: Sequence[QCPoint]) -> list[QCPoint]:
    """Nicht dominierte Punkte über (Q, C), beide zu minimieren; nach Q sortiert."""

    def dominated(p: QCPoint) -> bool:
        return any(
            o[0] <= p[0] and o[1] <= p[1] and (o[0] < p[0] or o[1] < p[1])
            for o in points
        )

    return sorted((p for p in points if not dominated(p)), key=lambda p: (p[0], p[1]))


def _baseline_point(events: Iterable[Event]) -> QCPoint | None:
    for e in events:
        if e.get("kind") == EV_LAB and e.get("action") == "baseline":
            q, score = e.get("q"), e.get("baseline_score")
            if isinstance(q, int) and q > 0 and isinstance(score, (int, float)):
                return (q, score / q, BASELINE_LABEL)
    return None


def qc_lines(events: Sequence[Event], evals: Sequence[Event]) -> list[str]:
    """Q, C und Score bestandener Kandidaten (billigste zuerst) und die
    Pareto-Front über (Q, C) mit markierter Basis."""
    pts = qc_points(evals)
    if not pts:
        return []
    lines = ["Q/C bestandener Kandidaten (C = Score/Q, billigste zuerst):"]
    lines += [
        f"  {cid} Q={q} C={c:,.2f} Score={s:,.2f}"
        for q, c, cid, s in sorted(pts, key=lambda p: p[3])[:QC_ROWS_SHOWN]
    ]
    base = _baseline_point(events)
    front = pareto_front(
        [(q, c, cid) for q, c, cid, _ in pts] + ([base] if base else [])
    )
    lines.append(
        "Pareto-Front (Q, C minimal): "
        + " | ".join(f"{label} Q={q} C={c:,.2f}" for q, c, label in front)
    )
    return lines


def best_scores(claims: dict[str, Claim]) -> dict[str, tuple[float, str]]:
    """Bester Score je Status (verified, experimental): (Score, Kennung)."""
    best: dict[str, tuple[float, str]] = {}
    for c in claims.values():
        if c.status in (VERIFIED, EXPERIMENTAL) and c.best_score is not None:
            if c.status not in best or c.best_score < best[c.status][0]:
                best[c.status] = (c.best_score, c.claim_id)
    return best


def prompt_summary(registry: Registry, baseline_score: float | None) -> str:
    """Kompakte Lage für Direktor und Teams: Basis-Score, Behauptungen je Status (die
    widerlegten zuerst, damit sie nicht wiederholt werden), letzte Gegenbeispiele."""
    claims = registry.claims()
    vetoed = vetoes(registry.events())
    lines = [
        "BASELINE score: "
        + (f"{baseline_score:,.2f}" if baseline_score is not None else "unknown"),
        "experimental = passed the local judge (measurement outcomes sampled); only "
        "verified (official verifier PASS) and a negative Delta count as a result.",
    ]
    for status in (REFUTED, VERIFIED, EXPERIMENTAL, HYPOTHESIS):
        group = [c for c in claims.values() if c.status == status]
        if not group:
            continue
        lines.append(f"{status.upper()} claims ({len(group)}):")
        lines += [
            "  - " + _claim_line(c, baseline_score, vetoed, PROMPT_CLAIM_CHARS)
            for c in group[-PROMPT_CLAIMS_PER_STATUS:]
        ]
    cxs = [
        (e.get("claim_id"), e["counterexample"])
        for e in evaluations(registry.events())
        if e.get("counterexample")
    ][-RECENT_COUNTEREXAMPLES:]
    if cxs:
        lines.append("RECENT COUNTEREXAMPLES from the judge:")
        lines += [f"  - {cid}: {counterexample_line(cx)}" for cid, cx in cxs]
    return "\n".join(lines)


def status_report(registry: Registry) -> str:
    """Text von `lab status`."""
    cfg, claims = registry.config(), registry.claims()
    events = list(registry.events())
    evals = evaluations(events)
    vetoed = vetoes(events)
    counts = Counter(c.status for c in claims.values())
    lines = [
        f"Labor: {registry.lab_dir} ({cfg.name}, Basis {cfg.baseline_sha256[:12]})",
        "Behauptungen: "
        + ", ".join(f"{s} {counts.get(s, 0)}" for s in STATUSES)
        + f" | Bewertungen: {len(evals)} | Vetos (beratend): {len(vetoed)}",
    ]
    if registry.corrupt_lines:
        lines.append(f"ACHTUNG: {registry.corrupt_lines} unlesbare Protokollzeile(n)")
    pin = registry.verifier_pin()
    lines.append(verifier_pin_line(pin))
    markers = official_markers(evals, claims, pin)
    base = next((e.get("baseline_score") for e in evals), None)
    if base is not None:
        lines.append(f"Basis-Score: {base:,.2f}")
    best = best_scores(claims)
    for status in (VERIFIED, EXPERIMENTAL):
        if status in best:
            score, cid = best[status]
            delta = f" (Delta {score - base:+,.2f})" if base is not None else ""
            lines.append(f"Bester Score {status}: {score:,.2f}{delta} [{cid}]")
        else:
            lines.append(f"Bester Score {status}: -")
    for status in STATUSES:
        group = [c for c in claims.values() if c.status == status]
        if group:
            lines.append(f"{status}:")
            lines += [
                "  "
                + _claim_line(
                    c, base, vetoed, STATUS_CLAIM_CHARS, markers.get(c.claim_id, "")
                )
                for c in group
            ]
    if vetoed:
        lines.append("Vetos des Kritikers (beratend, der Richter lief trotzdem):")
        lines += [
            f"  {cid}  {_short(reason, STATUS_CLAIM_CHARS)}"
            for cid, reason in vetoed.items()
        ]
    cxs = [e for e in evals if e.get("counterexample")][-RECENT_COUNTEREXAMPLES:]
    if cxs:
        lines.append("Letzte Gegenbeispiele:")
        lines += [
            f"  {e.get('claim_id')}  {counterexample_line(e['counterexample'])}"
            for e in cxs
        ]
    lines += qc_lines(events, evals)
    return "\n".join(lines)
