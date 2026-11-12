#!/usr/bin/env python3
"""
Autonomer Neuro-Symbolischer KI-Agent & Deterministischer Compiler für .kmx Quantenschaltkreise.

Konsolidierte Version (v4) — best-of aus den Vorschlägen v3 / v3.3 / v4:
  - Offizielles Kostenmodell: Q = max(Qubit-Index)+1; nur CCX/CCZ/CSWAP (Toffoli-artig),
    T/TDAG (+ T-artige Z_POW) mit /4 und feine Z_POW mit ROT_WEIGHT zählen; CX/CZ/SWAP/X/Z gratis.
  - Wortparalleler 64-Bit-Verifier mit 128-Bit Bit-Sliced Phasenakkumulator
    (unterstützt X, CX, CCX, SWAP, CSWAP, Z, CZ, CCZ, NEG, T, TDAG, Z_POW).
    <= EXACT_QUBIT_LIMIT aktive Qubits: vollständiger Wahrheitstabellenbeweis (exact=True).
    Darüber: Fuzzing (exact=False) — wird standardmäßig NICHT als Beweis akzeptiert.
  - Deterministische Pässe: starke Op-Pässe aus kmx_agent_kimi.py (bit-/bedingungs-/HMR-aware)
    + eigene 3CX->SWAP-Faltung + exakte Z/T/TDAG/Z_POW-Phasenfusion. Unsichere Legacy-Pässe
    (Dead-End-SWAP, Lifetime-Repack) nur hinter LEGACY_UNSAFE_PASSES=1.
  - Verifier-in-the-Loop: jeder Rewrite wird lokal geprüft; nur exakt bewiesene UND
    kostenreduzierende Züge werden akzeptiert. Optionales OFFICIAL_VERIFY_CMD-Gate vor
    atomarem Write; Kosten-Erhöhung bricht ab.
  - Beam-/Best-first-Suche mit Caches + Geduld; LLM (Default: lokale Weinstadt-KI, keyless)
    memoisiert mit Fast-Fail-Circuit-Breaker.
  - Defensive Eingaben: None/leer/Whitespace crasht nirgends.
  - v4: Differenzkegel-Reduktion (breite Fenster werden exakt statt nur per Fuzzing geprüft),
    O(1)-Lane-Masken, Ziel-XOR-Kommutierung, CCZ-/CSWAP-/Phasenkonjugations-Synthese,
    Qubit-Scope-Sperre für Rewrites, LRU-Metrik-Cache, Suche wird nie teurer als der Start.

Laufbar ohne Netzwerk (LLM per Stub/Env); Regressionstest: `python main.py --selftest`.
"""

import os
import re
import sys
import json
import shlex
import random
import difflib
import hashlib
import subprocess
import tempfile
import urllib.request
import urllib.error
from dataclasses import dataclass
from fractions import Fraction
from collections import defaultdict, Counter, OrderedDict
from typing import List, Dict, Tuple, Set, Optional, Any

# Starke Op-basierte Deterministen-Pässe (bit-/bedingungs-/HMR-Barriere-aware) werden aus
# kmx_agent_kimi.py wiederverwendet (stdlib-only, kein kickmix nötig). Fallback auf die
# line-basierten Pässe, falls die Datei nicht vorhanden ist.
try:
    import kmx_agent_fable as _kimi
except Exception:  # pragma: no cover - Datei optional
    try:
        import kmx_agent_kimi as _kimi   # Vorgänger mit gleicher Parser-/Pass-API
    except Exception:
        _kimi = None


# =====================================================================
# 1. KOSTENMODELL & METRIKEN
# =====================================================================

# Gewicht pro FEINER Z_POW-Rotation in Toffoli-Äquivalenten. Offiziell =
# (0.56*log2(1/eps)+5.3)/4; bei eps~2.4e-13 (unser a15b0d73) ~7.2. Per Env überschreibbar.
ROT_WEIGHT = float(os.environ.get("COST_ROT_WEIGHT", "7.2"))

_RE_QUBIT = re.compile(r"\bq(\d+)\b")
_RE_QTOKEN = re.compile(r"^q(0|[1-9]\d*)$")   # kanonisch: q01 wäre textuell != q1
_RE_CX = re.compile(r"^CX (q\d+) (q\d+)$")
_RE_CZ = re.compile(r"^CZ (q\d+) (q\d+)$")
_RE_JSON_ARRAY = re.compile(r"\[.*?\]", re.DOTALL)

_ZPOW_CACHE: Dict[str, Tuple[Tuple[int, ...], int, int]] = {}
_METRICS_CACHE: "OrderedDict[str, CircuitMetrics]" = OrderedDict()
_METRICS_CACHE_LIMIT = max(16, int(os.environ.get("METRICS_CACHE_SIZE", "2048")))


def _zpow_full(exp: str) -> Tuple[Tuple[int, ...], int, int]:
    """Exponent (Halbdrehungen) -> (gesetzte Bit-Ebenen 2^-127, Stufe, exakter 128-Bit-Wert).
    Stufe: 0 = Clifford (frei), 2 = T-artig (zählt als T/4), 3 = feine Rotation (voller Kosten).
    Defensiv: None/leer/ungültig -> ((), 0, 0)."""
    exp = (exp or "").strip()
    if not exp:
        return ((), 0, 0)
    hit = _ZPOW_CACHE.get(exp)
    if hit is None:
        try:
            e = round(Fraction(exp) * (1 << 127)) % (1 << 128)
        except (ValueError, ZeroDivisionError):
            e = 0
        planes = tuple(j for j in range(128) if (e >> j) & 1)
        level = 0 if e % (1 << 126) == 0 else (2 if e % (1 << 125) == 0 else 3)
        hit = (planes, level, e)
        _ZPOW_CACHE[exp] = hit
    return hit


def zpow_info(exp: str) -> Tuple[Tuple[int, ...], int]:
    """Öffentliche API: (Bit-Ebenen, Stufe). Defensiv: None/leer -> ((), 0)."""
    planes, level, _ = _zpow_full(exp)
    return planes, level


@dataclass(frozen=True)
class CircuitMetrics:
    total_lines: int
    num_qubits: int          # offizielles Q = max(Qubit-Index)+1
    max_qubit_id: int
    ccx_count: int
    ccz_count: int
    cswap_count: int
    cx_count: int
    cz_count: int
    swap_count: int
    x_count: int
    z_family_count: int
    hmr_count: int
    z_pow_count: int = 0     # alle Z_POW (nur Reporting)
    t_like_count: int = 0    # T/TDAG-Gates
    zpow_t_like: int = 0     # Z_POW auf T-Stufe (zählen als T/4)
    zpow_rot: int = 0        # Z_POW auf feiner Stufe (voller Kosten)

    @property
    def toffoli_cost(self) -> int:
        return self.ccx_count + self.ccz_count + self.cswap_count

    @property
    def inner_cost(self) -> float:
        """Kosten OHNE Qubit-Multiplikator. Toffoli hier STATISCH (der MEAN pro Shot benötigt
        den Vollsimulator aus kmx_agent_kimi.py); feine Rotationen mit ROT_WEIGHT, T-artiges
        (T/TDAG + Z_POW-T-Stufe) mit /4, Clifford-Z_POW gratis."""
        t_total = self.t_like_count + self.zpow_t_like
        return self.toffoli_cost + t_total / 4.0 + ROT_WEIGHT * self.zpow_rot

    @property
    def real_cost(self) -> float:
        """Kosten-Schätzung: nq * inner_cost."""
        return self.num_qubits * self.inner_cost

    def summary(self) -> str:
        return (
            f"Qubits: {self.num_qubits} (max q{self.max_qubit_id}) | "
            f"Toffolis (CCX+CCZ+CSWAP): {self.toffoli_cost} "
            f"({self.ccx_count}+{self.ccz_count}+{self.cswap_count}) | "
            f"Rot(fein): {self.zpow_rot} | T-artig: {self.t_like_count + self.zpow_t_like} | "
            f"CX: {self.cx_count} | CZ: {self.cz_count} | SWAP: {self.swap_count} | "
            f"X: {self.x_count} | Zeilen: {self.total_lines}"
        )


def _exact_decimal(x: Fraction) -> str:
    """Exakte Dezimaldarstellung (kein float), falls endlich (Nenner = 2^a*5^b); sonst 'p/q'.
    Die kickmix-Parser akzeptieren nur dezimale Exponenten."""
    den, places = x.denominator, 0
    while den % 10 == 0:
        den //= 10
        places += 1
    for p in (2, 5):
        while den % p == 0:
            den //= p
            places += 1
    if den != 1:
        return str(x)   # periodisch (z. B. 1/3): nur als Bruch exakt
    if places == 0:
        return str(x.numerator)
    digits = str(abs(x.numerator) * 10 ** places // x.denominator).rjust(places + 1, "0")
    return ("-" if x < 0 else "") + f"{digits[:-places]}.{digits[-places:]}".rstrip("0").rstrip(".")


def _clean_lines(lines: Optional[List[str]]) -> List[str]:
    """Defensiv: None/leer -> []; nur nicht-leere, nicht-Kommentar-Zeilen (gestrippt)."""
    out: List[str] = []
    for l in (lines or []):
        if isinstance(l, str):
            s = l.strip()
            if s and not s.startswith("#"):
                out.append(s)
    return out


def _operand_qubits(toks: List[str]) -> Set[int]:
    """Qubit-Indizes der Operanden (toks[1:]) vor einer 'if'-Bedingung bzw. einem Kommentar."""
    qubits: Set[int] = set()
    for token in toks[1:]:
        if token == "if" or token.startswith("#"):
            break
        token = token.strip("[],")
        if token.startswith("q") and token[1:].isdigit():
            qubits.add(int(token[1:]))
    return qubits


def compute_metrics(lines: Optional[List[str]]) -> CircuitMetrics:
    """Berechnet Gatter-Metriken inkl. exakter Z_POW-Klassifikation, CSWAP und offiziellem
    Q=max+1. Qubit-Operanden werden tokenweise gelesen (Kommentare/Registerzeilen zählen
    nicht als Qubits). Defensiv: None/leer -> leere Metriken. Ergebnis wird gecacht."""
    clean = _clean_lines(lines)
    if not clean:
        return CircuitMetrics(0, 0, -1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
    key = hashlib.sha256("\n".join(clean).encode("utf-8")).hexdigest()
    cached = _METRICS_CACHE.get(key)
    if cached is not None:
        _METRICS_CACHE.move_to_end(key)
        return cached

    qubits: Set[int] = set()
    counts: Counter = Counter()
    zpow_t_like = zpow_rot = 0
    for l in clean:
        toks = l.split()
        if not toks:
            continue
        op = toks[0]
        counts[op] += 1
        qubits |= _operand_qubits(toks)
        if op == "Z_POW" and len(toks) >= 3:
            lvl = _zpow_full(toks[2])[1]
            if lvl == 2:
                zpow_t_like += 1
            elif lvl == 3:
                zpow_rot += 1
    max_qubit = max(qubits) if qubits else -1
    m = CircuitMetrics(
        total_lines=len(clean),
        num_qubits=max_qubit + 1,
        max_qubit_id=max_qubit,
        ccx_count=counts["CCX"],
        ccz_count=counts["CCZ"],
        cswap_count=counts["CSWAP"],
        cx_count=counts["CX"],
        cz_count=counts["CZ"],
        swap_count=counts["SWAP"],
        x_count=counts["X"],
        z_family_count=counts["Z"] + counts["Z_POW"] + counts["NEG"],
        hmr_count=counts["HMR"],
        z_pow_count=counts["Z_POW"],
        t_like_count=counts["T"] + counts["TDAG"],
        zpow_t_like=zpow_t_like,
        zpow_rot=zpow_rot,
    )
    _METRICS_CACHE[key] = m
    while len(_METRICS_CACHE) > _METRICS_CACHE_LIMIT:
        _METRICS_CACHE.popitem(last=False)
    return m


def circuit_cost(lines: Optional[List[str]]) -> float:
    """Einziges Kostenmaß für die Suche: nq*(toffoli_like + t/4 + ROT_WEIGHT*z_pow).
    Defensiv: None/leer -> 0.0. CX/CZ/SWAP/X haben keinen Einfluss."""
    return compute_metrics(lines).real_cost


# =====================================================================
# 2. WORTPARALLELER 64-BIT VERIFIER (INKL. 128-BIT BIT-SLICED PHASE)
# =====================================================================

@dataclass(frozen=True)
class VerificationResult:
    """Lokaler Prüfnachweis; ``exact=False`` bedeutet ausdrücklich nur Fuzzing (kein Beweis)."""
    ok: bool
    message: str
    exact: bool = False

    def __iter__(self):
        # Rückwärtskompatibel zu ``ok, msg = verify_equivalence(...)``.
        yield self.ok
        yield self.message


def _proof_accepted(result: VerificationResult) -> bool:
    """Einheitliche Rewrite-Policy: exakt, oder ausdrücklich freigeschaltetes Fuzzing."""
    return result.ok and (
        result.exact or os.environ.get("ALLOW_PROBABILISTIC_REWRITES", "0") == "1"
    )


class BitParallelKMXVerifier:
    """Prüft klassisch-reversible/phasendiagonale .kmx-Teilblöcke lokal auf exakte Äquivalenz.

    Unterstützt X, CX, CCX, SWAP, CSWAP, Z, CZ, CCZ, NEG, T, TDAG und beliebige Z_POW über einen
    64-Spur-parallelen 128-Bit-Ripple-Carry-Phasenakkumulator. Bis EXACT_QUBIT_LIMIT aktiven
    Qubits entsteht ein vollständiger Wahrheitstabellenbeweis (exact=True); darüber ist das
    Ergebnis ausschließlich Fuzzing (exact=False) — kein Ersatz für den offiziellen Gesamtverifier.
    Breite Fenster werden vorher auf ihren Differenzkegel reduziert (_reduce_verification_cone).
    """
    EXACT_QUBIT_LIMIT = int(os.environ.get("EXACT_QUBIT_LIMIT", "12"))   # 2^12 = 64 Wort-Batches
    # Lane-Muster der unteren 6 Adressbits eines 64er-Batches (Bit i von Lane L).
    _LANE_MASKS = (0xAAAAAAAAAAAAAAAA, 0xCCCCCCCCCCCCCCCC, 0xF0F0F0F0F0F0F0F0,
                   0xFF00FF00FF00FF00, 0xFFFF0000FFFF0000, 0xFFFFFFFF00000000)
    SUPPORTED_OPS = {"X", "CX", "CCX", "SWAP", "CSWAP", "Z", "CZ", "CCZ", "NEG", "T", "TDAG", "Z_POW"}
    _ARITY = {"X": 1, "CX": 2, "CCX": 3, "SWAP": 2, "CSWAP": 3,
              "Z": 1, "CZ": 2, "CCZ": 3, "NEG": 0, "T": 1, "TDAG": 1, "Z_POW": 1}
    _MASK64 = (1 << 64) - 1
    _T_PLANES = (125,)                 # T = +1/8 Umdrehung
    _TDAG_PLANES = (125, 126, 127)     # TDAG = -1/8 mod 1

    @classmethod
    def can_verify_window(cls, lines: Optional[List[str]]) -> Tuple[bool, str]:
        for l in (lines or []):
            if not isinstance(l, str):
                continue
            s = l.strip()
            if not s or s.startswith("#"):
                continue
            if " if " in s:
                return False, f"Bedingte Instruktion im Fenster nicht erlaubt: {l}"
            toks = s.split()
            op = toks[0]
            if op not in cls.SUPPORTED_OPS:
                return False, f"Nicht-unterstützte Operation für lokalen Verifier: {op}"
            # Arity + Format der Operanden prüfen (defensiv gegen fehlgeleitete LLM-Antworten).
            if op == "Z_POW":
                if len(toks) != 3 or not _RE_QTOKEN.match(toks[1]):
                    return False, f"Falsche Operanden für Z_POW: {l}"
                try:
                    exact = (Fraction(toks[2]) * (1 << 127)).denominator == 1
                except (ValueError, ZeroDivisionError):
                    return False, f"Ungültiger Z_POW-Winkel: {l}"
                if not exact:
                    # Sonst würde auf 2^-127 gerundet und "exakt" wäre gelogen (z. B. 1e-40 == 0).
                    return False, f"Z_POW-Winkel nicht exakt in 128 Bit darstellbar: {l}"
            else:
                if (len(toks) != 1 + cls._ARITY[op] or len(set(toks[1:])) != cls._ARITY[op]
                        or not all(_RE_QTOKEN.match(t) for t in toks[1:])):
                    return False, f"Falsche Operanden für {op}: {l}"
        return True, "OK"

    @classmethod
    def _compile_window(cls, lines: Optional[List[str]]) -> Tuple[List[Tuple[Any, ...]], bool]:
        """Vorkompiliert Textzeilen einmalig in schnelle Integer-Tupel.
        Gibt (compiled_ops, uses_fine_phase) zurück. (Nur nach can_verify_window aufrufen.)"""
        compiled: List[Tuple[Any, ...]] = []
        uses_fine = False
        for l in (lines or []):
            if not isinstance(l, str):
                continue
            s = l.strip()
            if not s or s.startswith("#"):
                continue
            toks = s.split()
            op = toks[0]
            if op == "Z_POW":
                q = int(toks[1][1:])
                planes, _lvl, _e = _zpow_full(toks[2])
                if not planes:
                    continue
                if planes == (127,):
                    compiled.append(("Z", q))
                else:
                    uses_fine = True
                    compiled.append(("Z_POW", q, planes))
            elif op in ("T", "TDAG"):
                q = int(toks[1][1:])
                uses_fine = True
                compiled.append(("Z_POW", q, cls._T_PLANES if op == "T" else cls._TDAG_PLANES))
            elif op == "NEG":
                compiled.append(("NEG",))
            else:
                qs = tuple(int(t[1:]) for t in toks[1:])
                compiled.append((op, *qs))
        return compiled, uses_fine

    @staticmethod
    def _add_phase_planes(phase_planes: Dict[int, int], mask: int, planes: Tuple[int, ...]) -> None:
        """Addiert einen 128-Bit-Phasenwert (gesetzte Bit-Ebenen) auf allen Spuren, bei denen
        `mask` gesetzt ist (Ripple-Carry-Inkrement um 2^p pro gesetzter Ebene p)."""
        if not mask:
            return
        for p in planes:
            carry = mask
            bit = p
            while carry and bit < 128:
                old = phase_planes.get(bit, 0)
                phase_planes[bit] = old ^ carry
                carry &= old
                bit += 1

    @classmethod
    def simulate_compiled(cls, compiled_ops: List[Tuple[Any, ...]], init_state: Dict[int, int],
                          uses_fine_phase: bool = False) -> Tuple[Dict[int, int], Any]:
        state = dict(init_state or {})
        mask64 = cls._MASK64
        if not uses_fine_phase:
            # Schneller Pfad: nur (+/-1)-Phasen belegen Bit-Ebene 127 (ein 64-Bit-Wort).
            phase = 0
            for ins in compiled_ops:
                op = ins[0]
                if op == "X":
                    state[ins[1]] = state.get(ins[1], 0) ^ mask64
                elif op == "CX":
                    state[ins[2]] = state.get(ins[2], 0) ^ state.get(ins[1], 0)
                elif op == "CCX":
                    state[ins[3]] = state.get(ins[3], 0) ^ (state.get(ins[1], 0) & state.get(ins[2], 0))
                elif op == "SWAP":
                    q1, q2 = ins[1], ins[2]
                    state[q1], state[q2] = state.get(q2, 0), state.get(q1, 0)
                elif op == "CSWAP":
                    c, q1, q2 = ins[1], ins[2], ins[3]
                    diff = (state.get(q1, 0) ^ state.get(q2, 0)) & state.get(c, 0)
                    state[q1] = state.get(q1, 0) ^ diff
                    state[q2] = state.get(q2, 0) ^ diff
                elif op == "Z":
                    phase ^= state.get(ins[1], 0)
                elif op == "CZ":
                    phase ^= state.get(ins[1], 0) & state.get(ins[2], 0)
                elif op == "CCZ":
                    phase ^= state.get(ins[1], 0) & state.get(ins[2], 0) & state.get(ins[3], 0)
                elif op == "NEG":
                    phase ^= mask64
            return state, phase

        # Erweiterter Pfad: 128-Bit Bit-Sliced Phasenakkumulator für T/TDAG/Z_POW/NEG.
        phase_planes: Dict[int, int] = {}
        for ins in compiled_ops:
            op = ins[0]
            if op == "X":
                state[ins[1]] = state.get(ins[1], 0) ^ mask64
            elif op == "CX":
                state[ins[2]] = state.get(ins[2], 0) ^ state.get(ins[1], 0)
            elif op == "CCX":
                state[ins[3]] = state.get(ins[3], 0) ^ (state.get(ins[1], 0) & state.get(ins[2], 0))
            elif op == "SWAP":
                q1, q2 = ins[1], ins[2]
                state[q1], state[q2] = state.get(q2, 0), state.get(q1, 0)
            elif op == "CSWAP":
                c, q1, q2 = ins[1], ins[2], ins[3]
                diff = (state.get(q1, 0) ^ state.get(q2, 0)) & state.get(c, 0)
                state[q1] = state.get(q1, 0) ^ diff
                state[q2] = state.get(q2, 0) ^ diff
            elif op == "Z":
                phase_planes[127] = phase_planes.get(127, 0) ^ state.get(ins[1], 0)
            elif op == "CZ":
                phase_planes[127] = phase_planes.get(127, 0) ^ (state.get(ins[1], 0) & state.get(ins[2], 0))
            elif op == "CCZ":
                phase_planes[127] = phase_planes.get(127, 0) ^ (state.get(ins[1], 0) & state.get(ins[2], 0) & state.get(ins[3], 0))
            elif op == "NEG":
                phase_planes[127] = phase_planes.get(127, 0) ^ mask64
            elif op == "Z_POW":
                cls._add_phase_planes(phase_planes, state.get(ins[1], 0), ins[2])
        norm_planes = {k: v for k, v in phase_planes.items() if v}
        return state, norm_planes

    @classmethod
    def simulate_batch(cls, lines: List[str], init_state: Dict[int, int]) -> Tuple[Dict[int, int], Any]:
        """Abwärtskompatible API für Einzel-Batches."""
        comp, fine = cls._compile_window(lines)
        return cls.simulate_compiled(comp, init_state, fine)

    @classmethod
    def _phase_equal(cls, ph_a: Any, ph_b: Any, use_fine: bool, valid_mask: Optional[int] = None) -> bool:
        if use_fine:
            all_planes = set(ph_a.keys()) | set(ph_b.keys())
            for p in all_planes:
                va = ph_a.get(p, 0)
                vb = ph_b.get(p, 0)
                if valid_mask is not None:
                    va &= valid_mask
                    vb &= valid_mask
                if va != vb:
                    return False
            return True
        if valid_mask is not None:
            return (ph_a ^ ph_b) & valid_mask == 0
        return ph_a == ph_b

    @staticmethod
    def _ins_qubits(ins: Tuple[Any, ...]) -> Tuple[int, ...]:
        op = ins[0]
        if op == "NEG":
            return ()
        if op == "Z_POW":
            return (ins[1],)
        return ins[1:]

    @classmethod
    def _reduce_verification_cone(cls, comp_orig: List[Tuple[Any, ...]], comp_cand: List[Tuple[Any, ...]]
                                  ) -> Tuple[List[Tuple[Any, ...]], List[Tuple[Any, ...]], List[int]]:
        """Reduziert beide Fenster auf ihren Differenzkegel. Alle unterstützten Ops sind unitär:
        (1) L*O*R == L*C*R <=> O == C  -> identisches Präfix/Suffix entfällt.
        (2) Gatter verschiedener Qubit-Zusammenhangskomponenten (über BEIDE Restfolgen gebildet)
            kommutieren, der Operator zerfällt in ein Tensorprodukt; Komponenten mit identischer
            Gatterfolge tragen denselben Faktor bei und entfallen.
        NEG (globale Phase, ohne Qubit) bleibt immer erhalten."""
        start = 0
        end_o, end_c = len(comp_orig), len(comp_cand)
        while start < end_o and start < end_c and comp_orig[start] == comp_cand[start]:
            start += 1
        while end_o > start and end_c > start and comp_orig[end_o - 1] == comp_cand[end_c - 1]:
            end_o -= 1
            end_c -= 1
        rem_o, rem_c = comp_orig[start:end_o], comp_cand[start:end_c]

        parent: Dict[int, int] = {}

        def find(x: int) -> int:
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        for ins in rem_o + rem_c:
            qs = cls._ins_qubits(ins)
            for q in qs:
                parent.setdefault(q, q)
            for q in qs[1:]:
                ra, rb = find(qs[0]), find(q)
                if ra != rb:
                    parent[rb] = ra

        def project(seq: List[Tuple[Any, ...]]) -> Dict[int, List[Tuple[Any, ...]]]:
            out: Dict[int, List[Tuple[Any, ...]]] = defaultdict(list)
            for ins in seq:
                qs = cls._ins_qubits(ins)
                if qs:
                    out[find(qs[0])].append(ins)
            return out

        proj_o, proj_c = project(rem_o), project(rem_c)
        active = {q for q in parent if proj_o.get(find(q), []) != proj_c.get(find(q), [])}

        def keep(seq: List[Tuple[Any, ...]]) -> List[Tuple[Any, ...]]:
            return [ins for ins in seq
                    if ins[0] == "NEG" or cls._ins_qubits(ins)[0] in active]

        return keep(rem_o), keep(rem_c), sorted(active)

    @classmethod
    def verify_equivalence(cls, orig_lines: Optional[List[str]], cand_lines: Optional[List[str]],
                           num_batches: int = 32) -> VerificationResult:
        ok1, msg1 = cls.can_verify_window(orig_lines)
        if not ok1:
            return VerificationResult(False, f"Original-Fenster ungültig: {msg1}")
        ok2, msg2 = cls.can_verify_window(cand_lines)
        if not ok2:
            return VerificationResult(False, f"Kandidaten-Fenster ungültig: {msg2}")

        active: Set[int] = set()
        for l in list(orig_lines or []) + list(cand_lines or []):
            if isinstance(l, str):
                for qm in _RE_QUBIT.findall(l):
                    active.add(int(qm))
        q_list = sorted(active)

        comp_orig, _ = cls._compile_window(orig_lines)
        comp_cand, _ = cls._compile_window(cand_lines)
        scope = ""
        if len(q_list) > cls.EXACT_QUBIT_LIMIT:
            # Zu breit für die Wahrheitstabelle: auf den kausalen Differenzkegel reduzieren.
            comp_orig, comp_cand, q_list = cls._reduce_verification_cone(comp_orig, comp_cand)
            scope = " im Differenzkegel"
        use_fine = any(ins[0] == "Z_POW" for ins in comp_orig + comp_cand)

        # <= EXACT_QUBIT_LIMIT aktive Qubits: vollständige Wahrheitstabelle (100% Beweis).
        if len(q_list) <= cls.EXACT_QUBIT_LIMIT:
            total_states = 1 << len(q_list)
            lane_masks, mask64 = cls._LANE_MASKS, cls._MASK64
            for offset in range(0, total_states, 64):
                valid_lanes = min(64, total_states - offset)
                valid_mask = (1 << valid_lanes) - 1
                # offset ist Vielfaches von 64: Bits < 6 folgen dem Lane-Muster, höhere sind konstant.
                init_state: Dict[int, int] = {
                    q: (lane_masks[bit_idx] & valid_mask) if bit_idx < 6
                    else (valid_mask if (offset >> bit_idx) & 1 else 0)
                    for bit_idx, q in enumerate(q_list)
                }
                out_orig, ph_orig = cls.simulate_compiled(comp_orig, init_state, use_fine)
                out_cand, ph_cand = cls.simulate_compiled(comp_cand, init_state, use_fine)
                if not cls._phase_equal(ph_orig, ph_cand, use_fine, valid_mask):
                    return VerificationResult(False, f"Phasen-Abweichung bei Offset {offset}!")
                for q in q_list:
                    if (out_orig.get(q, 0) ^ out_cand.get(q, 0)) & valid_mask:
                        return VerificationResult(False, f"Wahrheitstabellen-Abweichung auf q{q} bei Offset {offset}!")
            return VerificationResult(
                True, f"Exakt bewiesen über alle 2^{len(q_list)} = {total_states} Basiszustände{scope}.", exact=True)

        # > EXACT_QUBIT_LIMIT: ausschliesslich Zufallstests, niemals als Beweis ausgeben.
        rng = random.Random(42)
        batches = max(1, int(num_batches))
        for batch in range(batches):
            init_state = {q: rng.getrandbits(64) for q in q_list}
            out_orig, ph_orig = cls.simulate_compiled(comp_orig, init_state, use_fine)
            out_cand, ph_cand = cls.simulate_compiled(comp_cand, init_state, use_fine)
            if not cls._phase_equal(ph_orig, ph_cand, use_fine, None):
                return VerificationResult(False, f"Phasen-Mismatch in Batch {batch}!")
            for q in q_list:
                if out_orig.get(q, 0) != out_cand.get(q, 0):
                    return VerificationResult(False, f"Bitvektor-Mismatch auf q{q} in Batch {batch}!")
        return VerificationResult(True, f"Nur Fuzzing: {batches * 64} Zufallsvektoren bestanden; kein exakter Beweis.", exact=False)


# =====================================================================
# 3. DETERMINISTISCHE COMPILER-ENGINE (PÄSSE)
# =====================================================================

class DeterministicKMXEngine:
    """Führt deterministische, äquivalenzerhaltende Optimierungspässe auf .kmx-Listen aus."""

    @staticmethod
    def pass_fold_3cx_to_swap(lines: Optional[List[str]]) -> Tuple[List[str], int]:
        clean = [l for l in (lines or []) if isinstance(l, str) and l.strip()]
        out: List[str] = []
        folded = 0
        i = 0
        n = len(clean)
        while i < n:
            if i + 2 < n:
                m1 = _RE_CX.match(clean[i])
                m2 = _RE_CX.match(clean[i + 1])
                m3 = _RE_CX.match(clean[i + 2])
                if m1 and m2 and m3:
                    a1, b1 = m1.groups()
                    a2, b2 = m2.groups()
                    a3, b3 = m3.groups()
                    if a1 == a3 == b2 and b1 == b3 == a2 and a1 != b1:
                        out.append(f"SWAP {a1} {b1}")
                        folded += 1
                        i += 3
                        continue
            out.append(clean[i])
            i += 1
        return out, folded

    @staticmethod
    def _get_rw_sets(line: str):
        """(X-Menge, Z-Menge, Op, Args, Cond). Messung/Reset/Klassik/Metadaten/UNBEKANNT sind
        Barrieren (None,None) -> konservativ, nie falsch-kommutiert."""
        parts = line.split(" if ")
        cond = parts[1].strip() if len(parts) > 1 else None
        tokens = parts[0].split()
        if not tokens or tokens[0].startswith("#"):
            return None, None, "BARRIER", [], cond
        op = tokens[0]
        args = tokens[1:]
        known = ("X", "CX", "CCX", "SWAP", "CSWAP", "Z", "Z_POW", "T", "TDAG", "CZ", "CCZ")
        if op not in known:
            return None, None, op, args, cond
        arity = 2 if op == "Z_POW" else BitParallelKMXVerifier._ARITY[op]
        qargs = args[:1] if op == "Z_POW" else args
        if (len(args) != arity or len(parts) > 2 or cond == "" or len(set(qargs)) != len(qargs)
                or not all(_RE_QTOKEN.match(a) for a in qargs)):
            return None, None, op, args, cond   # malformed -> Barriere statt IndexError/Fehlauslöschung
        x_set: Set[str] = set()
        z_set: Set[str] = set()
        if op == "X":
            x_set.add(args[0])
        elif op in ("Z", "Z_POW", "T", "TDAG"):
            z_set.add(args[0])
        elif op in ("CZ", "CCZ"):
            z_set.update(args)
        elif op == "CX":
            z_set.add(args[0])
            x_set.add(args[1])
        elif op == "CCX":
            z_set.update(args[:2])
            x_set.add(args[2])
        elif op == "SWAP":
            x_set.update(args)
            z_set.update(args)
        elif op == "CSWAP":
            z_set.add(args[0])
            x_set.update(args[1:3])
            z_set.update(args[1:3])
        if cond:
            z_set.add(f"cond:{cond}")   # Bedingung liest das Bit -> Z-Abhängigkeit
        return x_set, z_set, op, args, cond

    @classmethod
    def _commutes(cls, g1, g2) -> bool:
        x1, z1, op1, _, _ = g1
        x2, z2, op2, _, _ = g2
        if x1 is None or x2 is None:
            return False
        # X-Mengen dürfen sich überlappen: reine Ziel-XORs (X/CX/CCX auf dasselbe Ziel) kommutieren,
        # solange keines das Ziel des anderen liest. SWAP/CSWAP-Ziele liegen in X- UND Z-Menge und
        # blockieren damit jedes Gatter, das sie berührt (kommutieren nur über disjunkte Qubits).
        return x1.isdisjoint(z2) and z1.isdisjoint(x2)

    @classmethod
    def _canonical(cls, line: str) -> str:
        x_set, _, op, args, cond = cls._get_rw_sets(line)
        if x_set is None:
            return line   # Barrieren (Kommentare, Messungen, malformed) unverändert durchreichen
        if op in ("CZ", "CCZ", "SWAP"):
            args = sorted(args)
        elif op == "CCX":
            args = sorted(args[:2]) + [args[2]]
        elif op == "CSWAP":
            args = [args[0]] + sorted(args[1:3])
        base = f"{op} {' '.join(args)}" if args else op
        return f"{base} if {cond}" if cond else base

    @staticmethod
    def _phase_exp(op: str, args: List[str]) -> Optional[Fraction]:
        """Phasenexponent in Halbdrehungen (mod 2) für Z/T/TDAG/Z_POW; sonst None."""
        if op == "Z":
            return Fraction(1, 1)
        if op == "T":
            return Fraction(1, 4)
        if op == "TDAG":
            return Fraction(7, 4)
        if op == "Z_POW" and len(args) >= 2:
            try:
                return Fraction(args[1]) % 2
            except (ValueError, ZeroDivisionError):
                return None
        return None

    @staticmethod
    def _format_phase_gate(q: str, exp: Fraction, cond: Optional[str]) -> Optional[str]:
        exp = exp % 2
        if exp == 0:
            return None
        if exp == 1:
            base = f"Z {q}"
        elif exp == Fraction(1, 4):
            base = f"T {q}"
        elif exp == Fraction(7, 4):
            base = f"TDAG {q}"
        else:
            base = f"Z_POW {q} {_exact_decimal(exp)}"
        return f"{base} if {cond}" if cond else base

    @classmethod
    def pass_commuting_cancellation(cls, lines: Optional[List[str]]) -> Tuple[List[str], int]:
        """Kommutierende Paar-Auslöschung UND exakte Z/T/TDAG/Z_POW-Phasenfusion."""
        clean = [l for l in (lines or []) if isinstance(l, str) and l.strip()]
        opt_lines: List[str] = []
        parsed_stack = []
        cancelled_or_merged = 0
        open_lines: Counter = Counter()    # kanonische Zeile -> Anzahl in opt_lines
        open_phase: Counter = Counter()    # (Qubit, Bedingung) -> offene Phasengatter
        phase_ops = ("Z", "T", "TDAG", "Z_POW")
        for line in clean:
            c_line = cls._canonical(line)
            rw = cls._get_rw_sets(c_line)
            _, _, op, args, cond = rw
            handled = False
            # 1. Selbstinverse Gatter (X, Z, CX, CZ, CCX, CCZ, SWAP, CSWAP)
            if (rw[0] is not None and open_lines[c_line]
                    and op in ("X", "Z", "CX", "CZ", "CCX", "CCZ", "SWAP", "CSWAP")):
                for j in range(len(parsed_stack) - 1, -1, -1):
                    if opt_lines[j] == c_line:
                        open_lines[c_line] -= 1
                        if op == "Z":
                            open_phase[(args[0], cond)] -= 1
                        del opt_lines[j]
                        del parsed_stack[j]
                        cancelled_or_merged += 1
                        handled = True
                        break
                    if not cls._commutes(rw, parsed_stack[j]):
                        break
            # 2. Exakte Phasenfusion für Z / T / TDAG / Z_POW auf demselben Qubit
            if not handled and rw[0] is not None and op in phase_ops and open_phase[(args[0], cond)]:
                exp1 = cls._phase_exp(op, args)
                q_target = args[0]
                if exp1 is not None:
                    for j in range(len(parsed_stack) - 1, -1, -1):
                        prev_rw = parsed_stack[j]
                        _, _, p_op, p_args, p_cond = prev_rw
                        if prev_rw[0] is not None and p_op in phase_ops and p_args[0] == q_target and p_cond == cond:
                            exp0 = cls._phase_exp(p_op, p_args)
                            if exp0 is not None:
                                merged_line = cls._format_phase_gate(q_target, exp0 + exp1, cond)
                                open_lines[opt_lines[j]] -= 1
                                if merged_line is None:
                                    open_phase[(q_target, cond)] -= 1
                                    del opt_lines[j]
                                    del parsed_stack[j]
                                else:
                                    open_lines[merged_line] += 1
                                    opt_lines[j] = merged_line
                                    parsed_stack[j] = cls._get_rw_sets(merged_line)
                                cancelled_or_merged += 1
                                handled = True
                                break
                        if not cls._commutes(rw, prev_rw):
                            break
            if not handled:
                opt_lines.append(c_line)
                parsed_stack.append(rw)
                open_lines[c_line] += 1
                if rw[0] is not None and op in phase_ops:
                    open_phase[(args[0], cond)] += 1
        return opt_lines, cancelled_or_merged

    @staticmethod
    def pass_eliminate_dead_end_swaps(lines: Optional[List[str]], output_qubits: Set[int]) -> Tuple[List[str], int]:
        """Eliminiert SWAP-Gatter im abschließenden Routing-Block, die nur tote |0>-Ancillas tauschen."""
        clean = [l for l in (lines or []) if isinstance(l, str) and l.strip()]
        live = set(output_qubits or set())
        keep_flags = [True] * len(clean)
        removed = 0
        for idx in range(len(clean) - 1, -1, -1):
            l = clean[idx]
            op = l.split()[0]
            if op == "X":
                continue
            elif op == "SWAP" and " if " not in l:
                qs = [int(x) for x in _RE_QUBIT.findall(l)]
                if len(qs) < 2:
                    break
                q1, q2 = qs[0], qs[1]
                in1, in2 = (q1 in live), (q2 in live)
                if not in1 and not in2:
                    keep_flags[idx] = False
                    removed += 1
                else:
                    live.discard(q1)
                    live.discard(q2)
                    if in1:
                        live.add(q2)
                    if in2:
                        live.add(q1)
            else:
                break
        return [l for l, k in zip(clean, keep_flags) if k], removed

    @staticmethod
    def pass_repack_short_lifetimes(lines: Optional[List[str]], target_qubits: Tuple[int, ...] = (60, 61)) -> Tuple[List[str], int]:
        """Analysiert HMR/R-Lebenszyklen und evakuiert hohe Ancillas All-or-Nothing auf niedrigere."""
        clean = [l for l in (lines or []) if isinstance(l, str) and l.strip()]
        wire_intervals: Dict[int, List[Tuple[int, int]]] = defaultdict(list)
        wire_start: Dict[int, int] = {q: 0 for q in range(22)}
        active_qubits: Set[int] = set()
        for idx, l in enumerate(clean):
            if l.startswith(("APPEND", "REGISTER")):
                continue
            qs = [int(x) for x in _RE_QUBIT.findall(l)]
            for q in qs:
                active_qubits.add(q)
                if q not in wire_start:
                    wire_start[q] = idx
            tok0 = l.split()[0] if l else ""
            if tok0 in ("HMR", "R") and qs:
                q = qs[0]
                wire_intervals[q].append((wire_start[q], idx))
                del wire_start[q]
        for q, st in wire_start.items():
            wire_intervals[q].append((st, len(clean) - 1))

        def is_free(intervals: List[Tuple[int, int]], start_idx: int, end_idx: int) -> bool:
            for s, e in intervals:
                if not (e < start_idx or s > end_idx):
                    return False
            return True

        high_ancillas = sorted((q for q in active_qubits if q >= 22), reverse=True)
        ordered_targets: List[int] = []
        for tq in list(target_qubits or []) + high_ancillas:
            if tq >= 22 and tq in wire_intervals and tq not in ordered_targets:
                ordered_targets.append(tq)

        out = list(clean)
        remapped = 0
        for tq in ordered_targets:
            tq_intervals = list(wire_intervals.get(tq, []))
            if not tq_intervals:
                continue
            candidate_pool = sorted(q for q in active_qubits if 22 <= q < tq)
            planned_moves: List[Tuple[int, int, int]] = []
            temp_added: Dict[int, List[Tuple[int, int]]] = defaultdict(list)
            all_placed = True
            for s, e in tq_intervals:
                placed_this = False
                for cand in candidate_pool:
                    combined = wire_intervals[cand] + temp_added[cand]
                    if is_free(combined, s, e):
                        planned_moves.append((s, e, cand))
                        temp_added[cand].append((s, e))
                        placed_this = True
                        break
                if not placed_this:
                    all_placed = False
                    break
            if all_placed and planned_moves:
                pattern = re.compile(rf"\bq{tq}\b")
                for s, e, cand in planned_moves:
                    for i in range(s, e + 1):
                        out[i] = pattern.sub(f"q{cand}", out[i])
                    wire_intervals[cand].append((s, e))
                    remapped += 1
                del wire_intervals[tq]
                active_qubits.discard(tq)
        return out, remapped


# =====================================================================
# 4. KI-TOOLING-LAYER & ALGEBRAISCHER REWRITE-SYNTHESIZER
# =====================================================================

class AgentToolbox:
    """Werkzeugkasten, den der autonome KI-Agent (oder der symbolische Synthesizer) aufruft."""

    def __init__(self, lines: Optional[List[str]]):
        self.lines: List[str] = [l for l in (lines or []) if isinstance(l, str) and l.strip()]
        self.audit_log: List[str] = []

    def find_toffoli_hotspots(self, max_distance: int = 25) -> List[Dict[str, Any]]:
        """Findet dicht aufeinanderfolgende CCX/CCZ/CSWAP-Paare mit identischen Qubits,
        sortiert nach Position (Voraussetzung für das Rückwärts-Anwenden im Greedy-Modus)."""
        pos_map: Dict[Tuple[str, ...], List[int]] = defaultdict(list)
        for idx, l in enumerate(self.lines):
            if not isinstance(l, str) or " if " in l:
                continue
            parts = l.split()
            if len(parts) != 4:
                continue
            op = parts[0]
            if op == "CCX":
                key = (op, *sorted(parts[1:3]), parts[3])
            elif op == "CCZ":
                key = (op, *sorted(parts[1:4]))
            elif op == "CSWAP":
                key = (op, parts[1], *sorted(parts[2:4]))
            else:
                continue
            pos_map[key].append(idx)
        hotspots = []
        for key, indices in pos_map.items():
            for i1, i2 in zip(indices, indices[1:]):
                if i2 - i1 <= max_distance:
                    window = self.lines[i1:i2 + 1]
                    ok, _ = BitParallelKMXVerifier.can_verify_window(window)
                    if ok:
                        hotspots.append({
                            "op": key[0],
                            "triple": key[1:],
                            "start_idx": i1,
                            "end_idx": i2,
                            "distance": i2 - i1,
                            "window_lines": window,
                        })
        hotspots.sort(key=lambda h: (h["start_idx"], h["end_idx"]))
        return hotspots

    def inspect_window(self, start_idx: int, end_idx: int) -> Dict[str, Any]:
        if not (0 <= start_idx <= end_idx < len(self.lines)):
            return {"start_idx": start_idx, "end_idx": end_idx, "verifiable": False,
                    "reason": "Indizes außerhalb", "lines": []}
        window = self.lines[start_idx:end_idx + 1]
        verifiable, reason = BitParallelKMXVerifier.can_verify_window(window)
        return {"start_idx": start_idx, "end_idx": end_idx, "verifiable": verifiable,
                "reason": reason, "lines": window}

    def apply_verified_rewrite(self, start_idx: int, end_idx: int, candidate_lines: Optional[List[str]],
                               description: str = "") -> Dict[str, Any]:
        """Prüft einen vorgeschlagenen Rewrite mit dem lokalen Verifier. Wird NUR übernommen,
        wenn der Block exakt äquivalent ist UND das echte Kostenmodell senkt (inner_cost; bei
        gleicher Kosten die Zeilenzahl reduziert). Standardmäßig nur exakt bewiesene Züge.
        Defensiv: None/leer/ungültige Indizes werden abgelehnt."""
        if candidate_lines is None:
            return {"accepted": False, "reason": "Kandidat ist None."}
        if not (0 <= start_idx <= end_idx < len(self.lines)):
            return {"accepted": False,
                    "reason": f"Indizes {start_idx}..{end_idx} ausserhalb (len={len(self.lines)})."}
        candidate_lines = [x.strip() for x in candidate_lines if isinstance(x, str) and x.strip()]

        orig_window = self.lines[start_idx:end_idx + 1]

        # Qubit-Scope-Sperre: fensterfremde (z. B. halluzinierte) Qubits würden Q=max+1 aufblähen
        # und Draht-Zustände ausserhalb des geprüften Fensters anfassen.
        orig_qs = set().union(*(_operand_qubits(l.split()) for l in _clean_lines(orig_window)))
        extra = sorted(set().union(*(_operand_qubits(l.split()) for l in _clean_lines(candidate_lines))) - orig_qs)
        if extra:
            return {"accepted": False, "reason": f"Kandidat führt fensterfremde Qubits ein: {extra}"}

        orig_m = compute_metrics(orig_window)
        cand_m = compute_metrics(candidate_lines)

        # Akzeptanz nach echtem Kostenmodell: erst inner_cost, dann Zeilen (tie-break).
        if (cand_m.inner_cost, len(candidate_lines)) >= (orig_m.inner_cost, len(orig_window)):
            return {"accepted": False,
                    "reason": f"Keine Kostensenkung (inner_cost {orig_m.inner_cost:.4f}->{cand_m.inner_cost:.4f})."}

        result = BitParallelKMXVerifier.verify_equivalence(orig_window, candidate_lines)
        if not result.ok:
            return {"accepted": False, "reason": f"Verifier-Ablehnung: {result.message}"}
        if not _proof_accepted(result):
            return {"accepted": False,
                    "reason": "Nur Fuzzing möglich; exakter lokaler Beweis erforderlich "
                              "(ALLOW_PROBABILISTIC_REWRITES=1 hebt diese Sperre auf)."}
        self.lines[start_idx:end_idx + 1] = candidate_lines
        log_entry = (
            f"[VERIFIED REWRITE] Zeilen {start_idx + 1}..{end_idx + 1}: "
            f"inner_cost {orig_m.inner_cost:.4f}->{cand_m.inner_cost:.4f}, "
            f"Toffoli {orig_m.toffoli_cost}->{cand_m.toffoli_cost}, "
            f"Z_POW {orig_m.z_pow_count}->{cand_m.z_pow_count} ({description}) | {result.message}"
        )
        self.audit_log.append(log_entry)
        return {"accepted": True, "message": log_entry, "exact": result.exact}

    def run_deterministic_passes(self) -> Dict[str, Any]:
        summary: Dict[str, Any] = {}
        # Starke Op-basierte Pässe aus kmx_agent_kimi.py: CX-Tripel->SWAP, exakte
        # Z/Z_POW-Phasenfusion und Kommutations-Auslöschung (bit-/bedingungs-/HMR-aware).
        # Sie finden deutlich mehr gültige Auslösungen als die line-basierten Pässe
        # (z. B. 272 vs 5 auf a15b0d73). Korrekt, da jede Transformation äquivalenzerhaltend ist.
        if _kimi is not None:
            try:
                ops = _kimi.parse_lines(self.lines)
                n_ops = len(ops)
                tot_fold = tot_phase = tot_cancel = 0
                for _ in range(3):  # bis zur Konvergenz
                    ops, n_fold = _kimi.pass_fold(ops)
                    n_phase = 0
                    if hasattr(_kimi, "pass_phase_merge"):
                        ops, n_phase = _kimi.pass_phase_merge(ops)
                    # kimi: (ops, n_cancel); fable: (ops, n_cancel, n_merged)
                    ops, n_cancel, *n_merged = _kimi.pass_cancel(ops)
                    n_phase += sum(n_merged)
                    tot_fold += n_fold
                    tot_phase += n_phase
                    tot_cancel += n_cancel
                    if n_fold == 0 and n_phase == 0 and n_cancel == 0:
                        break
                new_lines = [l for l in _kimi.format_ops(ops).splitlines() if l.strip()]
                summary["kimi"] = {"folded": tot_fold, "phase_merged": tot_phase,
                                   "cancelled": tot_cancel, "lines_removed": n_ops - len(new_lines)}
                self.lines = new_lines
            except Exception as exc:  # noqa: BLE001 - defensive: Fallback auf line-basierte Pässe
                summary["kimi_error"] = f"{type(exc).__name__}: {str(exc)[:80]}"
                self.lines, n_swaps = DeterministicKMXEngine.pass_fold_3cx_to_swap(self.lines)
                self.lines, n_canc = DeterministicKMXEngine.pass_commuting_cancellation(self.lines)
                summary["legacy"] = {"folded_3cx_swaps": n_swaps, "cancelled_or_phase_merged": n_canc}
        else:
            self.lines, n_swaps = DeterministicKMXEngine.pass_fold_3cx_to_swap(self.lines)
            self.lines, n_canc = DeterministicKMXEngine.pass_commuting_cancellation(self.lines)
            summary["legacy"] = {"folded_3cx_swaps": n_swaps, "cancelled_or_phase_merged": n_canc}

        # Zweite, eigene Konvergenzschleife (räumt Reste auf, inkl. Phasenfusion).
        tot_swaps = tot_canc = 0
        for _ in range(3):
            self.lines, n_swaps = DeterministicKMXEngine.pass_fold_3cx_to_swap(self.lines)
            self.lines, n_canc = DeterministicKMXEngine.pass_commuting_cancellation(self.lines)
            tot_swaps += n_swaps
            tot_canc += n_canc
            if n_swaps == 0 and n_canc == 0:
                break
        summary["second_sweep"] = {"folded_3cx_swaps": tot_swaps, "cancelled_or_phase_merged": tot_canc}

        # Unsichere Legacy-Pässe (feste Output-/Ziel-Qubits, HMR-Intervalle) nur explizit.
        if os.environ.get("LEGACY_UNSAFE_PASSES", "0") == "1":
            self.lines, n_dead = DeterministicKMXEngine.pass_eliminate_dead_end_swaps(self.lines, set(range(22)))
            self.lines, n_repack = DeterministicKMXEngine.pass_repack_short_lifetimes(self.lines, (60, 61))
            summary["legacy_unsafe"] = {"eliminated_dead_swaps": n_dead, "repacked_lifetime_intervals": n_repack}
        else:
            summary["legacy_unsafe"] = "disabled"
        self.audit_log.append(f"[DETERMINISTIC PASSES] {json.dumps(summary)}")
        return summary


# =====================================================================
# 5. AUTONOMER KI-AGENT (TOOL-CALLING LLM + SYMBOLISCHER SYNTHESIZER)
# =====================================================================

class AutonomousKMXAgent:
    """Steuert den Optimierungsprozess autonom:
    1. Deterministische Basis-Pässe (inkl. Phasenfusion).
    2. Symbolische Synthese für gepaarte CCX-/CCZ-/CSWAP-Fenster (0-/1-Toffoli-Reduktionen).
    3. Memoisierte LLM-Hotspot-Synthese mit Fast-Fail-Circuit-Breaker.
    Jeder Kandidat läuft zwingend durch den BitParallelKMXVerifier (Verifier-in-the-Loop)."""

    def __init__(self, toolbox: AgentToolbox, api_key: Optional[str] = None,
                 model: Optional[str] = None, api_url: Optional[str] = None):
        self.toolbox = toolbox
        # Default: lokale Weinstadt-KI (keyless, OpenAI-kompatibel). Cloud per Env überschreibbar.
        self.api_url = api_url or os.environ.get("LLM_API_URL", "http://192.168.212.81:8000/v1/chat/completions")
        self.model = model or os.environ.get("LLM_MODEL", "qwen3.8-27b")
        self.api_key = (api_key or os.environ.get("LLM_API_KEY")
                        or os.environ.get("OPENROUTER_API_KEY") or os.environ.get("OPENAI_API_KEY"))
        self.max_tokens = int(os.environ.get("LLM_MAX_TOKENS", "8192"))
        self.max_llm_calls = int(os.environ.get("LLM_MAX_CALLS", "40"))
        self.llm_timeout = float(os.environ.get("LLM_TIMEOUT", "60"))
        self._llm_calls = 0
        self._endpoint_unreachable = False
        self._llm_cache: Dict[Tuple[str, ...], Optional[List[str]]] = {}
        # Qwen3.x ist ein Reasoning-Modell: privates Thinking abschalten, sonst leeres content.
        self.extra_body = json.loads(
            os.environ.get("LLM_EXTRA_BODY", '{"chat_template_kwargs":{"enable_thinking":false}}')
        )

    @staticmethod
    def _proven(window: List[str], cand: List[str]) -> bool:
        return _proof_accepted(BitParallelKMXVerifier.verify_equivalence(window, cand, num_batches=8))

    def _synthesize_ccz_merge(self, window: List[str], qs: List[str]) -> Optional[Tuple[List[str], str]]:
        """Reduktionen für gepaarte CCZ-Fenster (CCZ ist symmetrisch in allen drei Qubits)."""
        inner = window[1:-1]
        for i in range(3):
            q_mod, q_k1, q_k2 = qs[i], qs[(i + 1) % 3], qs[(i + 2) % 3]
            # CCZ a b c; X a; CCZ a b c == CZ b c; X a  -> 0 Toffolis.
            if f"X {q_mod}" in inner:
                for pos in (0, len(inner)):
                    cand = inner[:pos] + [f"CZ {q_k1} {q_k2}"] + inner[pos:]
                    if self._proven(window, cand):
                        return cand, f"2-CCZ->0-Toffoli Paritätsfaltung ({q_mod} invertiert -> CZ {q_k1} {q_k2})"
            # CCZ a b c; CX s a; CCZ a b c == CX s a; CCZ s b c  -> 1 Toffoli.
            for idx_cx, l in enumerate(inner):
                m = _RE_CX.match(l)
                if not m or m.group(2) != q_mod or m.group(1) in (q_k1, q_k2):
                    continue
                for insert_pos in (idx_cx, idx_cx + 1):
                    cand = inner[:insert_pos] + [f"CCZ {m.group(1)} {q_k1} {q_k2}"] + inner[insert_pos:]
                    if self._proven(window, cand):
                        return cand, f"Algebraische 2-CCZ->1-CCZ Differenzfaltung ({q_mod} via {m.group(1)})"
        return None

    def synthesize_algebraic_ccx_merge(self, window: Optional[List[str]]) -> Optional[Tuple[List[str], str]]:
        """Symbolischer Synthesizer für gepaarte CCX-/CCZ-/CSWAP-Fenster. Jeder Kandidat wird vor
        Rückgabe verifiziert (Policy: _proof_accepted). Familien:
          1. 2 Toffoli -> 0: Kommutierungs-Auslöschung (CCX, CCZ, CSWAP)
          2. 2 CCX -> 0: Phasenkonjugation  CCX c1 c2 t; Z t; CCX c1 c2 t == Z t; CZ c1 c2
          3. 2 CCX -> 0: X-Paritäts-Faltung (ein kostenloses CX)
          4. 2 CCX -> 1 CCX: Differenz-Faltung
          5. 2 CCX -> 1 CCX + 1 CX: affine Differenz-Faltung
          6. 2 CCX -> 1 CCZ: Phasenkonjugation  CCX c1 c2 t; CZ q t; CCX c1 c2 t == CZ q t; CCZ c1 c2 q
          + CCZ-Varianten von 3/4 (_synthesize_ccz_merge).
        Defensiv: None/leer/falsche Form -> None."""
        window = [w.strip() for w in (window or []) if isinstance(w, str) and w.strip()]
        if len(window) < 2:
            return None
        parts = window[0].split()
        op = parts[0]
        if op not in ("CCX", "CCZ", "CSWAP") or len(parts) != 4 or window[-1].split()[0] != op:
            return None
        inner = window[1:-1]
        proven = self._proven

        # 1. Reine 0-Toffoli-Auslöschung (beide Rand-Gatter entfallen komplett).
        if proven(window, inner):
            return inner, f"Vollständige 2-{op}->0-{op} Kommutierungs-Auslöschung ({','.join(parts[1:])})"
        if op == "CCZ":
            return self._synthesize_ccz_merge(window, parts[1:4])
        if op != "CCX":
            return None
        c1, c2, t = parts[1], parts[2], parts[3]

        # 2. Phasenkonjugation über Z t (Z und CZ sind kostenlos).
        if f"Z {t}" in inner:
            pos = inner.index(f"Z {t}") + 1
            cand = inner[:pos] + [f"CZ {c1} {c2}"] + inner[pos:]
            if proven(window, cand):
                return cand, f"2-CCX->0-Toffoli Phasenkonjugation (Z {t} -> CZ {c1} {c2})"

        for ctrl_mod, ctrl_keep in ((c1, c2), (c2, c1)):
            x_gate = f"X {ctrl_mod}"
            # 3. 0-CCX X-Paritäts-Faltung: (cm&ck)^((cm^1)&ck) == ck -> 1 CX statt 2 CCX.
            if x_gate in inner:
                for pos in (0, len(inner)):
                    cand = inner[:pos] + [f"CX {ctrl_keep} {t}"] + inner[pos:]
                    if proven(window, cand):
                        return cand, f"2-CCX->0-CCX Paritätsfaltung ({ctrl_mod} invertiert -> CX {ctrl_keep} {t})"
            # 4./5. 1-CCX Differenz-Faltung über innere CX-Updates auf ctrl_mod.
            for idx_cx, l in enumerate(inner):
                m = _RE_CX.match(l)
                if not m or m.group(2) != ctrl_mod:
                    continue
                src = m.group(1)
                if src in (ctrl_keep, t):
                    continue
                # 4. Reine Differenz ohne X: 2 CCX -> 1 CCX src ctrl_keep t.
                for insert_pos in (idx_cx, idx_cx + 1):
                    cand = inner[:insert_pos] + [f"CCX {src} {ctrl_keep} {t}"] + inner[insert_pos:]
                    if proven(window, cand):
                        return cand, f"Algebraische 2-CCX->1-CCX Differenzfaltung ({ctrl_mod},{ctrl_keep}->{t} via {src})"
                # 5. Affine Differenz mit X: (cm&ck)^((cm^src^1)&ck).
                if x_gate in inner:
                    cand_no_x = [g for g in inner if g != x_gate]
                    idx_src = cand_no_x.index(f"CX {src} {ctrl_mod}")
                    for tail_x in ([x_gate], []):
                        cand = (cand_no_x[:idx_src]
                                + [f"CX {ctrl_keep} {t}", f"CCX {src} {ctrl_keep} {t}"]
                                + cand_no_x[idx_src:] + tail_x)
                        if proven(window, cand):
                            return cand, f"Algebraische CCX-Paarfaltung ({c1},{c2}->{t}) über Differenz-Control {src}"

        # 6. Phasenkonjugation über CZ q t: 2 CCX -> 1 CCZ.
        for idx_cz, l in enumerate(inner):
            m = _RE_CZ.match(l)
            if not m or t not in m.groups():
                continue
            q_other = m.group(2) if m.group(1) == t else m.group(1)
            if q_other in (c1, c2, t):
                continue
            cand = inner[:idx_cz + 1] + [f"CCZ {c1} {c2} {q_other}"] + inner[idx_cz + 1:]
            if proven(window, cand):
                return cand, f"2-CCX->1-CCZ Phasenkonjugation (CZ {q_other} {t} -> CCZ {c1} {c2} {q_other})"
        return None

    def query_llm_for_window(self, window: Optional[List[str]]) -> Optional[List[str]]:
        """Fragt die angebundene KI nach einem Block mit niedrigerem Kostenwert. Memoisiert nach
        Fenster-Inhalt und bricht bei Offline-Endpunkt sofort ab (Circuit-Breaker). Defensiv:
        None/leere Fenster -> None (kein LLM-Call)."""
        if self._endpoint_unreachable or self._llm_calls >= self.max_llm_calls:
            return None
        clean_window = [w.strip() for w in (window or []) if isinstance(w, str) and w.strip()]
        if not clean_window:
            return None
        cache_key = tuple(clean_window)
        if cache_key in self._llm_cache:
            return self._llm_cache[cache_key]

        prompt = (
            "Du bist ein Quanten-Compiler-Agent fuer das Kickmix (.kmx)-Format.\n"
            "KOSTENMODELL (entscheidend!): Nur diese Gatter erhoehen die Kosten:\n"
            "  - CCX, CCZ, CSWAP (Toffoli-artig, je 1)\n"
            f"  - feine Z_POW     (je {ROT_WEIGHT} Toffoli-Aequivalente)\n"
            "  - T / TDAG und T-artige Z_POW (je 1/4 Toffoli)\n"
            "Gegenueber KOSTENLOS (zaehlen NICHT): X, CX, CZ, SWAP, Z, Clifford-Z_POW.\n"
            "Aufgabe: Ersetze den folgenden Subblock durch einen, der EXAKT dieselbe unitaere\n"
            "Funktion berechnet, aber WENIGER CCX/CCZ/CSWAP/feine-Z_POW/T enthaelt.\n"
            "Regeln:\n"
            "  1. Verwende NUR die Operationen: X, CX, CCX, SWAP, CSWAP, Z, CZ, CCZ, T, TDAG, Z_POW.\n"
            "  2. Keine ' if '-Bedingungen, keine HMR/R/BIT_*/PUSH/POP/NEG/REGISTER.\n"
            "  3. Gleiche Qubit-Namen (qN) wie im Block; keine neuen Qubits einfuehren.\n"
            "  4. Wenn du die Kosten NICHT senken kannst, antworte mit dem ORIGINALBLOCK.\n"
            "     Ein leeres Array [] ist nur erlaubt, wenn der ganze Block entfallen kann.\n"
            "  5. Antworte NUR mit einem JSON-Array von .kmx-Zeilen (Strings), keine Prosa.\n\n"
            "Block:\n" + "\n".join(clean_window)
        )
        body: Dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
            "max_tokens": self.max_tokens,
        }
        if isinstance(self.extra_body, dict):
            body.update(self.extra_body)
        payload = json.dumps(body).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        req = urllib.request.Request(self.api_url, data=payload, headers=headers)
        self._llm_calls += 1

        result: Optional[List[str]] = None
        try:
            with urllib.request.urlopen(req, timeout=self.llm_timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                content = (data["choices"][0]["message"].get("content")) or ""
                m = _RE_JSON_ARRAY.search(content)
                if m:
                    cand = json.loads(m.group(0))
                    if isinstance(cand, list) and all(isinstance(x, str) and x.strip() for x in cand):
                        result = [x.strip() for x in cand]
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            self._endpoint_unreachable = True   # Server weg -> Folge-Timeouts sparen
        except Exception:
            result = None
        self._llm_cache[cache_key] = result
        return result

    def run_autonomous_optimization(self) -> List[str]:
        self.toolbox.run_deterministic_passes()
        rejected: Set[Tuple[str, ...]] = set()   # Fenster ohne akzeptierten Rewrite nicht erneut prüfen
        # ponytail: Neustart nach jedem Treffer ist O(Treffer * Hotspots); Deckel gegen Ausreißer.
        for _ in range(int(os.environ.get("GREEDY_MAX_REWRITES", "500"))):
            accepted = False
            for hs in reversed(self.toolbox.find_toffoli_hotspots(max_distance=25)):
                s_idx, e_idx = hs["start_idx"], hs["end_idx"]
                window = self.toolbox.lines[s_idx:e_idx + 1]
                if tuple(window) in rejected:
                    continue
                synth = self.synthesize_algebraic_ccx_merge(window)
                if synth is not None:
                    cand, desc = synth
                else:
                    cand, desc = self.query_llm_for_window(window), "LLM-Agent-Synthese"
                if cand is not None and self.toolbox.apply_verified_rewrite(
                        s_idx, e_idx, cand, description=desc).get("accepted"):
                    accepted = True
                    break
                rejected.add(tuple(window))
            if not accepted:
                break
        self.toolbox.run_deterministic_passes()
        return self.toolbox.lines


# =====================================================================
# 5b. BEAM-/BEST-FIRST-SUCHE UEBER AEQUIVALENZERHALTENDE REWRITES (TRACK A)
# =====================================================================

class BeamSearchKMXOptimizer:
    """Best-first / Beam-Suche über äquivalenzerhaltende Rewrites.
    Knoten=Schaltung, Kanten=(a) deterministische Pässe + (b) Verifier-geprüfte Symbol-/LLM-Rewrites,
    Score=circuit_cost(). Legalität exakt geprüft (kein Partial-Credit); kleiner Aktionsraum ->
    Best-first schlägt Monte-Carlo. Caches + Geduld gegen redundante Arbeit."""

    def __init__(self, agent: "AutonomousKMXAgent", beam_width: Optional[int] = None,
                 max_iterations: Optional[int] = None, use_llm: bool = True):
        self.agent = agent
        self.beam_width = max(1, int(beam_width or os.environ.get("BEAM_WIDTH", "3")))
        self.max_iterations = max(1, int(max_iterations or os.environ.get("BEAM_ITERS", "4")))
        self.use_llm = use_llm
        self.patience = max(0, int(os.environ.get("BEAM_PATIENCE", "2")))
        self.audit: List[str] = []
        self._cost_cache: Dict[str, Tuple[float, int]] = {}
        self._det_cache: Dict[str, List[str]] = {}
        self._llm_cache: Dict[str, Optional[List[str]]] = {}

    @staticmethod
    def _state_id(lines: List[str]) -> str:
        return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()

    def _state_key(self, lines: List[str]) -> Tuple[float, int]:
        sid = self._state_id(lines)
        key = self._cost_cache.get(sid)
        if key is None:
            key = (compute_metrics(lines).real_cost, len(lines))
            self._cost_cache[sid] = key
        return key

    def _run_deterministic(self, lines: List[str]) -> List[str]:
        sid = self._state_id(lines)
        cached = self._det_cache.get(sid)
        if cached is not None:
            return list(cached)
        tb = AgentToolbox(list(lines))
        tb.run_deterministic_passes()
        self._det_cache[sid] = list(tb.lines)
        return tb.lines

    def _expand(self, lines: List[str]) -> List[Tuple[List[str], str]]:
        succ: List[Tuple[List[str], str]] = []
        det_lines = self._run_deterministic(lines)
        if det_lines != lines:
            succ.append((det_lines, "det"))
        probe = AgentToolbox(list(lines))
        for hs in probe.find_toffoli_hotspots(max_distance=25):
            s, e = hs["start_idx"], hs["end_idx"]
            window = lines[s:e + 1]
            attempts: List[Tuple[List[str], str]] = []
            synth = self.agent.synthesize_algebraic_ccx_merge(window)
            if synth is not None:
                attempts.append((synth[0], "sym"))
            if self.use_llm:
                window_id = self._state_id(window)
                if window_id not in self._llm_cache:
                    self._llm_cache[window_id] = self.agent.query_llm_for_window(window)
                llm = self._llm_cache[window_id]
                if llm is not None:
                    attempts.append((llm, "llm"))
            for cand, kind in attempts:
                tbc = AgentToolbox(list(lines))
                res = tbc.apply_verified_rewrite(s, e, cand, description=kind)
                if res.get("accepted"):
                    self.audit.append(res.get("message", "[VERIFIED REWRITE]"))
                    succ.append((list(tbc.lines), f"{kind}@{s + 1}"))
        return succ

    def optimize(self, initial_lines: Optional[List[str]]) -> List[str]:
        lines = [l.strip() for l in (initial_lines or []) if isinstance(l, str) and l.strip()]
        if not lines:
            return lines
        start_cost = self._state_key(lines)[0]
        base = self._run_deterministic(lines)
        initial_key = (start_cost, len(lines))
        best_key = self._state_key(base)
        if best_key > initial_key:
            # Deterministik darf niemals einen teureren Startpunkt erzwingen.
            base, best_key = list(lines), initial_key
        best_lines = base
        self.audit.append(
            f"[BEAM INIT] Basis-Pässe {'verändert' if base != lines else 'neutral'} "
            f"(lines {len(lines)}->{len(base)}, cost {start_cost:.4f}->{best_key[0]:.4f})"
        )
        beam: List[Tuple[List[str], Tuple[float, int], str]] = [(base, best_key, "init")]
        seen = {self._state_id(base)}
        stale_rounds = 0

        for it in range(1, self.max_iterations + 1):
            candidates: List[Tuple[List[str], Tuple[float, int], str]] = []
            for st_lines, _st_key, prov in beam:
                for slines, sprev in self._expand(st_lines):
                    sid = self._state_id(slines)
                    if sid in seen:
                        continue
                    seen.add(sid)
                    key = self._state_key(slines)
                    candidates.append((slines, key, f"{prov}->{sprev}"))
            if not candidates:
                self.audit.append(f"[BEAM it={it}] keine Nachfolger -> Stopp")
                break
            candidates.sort(key=lambda x: x[1])
            beam = candidates[:self.beam_width]
            improved = beam[0][1] < best_key
            if improved:
                best_lines, best_key = beam[0][0], beam[0][1]
                stale_rounds = 0
            else:
                stale_rounds += 1
            self.audit.append(
                f"[BEAM it={it}] erzeugt={len(candidates)} best_cost={best_key[0]:.4f} "
                f"best_lines={best_key[1]} improved={improved} stale={stale_rounds}"
            )
            if stale_rounds > self.patience:
                self.audit.append(f"[BEAM it={it}] Geduld {self.patience} erschöpft -> Stopp")
                break

        cleaned = self._run_deterministic(best_lines)
        cleaned_key = self._state_key(cleaned)
        if cleaned != best_lines and cleaned_key <= best_key:
            best_lines, best_key = cleaned, cleaned_key
        self.audit.append(
            f"[BEAM ERGEBNIS] final_cost={best_key[0]:.4f} final_lines={best_key[1]} "
            f"(Start: {start_cost:.4f} / {len(lines)})"
        )
        return best_lines


# =====================================================================
# 6. CLI-HAUPTPROGRAMM, OFFIZIELLES GATE & SELFTEST
# =====================================================================

def _run_external_verifier(command: str, candidate_path: str) -> Tuple[bool, str]:
    """Führt den konfigurierten offiziellen Verifier auf einer Tempdatei aus.
    ``{candidate}``/``{out}`` wird durch den Pfad ersetzt; ohne Platzhalter wird er angehängt.
    Der Befehl kommt aus der Nutzerkonfiguration und wird als Shell-Kommando ausgeführt."""
    candidate_arg = shlex.quote(candidate_path)
    if "{candidate}" in command or "{out}" in command:
        cmd = command.replace("{candidate}", candidate_arg).replace("{out}", candidate_arg)
    else:
        cmd = f"{command} {candidate_arg}"
    timeout = int(os.environ.get("OFFICIAL_VERIFY_TIMEOUT", "3600"))
    try:
        proc = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, f"Verifier-Ausführung fehlgeschlagen: {exc}"
    output = (proc.stdout + proc.stderr).strip()
    if len(output) > 4000:
        output = output[-4000:]
    return proc.returncode == 0, output or f"Exit-Code {proc.returncode}"


def _atomic_write(path: str, text: str) -> None:
    directory = os.path.dirname(os.path.abspath(path)) or "."
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".kmx-write-", dir=directory, text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def run_pipeline(input_kmx: str, output_kmx: str, diff_out: str) -> int:
    if not input_kmx or not isinstance(input_kmx, str) or not os.path.exists(input_kmx):
        print(f"Fehler: Eingabedatei nicht gefunden: {input_kmx!r}")
        return 1
    with open(input_kmx, "r", encoding="utf-8") as f:
        orig_lines = [l.strip() for l in f if l.strip()]
    if not orig_lines:
        print("Fehler: Eingabedatei ist leer.")
        return 1

    mode = (os.environ.get("OPT_MODE", "beam").strip().lower() or "beam")
    if mode not in ("beam", "greedy"):
        print(f"Fehler: unbekannter OPT_MODE={mode!r}; erlaubt: beam, greedy")
        return 1
    orig_metrics = compute_metrics(orig_lines)
    print(f"MODUS   : {mode}  (OPT_MODE=beam|greedy)")
    print("VORHER  : ", orig_metrics.summary())
    print(f"          real_cost = {orig_metrics.real_cost:.4f}   "
          f"[Q=max+1; toffoli_like+t/4+{ROT_WEIGHT}*z_pow; CX/CZ/SWAP/X/Z kostenlos]")

    if mode == "beam":
        agent = AutonomousKMXAgent(AgentToolbox(orig_lines))
        optimizer = BeamSearchKMXOptimizer(agent)
        opt_lines = optimizer.optimize(orig_lines)
        audit_entries = list(optimizer.audit)
    else:
        toolbox = AgentToolbox(orig_lines)
        agent = AutonomousKMXAgent(toolbox)
        opt_lines = agent.run_autonomous_optimization()
        audit_entries = list(toolbox.audit_log)

    opt_metrics = compute_metrics(opt_lines)
    print("NACHHER : ", opt_metrics.summary())
    print(f"          real_cost = {opt_metrics.real_cost:.4f}")
    delta = orig_metrics.real_cost - opt_metrics.real_cost
    verdict = ("senkt Kosten" if delta > 1e-9
               else ("neutral / lokal-optimal" if abs(delta) <= 1e-9 else "ERHOEHT Kosten (nicht uebernehmen!)"))
    print(f"          Kosten-Delta = {delta:+.4f}  -> {verdict}")
    print("\n--- AGENT AUDIT LOG ---")
    for entry in audit_entries:
        print(" ", entry)

    if delta < -1e-9:
        print("ABBRUCH : Kandidat erhöht die Kosten; vorhandene Ausgabe bleibt unverändert.")
        return 2

    verify_cmd = os.environ.get("OFFICIAL_VERIFY_CMD", "").strip()
    if not verify_cmd and os.environ.get("REQUIRE_OFFICIAL_VERIFY", "0") == "1":
        print("ABBRUCH : REQUIRE_OFFICIAL_VERIFY=1, aber OFFICIAL_VERIFY_CMD fehlt.")
        return 3

    # Kandidat zuerst temporär schreiben; erst nach optionalem offiziellem Gate atomar ersetzen.
    out_dir = os.path.dirname(os.path.abspath(output_kmx)) or "."
    os.makedirs(out_dir, exist_ok=True)
    fd, candidate_path = tempfile.mkstemp(prefix=".kmx-candidate-", suffix=".kmx", dir=out_dir, text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write("\n".join(opt_lines) + "\n")
        if verify_cmd:
            ok, verifier_msg = _run_external_verifier(verify_cmd, candidate_path)
            print(f"OFFIZIELLER VERIFIER: {'PASS' if ok else 'FAIL'} | {verifier_msg}")
            if not ok:
                print("ABBRUCH : Kandidat nicht übernommen; Ausgabe bleibt unverändert.")
                return 3
        else:
            print("HINWEIS : Nur lokale Prüfung; kein offizieller Gesamtverifier ausgeführt.")
        os.replace(candidate_path, output_kmx)
        candidate_path = ""
    finally:
        if candidate_path:
            try:
                os.unlink(candidate_path)
            except OSError:
                pass

    diff_lines = list(difflib.unified_diff(orig_lines, opt_lines, fromfile=input_kmx,
                                           tofile=output_kmx, lineterm="", n=2))
    _atomic_write(diff_out, "\n".join(diff_lines) + "\n")
    print(f"\nOptimierte Datei gespeichert unter: {output_kmx} | Unified Diff: {diff_out}")
    return 0


def selftest() -> int:
    """Schnelle, netzwerkfreie Regressionstests für Metriken, Verifier und Suche."""
    checks: List[Tuple[str, bool]] = []

    m = compute_metrics(["# q999 nur Kommentartext", "CSWAP q3 q61 q2", "CCX q3 q61 q2", "Z_POW q3 0.25"])
    checks.append(("offizielles Q=max+1", m.num_qubits == 62 and m.max_qubit_id == 61))
    checks.append(("CSWAP-Toffoli-Kosten", m.toffoli_cost == 2))
    checks.append(("T-artige Z_POW", m.zpow_t_like == 1 and m.zpow_rot == 0))
    checks.append(("Kommentare keine Instruktionen", m.total_lines == 3))

    same = BitParallelKMXVerifier.verify_equivalence(["CCX q0 q1 q2"], ["CCX q0 q1 q2"])
    different = BitParallelKMXVerifier.verify_equivalence(["X q0"], [])
    checks.append(("exakter Verifier positiv", same.ok and same.exact))
    checks.append(("exakter Verifier negativ", not different.ok))
    # Äquivalent, aber über EINE zu breite Zusammenhangskomponente verschieden -> nur Fuzzing.
    chain = [f"CZ q{i} q{i + 1}" for i in range(BitParallelKMXVerifier.EXACT_QUBIT_LIMIT + 1)]
    fuzzy = BitParallelKMXVerifier.verify_equivalence(chain, chain[::-1], num_batches=1)
    checks.append(("Fuzzing nicht als Beweis", fuzzy.ok and not fuzzy.exact and "kein exakter" in fuzzy.message))
    # Rotation tragendes kleines Fenster: exakt über 128-Bit-Phase prüfbar.
    rot_eq = BitParallelKMXVerifier.verify_equivalence(["Z_POW q0 0.25", "Z_POW q0 0.25"], ["Z_POW q0 0.5"])
    checks.append(("Z_POW-Phasenfusion im Verifier", rot_eq.ok and rot_eq.exact))

    barrier = ["X q0", "R q0 0.25", "X q0"]
    barrier_out, barrier_n = DeterministicKMXEngine.pass_commuting_cancellation(barrier)
    checks.append(("unbekannte/Mess-Ops sind Barrieren", barrier_out == barrier and barrier_n == 0))

    pair = ["CCX q0 q1 q2", "CCX q0 q1 q2"]
    pair_out, pair_n = DeterministicKMXEngine.pass_commuting_cancellation(pair)
    checks.append(("Fallback-Cancellation", pair_out == [] and pair_n == 1))

    tb = AgentToolbox(pair)
    rewrite = tb.apply_verified_rewrite(0, 1, [], "leerer Ersatzblock")
    checks.append(("leerer exakter Rewrite", rewrite.get("accepted") is True and tb.lines == []))

    tb_same = AgentToolbox([f"X q{i}" for i in range(11)])
    same_reject = tb_same.apply_verified_rewrite(0, 0, ["X q0"], "gleich")
    checks.append(("Gleichstand ohne Kürzen abgelehnt", not same_reject.get("accepted")))

    agent = AutonomousKMXAgent(AgentToolbox(pair))
    beam = BeamSearchKMXOptimizer(agent, beam_width=2, max_iterations=2, use_llm=False)
    beam_out = beam.optimize(pair)
    checks.append(("Beam ohne LLM/netzwerk", beam_out == []))

    # --- v4 ---
    E, V = DeterministicKMXEngine, BitParallelKMXVerifier
    comment_out, comment_n = E.pass_commuting_cancellation(["# q9 Kommentar", "X q0", "X q0"])
    checks.append(("Kommentare bleiben erhalten", comment_out == ["# q9 Kommentar"] and comment_n == 1))
    checks.append(("Malformed Ops sind Barrieren", E.pass_commuting_cancellation(["X", "X"])[0] == ["X", "X"]))

    spectators = [f"CX q{i} q{i + 1}" for i in range(10, 10 + V.EXACT_QUBIT_LIMIT)]
    wide_orig = ["CCX q0 q1 q2"] + spectators + ["X q0", "CCX q0 q1 q2"]
    wide_ok = V.verify_equivalence(wide_orig, spectators + ["CX q1 q2", "X q0"])
    wide_bad = V.verify_equivalence(wide_orig, spectators + ["CX q0 q2", "X q0"])
    checks.append(("Differenzkegel beweist breite Fenster exakt", wide_ok.ok and wide_ok.exact))
    checks.append(("Differenzkegel lehnt falschen Rewrite ab", not wide_bad.ok))

    xor_out, xor_n = E.pass_commuting_cancellation(["CCX q0 q1 q2", "CX q3 q2", "CCX q0 q1 q2"])
    checks.append(("Ziel-XOR-Kommutierung", xor_out == ["CX q3 q2"] and xor_n == 1))
    read_out, _ = E.pass_commuting_cancellation(["CCX q0 q1 q2", "CX q2 q0", "CCX q0 q1 q2"])
    checks.append(("Ziel wird gelesen -> keine Auslöschung", len(read_out) == 3))
    swap_out, _ = E.pass_commuting_cancellation(["X q0", "SWAP q0 q1", "X q0"])
    checks.append(("SWAP blockiert berührte Qubits", len(swap_out) == 3))

    for name, win in (("CCX+Z+CCX -> Z+CZ", ["CCX q0 q1 q2", "Z q2", "CCX q0 q1 q2"]),
                      ("CCZ+X+CCZ -> CZ+X", ["CCZ q0 q1 q2", "X q0", "CCZ q0 q1 q2"])):
        synth = agent.synthesize_algebraic_ccx_merge(win)
        checks.append((f"{name} (0 Toffolis)", synth is not None and compute_metrics(synth[0]).toffoli_cost == 0))
    conj = agent.synthesize_algebraic_ccx_merge(["CCX q0 q1 q2", "CZ q3 q2", "CCX q0 q1 q2"])
    checks.append(("CCX+CZ+CCX -> CZ+CCZ (1 Toffoli)", conj is not None and compute_metrics(conj[0]).toffoli_cost == 1))

    frac_out, frac_n = E.pass_commuting_cancellation(["Z_POW q0 1/3", "Z_POW q0 1/3"])
    checks.append(("Exakte Z_POW-Bruchfusion", frac_out == ["Z_POW q0 2/3"] and frac_n == 1))
    checks.append(("Dyadische Z_POW exakt formatiert",
                   E._format_phase_gate("q0", Fraction(127, 64), None) == "Z_POW q0 1.984375"))
    # --- Funde aus dem adversarialen Review ---
    checks.append(("Dezimalsummen bleiben dezimal",
                   E.pass_commuting_cancellation(["Z_POW q0 0.1", "Z_POW q0 0.2"])[0] == ["Z_POW q0 0.3"]
                   and E.pass_commuting_cancellation(["TDAG q0", "Z_POW q0 0.1"])[0] == ["Z_POW q0 1.85"]
                   and _exact_decimal(Fraction(1, 1 << 70)) == "0." + "0" * 21 + str(5 ** 70)))
    checks.append(("Winzige Z_POW nicht als Identität bewiesen", not V.verify_equivalence(["Z_POW q0 1e-40"], []).ok))
    checks.append(("Doppelte Operanden unverifizierbar", not V.verify_equivalence(["Z q0"], ["CZ q0 q0"]).ok))
    alias = ["CX q1 q2", "X q01", "CX q1 q2"]
    checks.append(("q01 ist Barriere, kein fremdes Qubit", E.pass_commuting_cancellation(alias)[0] == alias))
    dbl = ["X q0 if b0 if b1", "X q0 if b0"]
    checks.append(("Doppelte Bedingung ist Barriere", E.pass_commuting_cancellation(dbl)[0] == dbl))
    tb_c = AgentToolbox(["CCX q0 q1 q2", "# scratch q9", "CX q0 q1", "CCX q0 q1 q2"])
    res_c = tb_c.apply_verified_rewrite(0, 3, ["CX q0 q2", "CX q0 q1", "X q9", "X q9"], "Kommentar-Qubit")
    checks.append(("Kommentar gibt kein Qubit frei", not res_c.get("accepted")))
    fan = [f"CX q{i + 1} q0" for i in range(6000)]
    checks.append(("Fan-in ohne Partner bleibt linear", E.pass_commuting_cancellation(fan)[0] == fan))

    scope = AgentToolbox(pair).apply_verified_rewrite(0, 1, ["CX q7 q8", "CX q7 q8"], "fremde Qubits")
    checks.append(("Qubit-Scope-Sperre", not scope.get("accepted") and "fensterfremde" in scope.get("reason", "")))

    class _FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self):
            return b'{"choices":[{"message":{"content":"[]"}}]}'

    real_urlopen = urllib.request.urlopen
    try:
        urllib.request.urlopen = lambda *a, **k: _FakeResponse()
        llm_agent = AutonomousKMXAgent(AgentToolbox(pair))
        empty_cand, cached_cand = llm_agent.query_llm_for_window(pair), llm_agent.query_llm_for_window(pair)
    finally:
        urllib.request.urlopen = real_urlopen
    checks.append(("leerer LLM-Kandidat + Cache", empty_cand == [] and cached_cand == [] and llm_agent._llm_calls == 1))

    failed = [name for name, ok in checks if not ok]
    for name, ok in checks:
        print(f"[{'OK' if ok else 'FAIL'}] {name}")
    print(f"SELFTEST: {len(checks) - len(failed)}/{len(checks)} bestanden")
    return 1 if failed else 0


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--selftest":
        sys.exit(selftest())
    in_file = sys.argv[1] if len(sys.argv) > 1 else "invsqrt.kmx"
    out_file = sys.argv[2] if len(sys.argv) > 2 else "invsqrt_optimized.kmx"
    diff_file = sys.argv[3] if len(sys.argv) > 3 else "invsqrt_optimization.diff"
    if os.path.exists(in_file):
        sys.exit(run_pipeline(in_file, out_file, diff_file))
    else:
        print(f"Hinweis: Lege '{in_file}' ins Arbeitsverzeichnis oder übergib den Pfad als Argument.")
        sys.exit(1)
