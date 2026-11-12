"""Kompaktes Dossier für die Teams: Kennzahlen der Basis (Q, Toffoli-Mittel, C, exakter
Score), die teuersten Toffoli-Stellen der Basis und der beste bisherige Kandidat.

Die Basis stammt vom Betreiber und gilt als vertrauenswürdig; ihr Teil wird einmal je
Lauf berechnet (`baseline_dossier`). Vom besten Kandidaten erscheinen nur Werte, die
der Richter nach seinen Schranken berechnet hat (Score, Q). Das ganze Dossier ist auf
DOSSIER_MAX_CHARS Zeichen begrenzt.
"""

from __future__ import annotations

from kmx.cost import compute_metrics
from kmx.lab.claims import EV_EVALUATION, EXPERIMENTAL, VERIFIED, safe_text
from kmx.lab.registry import Registry
from kmx.lab.report import best_scores
from kmx.profile import profile_segments
from kmx.session import Session

DOSSIER_MAX_CHARS = 1500
DOSSIER_HOTSPOTS = 5
DOSSIER_SEGMENT_CHARS = 80
DOSSIER_HEADER = "BASELINE DOSSIER (operator-supplied baseline; C = score / Q):"


def _num(x: float | None) -> str:
    return f"{x:,.2f}" if x is not None else "unknown"


def baseline_dossier(
    session: Session, baseline_score: float | None, score_kind: str | None
) -> str:
    """Basis-Teil des Dossiers: Q, Toffoli-Mittel je Shot, C, Score und die
    DOSSIER_HOTSPOTS teuersten Segmente (Indexbereich, Toffoli-Zahl)."""
    m = compute_metrics(session.orig)
    sig = session.orig_sig
    tof = sig.tof_mean if sig is not None else float(m.toffoli)
    c = baseline_score / m.num_qubits if baseline_score and m.num_qubits else None
    lines = [
        DOSSIER_HEADER,
        f"  baseline: Q={m.num_qubits}, Toffoli mean/shot={tof:,.2f} "
        f"(static {m.toffoli}), C={_num(c)}, score={_num(baseline_score)} "
        f"({score_kind or '-'})",
        "  baseline Toffoli hotspots (segment, op index range, Toffoli count):",
    ]
    rows = [r for r in profile_segments(session.orig) if r["toffoli"]]
    for r in rows[:DOSSIER_HOTSPOTS]:
        seg = safe_text(r["segment"], DOSSIER_SEGMENT_CHARS)
        lines.append(f"    - {seg} idx {r['von']}..{r['bis']}: {r['toffoli']} Toffoli")
    return "\n".join(lines)


def _best_q(registry: Registry, cid: str, score: float) -> int | None:
    """Q aus der Richter-Bewertung, die den besten Score der Behauptung belegt."""
    q = None
    for e in registry.events():
        if (
            e.get("kind") == EV_EVALUATION
            and e.get("claim_id") == cid
            and e.get("passed")
            and e.get("score") == score
        ):
            raw = (e.get("metrics") or {}).get("q")
            q = raw if isinstance(raw, int) and raw > 0 else q
    return q


def _cap(text: str, limit: int) -> str:
    """Kürzt an einer Zeilengrenze auf höchstens `limit` Zeichen."""
    if len(text) <= limit:
        return text
    cut = text[:limit]
    return cut[: cut.rfind("\n")] if "\n" in cut else cut


def lab_dossier(baseline_part: str, registry: Registry) -> str:
    """Dossier aus dem (zwischengespeicherten) Basis-Teil und dem besten
    verified/experimental-Kandidaten mit Q und C."""
    best = best_scores(registry.claims())
    head = baseline_part.split("\n")
    lines = head[:2]  # Kopf und Kennzahlen der Basis, dann der beste Stand
    for status in (VERIFIED, EXPERIMENTAL):
        if status not in best:
            lines.append(f"  best {status}: -")
            continue
        score, cid = best[status]
        q = _best_q(registry, cid, score)
        qc = f", Q={q}, C={score / q:,.2f}" if q else ""
        lines.append(f"  best {status}: score {score:,.2f}{qc} [{cid}]")
    lines += head[2:]  # Hotspots zuletzt (fallen bei Platzmangel zuerst weg)
    return _cap("\n".join(lines), DOSSIER_MAX_CHARS)
