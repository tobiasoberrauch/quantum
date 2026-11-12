"""Werkbank: die Tools, die der LLM-Agent aufruft. Jede Änderung wird verifiziert,
bevor sie übernommen wird.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from kmx.agent.facts import (
    WINDOW_REACHABLE_CAP,
    reachable_lane_groups,
    taint_before,
    window_entry_facts,
)
from kmx.agent.hotspots import HOTSPOT_FINDERS, HOTSPOT_KIND_ERROR
from kmx.agent.rewrite import (
    prove_window,
    rewrite_rejection,
    rewrite_shape_error,
    static_window_cost,
    window_dead_bits,
)
from kmx.agent.state_cache import StateCache
from kmx.agent.tools import TOOL_NAMES, ToolResult
from kmx.cost import compute_metrics
from kmx.domains import LaneVector, first_lane
from kmx.ops import (
    TOFFOLI_LIKE,
    KmxError,
    Op,
    ops_unchanged,
    parse_lines,
    qubit_token,
    register_token,
)
from kmx.profile import profile_segments
from kmx.session import Session
from kmx.simulator import State, push_depths
from kmx.verify.window import (
    EXACT_MAX_VARIABLES,
    check_context,
    exact_keys,
    off_grid_phase,
)

HOTSPOT_LIMIT_MAX = 50
WINDOW_MAX_SPAN = 300  # größte Differenz end - start, die analyze_window annimmt
# bis zu so vielen erreichbaren Zuständen wird die Liste ausgegeben
WINDOW_STATE_LIST_MAX = 24
WINDOW_FACTS_MAX = 60
WINDOW_CLEAN_ANCILLAS_MAX = 8
WINDOW_SAMPLE_HINT = (
    "Fakten stammen aus der Stichprobe; beim Einreichen wird auf der ganzen Domäne "
    "geprüft."
)
# Rundung der mittleren Toffoli-Kosten vor dem Vergleich (Gleitkomma-Rauschen)
REWRITE_COST_DECIMALS = 9
REWRITE_RATIONALE_MAX = 160
REWRITE_SHIFT_HINT = "Indizes hinter dem Fenster haben sich verschoben."
NOTE_MAX_CHARS = 500
OVERVIEW_PROFILE_ROWS = 15
OVERVIEW_NOTES = 10
READ_LINES_DEFAULT = 60
READ_LINES_MAX = 200
HOTSPOT_LIMIT_DEFAULT = 15
CONTEXT_ROUNDS_DEFAULT = 4
ROLLBACK_AUDIT_ENTRY = (
    "[ROLLBACK] End-to-End-Prüfung schlug fehl; letzter Schritt zurückgenommen"
)

# (Toffoli/Shot gerundet, statische Toffoli, Instruktionen); vergleichbar als Tupel
WindowCost = tuple[float, int, int]


class Workbench:
    """Werkzeuge, die der LLM-Agent aufruft. Jede Änderung wird verifiziert,
    bevor sie übernommen wird. Die Tool-Methoden tragen die Namen aus TOOLS."""

    def __init__(
        self,
        session: Session,
        context_rounds: int = CONTEXT_ROUNDS_DEFAULT,
        exact_only: bool = False,
    ) -> None:
        self.session = session
        self.rounds = context_rounds
        # nur Beweise über ALLE Belegungen annehmen (keine Don't-Cares)
        self.exact_only = exact_only
        self.states = StateCache(session)
        self.undo_stack: list[list[Op]] = []
        self.notes: list[str] = []
        self.accepted = 0
        self.finished: str | None = None

    # ---- lesende Tools ----
    def overview(self) -> ToolResult:
        """Tool: Kennzahlen des aktuellen Stands und des Originals, Register,
        Toffoli-Profil und letzte Notizen."""
        s = self.session
        return {
            "stand": s.current_status_line,
            "original": compute_metrics(s.orig).summary(),
            "register": {
                s.layout.names.get(r, register_token(r)): len(t)
                for r, t in s.layout.registers.items()
            },
            "domäne": s.dom.label,
            "angenommene_rewrites": self.accepted,
            "profil_top": profile_segments(s.ops, OVERVIEW_PROFILE_ROWS),
            "notizen": self.notes[-OVERVIEW_NOTES:],
        }

    def read_lines(self, start: int, count: int = READ_LINES_DEFAULT) -> ToolResult:
        """Tool: Instruktionen ab Index `start` (höchstens READ_LINES_MAX),
        jeweils mit ihrem Index."""
        ops = self.session.ops
        start = max(0, min(start, len(ops)))
        end = min(len(ops), start + max(1, min(count, READ_LINES_MAX)))
        return {
            "gesamt": len(ops),
            "zeilen": [f"{i}: {ops[i].fmt()}" for i in range(start, end)],
        }

    def find_hotspots(
        self, kind: str = "runs", limit: int = HOTSPOT_LIMIT_DEFAULT
    ) -> ToolResult:
        """Tool: lohnende Stellen der Art `kind` (siehe HOTSPOT_FINDERS), beste
        zuerst."""
        # nur Zeichenketten nachschlagen: ein unhashbares JSON-Argument ist eine
        # ungültige Art, kein Absturz
        finder = HOTSPOT_FINDERS.get(kind) if isinstance(kind, str) else None
        if finder is None:
            return {"fehler": HOTSPOT_KIND_ERROR}
        s = self.session
        hits = finder(s.ops, s.layout, s.sample_dom)
        return {
            "art": kind,
            "treffer": len(hits),
            "liste": hits[: max(1, min(limit, HOTSPOT_LIMIT_MAX))],
        }

    def analyze_window(self, start: int, end: int) -> ToolResult:
        """Tool: Zeilen des Fensters [start, end] und was die Stichprobe über seine
        Qubits am Eingang weiß (Fakten, erreichbare Zustände, freie saubere Ancillas, ob
        ein exakter Beweis in Reichweite ist).
        """
        ops = self.session.ops
        if not (0 <= start <= end < len(ops)):
            return {"fehler": f"Indizes außerhalb 0..{len(ops) - 1}"}
        if end - start > WINDOW_MAX_SPAN:
            return {"fehler": f"Fenster zu groß (max. {WINDOW_MAX_SPAN} Instruktionen)"}
        window = ops[start : end + 1]
        entry = self.states.state_at(start)
        tainted = taint_before(ops, start).random_qubits
        qubits = sorted({q for o in window for q in o.qs})
        vec = {q: entry.q.get(q, 0) for q in qubits}
        facts = window_entry_facts(qubits, vec, tainted, entry.all_lanes)
        reach, states = self._reachable_summary(qubits, vec, entry.all_lanes)
        depths = push_depths(ops)
        clean = self._clean_ancillas(entry, qubits, tainted)
        exact_vars = len(exact_keys(window, window, depths[start]))
        return {
            "zeilen": [f"{start + i}: {o.fmt()}" for i, o in enumerate(window)],
            "qubits": [qubit_token(q) for q in qubits],
            "toffoli": sum(o.name in TOFFOLI_LIKE for o in window),
            "bedingungstiefe_am_eingang": depths[start],
            "fakten_am_eingang": facts[:WINDOW_FACTS_MAX],
            "erreichbare_zustände": reach,
            "von_möglichen": f"2^{len(qubits)}",
            "zustandsliste(q-Reihenfolge wie 'qubits')": states,
            "freie_saubere_ancillas": [
                qubit_token(q) for q in clean[:WINDOW_CLEAN_ANCILLAS_MAX]
            ],
            "exakter_beweis_möglich": exact_vars <= EXACT_MAX_VARIABLES,
            "hinweis": WINDOW_SAMPLE_HINT,
        }

    @staticmethod
    def _reachable_summary(
        qubits: Sequence[int], vec: dict[int, LaneVector], all_lanes: LaneVector
    ) -> tuple[int | str, list[str] | None]:
        """(Zahl erreichbarer Zustände, bei Überlauf als ">N"; Zustände als Bitstrings
        in der Reihenfolge von `qubits`, falls es wenige sind)."""
        groups = reachable_lane_groups(qubits, vec, all_lanes)
        if len(groups) > WINDOW_REACHABLE_CAP:
            return f">{len(groups)}", None
        if len(groups) > WINDOW_STATE_LIST_MAX:
            return len(groups), None
        states = [
            "".join(str((vec[q] >> first_lane(group)) & 1) for q in qubits)
            for group in groups
        ]
        return len(groups), states

    def _clean_ancillas(
        self, entry: State, qubits: Sequence[int], tainted: set[int]
    ) -> list[int]:
        """Scratch-Qubits außerhalb des Fensters, die am Eingang überall |0> und
        messunabhängig sind."""
        s = self.session
        return [
            q
            for q in range(compute_metrics(s.ops).num_qubits)
            if q not in s.layout.pinned
            and q not in qubits
            and entry.q.get(q, 0) == 0
            and q not in tainted
        ]

    # ---- ändernde Tools ----
    def propose_rewrite(
        self,
        start: int,
        end: int,
        new_lines: list[str],
        rationale: str = "",
        neutral_ok: bool = False,
    ) -> ToolResult:
        """Tool: ersetzt das Fenster [start, end] durch `new_lines`, wenn die Kosten
        sinken und der Verifier zustimmt.

        Reihenfolge: statische Vorbedingungen, Kostenvergleich auf der Stichprobe, dann
        der Beweis (exakt über alle Belegungen, sonst kontextuell auf der ganzen
        Domäne). `neutral_ok` lässt auch kostengleiche Fenster zu, nie aber solche mit
        mehr Toffoli pro Shot."""
        s, ops = self.session, self.session.ops
        orig_w, cand_w, rejection = self._parse_rewrite(start, end, new_lines)
        if rejection is not None:
            return rejection
        depths = push_depths(ops)
        dead = window_dead_bits(ops, end, orig_w, cand_w, s.layout, depths)
        rough = off_grid_phase((*orig_w, *cand_w))
        if rough is not None:
            return rewrite_rejection(
                f"{rough.fmt()!r} liegt nicht auf dem 2^-127-Phasenraster; "
                "ein solches Fenster lässt sich nicht bitgenau vergleichen"
            )
        sample_ok, sample_msg, (c_old, c_new) = check_context(
            self.states.state_at(start), orig_w, cand_w, dead, s.sample_dom, self.rounds
        )
        cost_old = (round(c_old, REWRITE_COST_DECIMALS), *static_window_cost(orig_w))
        cost_new = (round(c_new, REWRITE_COST_DECIMALS), *static_window_cost(cand_w))
        if not self._cost_gate(cost_old, cost_new, neutral_ok):
            return rewrite_rejection(
                f"keine Kostensenkung: Toffoli/Shot {c_old:.3f} -> {c_new:.3f}, "
                f"statisch {cost_old[1]} -> {cost_new[1]}"
            )
        proof, rejection = prove_window(
            orig_w,
            cand_w,
            dead,
            depths[start],
            (sample_ok, sample_msg),
            self.exact_only,
            lambda: self.states.state_at(start, exhaustive=True),
            s.dom,
            self.rounds,
        )
        if proof is None:
            return rejection
        self._apply_rewrite(start, end, cand_w)
        s.record(
            f"[REWRITE] idx {start}..{end}: Toffoli {cost_old[1]} -> {cost_new[1]} "
            f"({c_old:.2f} -> {c_new:.2f}/Shot) | "
            f"{rationale[:REWRITE_RATIONALE_MAX]} | {proof}"
        )
        return {
            "accepted": True,
            "message": proof,
            "neue_länge": len(s.ops),
            "hinweis": REWRITE_SHIFT_HINT,
        }

    def _parse_rewrite(
        self, start: int, end: int, new_lines: list[str]
    ) -> tuple[list[Op], list[Op], ToolResult | None]:
        """Statische Vorprüfung: (Originalfenster, Kandidat, None) oder eine
        Ablehnung wegen Indizes, Syntax oder Fensterform."""
        ops = self.session.ops
        if not (0 <= start <= end < len(ops)):
            return [], [], rewrite_rejection(f"Indizes außerhalb 0..{len(ops) - 1}")
        orig_w = ops[start : end + 1]
        try:
            cand_w = parse_lines(new_lines)
        except KmxError as e:
            return orig_w, [], rewrite_rejection(f"Syntaxfehler: {e}")
        shape_error = rewrite_shape_error(ops, orig_w, cand_w)
        if shape_error is not None:
            return orig_w, cand_w, rewrite_rejection(shape_error)
        return orig_w, cand_w, None

    @staticmethod
    def _cost_gate(
        cost_old: WindowCost, cost_new: WindowCost, neutral_ok: bool
    ) -> bool:
        """Mehr Toffoli (pro Shot oder statisch) nie; Gleichstand nur mit
        `neutral_ok`."""
        worse = cost_new[:2] > cost_old[:2]
        return not (worse or (not neutral_ok and cost_new >= cost_old))

    def _apply_rewrite(self, start: int, end: int, cand_w: list[Op]) -> None:
        """Übernimmt den bewiesenen Kandidaten (rücknehmbar)."""
        s = self.session
        self.undo_stack.append(list(s.ops))
        s.ops = s.ops[:start] + cand_w + s.ops[end + 1 :]
        self.states.invalidate(start)
        self.accepted += 1

    def run_passes(self) -> ToolResult:
        """Tool: deterministische Pässe der Sitzung; ein geänderter Stand
        wird rücknehmbar gemacht."""
        s = self.session
        before = list(s.ops)
        summary = s.run_passes()
        if not ops_unchanged(before, s.ops):
            self.undo_stack.append(before)
            self.states.invalidate(0)
        return {"zusammenfassung": summary, "stand": s.current_status_line}

    def full_check(self) -> ToolResult:
        """Tool: End-to-End-Prüfung gegen das Original; schlägt sie fehl, wird
        schrittweise zurückgerollt."""
        s = self.session
        ok, msg = s.final_check()
        # sollte nie passieren; zur Sicherheit zurückrollen (nur ins Audit, ohne Log)
        while not ok and self.undo_stack:
            s.ops = self.undo_stack.pop()
            self.states.invalidate(0)
            ok, msg = s.final_check()
            s.audit.append(ROLLBACK_AUDIT_ENTRY)
        return {"ok": ok, "meldung": msg, "stand": s.current_status_line}

    def undo(self) -> ToolResult:
        """Tool: nimmt die letzte angenommene Änderung (Rewrite
        oder Pass-Lauf) zurück."""
        if not self.undo_stack:
            return {"ok": False, "meldung": "nichts zum Zurücknehmen"}
        self.session.ops = self.undo_stack.pop()
        self.states.invalidate(0)
        return {"ok": True, "länge": len(self.session.ops)}

    def note(self, text: str) -> ToolResult:
        """Tool: hält eine Erkenntnis im gemeinsamen Notizbuch fest."""
        self.notes.append(text[:NOTE_MAX_CHARS])
        return {"ok": True}

    def finish(self, summary: str = "") -> ToolResult:
        """Tool: beendet die laufende Agentensitzung."""
        self.finished = summary or "fertig"
        return {"ok": True}

    def dispatch(self, name: str, args: dict[str, Any]) -> ToolResult:
        """Ruft das Tool `name` mit den Argumenten des Modells auf; Fehler werden zur
        Antwort statt zum Absturz."""
        if name not in TOOL_NAMES:
            return {"fehler": f"unbekanntes Tool {name}"}
        try:
            return getattr(self, name)(**args)
        except TypeError as e:
            return {"fehler": f"falsche Argumente für {name}: {e}"}
        # Tool-Fehler gehen als Rückmeldung ans Modell, nicht als Absturz: die
        # LLM-Grenze darf die Pipeline nie abbrechen
        except Exception as e:  # noqa: BLE001
            return {"fehler": f"{type(e).__name__}: {e}"}
