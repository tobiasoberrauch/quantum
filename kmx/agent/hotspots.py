"""Hotspot-Suche für den Agenten (Tool find_hotspots): lohnende Stellen je Art, beste
zuerst."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Sequence
from typing import Any

from kmx.domains import Domain
from kmx.layout import Layout
from kmx.ops import META_OPS, TOFFOLI_LIKE, Op, OpKey, is_plain_xt, qubit_token
from kmx.passes.repack import lifetimes_of, scratch_peak, trace_touches
from kmx.profile import segment_path_at
from kmx.simulator import push_depths

# Ein Treffer als JSON-Objekt (Schlüssel gehen so an das Modell)
Hotspot = dict[str, Any]
# (aktueller Stand, Layout, Stichproben-Domäne) -> Treffer
HotspotFinder = Callable[[Sequence[Op], Layout, Domain], list[Hotspot]]

# so viele CCX-Indizes einer Gruppe werden dem Modell gezeigt
HOTSPOT_RUN_INDEX_PREVIEW = 12
HOTSPOT_PAIR_MAX_DISTANCE = 40
HOTSPOT_DENSE_WINDOW = 40
# so viele der längsten Lebensdauern an der Qubit-Spitze werden gezeigt
HOTSPOT_PEAK_LIFETIMES = 12


def hotspot_ccx_runs(ops: Sequence[Op], depths: Sequence[int]) -> list[Hotspot]:
    """Gruppen mehrerer unbedingter CCX auf dasselbe Ziel, zwischen denen
    das Ziel nicht gelesen wird.

    Eine offene Gruppe endet, sobald ihr Ziel als Kontrolle eines schlichten X-artigen
    Gatters oder von irgendeiner anderen Instruktion berührt wird. Größte Gruppen
    zuerst, bei Gleichstand die kompakteren.
    """
    open_runs: dict[int, list[int]] = {}
    closed: list[list[int]] = []
    for i, o in enumerate(ops):
        if o.name in META_OPS or not o.qs:
            continue
        plain = is_plain_xt(o, depths[i])
        for q in o.qs[:-1] if plain else o.qs:
            run = open_runs.pop(q, None)
            if run and len(run) > 1:
                closed.append(run)
        if plain and o.name == "CCX":
            open_runs.setdefault(o.qs[-1], []).append(i)
    closed += [run for run in open_runs.values() if len(run) > 1]
    closed.sort(key=lambda run: (-(len(run)), run[-1] - run[0]))
    return [
        {
            "ziel": qubit_token(ops[run[0]].qs[-1]),
            "ccx_indizes": run[:HOTSPOT_RUN_INDEX_PREVIEW],
            "anzahl": len(run),
            "spanne": run[-1] - run[0] + 1,
        }
        for run in closed
    ]


def hotspot_ccx_pairs(ops: Sequence[Op]) -> list[Hotspot]:
    """Identische unbedingte CCX-Tripel in kurzer Distanz, engste Paare zuerst."""
    positions: dict[OpKey, list[int]] = defaultdict(list)
    for i, o in enumerate(ops):
        if o.name == "CCX" and o.cond is None:
            positions[o.key()].append(i)
    hits: list[Hotspot] = []
    for indices in positions.values():
        for a, b in zip(indices, indices[1:], strict=False):
            if b - a <= HOTSPOT_PAIR_MAX_DISTANCE:
                hits.append(
                    {"gatter": ops[a].fmt(), "start": a, "ende": b, "distanz": b - a}
                )
    hits.sort(key=lambda hit: hit["distanz"])
    return hits


def hotspot_dense_windows(ops: Sequence[Op]) -> list[Hotspot]:
    """Halb überlappende Fenster fester Breite, absteigend nach Toffoli-Zahl (Fenster
    ohne Toffoli entfallen)."""
    width = HOTSPOT_DENSE_WINDOW
    prefix = [0]
    for o in ops:
        prefix.append(prefix[-1] + (o.name in TOFFOLI_LIKE))
    scored = sorted(
        (
            (prefix[min(len(ops), i + width)] - prefix[i], i)
            for i in range(0, len(ops), width // 2)
        ),
        reverse=True,
    )
    return [
        {"start": i, "ende": min(len(ops), i + width) - 1, "toffoli": count}
        for count, i in scored
        if count
    ]


def hotspot_conditional_toffolis(
    ops: Sequence[Op], depths: Sequence[int]
) -> list[Hotspot]:
    """Toffoli-artige Gatter unter klassischer Bedingung (if bN oder innerhalb eines
    PUSH_CONDITION-Blocks)."""
    return [
        {"idx": i, "gatter": o.fmt(), "tiefe": depths[i]}
        for i, o in enumerate(ops)
        if o.name in TOFFOLI_LIKE and (o.cond is not None or depths[i])
    ]


def hotspot_qubit_peak(
    ops: Sequence[Op], layout: Layout, sample_dom: Domain
) -> list[Hotspot]:
    """Wo liegt die Scratch-Qubit-Spitze (auf der Stichprobe), und welche
    Lebensdauern tragen sie (längste zuerst)?"""
    lifetimes, _ = lifetimes_of(ops, trace_touches(ops, layout, sample_dom))
    peak, peak_idx = scratch_peak(lifetimes)
    peak_idx = min(peak_idx, len(ops) - 1)
    carriers = sorted(
        ((b - a, q, a, b) for a, b, q, _ in lifetimes if a <= peak_idx <= b),
        reverse=True,
    )
    return [
        {
            "spitze_bei_idx": peak_idx,
            "scratch_gleichzeitig": peak,
            "segment": segment_path_at(ops, peak_idx),
            "längste_lebensdauern": [
                {"qubit": qubit_token(q), "von": a, "bis": b}
                for _, q, a, b in carriers[:HOTSPOT_PEAK_LIFETIMES]
            ],
        }
    ]


# Art -> Suche, in der Reihenfolge des Tool-Schemas (enum von find_hotspots)
HOTSPOT_FINDERS: dict[str, HotspotFinder] = {
    "runs": lambda ops, _layout, _dom: hotspot_ccx_runs(ops, push_depths(ops)),
    "pairs": lambda ops, _layout, _dom: hotspot_ccx_pairs(ops),
    "dense": lambda ops, _layout, _dom: hotspot_dense_windows(ops),
    "peak": hotspot_qubit_peak,
    "conditional": lambda ops, _layout, _dom: hotspot_conditional_toffolis(
        ops, push_depths(ops)
    ),
}
HOTSPOT_KINDS: tuple[str, ...] = tuple(HOTSPOT_FINDERS)
HOTSPOT_KIND_ERROR = (
    f"kind muss {', '.join(HOTSPOT_KINDS[:-1])} oder {HOTSPOT_KINDS[-1]} sein"
)
