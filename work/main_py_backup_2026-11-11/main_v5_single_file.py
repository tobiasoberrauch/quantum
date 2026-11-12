"""
main.py (v5) — Verifier-gestützter Optimierer und KI-Agent für kickmix-Schaltkreise (.kmx / .kmb).

Eine Datei, Python >= 3.10, nur Standardbibliothek. Optional: numpy (exakter invsqrt-Score), kickmix (Gegenprüfung,
.kmb). kmx_agent_kimi.py wird NICHT mehr gebraucht: Parser, Simulator und alle Pässe stehen hier.

Was die Datei tut
  1. Parser für das kickmix-Textformat v2 (inkl. CSWAP, Z_POW, R, INFO_TAG, PUSH_CONDITION if bN).
     T/TDAG gibt es in kickmix nicht; Phasen sind Z und Z_POW mit dezimalem Exponenten.
  2. Wortparalleler Simulator für das volle Instruktionsset. Für invsqrt läuft die GESAMTE gültige
     Eingabedomäne (x in [1, 3133452]) in einem Durchlauf, jede Lane ein Bit einer Python-Ganzzahl.
  3. Verifier in drei Stufen:
       L1  exakt:       Wahrheitstabelle eines Fensters über alle Belegungen (inkl. Messergebnisse), bis 20 Variablen
       L2  kontextuell: Fenster auf den tatsächlich erreichbaren Zuständen (nutzt Don't-Cares der Domäne)
       L3  End-to-End:  Original gegen Ergebnis auf der ganzen Domäne (Register, Scratch, 128-Bit-Phase)
     Breite unitäre Fenster werden vor der Wahrheitstabelle auf ihren Differenzkegel reduziert; Z_POW-Winkel
     außerhalb des 2^-127-Rasters gelten nie als bewiesen.
  4. Deterministische Pässe bis zum Fixpunkt, jeder einzeln End-to-End geprüft:
       - Auslöschung kommutierender Paare und exakte Z/Z_POW-Phasenfusion (bit-, bedingungs- und HMR-bewusst)
       - simulationsgeführte Reduktion: nie feuernde Toffolis, implizierte Kontrollen, Toffoli -> CX-Kaskade,
         Toffoli-Gruppen auf einem Ziel, Rotationen auf wertgleichen Qubits
       - Measurement-Based Uncomputation für reversible Uncompute-Ketten
       - Qubit-Repacking per Intervallfärbung (Q = größter Index + 1)
  5. Exakter invsqrt-Score, gerechnet wie der offizielle Verifier (Phase je x gegen 1/sqrt(x), Rotationskosten aus
     der Reserve). Optional --trim-rotations: feine Rotationen streichen, wenn der exakte Score dadurch sinkt.
  6. LLM-Stufe: Tool-Calling-Agent (mehrere Modelle im Staffellauf) oder, für Modelle ohne Tool-Calling, ein
     JSON-Modus je Fenster mit Fakten und einer Nachbesserung per Gegenbeispiel. Standard-Endpunkt ist die lokale
     Weinstadt-KI; nicht erreichbar -> wird übersprungen.
  7. Offizielles Gate (OFFICIAL_VERIFY_CMD / --verify-cmd) VOR dem atomaren Schreiben; steigen die Kosten, wird
     nichts geschrieben.
  8. Research-Brief für Deep-Research-Werkzeuge; das Ergebnis geht per --playbook an den Agenten.

Aufruf
  python main.py invsqrt.kmx [OUT] [DIFF]          wie bisher: Pässe + LLM-Stufe + Gate
  python main.py optimize invsqrt.kmx -o out.kmx   nur deterministische Pässe
  python main.py agent invsqrt.kmx -o out.kmx --models MODELL_A,MODELL_B --api-url URL
  python main.py research invsqrt.kmx --out research_brief.md
  python main.py check original.kmx kandidat.kmx   zwei Dateien End-to-End vergleichen, exakter Score
  python main.py info invsqrt.kmx                  Kennzahlen, Score, Toffoli-Profil
  python main.py --selftest

Umgebungsvariablen (wie in v3, soweit noch sinnvoll)
  LLM_API_URL, LLM_MODEL, LLM_API_KEY | OPENROUTER_API_KEY | OPENAI_API_KEY, LLM_MAX_TOKENS, LLM_MAX_CALLS
  (0 = LLM aus), LLM_TIMEOUT, LLM_EXTRA_BODY, LLM_EXTRA_HEADERS, LLM_TEMPERATURE, LLM_MODE=auto|tools|json,
  OFFICIAL_VERIFY_CMD, REQUIRE_OFFICIAL_VERIFY, OFFICIAL_VERIFY_TIMEOUT, COST_ROT_WEIGHT,
  ALLOW_PROBABILISTIC_REWRITES, TRIM_ROTATIONS, EXACT_ONLY.
  Entfallen: OPT_MODE und BEAM_* (die Pässe laufen bis zum Fixpunkt) sowie LEGACY_UNSAFE_PASSES
  (das Repacking ist jetzt simulationsgestützt und End-to-End geprüft).
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import heapq
import json
import math
import os
import random
import re
import shlex
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from fractions import Fraction
from typing import Any, Callable, Dict, Iterator, List, Optional, Sequence, Set, Tuple

try:  # optional: offizielle Bibliothek nur zur Gegenprüfung
    import kickmix as _km
except Exception:  # pragma: no cover
    _km = None
try:  # optional: nur für den exakten invsqrt-Score
    import numpy as _np
except Exception:  # pragma: no cover
    _np = None


# =====================================================================
# 1. PARSER FÜR DAS KICKMIX-TEXTFORMAT (.kmx, Version 2)
# =====================================================================

GATE_ARITY = {
    "X": 1,
    "CX": 2,
    "CCX": 3,
    "Z": 1,
    "CZ": 2,
    "CCZ": 3,
    "SWAP": 2,
    "CSWAP": 3,
    "R": 1,
}
BIT_OPS = ("BIT_INVERT", "BIT_STORE0", "BIT_STORE1")
META_OPS = ("REGISTER", "APPEND_TO_REGISTER", "INFO_TAG", "DEBUG_PRINT")
TOFFOLI_LIKE = ("CCX", "CCZ", "CSWAP")
X_TYPE = ("X", "CX", "CCX")
SELF_INVERSE = (
    "X",
    "CX",
    "CCX",
    "CZ",
    "CCZ",
    "SWAP",
    "CSWAP",
    "NEG",
)  # Z läuft über die Phasenfusion
_EXP_RE = re.compile(r"^[-+]?\d+\.\d+$")  # wie kickmix: [-+]?[0-9]+.[0-9]+

QUBIT_PREFIX, BIT_PREFIX, REGISTER_PREFIX = "q", "b", "r"
COMMENT_MARKER = "#"
CONDITION_KEYWORD = "if"

OpKey = Tuple[str, Tuple[str, ...], Optional[int]]


class KmxError(ValueError):
    """Syntaktisch oder strukturell ungültige kickmix-Eingabe (Meldung nennt Fundstelle und Instruktion)."""


def _is_id(tok: str, prefix: str) -> bool:
    """Ist `tok` ein Bezeichner der Form <prefix><Dezimalzahl> (q7, b3, r0)?"""
    return len(tok) > 1 and tok[0] == prefix and tok[1:].isdigit()


class Op:
    """Eine kickmix-Instruktion. `args` sind die Ziel-Token in Originalreihenfolge.

    `qs` sind die Qubit-Indizes in Argumentreihenfolge, `bit` das erste Bit-Argument (sonst None), `cond` das Bit
    einer `if bN`-Bedingung und `text` ein angehängter Quoted-Text samt Anführungszeichen.
    """

    __slots__ = ("name", "args", "cond", "text", "qs", "bit")

    def __init__(
        self,
        name: str,
        args: Sequence[str] = (),
        cond: Optional[int] = None,
        text: Optional[str] = None,
    ) -> None:
        self.name = name
        self.args = tuple(args)
        self.cond = cond
        self.text = text
        self.qs = tuple(int(a[1:]) for a in self.args if _is_id(a, QUBIT_PREFIX))
        bits = [int(a[1:]) for a in self.args if _is_id(a, BIT_PREFIX)]
        self.bit = bits[0] if bits else None

    def fmt(self) -> str:
        """Die Instruktion als kanonische .kmx-Zeile (v2-Schreibweise, ohne Zeilenende)."""
        parts = [self.name, *self.args]
        if self.cond is not None:
            parts += [CONDITION_KEYWORD, f"{BIT_PREFIX}{self.cond}"]
        if self.text is not None:
            parts.append(self.text)
        return " ".join(parts)

    __repr__ = fmt

    def renamed(self, qmap: Dict[int, int]) -> "Op":
        """Dieselbe Instruktion mit umbenannten Qubits; unverändert (dasselbe Objekt), wenn `qmap` keins betrifft."""
        if not any(q in qmap for q in self.qs):
            return self
        args = tuple(
            (
                f"{QUBIT_PREFIX}{qmap.get(int(a[1:]), int(a[1:]))}"
                if _is_id(a, QUBIT_PREFIX)
                else a
            )
            for a in self.args
        )
        return Op(self.name, args, self.cond, self.text)

    def key(self) -> OpKey:
        """Kanonischer Schlüssel: gleiche Schlüssel = gleiche Operation.

        Argumente, deren Reihenfolge die Wirkung nicht ändert (beide Kontrollen von CCX, alle Ziele von CZ/CCZ/SWAP,
        das Tauschpaar von CSWAP), werden sortiert."""
        args = self.args
        if self.name in ("CZ", "CCZ", "SWAP"):
            args = tuple(sorted(args))
        elif self.name == "CCX":
            args = tuple(sorted(args[:2])) + args[2:]
        elif self.name == "CSWAP":
            args = args[:1] + tuple(sorted(args[1:]))
        return (self.name, args, self.cond)


def _operand_shape_error(op: Op) -> Optional[str]:
    """Fehlertext, falls Anzahl oder Art der Argumente nicht zur Instruktion passen; None, wenn alles stimmt."""
    name, args = op.name, op.args
    if name in GATE_ARITY:
        arity = GATE_ARITY[name]
        if len(args) != arity or len(op.qs) != arity:
            return f"{name} erwartet {arity} Qubit(s)"
        if len(set(op.qs)) != len(op.qs):
            return "dasselbe Qubit kommt mehrfach vor"
    elif name == "HMR":
        if (
            len(args) != 2
            or not _is_id(args[0], QUBIT_PREFIX)
            or not _is_id(args[1], BIT_PREFIX)
        ):
            return "HMR erwartet 'HMR qN bN'"
    elif name == "Z_POW":
        if (
            len(args) != 2
            or not _is_id(args[0], QUBIT_PREFIX)
            or not _EXP_RE.match(args[1])
        ):
            return "Z_POW erwartet 'Z_POW qN <dezimaler Exponent>'"
    elif name == "NEG":
        if args:
            return "NEG hat keine Ziele"
    elif name == "PUSH_CONDITION":
        if args or op.cond is None:
            return "PUSH_CONDITION erwartet 'PUSH_CONDITION if bN'"
    elif name == "POP_CONDITION":
        if args or op.cond is not None:
            return "POP_CONDITION hat keine Argumente"
    elif name in BIT_OPS:
        if len(args) != 1 or not _is_id(args[0], BIT_PREFIX):
            return f"{name} erwartet genau ein Bit"
    elif name not in META_OPS:
        return "unbekannte Instruktion"
    return None


def _validate(op: Op, where: str = "") -> None:
    """Wirft KmxError, wenn `op` keine wohlgeformte Instruktion ist. Meta-Instruktionen werden nicht geprüft."""
    problem = _operand_shape_error(op)
    if problem is not None:
        raise KmxError(f"{where}{op.fmt()!r}: {problem}")


def _split_trailing_condition(
    tokens: List[str], raw: str, where: str
) -> Tuple[Optional[int], List[str]]:
    """Trennt ein abschließendes `if bN` ab: (Bedingungsbit oder None, übrige Token)."""
    if len(tokens) < 2 or tokens[-2] != CONDITION_KEYWORD:
        return None, tokens
    if not _is_id(tokens[-1], BIT_PREFIX):
        raise KmxError(f"{where}{raw!r}: Bedingung muss ein Bit sein")
    return int(tokens[-1][1:]), tokens[:-2]


def parse_line(raw: str, where: str = "") -> Optional[Op]:
    """Parst eine .kmx-Zeile zu einer geprüften Instruktion; None für Leer- und reine Kommentarzeilen.

    `where` wird Fehlermeldungen vorangestellt (z. B. "Zeile 12: ")."""
    # Wie kickmix beim Lesen einer Datei: '#' innerhalb des Quoted-Texts ist ein Zeichen, kein Kommentar.
    quote_at, hash_at = raw.find('"'), raw.find(COMMENT_MARKER)
    text = None
    if quote_at >= 0 and (hash_at < 0 or quote_at < hash_at):
        close_at = raw.find('"', quote_at + 1)
        if close_at < 0:
            raise KmxError(f"{where}{raw!r}: Text nicht abgeschlossen")
        tail = raw[close_at + 1 :].strip()
        if tail and not tail.startswith(COMMENT_MARKER):
            raise KmxError(
                f"{where}{raw!r}: nach dem Text darf nur ein Kommentar folgen"
            )
        text, body = raw[quote_at : close_at + 1], raw[:quote_at].strip()
    else:
        body = raw.split(COMMENT_MARKER, 1)[0].strip()
        if not body:
            return None
    tokens = body.split()
    if not tokens:
        raise KmxError(f"{where}{raw!r}: Instruktionsname fehlt")
    name = tokens[0]
    cond, rest = _split_trailing_condition(tokens[1:], raw, where)
    if (
        name == "PUSH_CONDITION"
        and cond is None
        and len(rest) == 1
        and _is_id(rest[0], BIT_PREFIX)
    ):
        cond, rest = int(rest[0][1:]), []  # v1-Schreibweise tolerieren, v2 ausgeben
    op = Op(name, rest, cond, text)
    _validate(op, where)
    return op


def parse_text(text: str) -> List[Op]:
    """Parst einen ganzen .kmx-Text; Fehlermeldungen nennen die 1-basierte Zeilennummer."""
    ops = []
    for line_no, raw in enumerate(text.splitlines(), 1):
        op = parse_line(raw, f"Zeile {line_no}: ")
        if op is not None:
            ops.append(op)
    return ops


def parse_lines(lines: Sequence[str]) -> List[Op]:
    """Parst eine Liste einzelner Zeilen (z. B. aus einer LLM-Antwort); Fehlermeldungen nennen den 0-basierten Index.

    Die Einträge stammen aus nicht vertrauenswürdigem JSON, deshalb wird der Typ jedes Eintrags geprüft.
    """
    ops = []
    for index, raw in enumerate(lines):
        if not isinstance(raw, str):
            raise KmxError(f"Eintrag {index} ist kein String")
        op = parse_line(raw, f"Eintrag {index}: ")
        if op is not None:
            ops.append(op)
    return ops


def format_ops(ops: Sequence[Op]) -> str:
    """Serialisiert Instruktionen als .kmx-Text, eine je Zeile, mit abschließendem Zeilenumbruch."""
    return "\n".join(o.fmt() for o in ops) + "\n"


# =====================================================================
# 2. LAYOUT (REGISTER), METRIKEN UND KOSTENMODELL
# =====================================================================

INVSQRT_WIDTH, INVSQRT_MAX_X = 22, 3133452  # n_p = 10: x in [1, 3*(2^10-2)^2]
INVSQRT_MIN_X = 1
VALUE_RANGE_SEPARATOR = ":"


@dataclass
class Layout:
    """Registerstruktur eines Schaltkreises: welche Qubits Eingabe sind, welche ihren Index behalten müssen und auf
    welchem Wertebereich des Eingaberegisters der Schaltkreis korrekt sein muss."""

    registers: Dict[
        int, List[str]
    ]  # Registernummer -> Token (qN / bN) in Deklarationsreihenfolge
    names: Dict[int, str]  # Registernummer -> Name aus dem REGISTER-Text
    input_qubits: List[int]  # Eingaberegister, niederwertigstes Bit zuerst
    pinned: Set[int]  # alle Register-Qubits (behalten ihren Index)
    reg_bits: List[int]  # klassische Bits, die in einem Register stehen (aufsteigend)
    lo: Optional[int] = None  # gültiger Wertebereich des Eingaberegisters
    hi: Optional[int] = None
    notes: List[str] = field(default_factory=list)
    invsqrt: bool = False  # offizieller invsqrt-Kontrakt (22 Bit, x in [1, 3133452])


def _declared_registers(
    ops: Sequence[Op],
) -> Tuple[Dict[int, List[str]], Dict[int, str]]:
    """Sammelt REGISTER / APPEND_TO_REGISTER ein: (Registernummer -> Token, Registernummer -> Name).
    Die Schlüsselreihenfolge ist die des ersten Auftretens im Schaltkreis."""
    registers: Dict[int, List[str]] = defaultdict(list)
    names: Dict[int, str] = {}
    for o in ops:
        if (
            o.name == "APPEND_TO_REGISTER"
            and len(o.args) == 2
            and _is_id(o.args[1], REGISTER_PREFIX)
        ):
            registers[int(o.args[1][1:])].append(o.args[0])
        elif o.name == "REGISTER" and o.args and _is_id(o.args[0], REGISTER_PREFIX):
            registers.setdefault(int(o.args[0][1:]), [])
            if o.text:
                names[int(o.args[0][1:])] = o.text.strip('"')
    return registers, names


def _select_input_qubits(
    qubit_registers: Dict[int, List[int]],
    names: Dict[int, str],
    input_register: str,
    fallback_inputs: int,
    notes: List[str],
) -> List[int]:
    """Qubits des Eingaberegisters: das Register namens `input_register`, sonst das mit der kleinsten Nummer, sonst
    q0..q{fallback_inputs-1}. Jede Abweichung vom Normalfall wird in `notes` vermerkt.
    """
    chosen = next((r for r in qubit_registers if names.get(r) == input_register), None)
    if chosen is None and qubit_registers:
        chosen = min(qubit_registers)
        notes.append(
            f"Kein Register namens '{input_register}' gefunden; nutze r{chosen} als Eingabe."
        )
    if chosen is None:
        notes.append(
            f"Keine REGISTER-Deklaration gefunden; nehme q0..q{fallback_inputs - 1} als Eingaberegister an."
        )
        return list(range(fallback_inputs))
    return qubit_registers[chosen]


def _parse_value_range(value_range: str, width: int) -> Tuple[int, int]:
    """'LO:HI' -> (LO, HI); verlangt 0 <= LO <= HI < 2^width, sonst wäre die 'vollständige' Domäne gelogen."""
    try:
        lo_text, hi_text = value_range.split(VALUE_RANGE_SEPARATOR)
        lo, hi = int(lo_text), int(hi_text)
    except ValueError:
        raise KmxError(
            f"--range erwartet LO:HI mit ganzen Zahlen, nicht {value_range!r}"
        ) from None
    if not 0 <= lo <= hi < (1 << width):
        raise KmxError(
            f"--range {value_range}: verlangt 0 <= LO <= HI < 2^{width} (Breite des Eingaberegisters)"
        )
    return lo, hi


def analyze_layout(
    ops: Sequence[Op],
    input_register: str = "x",
    value_range: Optional[str] = None,
    fallback_inputs: int = INVSQRT_WIDTH,
) -> Layout:
    """Leitet das Layout aus den Registerdeklarationen ab.

    `value_range` ("LO:HI") legt den gültigen Wertebereich fest. Ohne Angabe gilt der invsqrt-Kontrakt, sobald
    das Eingaberegister 22 Qubits hat und es keine weiteren Register-Qubits gibt; sonst bleibt der Bereich offen.
    """
    registers, names = _declared_registers(ops)
    notes: List[str] = []
    qubit_registers = {
        r: [int(t[1:]) for t in tokens if t[0] == QUBIT_PREFIX]
        for r, tokens in registers.items()
    }
    qubit_registers = {r: qubits for r, qubits in qubit_registers.items() if qubits}
    inputs = _select_input_qubits(
        qubit_registers, names, input_register, fallback_inputs, notes
    )
    pinned = set(inputs)
    for qubits in qubit_registers.values():
        pinned.update(qubits)
    reg_bits = sorted(
        {
            int(t[1:])
            for tokens in registers.values()
            for t in tokens
            if t[0] == BIT_PREFIX
        }
    )
    lo = hi = None
    if value_range:
        lo, hi = _parse_value_range(value_range, len(inputs))
    elif len(inputs) == INVSQRT_WIDTH and len(pinned) == INVSQRT_WIDTH:
        lo, hi = INVSQRT_MIN_X, INVSQRT_MAX_X
        notes.append(
            f"{INVSQRT_WIDTH}-Bit-Eingaberegister erkannt: nehme den invsqrt-Kontrakt "
            f"x in [{INVSQRT_MIN_X}, {INVSQRT_MAX_X}] an (mit --range LO:HI überschreibbar)."
        )
    is_invsqrt = (
        (lo, hi) == (INVSQRT_MIN_X, INVSQRT_MAX_X)
        and len(inputs) == INVSQRT_WIDTH
        and pinned == set(inputs)
    )
    return Layout(
        dict(registers), names, inputs, pinned, reg_bits, lo, hi, notes, is_invsqrt
    )


# Toffoli-Äquivalente je FEINER Z_POW-Rotation für die Schnellschätzung. Offiziell (0.56*log2(1/eps)+5.3)/4;
# für invsqrt rechnet `invsqrt_score` den Wert exakt aus, dieser Schätzwert gilt nur als Rückfallebene.
DEFAULT_ROT_WEIGHT = "7.2"
ROT_WEIGHT = float(os.environ.get("COST_ROT_WEIGHT", DEFAULT_ROT_WEIGHT))
T_PER_TOFFOLI = 4.0  # vier T-Gatter kosten so viel wie ein Toffoli

# Phasen sind 128-Bit-Festkommazahlen: Exponent e (Halbdrehungen) <-> round(e * 2^127) mod 2^128.
PHASE_FRACTION_BITS = 127
PHASE_WORD_BITS = 128
ZPOW_LEVEL_CLIFFORD, ZPOW_LEVEL_T, ZPOW_LEVEL_ROTATION = 0, 2, 3
_CLIFFORD_STEP = 1 << (PHASE_FRACTION_BITS - 1)  # Vielfache einer Vierteldrehung (S)
_T_STEP = 1 << (PHASE_FRACTION_BITS - 2)  # Vielfache einer Achteldrehung (T)

ZpowDetails = Tuple[
    Tuple[int, ...], int, int
]  # (gesetzte Bit-Ebenen, Stufe, Festkommawert)

_ZPOW_CACHE: Dict[str, ZpowDetails] = {}


def _zpow_full(exp: str) -> ZpowDetails:
    """Wie `zpow_info`, zusätzlich mit dem 128-Bit-Festkommawert des Exponenten; je Exponent-Text gecacht."""
    hit = _ZPOW_CACHE.get(exp)
    if hit is None:
        fixed = round(Fraction(exp) * (1 << PHASE_FRACTION_BITS)) % (
            1 << PHASE_WORD_BITS
        )
        planes = tuple(j for j in range(PHASE_WORD_BITS) if (fixed >> j) & 1)
        if fixed % _CLIFFORD_STEP == 0:
            level = ZPOW_LEVEL_CLIFFORD
        elif fixed % _T_STEP == 0:
            level = ZPOW_LEVEL_T
        else:
            level = ZPOW_LEVEL_ROTATION
        hit = _ZPOW_CACHE[exp] = (planes, level, fixed)
    return hit


def zpow_info(exp: str) -> Tuple[Tuple[int, ...], int]:
    """Exponent (Halbdrehungen) -> (gesetzte Bit-Ebenen in Einheiten von 2^-127, Stufe).
    Stufe: 0 = Clifford (frei), 2 = T-artig (1 T), 3 = feine Rotation."""
    return _zpow_full(exp)[:2]


def phase_exponent(op: "Op") -> Optional[Fraction]:
    """Exponent von Z / Z_POW in Halbdrehungen, falls er sich ohne Rundung auf dem 2^-127-Raster darstellen lässt
    (nur dann ist das Zusammenfassen zweier Rotationen bitgenau)."""
    if op.name == "Z":
        return Fraction(1)
    if op.name == "Z_POW":
        exponent = Fraction(op.args[1])
        if (exponent * (1 << PHASE_FRACTION_BITS)).denominator == 1:
            return exponent
    return None


def phase_op(q: int, exponent: Fraction, cond: Optional[int]) -> Optional["Op"]:
    """Phasengatter für einen Exponenten (mod 2): None bei 0, Z bei 1, sonst Z_POW mit exakter Dezimalzahl.
    kickmix verlangt die Form [-+]?[0-9]+.[0-9]+ - keine Brüche, keine Exponentialschreibweise.
    """
    reduced = exponent % 2
    if reduced > 1:
        reduced -= 2
    if reduced == 0:
        return None
    if reduced == 1:
        return Op("Z", (f"q{q}",), cond)
    k = reduced.denominator.bit_length() - 1  # Nenner ist 2^k
    digits = str(abs(reduced.numerator) * 5**k).rjust(
        k + 1, "0"
    )  # n / 2^k = n * 5^k / 10^k
    fraction_digits = digits[-k:].rstrip("0") or "0"
    sign = "-" if reduced < 0 else ""
    return Op("Z_POW", (f"q{q}", f"{sign}{digits[:-k]}.{fraction_digits}"), cond)


@dataclass
class Metrics:
    """Statische Kennzahlen eines Schaltkreises (ohne Simulation, also ohne Rücksicht auf Bedingungen)."""

    ops: int
    num_qubits: int  # wie kickmix: größter Qubit-Index + 1  (das ist Q im Score)
    distinct_qubits: int
    counts: Counter  # Instruktionsname -> Anzahl
    toffoli: int  # CCX + CCZ + CSWAP, statisch gezählt
    t_like: int
    rotations: int  # nicht-Clifford-, nicht-T-Z_POW

    # Namen der Vorgängerversion (v3), damit vorhandene Auswerteskripte weiterlaufen
    @property
    def toffoli_cost(self) -> int:
        """v3-Name von `toffoli`."""
        return self.toffoli

    @property
    def inner_cost(self) -> float:
        """Geschätzte Toffoli-Äquivalente: Toffoli + T/4 + ROT_WEIGHT x Rotationen."""
        return self.toffoli + self.t_like / T_PER_TOFFOLI + ROT_WEIGHT * self.rotations

    @property
    def real_cost(self) -> float:
        """Geschätzter Score Q x `inner_cost`."""
        return self.num_qubits * self.inner_cost

    def summary(self) -> str:
        """Einzeilige Übersicht für Log und Konsole."""
        c = self.counts
        return (
            f"Q={self.num_qubits} ({self.distinct_qubits} benutzt) | Toffoli-artig={self.toffoli} "
            f"(CCX {c['CCX']}, CCZ {c['CCZ']}, CSWAP {c['CSWAP']}) | T={self.t_like} | Rot={self.rotations} | "
            f"CX {c['CX']} | CZ {c['CZ']} | HMR {c['HMR']} | Instruktionen {self.ops}"
        )


def compute_metrics(ops: Sequence[Any]) -> Metrics:
    """Statische Kennzahlen. Nimmt Op-Listen oder (wie v3) eine Liste von Textzeilen."""
    if ops and isinstance(ops[0], str):
        ops = parse_lines(ops)
    counts: Counter = Counter()
    qubits: Set[int] = set()
    t_like = rotations = 0
    for o in ops:
        counts[o.name] += 1
        qubits.update(o.qs)
        if o.name == "Z_POW":
            level = zpow_info(o.args[1])[1]
            t_like += level == ZPOW_LEVEL_T
            rotations += level == ZPOW_LEVEL_ROTATION
    toffoli = sum(counts[n] for n in TOFFOLI_LIKE)
    num_qubits = (max(qubits) + 1) if qubits else 0
    return Metrics(
        len(ops), num_qubits, len(qubits), counts, toffoli, t_like, rotations
    )


def score_estimate(
    q: int, toffoli_mean: float, t_mean: float, rot_mean: float, rot_weight: float
) -> float:
    """Schnellschätzung S = Q x (Toffoli + T/4 + rot_weight x Rotationen), Mittel pro Shot."""
    return q * (toffoli_mean + t_mean / T_PER_TOFFOLI + rot_mean * rot_weight)


def circuit_cost(lines: Sequence[Any]) -> float:
    """v3-Schnittstelle: statische Kostenschätzung einer Zeilen- oder Op-Liste."""
    return compute_metrics(lines).real_cost if lines else 0.0


# =====================================================================
# 3. DOMÄNEN UND WORTPARALLELER SIMULATOR (VOLLES INSTRUKTIONSSET)
# =====================================================================

# Ein Lane-Vektor ist eine Python-Ganzzahl: Bit i trägt den Wert der Trajektorie (Lane) i.
LaneVector = int
# Kompilierte Instruktion, siehe compile_op: (Code, q0, q1, q2, Bit, Bedingungsbit, Z_POW-Ebenen, Kostenklasse).
CompiledOp = Tuple[
    int,
    Optional[int],
    Optional[int],
    Optional[int],
    Optional[int],
    Optional[int],
    Optional[Tuple[int, ...]],
    int,
]
# Schlüssel eines Messergebnisses: (Art "H"|"R", Bit bzw. Qubit, wievielte Ziehung).
MeasurementKey = Tuple[str, int, int]

PHASE_PLANES = 128  # Bit-Ebenen des Phasenakkumulators, Einheit 2^-127 Halbdrehung
SIGN_PLANE = PHASE_PLANES - 1  # höchstwertige Ebene = Vorzeichen (eine Halbdrehung)

# Kostenklassen einer kompilierten Instruktion (letztes Tupelfeld); 0 = wird nicht gezählt.
# Die Werte 2 und 3 sind die Stufen aus zpow_info. step vergleicht aus Tempogründen gegen die Literale.
COST_CLASS_NONE, COST_CLASS_TOFFOLI, COST_CLASS_T, COST_CLASS_ROTATION = 0, 1, 2, 3

SAMPLE_DOMAIN_SEED = (
    1  # Startwert der Stichproben-Domäne (zweites Ergebnis von build_domains)
)
FALLBACK_DOMAIN_SEED = (
    2  # Startwert der Ersatz-Domäne, wenn die Eingaben nicht aufzählbar sind
)


def pattern_bit(k: int, m: int) -> LaneVector:
    """Lane-Vektor der Länge m: Lane i trägt Bit k der Zahl i."""
    half = 1 << k
    v, length = ((1 << half) - 1) << half, half << 1
    while length < m:
        v |= v << length
        length <<= 1
    return v & ((1 << m) - 1)


class Domain:
    """Menge gleichzeitig simulierter Trajektorien (Lanes).

    `init_q` belegt die Qubits je Lane vor, `exhaustive` sagt, ob die Lanes ALLE gültigen Eingaben abdecken
    (nur dann sind Simulationsfakten Beweise), `describe` benennt eine Lane für Meldungen. Ist `tt` gesetzt,
    kommen Messergebnisse aus dieser Tabelle statt aus dem Zufallsgenerator (Wahrheitstabelle von L1).
    """

    def __init__(
        self,
        n: int,
        init_q: Dict[int, LaneVector],
        exhaustive: bool,
        label: str,
        describe: Callable[[int], str],
        tt: Optional[Dict[Tuple, LaneVector]] = None,
    ) -> None:
        self.n, self.ALL, self.init_q = n, (1 << n) - 1, init_q
        self.exhaustive, self.label, self.describe, self.tt = (
            exhaustive,
            label,
            describe,
            tt,
        )


def exhaustive_domain(layout: Layout) -> Domain:
    """Domäne mit genau einer Lane je gültigem Eingabewert x in [lo, hi] (Lane i trägt x = lo + i)."""
    lo, hi = layout.lo, layout.hi
    n = hi - lo + 1
    init = {q: pattern_bit(k, hi + 1) >> lo for k, q in enumerate(layout.input_qubits)}
    return Domain(
        n,
        init,
        True,
        f"alle {n:,} Eingaben x in [{lo}, {hi}]",
        lambda lane: f"x={lo + lane}",
    )


def _boundary_sample_values(lo: int, hi: int, width: int) -> List[int]:
    """Aufsteigend sortierte Randwerte des Eingabebereichs: beide Enden und alle Zweierpotenzen +-1."""
    vals = {lo, hi, min(hi, lo + 1), max(lo, hi - 1)}
    for k in range(width + 1):
        for d in (-1, 0, 1):
            if lo <= (1 << k) + d <= hi:
                vals.add((1 << k) + d)
    return sorted(vals)


def sample_domain(layout: Layout, n: int, seed: int) -> Domain:
    """Stichproben-Domäne mit n Lanes: zuerst die Randwerte, dann Zufallswerte aus [lo, hi].
    Register-Qubits außerhalb des Eingaberegisters werden zufällig vorbelegt."""
    rng = random.Random(seed)
    width = len(layout.input_qubits)
    lo = layout.lo if layout.lo is not None else 0
    hi = layout.hi if layout.hi is not None else (1 << width) - 1
    vals_l = _boundary_sample_values(lo, hi, width)[:n]
    while len(vals_l) < n:
        vals_l.append(rng.randint(lo, hi))
    init = {
        q: sum(((v >> k) & 1) << i for i, v in enumerate(vals_l))
        for k, q in enumerate(layout.input_qubits)
    }
    for q in sorted(layout.pinned - set(layout.input_qubits)):
        init[q] = rng.getrandbits(n)
    return Domain(
        n, init, False, f"{n:,} Stichproben-Eingaben", lambda lane: f"x={vals_l[lane]}"
    )


def build_domains(
    layout: Layout, max_exhaustive: int, sample_lanes: int, fallback_lanes: int
) -> Tuple[Domain, Domain]:
    """Liefert (Hauptdomäne, Stichproben-Domäne). Die Hauptdomäne ist vollständig, wenn das Eingaberegister
    das einzige Register ist und sein Wertebereich höchstens `max_exhaustive` Werte hat; sonst eine größere
    Stichprobe."""
    smp = sample_domain(layout, sample_lanes, SAMPLE_DOMAIN_SEED)
    only_input_pinned = set(layout.input_qubits) == layout.pinned
    if (
        layout.lo is not None
        and only_input_pinned
        and layout.hi - layout.lo + 1 <= max_exhaustive
    ):
        return exhaustive_domain(layout), smp
    return sample_domain(layout, fallback_lanes, FALLBACK_DOMAIN_SEED), smp


(
    C_X,
    C_CX,
    C_CCX,
    C_SWAP,
    C_CSWAP,
    C_Z,
    C_CZ,
    C_CCZ,
    C_NEG,
    C_ZPOW,
    C_HMR,
    C_R,
    C_B0,
    C_B1,
    C_BI,
    C_PUSH,
    C_POP,
    C_META,
) = range(18)
_CODE = {
    "X": C_X,
    "CX": C_CX,
    "CCX": C_CCX,
    "SWAP": C_SWAP,
    "CSWAP": C_CSWAP,
    "Z": C_Z,
    "CZ": C_CZ,
    "CCZ": C_CCZ,
    "NEG": C_NEG,
    "Z_POW": C_ZPOW,
    "HMR": C_HMR,
    "R": C_R,
    "BIT_STORE0": C_B0,
    "BIT_STORE1": C_B1,
    "BIT_INVERT": C_BI,
    "PUSH_CONDITION": C_PUSH,
    "POP_CONDITION": C_POP,
}


def compile_op(op: Op) -> CompiledOp:
    """Übersetzt eine Instruktion in das flache Tupel, das step interpretiert:
    (Code, q0, q1, q2, Bit, Bedingungsbit, Z_POW-Ebenen, Kostenklasse). Fehlende Qubits sind None.
    """
    code = _CODE.get(op.name, C_META)
    q = op.qs + (None, None, None)
    planes, cost_class = None, COST_CLASS_NONE
    if op.name in TOFFOLI_LIKE:
        cost_class = COST_CLASS_TOFFOLI
    elif op.name == "Z_POW":
        planes, cost_class = zpow_info(op.args[1])
    return (code, q[0], q[1], q[2], op.bit, op.cond, planes, cost_class)


def compile_ops(ops: Sequence[Op]) -> List[CompiledOp]:
    """Kompiliert eine Instruktionsfolge (siehe compile_op)."""
    return [compile_op(o) for o in ops]


class State:
    """Simulatorzustand: Qubits, Bits, Bedingungsstapel und Phase (128 Bit-Ebenen, Einheit 2^-127 Halbdrehung)."""

    __slots__ = (
        "n",
        "ALL",
        "q",
        "b",
        "top",
        "stack",
        "phase",
        "zp",
        "cnt",
        "seed",
        "tt",
        "count",
        "tof",
        "tl",
        "rot",
    )

    def __init__(self, dom: Domain, seed: Any = 0, count: bool = False) -> None:
        self.n, self.ALL = dom.n, dom.ALL
        self.q: Dict[int, LaneVector] = dict(dom.init_q)
        self.b: Dict[int, LaneVector] = {}
        self.top: Optional[LaneVector] = None  # None = alle Lanes aktiv
        self.stack: List[Optional[LaneVector]] = []
        self.phase = 0  # Parität von Z/CZ/CCZ/NEG/HMR-Kickback
        self.zp = [0] * PHASE_PLANES  # bitgeslicter Phasenakkumulator für Z_POW
        self.cnt: Dict[Tuple[str, int], int] = (
            {}
        )  # Anzahl bisheriger Ziehungen je (Art, Bit bzw. Qubit)
        self.seed, self.tt, self.count = seed, dom.tt, count
        self.tof = self.tl = self.rot = (
            0  # ausgeführte Toffolis / T-artige / feine Rotationen (Lanes)
        )

    def copy(self) -> "State":
        """Unabhängige Kopie (die Wahrheitstabelle `tt` wird geteilt, sie ist unveränderlich)."""
        s = State.__new__(State)
        s.n, s.ALL, s.q, s.b, s.top = (
            self.n,
            self.ALL,
            dict(self.q),
            dict(self.b),
            self.top,
        )
        s.stack, s.phase, s.zp, s.cnt = (
            list(self.stack),
            self.phase,
            list(self.zp),
            dict(self.cnt),
        )
        s.seed, s.tt, s.count, s.tof, s.tl, s.rot = (
            self.seed,
            self.tt,
            self.count,
            self.tof,
            self.tl,
            self.rot,
        )
        return s

    def rand(self, tag: str, ident: int) -> LaneVector:
        """Messergebnis je Lane. Gleicher Schlüssel (Bit, wievieltes HMR) -> gleiche Ergebnisse,
        damit Original und Kandidat gekoppelt verglichen werden können."""
        k = self.cnt.get((tag, ident), 0)
        self.cnt[(tag, ident)] = k + 1
        if self.tt is not None:
            return self.tt[(tag, ident, k)]
        return random.Random(f"{self.seed}/{tag}{ident}/{k}").getrandbits(self.n)

    def planes(self) -> List[LaneVector]:
        """Gesamtphase als 128 Bit-Ebenen: Z_POW-Akkumulator, die Paritätsphase auf der Vorzeichen-Ebene."""
        p = list(self.zp)
        p[SIGN_PLANE] ^= self.phase
        return p


def cur_mask(st: State, cond: Optional[int]) -> Optional[LaneVector]:
    """Lanes, auf denen eine Instruktion mit Bedingungsbit `cond` jetzt wirkt (None = alle)."""
    mask = st.top
    if cond is not None:
        cond_lanes = st.b.get(cond, 0)
        mask = cond_lanes if mask is None else (mask & cond_lanes)
    return mask


def step(st: State, cop: CompiledOp) -> None:
    """Führt EINE kompilierte Instruktion auf allen Lanes zugleich aus (heißer Pfad).

    Bewusst eine einzige flache Funktion ohne Hilfsaufrufe; die Zweige stehen nach Häufigkeit sortiert.
    `mask` sind die aktiven Lanes (None = alle, das spart die Maskierung riesiger Ganzzahlen).
    Feldindizes von `cop` siehe compile_op; cop[7] ist die Kostenklasse (1 Toffoli, 2 T-artig, 3 Rotation).
    """
    code = cop[0]
    if code == C_META:
        return
    mask = st.top
    if code == C_PUSH:
        st.stack.append(mask)
        cond_lanes = st.b.get(cop[5], 0)
        st.top = cond_lanes if mask is None else (mask & cond_lanes)
        return
    if code == C_POP:
        if st.stack:
            st.top = st.stack.pop()
        return
    if cop[5] is not None:
        cond_lanes = st.b.get(cop[5], 0)
        mask = cond_lanes if mask is None else (mask & cond_lanes)
    q = st.q
    a = cop[1]
    if st.count and cop[7]:
        active = st.n if mask is None else mask.bit_count()
        if cop[7] == 1:
            st.tof += active
        elif cop[7] == 2:
            st.tl += active
        elif cop[7] == 3:
            st.rot += active
    if code == C_CX:
        v = q.get(a, 0)
        if mask is not None:
            v &= mask
        if v:
            q[cop[2]] = q.get(cop[2], 0) ^ v
    elif code == C_CCX:
        v = q.get(a, 0) & q.get(cop[2], 0)
        if mask is not None:
            v &= mask
        if v:
            q[cop[3]] = q.get(cop[3], 0) ^ v
    elif code == C_X:
        q[a] = q.get(a, 0) ^ (st.ALL if mask is None else mask)
    elif code == C_HMR:
        if mask is not None and mask == 0:
            return  # nie ausgeführt: kein Messergebnis ziehen (hält die Kopplung stabil)
        outcome = st.rand("H", cop[4])
        v = q.get(a, 0)
        if mask is None:
            st.phase ^= outcome & v
            st.b[cop[4]] = outcome
            if v:
                q[a] = 0
        else:
            st.phase ^= outcome & v & mask
            st.b[cop[4]] = (st.b.get(cop[4], 0) & ~mask) | (outcome & mask)
            q[a] = v & ~mask
    elif code == C_R:
        v = q.get(a, 0)
        v_active = v if mask is None else (v & mask)
        if v_active:  # Reset eines gesetzten Qubits würfelt die Phase
            st.phase ^= st.rand("R", a) & v_active
            q[a] = v ^ v_active
    elif code == C_CZ:
        v = q.get(a, 0) & q.get(cop[2], 0)
        st.phase ^= v if mask is None else (v & mask)
    elif code == C_Z:
        v = q.get(a, 0)
        st.phase ^= v if mask is None else (v & mask)
    elif code == C_CCZ:
        v = q.get(a, 0) & q.get(cop[2], 0) & q.get(cop[3], 0)
        st.phase ^= v if mask is None else (v & mask)
    elif code == C_CSWAP:
        swapped = (q.get(cop[2], 0) ^ q.get(cop[3], 0)) & q.get(a, 0)
        if mask is not None:
            swapped &= mask
        if swapped:
            q[cop[2]] = q.get(cop[2], 0) ^ swapped
            q[cop[3]] = q.get(cop[3], 0) ^ swapped
    elif code == C_SWAP:
        swapped = q.get(a, 0) ^ q.get(cop[2], 0)
        if mask is not None:
            swapped &= mask
        if swapped:
            q[a] = q.get(a, 0) ^ swapped
            q[cop[2]] = q.get(cop[2], 0) ^ swapped
    elif code == C_ZPOW:
        v = q.get(a, 0)
        if mask is not None:
            v &= mask
        if v:
            # Bitgeslicte Addition: je gesetzter Ebene des Exponenten ein Übertragslauf; Überlauf über
            # Ebene 127 hinaus entfällt (Phase modulo zwei Halbdrehungen).
            zp = st.zp
            for j in cop[6]:
                carry = v
                while carry and j < 128:
                    plane = zp[j]
                    zp[j] = plane ^ carry
                    carry &= plane
                    j += 1
    elif code == C_NEG:
        st.phase ^= st.ALL if mask is None else mask
    elif code == C_B0:
        st.b[cop[4]] = 0 if mask is None else (st.b.get(cop[4], 0) & ~mask)
    elif code == C_B1:
        st.b[cop[4]] = st.ALL if mask is None else (st.b.get(cop[4], 0) | mask)
    elif code == C_BI:
        st.b[cop[4]] = st.b.get(cop[4], 0) ^ (st.ALL if mask is None else mask)


def simulate(
    cops: Sequence[CompiledOp], dom: Domain, seed: Any = 0, count: bool = False
) -> State:
    """Simuliert ein kompiliertes Programm von Anfang an auf der ganzen Domäne."""
    st = State(dom, seed, count)
    for cop in cops:
        step(st, cop)
    return st


def push_depths(ops: Sequence[Op]) -> List[int]:
    """Tiefe des Bedingungsstapels VOR jeder Instruktion (überzählige POP_CONDITION zählen nicht)."""
    depths, depth = [], 0
    for o in ops:
        depths.append(depth)
        if o.name == "PUSH_CONDITION":
            depth += 1
        elif o.name == "POP_CONDITION" and depth:
            depth -= 1
    return depths


class Taint:
    """Statische Zufalls-Analyse: Welche Bits/Qubits hängen von Messergebnissen ab?
    Fakten aus der Simulation gelten nur für NICHT markierte Qubits als exakt (deterministische
    Funktion der Eingabe, die vollständig aufgezählt wird)."""

    def __init__(self) -> None:
        self.tb: Set[int] = set()  # zufallsabhängige Bits
        self.tq: Set[int] = set()  # zufallsabhängige Qubits
        self.stack: List[bool] = (
            []
        )  # je offener PUSH_CONDITION: hängt die Bedingung vom Zufall ab?

    def mask_random(self, op: Op) -> bool:
        """Hängt es vom Messzufall ab, OB `op` ausgeführt wird (eigene Bedingung oder offener Kontext)?"""
        return (op.cond is not None and op.cond in self.tb) or any(self.stack)

    def advance(self, op: Op) -> None:
        """Schreibt die Markierungen über `op` fort. Konservativ: Markierungen fallen nur weg, wenn ein Wert
        unbedingt und außerhalb jedes Bedingungskontexts neu gesetzt wird."""
        name = op.name
        if name == "PUSH_CONDITION":
            self.stack.append(op.cond in self.tb)
            return
        if name == "POP_CONDITION":
            if self.stack:
                self.stack.pop()
            return
        if name in META_OPS:
            return
        executes_randomly = self.mask_random(op)
        unconditional = op.cond is None and not self.stack
        tq = self.tq
        if name == "HMR":
            self.tb.add(op.bit)
            (tq.add if not unconditional else tq.discard)(op.qs[0])
        elif name == "R":
            (tq.add if not unconditional else tq.discard)(op.qs[0])
        elif name in BIT_OPS:
            if executes_randomly:
                self.tb.add(op.bit)
            elif unconditional and name != "BIT_INVERT":
                self.tb.discard(op.bit)
        elif name in X_TYPE:
            if executes_randomly or any(control in tq for control in op.qs[:-1]):
                tq.add(op.qs[-1])
        elif name == "SWAP":
            a, b = op.qs
            if executes_randomly:
                tq.update(op.qs)
            elif (a in tq) != (b in tq):
                tq.symmetric_difference_update(op.qs)
        elif name == "CSWAP":
            if executes_randomly or any(q in tq for q in op.qs):
                tq.update(op.qs[1:])


# =====================================================================
# 4. VERIFIER: END-TO-END (L3), FENSTER EXAKT (L1) UND KONTEXTUELL (L2)
# =====================================================================


DIGEST_BYTES = 16  # Länge der BLAKE2b-Fingerabdrücke von Lane-Vektoren
EXACT_MAX_VARIABLES = 20  # größte Wahrheitstabelle von L1: 2^20 Belegungen

# Variable der L1-Wahrheitstabelle: ("q", Qubit) | ("b", Bit) | ("top",) | MeasurementKey.
TruthTableKey = Tuple
# Erste Abweichung zweier Fensterzustände: (Beschreibung, Lane).
WindowDifference = Tuple[str, int]


def _digest(v: LaneVector) -> bytes:
    """Fingerabdruck eines Lane-Vektors (die Vektoren selbst sind Megabit-Zahlen)."""
    return hashlib.blake2b(
        v.to_bytes((v.bit_length() + 7) // 8 or 1, "little"), digest_size=DIGEST_BYTES
    ).digest()


def _first_lane(diff: LaneVector) -> int:
    """Index der niedrigsten gesetzten Lane."""
    return (diff & -diff).bit_length() - 1


@dataclass
class FinalSig:
    """Fingerabdruck eines Endzustands plus mittlere Kosten je Lane (Vergleichsgröße von L3)."""

    reg: Tuple[bytes, ...]  # Register-Qubits, nach Index sortiert
    planes: Tuple[bytes, ...]  # die 128 Phasenebenen
    bits: Tuple[bytes, ...]  # Register-Bits
    scratch_clean: bool
    scratch: bytes  # Fingerabdruck der Scratch-Werte (nur relevant, wenn das Original nicht sauber endet)
    depth: int  # Tiefe des Bedingungsstapels am Ende
    tof_mean: float
    t_mean: float
    rot_mean: float


def final_sig(st: State, layout: Layout) -> FinalSig:
    """Bildet die Signatur eines Endzustands; `st` muss mit count=True simuliert sein, sonst sind die Kosten 0."""
    reg = tuple(_digest(st.q.get(q, 0)) for q in sorted(layout.pinned))
    dirty = sorted((q, v) for q, v in st.q.items() if v and q not in layout.pinned)
    scratch_hash = hashlib.blake2b(digest_size=DIGEST_BYTES)
    for q, v in dirty:
        scratch_hash.update(q.to_bytes(4, "little") + _digest(v))
    planes = tuple(_digest(p) for p in st.planes())
    bits = tuple(_digest(st.b.get(b, 0)) for b in layout.reg_bits)
    return FinalSig(
        reg,
        planes,
        bits,
        not dirty,
        scratch_hash.digest(),
        len(st.stack),
        st.tof / st.n,
        st.tl / st.n,
        st.rot / st.n,
    )


def _final_sig_mismatch(sig: FinalSig, ref: FinalSig) -> Optional[str]:
    """Erster Grund, aus dem ein Kandidat (`sig`) vom Original (`ref`) abweicht; None = gleichwertig.
    Scratch muss sauber enden, wenn das Original sauber endet; sonst müssen die Endwerte übereinstimmen.
    """
    if sig.reg != ref.reg:
        return "Registerinhalt weicht ab"
    if sig.planes != ref.planes:
        return "Phase weicht ab"
    if sig.bits != ref.bits:
        return "Register-Bits weichen ab"
    if ref.scratch_clean and not sig.scratch_clean:
        return "Scratch-Qubit endet nicht in |0>"
    if not ref.scratch_clean and sig.scratch != ref.scratch:
        return "Scratch-Endwerte weichen ab"
    if sig.depth != ref.depth:
        return "Bedingungsstapel unausgeglichen"
    return None


class Oracle:
    """End-to-End-Prüfer (L3): vergleicht jeden Kandidaten mit dem ORIGINAL auf der ganzen Domäne."""

    def __init__(
        self,
        orig_ops: Sequence[Op],
        layout: Layout,
        dom: Domain,
        log: Callable[[str], None] = print,
    ) -> None:
        self.orig_c, self.layout, self.dom, self.log = (
            compile_ops(orig_ops),
            layout,
            dom,
            log,
        )
        self._sig: Dict[int, FinalSig] = {}
        self.runs = 0

    def orig_sig(self, seed: int) -> FinalSig:
        """Signatur des Originals für eine Messrunde (je Startwert einmal simuliert, dann gemerkt)."""
        if seed not in self._sig:
            self._sig[seed] = final_sig(
                simulate(self.orig_c, self.dom, seed, count=True), self.layout
            )
            self.runs += 1
        return self._sig[seed]

    def self_check(self) -> List[str]:
        """Kontrakt-Selbsttest des Originals: Scratch sauber, x erhalten, Phase unabhängig vom Messzufall."""
        first, second = self.orig_sig(0), self.orig_sig(1)
        issues = []
        init = tuple(
            _digest(self.dom.init_q.get(q, 0)) for q in sorted(self.layout.pinned)
        )
        if not first.scratch_clean:
            issues.append("Scratch-Qubits enden nicht alle in |0>")
        if first.reg != init:
            issues.append("Register werden nicht wiederhergestellt")
        if first.planes != second.planes:
            issues.append(
                "Endphase hängt vom Messzufall ab (unkorrigierter HMR-Kickback?)"
            )
        if first.depth:
            issues.append("Bedingungsstapel am Ende nicht leer")
        return issues

    def check(
        self, ops: Sequence[Op], seeds: Sequence[int] = (0,)
    ) -> Tuple[bool, str, Optional[FinalSig]]:
        """Vergleicht `ops` je Messrunde mit dem Original. Rückgabe (gleichwertig, Text, letzte Signatur)."""
        cops = compile_ops(ops)
        sig = None
        for seed in seeds:
            ref = self.orig_sig(seed)
            st = simulate(cops, self.dom, seed, count=True)
            self.runs += 1
            sig = final_sig(st, self.layout)
            problem = _final_sig_mismatch(sig, ref)
            if problem:
                return False, f"{problem} ({self._locate(st, seed)})", sig
        return True, f"identisch auf {self.dom.label} x {len(seeds)} Messrunde(n)", sig

    def _locate(self, st: State, seed: int) -> str:
        """Nennt eine Beispiel-Lane, auf der `st` vom Original abweicht (Register, Phase, Scratch ungleich 0)."""
        ref = simulate(self.orig_c, self.dom, seed)
        diff = 0
        for q in self.layout.pinned:
            diff |= st.q.get(q, 0) ^ ref.q.get(q, 0)
        for x, y in zip(st.planes(), ref.planes()):
            diff |= x ^ y
        for q, v in st.q.items():
            if q not in self.layout.pinned:
                diff |= v
        if not diff:
            return "Lane nicht lokalisierbar"
        return f"z. B. {self.dom.describe(_first_lane(diff))}, {diff.bit_count():,} betroffene Lanes"


def _op_bits_written(ops: Sequence[Op]) -> Set[int]:
    """Bits, die das Fenster schreibt (HMR-Ergebnisse und BIT_*-Instruktionen)."""
    return {
        o.bit
        for o in ops
        if o.bit is not None and (o.name == "HMR" or o.name in BIT_OPS)
    }


def _op_bits_read(ops: Sequence[Op]) -> Set[int]:
    """Bits, die das Fenster als Bedingung liest."""
    return {o.cond for o in ops if o.cond is not None}


def _has_randomness(ops: Sequence[Op]) -> bool:
    """Kann der Messzufall das Fenster beeinflussen (Messung, Reset oder bedingte Instruktion)?"""
    return any(o.name in ("HMR", "R") or o.cond is not None for o in ops)


def _bit_read_before_overwrite(
    ops: Sequence[Op], start: int, bit: int, depths: Sequence[int]
) -> bool:
    """Wird der Wert von `bit` ab Index `start` noch gelesen, bevor ihn eine unbedingte Instruktion auf
    Stapeltiefe 0 überschreibt? BIT_INVERT liest den alten Wert, bedingte Schreiber lassen ihn teils stehen.
    """
    for j in range(start, len(ops)):
        o = ops[j]
        if o.cond == bit:
            return True
        if o.bit == bit and o.name not in META_OPS:
            if o.name == "BIT_INVERT":
                return True
            if o.cond is None and depths[j] == 0:
                return False
    return False


def dead_bits_after(
    ops: Sequence[Op], end: int, bits: Set[int], layout: Layout, depths: Sequence[int]
) -> Set[int]:
    """Bits, deren Wert nach Index `end` nie mehr gelesen wird (vor dem nächsten unbedingten Überschreiben).
    Register-Bits sind nie tot: sie gehören zum Ergebnis."""
    dead = set()
    for b in bits:
        if b in layout.reg_bits:
            continue
        if not _bit_read_before_overwrite(ops, end + 1, b, depths):
            dead.add(b)
    return dead


def compare_window_states(
    sa: State, sb: State, qubits: Set[int], bits: Set[int], dom: Domain
) -> Optional[WindowDifference]:
    """Vergleicht zwei Zustände nach einem Fenster. Liefert (Beschreibung, Lane) der ersten Abweichung."""
    for q in sorted(qubits):
        diff = sa.q.get(q, 0) ^ sb.q.get(q, 0)
        if diff:
            return f"Qubit q{q}", _first_lane(diff)
    for j, (x, y) in enumerate(zip(sa.planes(), sb.planes())):
        if x != y:
            what = (
                "Phase (Vorzeichen)"
                if j == SIGN_PLANE
                else f"Phase (Ebene 2^-{SIGN_PLANE - j} Halbdrehung)"
            )
            return what, _first_lane(x ^ y)
    for b in sorted(bits):
        diff = sa.b.get(b, 0) ^ sb.b.get(b, 0)
        if diff:
            return f"Bit b{b}", _first_lane(diff)
    if len(sa.stack) != len(sb.stack):
        return "Bedingungsstapel (Tiefe)", 0
    top_a = sa.ALL if sa.top is None else sa.top
    top_b = sb.ALL if sb.top is None else sb.top
    if top_a != top_b:
        return "Bedingungsstapel", _first_lane(top_a ^ top_b)
    return None


def _exact_keys(
    orig_w: Sequence[Op], cand_w: Sequence[Op], entry_depth: int
) -> List[TruthTableKey]:
    """Freie Variablen eines Fensters: Qubits, gelesene Bits, Bedingungskontext, Messergebnisse.
    Je Messstelle (HMR-Bit bzw. R-Qubit) so viele Ergebnisse, wie das Fenster mit den meisten Ziehungen braucht.
    """
    both = list(orig_w) + list(cand_w)
    qubits = sorted({q for o in both for q in o.qs})
    # Auch nur geschriebene Bits sind frei: ihr Startwert ist unbekannt ("b0 := 0" ist nicht "b0 unverändert").
    bits = sorted(_op_bits_read(both) | _op_bits_written(both))
    keys: List[TruthTableKey] = [("q", q) for q in qubits] + [("b", b) for b in bits]
    if entry_depth:
        keys.append(("top",))
    for tag, name in (("H", "HMR"), ("R", "R")):
        draws_needed: Counter = Counter()
        for w in (orig_w, cand_w):
            draws = Counter(
                (o.bit if tag == "H" else o.qs[0]) for o in w if o.name == name
            )
            for ident, k in draws.items():
                draws_needed[ident] = max(draws_needed[ident], k)
        for ident, k in sorted(draws_needed.items()):
            keys += [(tag, ident, i) for i in range(k)]
    return keys


UNITARY_OPS = ("X", "CX", "CCX", "SWAP", "CSWAP", "Z", "CZ", "CCZ", "Z_POW", "NEG")


def off_grid_phase(ops: Sequence[Op]) -> Optional[Op]:
    """Erstes Z_POW, dessen Exponent nicht auf dem 2^-127-Raster liegt. Der Simulator rundet solche Winkel;
    ein Fenstervergleich wäre dann kein Beweis mehr (ein Winkel unter 2^-128 sähe aus wie die Identität).
    """
    return next(
        (o for o in ops if o.name == "Z_POW" and phase_exponent(o) is None), None
    )


def _strip_common_gates(
    orig_w: Sequence[Op], cand_w: Sequence[Op]
) -> Tuple[Sequence[Op], Sequence[Op]]:
    """Entfernt das längste gemeinsame Präfix und danach das längste gemeinsame Suffix beider Fenster
    (Vergleich über Op.key). Die Reste überlappen das Präfix nicht."""
    keys_a, keys_b = [o.key() for o in orig_w], [o.key() for o in cand_w]
    lo = 0
    while lo < len(keys_a) and lo < len(keys_b) and keys_a[lo] == keys_b[lo]:
        lo += 1
    hi_a, hi_b = len(keys_a), len(keys_b)
    while hi_a > lo and hi_b > lo and keys_a[hi_a - 1] == keys_b[hi_b - 1]:
        hi_a, hi_b = hi_a - 1, hi_b - 1
    return orig_w[lo:hi_a], cand_w[lo:hi_b]


class _QubitComponents:
    """Zusammenhangskomponenten von Qubits (Union-Find): zwei Qubits hängen zusammen, sobald irgendein Gatter
    der übergebenen Folge beide berührt."""

    __slots__ = ("_root",)

    def __init__(self, ops: Sequence[Op]) -> None:
        self._root: Dict[int, int] = {}
        for o in ops:
            for q in o.qs:
                self._root.setdefault(q, q)
            for q in o.qs[1:]:
                self._root[self.find(q)] = self.find(o.qs[0])

    def find(self, q: int) -> int:
        """Vertreter der Komponente von `q` (mit Pfadhalbierung)."""
        root = self._root
        while root[q] != q:
            root[q] = root[root[q]]
            q = root[q]
        return q

    def gate_keys(self, ops: Sequence[Op]) -> Dict[int, List[Tuple]]:
        """Gatterfolge (als Op.key) je Komponente, in Programmreihenfolge. Gatter ohne Qubit fehlen."""
        by_component: Dict[int, List[Tuple]] = defaultdict(list)
        for o in ops:
            if o.qs:
                by_component[self.find(o.qs[0])].append(o.key())
        return by_component

    def restrict(self, ops: Sequence[Op], components: Set[int]) -> List[Op]:
        """Gatter von `ops`, die in einer der `components` liegen; Gatter ohne Qubit bleiben immer."""
        return [o for o in ops if not o.qs or self.find(o.qs[0]) in components]


def difference_cone(
    orig_w: Sequence[Op], cand_w: Sequence[Op]
) -> Tuple[Sequence[Op], Sequence[Op]]:
    """Reduziert zwei Fenster aus unbedingten, unitären Gattern auf das, worin sie sich unterscheiden:
      1. L*O*R == L*C*R  <=>  O == C: gemeinsames Präfix und Suffix entfallen.
      2. Gatter verschiedener Qubit-Zusammenhangskomponenten (über BEIDE Reste gebildet) kommutieren, der
         Operator zerfällt in ein Tensorprodukt; Komponenten mit identischer Gatterfolge entfallen.
    So passen auch breite Fenster mit vielen unbeteiligten Gattern in die Wahrheitstabelle.
    NEG (globale Phase, ohne Qubit) bleibt immer stehen. Andere Fenster kommen unverändert zurück.
    """
    if any(
        o.cond is not None or o.name not in UNITARY_OPS
        for w in (orig_w, cand_w)
        for o in w
    ):
        return orig_w, cand_w
    rest_a, rest_b = _strip_common_gates(orig_w, cand_w)
    components = _QubitComponents((*rest_a, *rest_b))
    gates_a, gates_b = components.gate_keys(rest_a), components.gate_keys(rest_b)
    differing = {
        c for c in gates_a.keys() | gates_b.keys() if gates_a.get(c) != gates_b.get(c)
    }
    return components.restrict(rest_a, differing), components.restrict(
        rest_b, differing
    )


def _truth_table_domain(
    vec: Dict[TruthTableKey, LaneVector], n: int, num_vars: int
) -> Domain:
    """Domäne mit einer Lane je Belegung: Qubit-Variablen als Anfangswerte, Messergebnisse als Tabelle."""
    return Domain(
        n,
        {k[1]: v for k, v in vec.items() if k[0] == "q"},
        True,
        f"alle 2^{num_vars} Belegungen",
        lambda lane: f"Belegung {lane:#x}",
        tt={k: v for k, v in vec.items() if k[0] in ("H", "R")},
    )


def _run_window_on_truth_table(
    window: Sequence[Op],
    dom: Domain,
    vec: Dict[TruthTableKey, LaneVector],
    entry_depth: int,
) -> State:
    """Führt ein Fenster auf allen Belegungen aus; gelesene Bits und der Bedingungskontext sind frei."""
    st = State(dom)
    st.b = {k[1]: v for k, v in vec.items() if k[0] == "b"}
    if entry_depth:
        st.top = vec[("top",)]
    for cop in compile_ops(window):
        step(st, cop)
    return st


def check_exact(
    orig_w: Sequence[Op],
    cand_w: Sequence[Op],
    entry_depth: int,
    dead_bits: Set[int],
    max_vars: int = EXACT_MAX_VARIABLES,
) -> Tuple[str, str]:
    """L1: vollständige Wahrheitstabelle über Fenster-Qubits, gelesene Bits, Bedingungskontext und
    alle Messergebnisse. Rückgabe ('proved'|'refuted'|'na', Text).

    Beweiskraft hat das nur, weil (a) Winkel außerhalb des Phasenrasters vorab abgelehnt werden und
    (b) difference_cone ausschließlich Gatter streicht, die auf beiden Seiten denselben Faktor bilden.
    """
    rough = off_grid_phase((*orig_w, *cand_w))
    if rough is not None:
        return "na", f"{rough.fmt()!r} liegt nicht auf dem 2^-127-Phasenraster"
    orig_w, cand_w = difference_cone(orig_w, cand_w)
    keys = _exact_keys(orig_w, cand_w, entry_depth)
    if len(keys) > max_vars:
        return "na", f"{len(keys)} Variablen > {max_vars}"
    n = 1 << len(keys)
    vec = {k: pattern_bit(i, n) for i, k in enumerate(keys)}
    dom = _truth_table_domain(vec, n, len(keys))
    st_orig = _run_window_on_truth_table(orig_w, dom, vec, entry_depth)
    st_cand = _run_window_on_truth_table(cand_w, dom, vec, entry_depth)
    qubits = {k[1] for k in keys if k[0] == "q"}
    bits = (_op_bits_written(orig_w) | _op_bits_written(cand_w)) - dead_bits
    diff = compare_window_states(st_orig, st_cand, qubits, bits, dom)
    if diff is None:
        return (
            "proved",
            f"exakt bewiesen über alle 2^{len(keys)} = {n:,} Belegungen (inkl. Messergebnisse)",
        )
    what, lane = diff
    assign = ", ".join(
        f"{k[0]}{k[1] if len(k) > 1 else ''}={(vec[k] >> lane) & 1}"
        for k in keys
        if k[0] in ("q", "b")
    )
    return "refuted", f"allgemeine Belegung verletzt: {what} bei {assign}"


def check_context(
    entry: State,
    orig_w: Sequence[Op],
    cand_w: Sequence[Op],
    dead_bits: Set[int],
    dom: Domain,
    rounds: int,
) -> Tuple[bool, str, Tuple[float, float]]:
    """L2: Fenster auf den tatsächlich erreichten Zuständen. Liefert auch die mittleren Toffoli-Kosten.
    Ohne Zufall im Fenster und ohne Bedingungskontext genügt eine Messrunde."""
    both = list(orig_w) + list(cand_w)
    qubits = {q for o in both for q in o.qs}
    bits = (_op_bits_written(orig_w) | _op_bits_written(cand_w)) - dead_bits
    cops_orig, cops_cand = compile_ops(orig_w), compile_ops(cand_w)
    cost = (0.0, 0.0)
    if not _has_randomness(both) and entry.top is None:
        rounds = 1
    for r in range(rounds):
        st_orig, st_cand = entry.copy(), entry.copy()
        for st in (st_orig, st_cand):
            st.seed, st.count, st.tof = f"{entry.seed}~{r}", True, 0
        for cop in cops_orig:
            step(st_orig, cop)
        for cop in cops_cand:
            step(st_cand, cop)
        cost = (st_orig.tof / st_orig.n, st_cand.tof / st_cand.n)
        diff = compare_window_states(st_orig, st_cand, qubits, bits, dom)
        if diff is not None:
            what, lane = diff
            vals = ", ".join(
                f"q{q}={(entry.q.get(q, 0) >> lane) & 1}" for q in sorted(qubits)
            )
            return (
                False,
                f"{what} weicht ab bei {dom.describe(lane)} (Fenstereingang: {vals})",
                cost,
            )
    return True, f"gleich auf {dom.label} x {rounds} Messrunde(n)", cost


@dataclass(frozen=True)
class VerificationResult:
    """v3-Schnittstelle: Ergebnis einer lokalen Fensterprüfung; `exact` nur bei vollständigem Beweis."""

    ok: bool
    message: str
    exact: bool = False

    def __iter__(self) -> Iterator[Any]:
        """Erlaubt das v3-Entpacken `ok, message = result`."""
        yield self.ok
        yield self.message


class BitParallelKMXVerifier:
    """v3-Schnittstelle auf den exakten Fenster-Verifier (L1). Anders als in v3 gibt es kein Fuzzing als Ersatz:
    Passt ein Fenster nicht in die Wahrheitstabelle, ist das Ergebnis 'nicht bewiesen'.
    """

    EXACT_QUBIT_LIMIT = EXACT_MAX_VARIABLES

    @staticmethod
    def _parse_window(lines: Optional[Sequence[str]]) -> List[Op]:
        """Parst die Textzeilen eines Fensters; Einträge, die keine Zeichenketten sind, werden übergangen."""
        return parse_lines([line for line in (lines or []) if isinstance(line, str)])

    @classmethod
    def can_verify_window(cls, lines: Optional[Sequence[str]]) -> Tuple[bool, str]:
        """Passt das Fenster (für sich allein) in die Wahrheitstabelle? Rückgabe (ja/nein, Begründung)."""
        try:
            ops = cls._parse_window(lines)
        except KmxError as e:
            return False, str(e)
        if any(o.name in META_OPS for o in ops):
            return False, "Metadaten-Instruktion im Fenster"
        num_vars = len(_exact_keys(ops, [], 0))
        fits = num_vars <= cls.EXACT_QUBIT_LIMIT
        return fits, (
            "OK" if fits else f"{num_vars} Variablen > {cls.EXACT_QUBIT_LIMIT}"
        )

    @classmethod
    def verify_equivalence(
        cls,
        orig_lines: Optional[Sequence[str]],
        cand_lines: Optional[Sequence[str]],
        num_batches: int = 0,
    ) -> VerificationResult:
        """Exakter Äquivalenzbeweis zweier Fenster. `num_batches` gibt es nur noch für v3-Aufrufer (ohne Wirkung)."""
        try:
            orig_w = cls._parse_window(orig_lines)
            cand_w = cls._parse_window(cand_lines)
        except KmxError as e:
            return VerificationResult(False, f"Fenster ungültig: {e}")
        status, msg = check_exact(orig_w, cand_w, 0, set(), cls.EXACT_QUBIT_LIMIT)
        proved = status == "proved"
        return VerificationResult(
            proved,
            msg if status != "na" else f"kein exakter Beweis möglich ({msg})",
            proved,
        )


# =====================================================================
# 5. DETERMINISTISCHE PÄSSE
# =====================================================================

_CONDITION_STACK_OPS = ("PUSH_CONDITION", "POP_CONDITION")
_PHASE_GATES = ("Z", "CZ", "CCZ", "Z_POW")

# (X-Maske, Z-Maske, allgemeine Maske, gelesene Bits, geschriebene Bits, Barriere) - siehe _deps
OpDeps = Tuple[int, int, int, int, int, bool]


def pass_fold(ops: Sequence[Op]) -> Tuple[List[Op], int]:
    """Syntaktische Aufräumarbeiten: CX-Tripel -> SWAP, leere PUSH/POP-Blöcke entfernen."""
    out: List[Op] = []
    folded = 0
    for o in ops:
        out.append(o)
        if o.name == "CX" and o.cond is None and len(out) >= 3:
            a, b, c = out[-3], out[-2], out[-1]
            if (
                a.name == b.name == "CX"
                and a.cond is None
                and b.cond is None
                and a.qs == c.qs
                and b.qs == (a.qs[1], a.qs[0])
            ):
                del out[-3:]
                out.append(Op("SWAP", (f"q{a.qs[0]}", f"q{a.qs[1]}")))
                folded += 1
        elif (
            o.name == "POP_CONDITION"
            and len(out) >= 2
            and out[-2].name == "PUSH_CONDITION"
        ):
            del out[-2:]
            folded += 1
    return out, folded


def _deps(op: Op) -> OpDeps:
    """(X-Maske, Z-Maske, allgemeine Maske, gelesene Bits, geschriebene Bits, Barriere)."""
    n, qs = op.name, op.qs
    x = z = g = br = bw = 0
    if op.cond is not None:
        br |= 1 << op.cond
    if n in _CONDITION_STACK_OPS:
        return 0, 0, 0, br, 0, True
    if n in X_TYPE:
        x = 1 << qs[-1]
        for c in qs[:-1]:
            z |= 1 << c
    elif n in _PHASE_GATES:
        for c in qs:
            z |= 1 << c
    elif n == "SWAP":
        g = (1 << qs[0]) | (1 << qs[1])
    elif n == "CSWAP":
        z, g = 1 << qs[0], (1 << qs[1]) | (1 << qs[2])
    elif n in ("HMR", "R"):
        g = 1 << qs[0]
        if n == "HMR":
            bw = 1 << op.bit
    elif n in BIT_OPS:
        bw = 1 << op.bit
    return x, z, g, br, bw, False


def _commute(a: OpDeps, b: OpDeps) -> bool:
    """Kommutieren zwei Operationen (als _deps-Tupel)? Barrieren nie; 'allgemeine' Qubits vertragen keinen
    weiteren Zugriff; X-artig gegen Z-artig nur auf verschiedenen Qubits; Bit-Schreiber blockieren Leser/Schreiber.
    """
    if a[5] or b[5]:
        return False
    if a[2] & (b[0] | b[1] | b[2]) or b[2] & (a[0] | a[1] | a[2]):
        return False
    if a[0] & b[1] or a[1] & b[0]:
        return False
    return not (a[4] & (b[3] | b[4]) or b[4] & a[3])


def pass_cancel(ops: Sequence[Op], depth: int = 200) -> Tuple[List[Op], int, int]:
    """Löscht Paare identischer selbstinverser Gatter und fasst Z/Z_POW auf demselben Qubit (gleiche Bedingung)
    exakt zusammen, wenn dazwischen nur kommutierende Operationen liegen. Gleiches Ziel kommutiert
    (CX a t / CCX b c t); Messungen und Bit-Schreiber blockieren ihre Leser.
    Rückgabe: (Ops, gelöschte Paare, zusammengefasste Phasengatter)."""
    kept: List[Op] = []
    deps: List[Optional[OpDeps]] = (
        []
    )  # parallel zu kept; None = Meta-Instruktion (wird übersprungen)
    cancelled = merged = 0
    for op in ops:
        if op.name in META_OPS:
            kept.append(op)
            deps.append(None)
            continue
        op_deps = _deps(op)
        hit = -1
        exp = phase_exponent(op)
        if exp is not None or op.name in SELF_INVERSE:
            key, seen = op.key(), 0
            for j in range(len(kept) - 1, -1, -1):
                other_deps = deps[j]
                if other_deps is None:
                    continue
                o = kept[j]
                if exp is not None:
                    if (
                        o.qs == op.qs
                        and o.cond == op.cond
                        and phase_exponent(o) is not None
                    ):
                        hit = j
                        break
                elif o.name == op.name and o.key() == key:
                    hit = j
                    break
                seen += 1
                if seen > depth or not _commute(op_deps, other_deps):
                    break
        if hit < 0:
            kept.append(op)
            deps.append(op_deps)
        elif exp is None:
            del kept[hit], deps[hit]
            cancelled += 1
        else:
            both = phase_op(op.qs[0], exp + phase_exponent(kept[hit]), op.cond)
            if both is None:
                del kept[hit], deps[hit]
            else:
                kept[hit], deps[hit] = both, _deps(both)
            merged += 1
    return kept, cancelled, merged


ONE = "1"  # Etikett des konstanten Erzeugers (darf nicht mit einer Qubit-Nummer kollidieren)


class XorBasis:
    """GF(2)-Basis über Lane-Vektoren mit Buchführung, welche Erzeuger kombiniert wurden.

    `piv` bildet das höchste gesetzte Bit auf (reduzierter Vektor, Kombinationsmaske) ab; Bit k der Maske
    steht für den k-ten hinzugefügten Erzeuger (`labels[k]`)."""

    def __init__(self) -> None:
        self.labels: List[Any] = []
        self.piv: Dict[int, Tuple[int, int]] = {}

    def copy(self) -> "XorBasis":
        """Unabhängige Kopie (die Einträge selbst sind unveränderlich)."""
        nb = XorBasis()
        nb.labels, nb.piv = list(self.labels), dict(self.piv)
        return nb

    def add(self, label: Any, vec: int) -> None:
        """Nimmt den Erzeuger `label` mit Lane-Vektor `vec` auf (linear abhängige zählen nur als Etikett)."""
        combo = 1 << len(self.labels)
        self.labels.append(label)
        piv = self.piv
        while vec:
            p = vec.bit_length() - 1
            e = piv.get(p)
            if e is None:
                piv[p] = (vec, combo)
                return
            vec ^= e[0]
            combo ^= e[1]

    def solve(self, v: int) -> Optional[List[Any]]:
        """Etiketten der Erzeuger, deren XOR genau `v` ergibt, oder None, wenn `v` nicht im Spann liegt."""
        combo, piv = 0, self.piv
        while v:
            e = piv.get(v.bit_length() - 1)
            if e is None:
                return None
            v ^= e[0]
            combo ^= e[1]
        return [lab for i, lab in enumerate(self.labels) if (combo >> i) & 1]


def _lin_ops(terms: Sequence[Any], target: int, cond: Optional[int]) -> List[Op]:
    """Erzeugt target ^= XOR(terms); ONE steht für die Konstante."""
    out = []
    for t in terms:
        out.append(
            Op("X", (f"q{target}",), cond)
            if t == ONE
            else Op("CX", (f"q{t}", f"q{target}"), cond)
        )
    return out


# Entscheidungen von _direct: (Art, Argument). Die Art ist zugleich der Statistik-Schlüssel.
DirectDecision = Tuple[str, Any]
_DIRECT_DEAD: DirectDecision = ("dead", None)  # feuert auf keiner Lane
_DIRECT_SWAP: DirectDecision = ("swap", None)  # CSWAP wirkt wie SWAP


def _direct(op: Op, st: State, m: Optional[int], rnd: bool) -> Optional[DirectDecision]:
    """Vereinfachungen, die sich direkt an den simulierten Werten ablesen lassen."""
    n = op.name
    if n in _CONDITION_STACK_OPS or n in META_OPS:
        return None
    if m is not None and not rnd and m == 0:
        return _DIRECT_DEAD  # Bedingung ist (deterministisch) nie erfüllt
    mm = st.ALL if (m is None or rnd) else m
    g = st.q.get
    if n == "CCX":
        va, vb = g(op.qs[0], 0) & mm, g(op.qs[1], 0) & mm
        v = va & vb
        if v == 0:
            return _DIRECT_DEAD
        if v == va:
            return ("cx", op.qs[0])
        if v == vb:
            return ("cx", op.qs[1])
    elif n in ("CX", "Z", "Z_POW"):
        if g(op.qs[0], 0) & mm == 0:
            return _DIRECT_DEAD
    elif n == "CSWAP":
        d = (g(op.qs[1], 0) ^ g(op.qs[2], 0)) & mm
        dc = d & g(op.qs[0], 0)
        if dc == 0:
            return _DIRECT_DEAD
        if dc == d:
            return _DIRECT_SWAP
    elif n == "SWAP":
        if (g(op.qs[0], 0) ^ g(op.qs[1], 0)) & mm == 0:
            return _DIRECT_DEAD
    elif n == "CZ":
        if g(op.qs[0], 0) & g(op.qs[1], 0) & mm == 0:
            return _DIRECT_DEAD
    elif n == "CCZ":
        a, b, c = (g(x, 0) & mm for x in op.qs)
        p = a & b & c
        if p == 0:
            return _DIRECT_DEAD
        for i, j, pair in ((0, 1, a & b), (0, 2, a & c), (1, 2, b & c)):
            if p == pair:
                return ("cz", (op.qs[i], op.qs[j]))
    return None


def _apply_direct(op: Op, dec: DirectDecision) -> List[Op]:
    """Setzt eine Entscheidung von _direct in die Ersatz-Instruktionen für `op` um."""
    kind, arg = dec
    if kind == "dead":
        return []
    if kind == "cx":
        return [Op("CX", (f"q{arg}", f"q{op.qs[2]}"), op.cond)]
    if kind == "swap":
        return [Op("SWAP", (f"q{op.qs[1]}", f"q{op.qs[2]}"), op.cond)]
    if kind == "cz":
        return [Op("CZ", (f"q{arg[0]}", f"q{arg[1]}"), op.cond)]
    raise AssertionError(kind)


def _plain_xt(op: Op, depth: int) -> bool:
    """X/CX/CCX ohne jede Bedingung (weder `if bN` noch innerhalb eines PUSH_CONDITION-Blocks)."""
    return op.name in X_TYPE and op.cond is None and depth == 0


def _plain_phase(op: Op, depth: int) -> bool:
    """Z/Z_POW ohne jede Bedingung."""
    return op.cond is None and depth == 0 and phase_exponent(op) is not None


# ---------------------------------------------------------------------
# Simulationsgeführte Reduktion (pass_sim_reduce)
# ---------------------------------------------------------------------

# Kandidaten aus Phase A; das erste Element ist zugleich der Statistik-Schlüssel:
#   ("lin",  Terme)                           Produkt des Toffoli = XOR(Terme)
#   ("grp0", Indizes, Terme)                  Summe der CCX-Produkte der Gruppe = XOR(Terme)
#   ("grp1", Indizes, u, wset, lset)          Summe = XOR(u) * XOR(wset) ^ XOR(lset)
# Terme sind Qubit-Nummern oder ONE; `Indizes` sind die CCX der Gruppe, der letzte ist der Kandidat selbst.
ReduceCandidate = Tuple[Any, ...]
_CAND_LINEAR = "lin"
_CAND_GROUP_AFFINE = "grp0"
_CAND_GROUP_PRODUCT = "grp1"
_GROUP_CANDIDATES = (_CAND_GROUP_AFFINE, _CAND_GROUP_PRODUCT)

_GROUP_PRODUCT_MAX_SPAN = (
    3000  # längere Gruppen werden nicht auf die Form u*w + affin untersucht (Laufzeit)
)
_PRODUCT_FACTOR_LABEL = (
    "p"  # Basis-Etikett ("p", w) steht für den Produktvektor XOR(u) & w
)


def _toffoli_product_lanes(op: Op, g: Callable[[int, int], int], mm: int) -> int:
    """Lane-Vektor, auf dem ein CCX/CSWAP/CCZ tatsächlich etwas bewirkt (eingeschränkt auf die Maske `mm`)."""
    if op.name == "CCX":
        return g(op.qs[0], 0) & g(op.qs[1], 0) & mm
    if op.name == "CSWAP":
        return (g(op.qs[1], 0) ^ g(op.qs[2], 0)) & g(op.qs[0], 0) & mm
    return g(op.qs[0], 0) & g(op.qs[1], 0) & g(op.qs[2], 0) & mm


def _xor_of_terms(terms: Sequence[Any], g: Callable[[int, int], int], mm: int) -> int:
    """XOR der Lane-Vektoren der Terme (ONE = Konstante 1), eingeschränkt auf die Maske `mm`."""
    acc = 0
    for t in terms:
        acc ^= mm if t == ONE else (g(t, 0) & mm)
    return acc


def _candidate_reads(cand: ReduceCandidate) -> List[int]:
    """Qubits, die der Ersatz eines Gruppenkandidaten (zusätzlich) liest."""
    return [x for part in cand[2:] for x in part if x != ONE]


def _linear_replacement(op: Op, terms: Sequence[Any]) -> List[Op]:
    """Toffoli-freier Ersatz eines CCX/CSWAP/CCZ, dessen Produkt gleich XOR(terms) ist."""
    if op.name == "CCX":
        return _lin_ops(terms, op.qs[2], op.cond)
    if op.name == "CSWAP":
        return _lin_ops(terms, op.qs[1], op.cond) + _lin_ops(terms, op.qs[2], op.cond)
    return [
        Op("NEG", (), op.cond) if t == ONE else Op("Z", (f"q{t}",), op.cond)
        for t in terms
    ]


def _product_group_replacement(
    u: Sequence[int], wset: Sequence[int], lset: Sequence[Any], target: int
) -> List[Op]:
    """target ^= XOR(u) * XOR(wset) ^ XOR(lset) mit EINEM Toffoli: die XOR-Summen werden per CX in u[0] bzw.
    wset[0] gesammelt, nach dem CCX wieder aufgelöst; der affine Rest folgt als CX-Kaskade.
    """
    piv = wset[0]
    pre = [Op("CX", (f"q{w}", f"q{piv}")) for w in wset[1:]]
    pre += [Op("CX", (f"q{c}", f"q{u[0]}")) for c in u[1:]]
    return (
        pre
        + [Op("CCX", (f"q{u[0]}", f"q{piv}", f"q{target}"))]
        + pre[::-1]
        + _lin_ops(lset, target, None)
    )


@dataclass
class _CcxTargetRun:
    """Lauf unbedingter CCX auf dasselbe Ziel, das dazwischen weder gelesen noch anders angefasst wird."""

    hist: List[
        Tuple[int, int]
    ]  # (Op-Index, Lane-Vektor des Kontrollprodukts), höchstens max_group
    cand: Optional[int] = (
        None  # Index des Gruppenkandidaten, der `hist` bereits abdeckt
    )


class _SampleCandidateSearch:
    """Phase A von pass_sim_reduce: Kandidatensuche auf der Stichproben-Domäne.

    Nur Vorschläge - übernommen wird ein Kandidat erst, wenn Phase B ihn auf der ganzen Domäne bestätigt.
    `cands` hält die Kandidaten in Entdeckungsreihenfolge, `skipped` zählt die Toffolis, die wegen des
    erschöpften Zeitbudgets nicht mehr untersucht wurden."""

    def __init__(
        self,
        ops: Sequence[Op],
        depths: Sequence[int],
        cops: Sequence[Tuple],
        smp: Domain,
        max_terms: int,
        max_group: int,
    ) -> None:
        self.ops, self.depths, self.cops = ops, depths, cops
        self.max_terms, self.max_group = max_terms, max_group
        self.st, self.taint = State(smp, "A"), Taint()
        self.runs: Dict[int, _CcxTargetRun] = {}  # Ziel-Qubit -> offener CCX-Lauf
        self.cands: Dict[int, ReduceCandidate] = {}
        self.skipped = 0

    def search(self, t0: float, budget_s: float) -> None:
        """Simuliert die Stichprobe einmal durch und untersucht jeden Toffoli, solange das Budget reicht."""
        ops, depths, cops, st, taint, runs = (
            self.ops,
            self.depths,
            self.cops,
            self.st,
            self.taint,
            self.runs,
        )
        for i, op in enumerate(ops):
            n = op.name
            if n in TOFFOLI_LIKE:
                if time.time() - t0 >= budget_s:
                    self.skipped += 1
                elif not any(q in taint.tq for q in op.qs):
                    self._examine_toffoli(i, op)
            # Lauf-Buchführung: ein Lauf endet, sobald das Ziel gelesen oder anders angefasst wird
            if n not in META_OPS and op.qs:
                if _plain_xt(op, depths[i]):
                    for c in op.qs[:-1]:
                        runs.pop(c, None)
                else:
                    for q in op.qs:
                        runs.pop(q, None)
            step(st, cops[i])
            taint.advance(op)

    def _examine_toffoli(self, i: int, op: Op) -> None:
        """Sucht für den Toffoli an Position i einen linearen Ersatz, sonst (unbedingtes CCX) eine Gruppe."""
        st = self.st
        m = cur_mask(st, op.cond)
        rnd = self.taint.mask_random(op)
        if _direct(op, st, m, rnd) is not None:
            return  # direkte Fälle findet Phase B selbst
        mm = st.ALL if (m is None or rnd) else m
        base = self._affine_basis(op, mm)
        v = _toffoli_product_lanes(op, st.q.get, mm)
        sol = base.solve(v)
        if sol is not None and len(sol) <= self.max_terms:
            self.cands[i] = (_CAND_LINEAR, sol)
            self._end_runs_of(sol)
        elif op.name == "CCX" and _plain_xt(op, self.depths[i]):
            self._extend_target_run(i, op.qs[2], v, base)

    def _end_runs_of(self, qubits: Sequence[Any]) -> None:
        """Der Ersatz liest diese Qubits neu: ihre Läufe enden hier."""
        runs = self.runs
        for x in qubits:
            runs.pop(x, None)

    def _affine_basis(self, op: Op, mm: int) -> XorBasis:
        """Basis aus der Konstanten und allen unverfälschten Qubits außer den Zielen von `op`, auf `mm` maskiert.
        Die eigenen Qubits von `op` kommen zuerst, damit Lösungen bevorzugt aus ihnen bestehen.
        """
        st, tainted = self.st, self.taint.tq
        n = op.name
        exclude = (
            set(op.qs[1:]) if n == "CSWAP" else ({op.qs[2]} if n == "CCX" else set())
        )
        base = XorBasis()
        base.add(ONE, mm)
        seen = {0, mm}
        order = list(op.qs) + sorted(q for q in st.q if q not in op.qs)
        for q in order:
            if q in exclude or q in tainted:
                continue
            v = st.q.get(q, 0) & mm
            if v not in seen:
                seen.add(v)
                base.add(q, v)
        return base

    def _extend_target_run(self, i: int, t: int, v: int, base: XorBasis) -> None:
        """Hängt das CCX an Position i (Produktvektor v) an den Lauf seines Ziels t und sucht eine Gruppe:
        zuerst der ganze Lauf, sonst - wenn noch kein Kandidat besteht - nur das letzte Paar.
        """
        runs, cands, max_group = self.runs, self.cands, self.max_group
        run = runs.setdefault(t, _CcxTargetRun([]))
        hist = run.hist
        found = (
            self._find_group(hist + [(i, v)], i, t, base)
            if hist and len(hist) < max_group
            else None
        )
        if found:  # größere Gruppe ersetzt den bisherigen Kandidaten
            self._end_runs_of(_candidate_reads(found))
            if run.cand is not None:
                cands.pop(run.cand, None)
            cands[i] = found
            hist.append((i, v))
            run.cand = i
            return
        if run.cand is not None:  # bestehender Kandidat bleibt, neuer Lauf beginnt hier
            runs[t] = _CcxTargetRun([(i, v)])
            return
        found = (
            self._find_group(hist[-1:] + [(i, v)], i, t, base)
            if len(hist) > 1
            else None
        )
        if found:
            cands[i] = found
            self._end_runs_of(_candidate_reads(found))
            runs[t] = _CcxTargetRun([hist[-1], (i, v)], i)
        else:
            hist.append((i, v))
            del hist[:-max_group]

    def _find_group(
        self, grp: Sequence[Tuple[int, int]], i: int, t: int, base: XorBasis
    ) -> Optional[ReduceCandidate]:
        """Ist die Summe der CCX-Produkte der Gruppe affin (0 Toffoli) oder von der Form u*w + affin (1 Toffoli)?"""
        delta = 0
        for _, product in grp:
            delta ^= product
        idxs = [j for j, _ in grp]
        sol = base.solve(delta)
        if sol is not None and len(sol) <= self.max_terms:
            return (_CAND_GROUP_AFFINE, idxs, sol)
        if i - idxs[0] > _GROUP_PRODUCT_MAX_SPAN:
            return None
        ctrl, local = self._group_factor_pools(idxs, i, t)
        return self._find_product_form(delta, idxs, ctrl, local, base)

    def _group_factor_pools(
        self, idxs: Sequence[int], i: int, t: int
    ) -> Tuple[List[int], List[int]]:
        """Faktor-Kandidaten einer Gruppe: `ctrl` sind die Kontrollen ihrer CCX, `local` zusätzlich alles, was
        zwischen erstem CCX und Position i per X/CX/CCX in eine dieser Kontrollen geschrieben wurde.
        """
        ops, tainted = self.ops, self.taint.tq
        ctrl: List[int] = []
        for j in idxs:
            for c in ops[j].qs[:2]:
                if c not in ctrl and c != t and c not in tainted:
                    ctrl.append(c)
        local = list(ctrl)
        for j in range(idxs[0], i):
            o = ops[j]
            if o.name in X_TYPE and o.qs[-1] in ctrl:
                for c in o.qs[:-1]:
                    if c not in local and c != t and c not in tainted:
                        local.append(c)
        return ctrl, local

    def _find_product_form(
        self,
        delta: int,
        idxs: List[int],
        ctrl: Sequence[int],
        local: Sequence[int],
        base: XorBasis,
    ) -> Optional[ReduceCandidate]:
        """Sucht delta = XOR(u) * XOR(wset) ^ XOR(lset) mit u aus ein oder zwei Kontrollen und wset aus `local`."""
        g = self.st.q.get
        factors = [(c,) for c in ctrl] + [
            (c, d) for k, c in enumerate(ctrl) for d in ctrl[k + 1 :]
        ]
        for u in factors:
            vu = 0
            for c in u:
                vu ^= g(c, 0)
            extended = base.copy()
            for w in local:
                if w != u[0]:
                    extended.add((_PRODUCT_FACTOR_LABEL, w), vu & g(w, 0))
            sol = extended.solve(delta)
            if sol is None:
                continue
            wset = [x[1] for x in sol if isinstance(x, tuple)]
            lset = [x for x in sol if not isinstance(x, tuple)]
            wset.sort(
                key=lambda w: w in u
            )  # Pivot (erstes Element) liegt außerhalb von u
            if (
                wset
                and wset[0] not in u
                and len(wset) + len(lset) <= 2 * self.max_terms
            ):
                return (_CAND_GROUP_PRODUCT, idxs, u, wset, lset)
        return None


class _DomainConfirmation:
    """Phase B von pass_sim_reduce: exakte Bestätigung auf der ganzen Domäne.

    Sammelt, was auf ALLEN Lanes gilt: direkte Fälle (_direct), bestätigte Kandidaten aus Phase A, Z_POW auf
    wertgleichen Qubits und Messungen von Qubits, die ohnehin |0> sind. `repl` (Index -> Ersatz) und `delete`
    beschreiben die Umformung; `stats` zählt in der Reihenfolge des ersten Auftretens.
    """

    def __init__(
        self,
        ops: Sequence[Op],
        depths: Sequence[int],
        cops: Sequence[Tuple],
        layout: Layout,
        dom: Domain,
        cands: Dict[int, ReduceCandidate],
    ) -> None:
        self.ops, self.depths, self.cops, self.layout, self.cands = (
            ops,
            depths,
            cops,
            layout,
            cands,
        )
        self.member_of: Dict[int, int] = (
            {}
        )  # CCX-Index -> Gruppenkandidat, in dem er aufgeht
        for i, c in cands.items():
            if c[0] in _GROUP_CANDIDATES:
                for j in c[1][:-1]:
                    self.member_of[j] = i
        # Ziel -> (erster, letzter Index) je Gruppenkandidat
        self.spans: Dict[int, List[Tuple[int, int]]] = defaultdict(list)
        for i, c in cands.items():
            if c[0] in _GROUP_CANDIDATES:
                self.spans[ops[i].qs[2]].append((c[1][0], i))
        self.zgroups: Dict[int, List[int]] = (
            {}
        )  # Lane-Vektor -> Z_POW-Indizes mit genau diesem Vektor
        self.stash: Dict[int, int] = (
            {}
        )  # CCX-Index -> Kontrollprodukt an seiner Originalposition
        self.repl: Dict[int, List[Op]] = {}
        self.delete: Set[int] = set()
        self.stats: Counter = Counter()
        self.idle_hmr: List[int] = (
            []
        )  # HMR auf Qubits, die auf der ganzen Domäne |0> sind
        self.st, self.taint = State(dom, "B"), Taint()

    def confirm(self) -> None:
        """Simuliert die ganze Domäne einmal durch und füllt repl/delete/stats/zgroups/idle_hmr."""
        ops, depths, cops, layout, cands = (
            self.ops,
            self.depths,
            self.cops,
            self.layout,
            self.cands,
        )
        member_of, zgroups, stash, repl, stats, idle_hmr = (
            self.member_of,
            self.zgroups,
            self.stash,
            self.repl,
            self.stats,
            self.idle_hmr,
        )
        st, taint = self.st, self.taint
        for i, op in enumerate(ops):
            n = op.name
            if (
                n == "HMR"
                and op.cond is None
                and depths[i] == 0
                and op.qs[0] not in taint.tq
                and op.qs[0] not in layout.pinned
                and st.q.get(op.qs[0], 0) == 0
            ):
                idle_hmr.append(i)
            if (
                n not in META_OPS
                and n not in _CONDITION_STACK_OPS
                and not any(q in taint.tq for q in op.qs)
            ):
                m = cur_mask(st, op.cond)
                rnd = taint.mask_random(op)
                g = st.q.get
                dec = _direct(op, st, m, rnd)
                if dec is not None:
                    repl[i] = _apply_direct(op, dec)
                    stats[dec[0]] += 1
                    stats["toffoli_saved"] += n in TOFFOLI_LIKE and not any(
                        o.name in TOFFOLI_LIKE for o in repl[i]
                    )
                if n == "Z_POW" and dec is None and _plain_phase(op, depths[i]):
                    zgroups.setdefault(g(op.qs[0], 0), []).append(i)
                cand = cands.get(i)
                if n == "CCX" and (
                    i in member_of or (cand and cand[0] != _CAND_LINEAR)
                ):
                    stash[i] = g(op.qs[0], 0) & g(op.qs[1], 0)
                if cand is not None:
                    mm = st.ALL if (m is None or rnd) else m
                    if cand[0] == _CAND_LINEAR and dec is None:
                        self._confirm_linear(i, op, cand[1], mm)
                    elif cand[0] in _GROUP_CANDIDATES and all(
                        j in stash for j in cand[1]
                    ):
                        self._confirm_group(i, op, cand, mm)
            step(st, cops[i])
            taint.advance(op)

    def _inside_group(self, q: Any, i: int) -> bool:
        """Würde ein neuer Lesezugriff auf q an Position i in eine (mögliche) Gruppenumformung von q fallen?"""
        return any(a < i < b for a, b in self.spans.get(q, ()))

    def _confirm_linear(self, i: int, op: Op, terms: Sequence[Any], mm: int) -> None:
        """Übernimmt einen "lin"-Kandidaten, wenn Produkt = XOR(terms) auf allen (aktiven) Lanes gilt."""
        g = self.st.q.get
        v = _toffoli_product_lanes(op, g, mm)
        if _xor_of_terms(terms, g, mm) == v and not any(
            self._inside_group(x, i) for x in terms
        ):
            self.repl[i] = _linear_replacement(op, terms)
            self.stats[_CAND_LINEAR] += 1
            self.stats["toffoli_saved"] += 1

    def _confirm_group(self, i: int, op: Op, cand: ReduceCandidate, mm: int) -> None:
        """Übernimmt einen Gruppenkandidaten: die an den Originalpositionen gemerkten Kontrollprodukte müssen in
        Summe dem Ersatz an Position i entsprechen. Die übrigen CCX der Gruppe werden gelöscht.
        """
        g, stash, repl, delete, stats = (
            self.st.q.get,
            self.stash,
            self.repl,
            self.delete,
            self.stats,
        )
        kind, members = cand[0], cand[1]
        delta = 0
        for j in members:
            delta ^= stash[j]
        t = op.qs[2]
        if kind == _CAND_GROUP_AFFINE:
            ok, new = _xor_of_terms(cand[2], g, mm) == delta, _lin_ops(cand[2], t, None)
        else:
            _, _, u, wset, lset = cand
            ok = (_xor_of_terms(u, g, mm) & _xor_of_terms(wset, g, mm)) ^ _xor_of_terms(
                lset, g, mm
            ) == delta
            new = _product_group_replacement(u, wset, lset, t)
        if not ok or any(self._inside_group(x, i) for x in _candidate_reads(cand)):
            return
        # Toffolis, die die Gruppe bisher noch kostet (gelöschte oder bereits Toffoli-frei ersetzte zählen nicht)
        before = sum(
            1
            for j in members
            if j not in delete
            and not (j in repl and not any(o.name == "CCX" for o in repl[j]))
        )
        for j in members[:-1]:
            delete.add(j)
            repl.pop(j, None)
        repl[i] = new
        stats[kind] += 1
        stats["toffoli_saved"] += before - (kind == _CAND_GROUP_PRODUCT)

    def merge_equal_rotations(self) -> None:
        """Rotationen auf Qubits mit identischem Wert (auf der ganzen Domäne) sind EINE Rotation mit der
        Winkelsumme; sie bleibt an der Stelle der letzten stehen."""
        ops, repl, delete = self.ops, self.repl, self.delete
        for idxs in self.zgroups.values():
            if len(idxs) > 1:
                total = sum((phase_exponent(ops[j]) for j in idxs), Fraction(0))
                for j in idxs[:-1]:
                    delete.add(j)
                    repl.pop(j, None)
                both = phase_op(ops[idxs[-1]].qs[0], total, None)
                repl[idxs[-1]] = [both] if both else []
                self.stats["phase_merge"] += len(idxs) - 1

    def rewritten(self, drop_idle_hmr: bool) -> List[Op]:
        """Wendet repl/delete an (und streicht auf Wunsch überflüssige HMR). Ohne Änderung: Kopie von `ops`."""
        ops, repl, delete, idle_hmr = self.ops, self.repl, self.delete, self.idle_hmr
        if not repl and not delete and not (drop_idle_hmr and idle_hmr):
            return list(ops)
        out: List[Op] = []
        pos: Dict[int, int] = {}  # alter Index -> Position des (ersten) Ersatzes in out
        for i, op in enumerate(ops):
            if i in delete:
                continue
            pos[i] = len(out)
            if i in repl:
                out.extend(repl[i])
            else:
                out.append(op)
        if drop_idle_hmr and idle_hmr:
            out = self._without_idle_hmr(out, pos)
        if len(out) == len(ops) and all(x is y for x, y in zip(out, ops)):
            return list(ops)
        return out

    def _without_idle_hmr(self, out: List[Op], pos: Dict[int, int]) -> List[Op]:
        """Ein HMR auf einem |0>-Qubit hat keinen Kickback; es darf weg, wenn sein Bit danach nicht mehr
        gelesen wird."""
        depths = push_depths(out)
        gone = {
            pos[i]
            for i in self.idle_hmr
            if i in pos
            and out[pos[i]].name == "HMR"
            and dead_bits_after(out, pos[i], {out[pos[i]].bit}, self.layout, depths)
        }
        if not gone:
            return out
        self.stats["idle_hmr"] = len(gone)
        return [o for k, o in enumerate(out) if k not in gone]


def pass_sim_reduce(
    ops: Sequence[Op],
    layout: Layout,
    dom: Domain,
    smp: Domain,
    deep: bool = True,
    budget_s: float = 180.0,
    max_terms: int = 8,
    max_group: int = 6,
    drop_idle_hmr: bool = True,
) -> Tuple[List[Op], Dict[str, int]]:
    """Simulationsgeführte Reduktion.

    Phase A (Stichprobe): sucht Kandidaten per linearer Algebra über den Lane-Vektoren:
       lin    CCX-Produkt liegt in der affinen Hülle der vorhandenen Qubits      -> CX-Kaskade (0 Toffoli)
       group  mehrere CCX auf dasselbe Ziel: Summe ist affin (0 Toffoli) oder u*w + affin (1 Toffoli)
    Phase B (ganze Domäne): bestätigt jeden Kandidaten exakt und findet direkte Fälle
       (nie feuernd, eine Kontrolle impliziert die andere, CSWAP wirkt wie SWAP, CCZ wie CZ).
    Übernommen wird nur, was in Phase B auf allen Lanes gilt."""
    depths = push_depths(ops)
    cops = compile_ops(ops)
    cands: Dict[int, ReduceCandidate] = {}
    t0 = time.time()
    skipped = 0
    if deep:
        search = _SampleCandidateSearch(ops, depths, cops, smp, max_terms, max_group)
        search.search(t0, budget_s)
        cands, skipped = search.cands, search.skipped

    confirmation = _DomainConfirmation(ops, depths, cops, layout, dom, cands)
    if skipped:
        confirmation.stats["suche_abgebrochen_bei_toffolis"] = (
            skipped  # Zeitbudget erschöpft: --budget erhöhen
        )
    confirmation.confirm()
    confirmation.merge_equal_rotations()
    out = confirmation.rewritten(drop_idle_hmr)
    return out, dict(confirmation.stats)


# ---------------------------------------------------------------------
# Scratch-Qubits: Zugriffe, Lebensdauern, MBU und Repacking
# ---------------------------------------------------------------------

ScratchTouch = Tuple[int, str, bool]  # (Op-Index, Rolle, 'danach auf allen Lanes |0>')
ScratchTouches = Dict[
    int, List[ScratchTouch]
]  # Scratch-Qubit -> Zugriffe in Programmreihenfolge
ScratchLifetime = Tuple[
    int, int, int, List[int]
]  # (Start, Ende, Qubit, Indizes der Zugriffe)
_ROLE_X_TARGET, _ROLE_CONTROL, _ROLE_GENERAL = "xt", "c", "g"
_WIRE_INDEX_LIMIT = 10**9  # obere Schranke für die Suche nach freien Drähten


def trace_touches(
    ops: Sequence[Op], layout: Layout, dom: Domain, seed: Any = "T"
) -> ScratchTouches:
    """Für jedes Scratch-Qubit: (Index, Rolle, 'danach auf allen Lanes |0>').
    Rollen: 'xt' = Ziel eines X/CX/CCX, 'c' = nur gelesen, 'g' = sonstiges (SWAP, HMR, R).
    """
    cops = compile_ops(ops)
    st, taint = State(dom, seed), Taint()
    touches: ScratchTouches = defaultdict(list)
    for i, op in enumerate(ops):
        step(st, cops[i])
        taint.advance(op)
        n = op.name
        if not op.qs or n in META_OPS:
            continue
        for k, q in enumerate(op.qs):
            if q in layout.pinned:
                continue
            if n in X_TYPE:
                role = _ROLE_X_TARGET if k == len(op.qs) - 1 else _ROLE_CONTROL
            elif n in _PHASE_GATES or (n == "CSWAP" and k == 0):
                role = _ROLE_CONTROL
            else:
                role = _ROLE_GENERAL
            touches[q].append((i, role, st.q.get(q, 0) == 0 and q not in taint.tq))
    return touches


def _mbu_uncompute_chains(
    ops: Sequence[Op], depths: Sequence[int], touches: ScratchTouches
) -> List[Tuple[int, List[int]]]:
    """(Qubit, Indizes) aller lückenlosen Folgen unbedingter X/CX/CCX auf ein Scratch-Qubit, nach denen es auf
    der ganzen Domäne |0> ist und die mindestens ein CCX enthalten (sonst spart MBU nichts).
    """
    chains: List[Tuple[int, List[int]]] = []
    for q, qubit_touches in touches.items():
        run: List[int] = []
        for i, role, zero in qubit_touches:
            if role != _ROLE_X_TARGET or depths[i] != 0:
                run = []
                continue
            run.append(i)
            if zero:
                if any(ops[j].name == "CCX" for j in run):
                    chains.append((q, run))
                run = []
    return chains


def _mbu_phase_fix(op: Op, bit: int) -> List[Op]:
    """Phasenkorrektur, die ein X/CX/CCX einer Uncompute-Kette ersetzt, wirksam nur bei Messergebnis `bit` = 1.
    War das Gatter selbst schon `if bN`-bedingt, bleibt diese Bedingung am Gatter und `bit` kommt per PUSH dazu.
    """
    if op.name == "CCX":
        name, args = "CZ", (f"q{op.qs[0]}", f"q{op.qs[1]}")
    elif op.name == "CX":
        name, args = "Z", (f"q{op.qs[0]}",)
    else:
        name, args = "NEG", ()
    if op.cond is None:
        return [Op(name, args, bit)]
    return [Op("PUSH_CONDITION", (), bit), Op(name, args, op.cond), Op("POP_CONDITION")]


def pass_mbu(
    ops: Sequence[Op], layout: Layout, dom: Domain
) -> Tuple[List[Op], Dict[str, int]]:
    """Measurement-Based Uncomputation. Endet eine Folge von X/CX/CCX auf ein Scratch-Qubit t damit, dass t
    auf der ganzen Domäne |0> ist (und wird t dazwischen nicht gelesen), dann hielt t vorher genau die XOR-Summe
    dieser Terme. Ersatz: HMR t b am Anfang, und jedes Gatter wird zur klassisch bedingten Phasenkorrektur
    (CCX a b t -> CZ a b if b; CX a t -> Z a if b; X t -> NEG if b). Jedes CCX der Kette spart ein Toffoli.
    """
    depths = push_depths(ops)
    chains = _mbu_uncompute_chains(ops, depths, trace_touches(ops, layout, dom))
    if not chains:
        return list(ops), {}
    used_bits = {o.bit for o in ops if o.bit is not None} | {
        o.cond for o in ops if o.cond is not None
    }
    next_bit = max(used_bits, default=-1) + 1
    pool: List[Tuple[int, int]] = (
        []
    )  # Heap (frei ab Index, Bit): Messbits abgeschlossener Ketten
    repl: Dict[int, List[Op]] = {}
    saved = 0
    for q, run in sorted(chains, key=lambda chain: chain[1][0]):
        if pool and pool[0][0] < run[0]:
            _, bit = heapq.heappop(pool)
        else:
            bit, next_bit = next_bit, next_bit + 1
        heapq.heappush(pool, (run[-1], bit))
        for k, i in enumerate(run):
            op = ops[i]
            saved += op.name == "CCX"
            measure = [Op("HMR", (f"q{q}", f"b{bit}"))] if k == 0 else []
            repl[i] = measure + _mbu_phase_fix(op, bit)
    out: List[Op] = []
    for i, op in enumerate(ops):
        if i in repl:
            out.extend(repl[i])
        else:
            out.append(op)
    return out, {"chains": len(chains), "toffoli_saved": saved}


def lifetimes_of(
    ops: Sequence[Op], touches: ScratchTouches
) -> Tuple[List[ScratchLifetime], Set[int]]:
    """Lebensdauern (Start, Ende, Qubit, Indizes) aller Scratch-Qubits und überflüssige R-Instruktionen.

    Eine Lebensdauer endet, sobald das Qubit nach echter Benutzung auf allen Lanes |0> ist. Ein R auf ein
    ohnehin leeres Qubit ('idle') ist überflüssig, solange darauf nur weitere solche R oder nichts mehr folgt.
    """
    lifetimes: List[ScratchLifetime] = []
    drop: Set[int] = set()
    for q, qubit_touches in touches.items():
        idxs: List[int] = []  # Zugriffe der offenen Lebensdauer; leer = keine offen
        used = False  # enthält die offene Lebensdauer mehr als ein einzelnes Idle-R?
        for i, _, zero in qubit_touches:
            idle_r = ops[i].name == "R" and zero
            if not idxs:
                idxs, used = [i], not idle_r
            elif not used and idle_r:
                drop.update(idxs)
                idxs = [i]
            else:
                idxs.append(i)
                used = True
            if used and zero:
                lifetimes.append((idxs[0], i, q, idxs))
                idxs = []
        if idxs:
            if used:
                lifetimes.append((idxs[0], len(ops), q, idxs))
            else:
                drop.update(idxs)
    lifetimes.sort()
    return lifetimes, drop


def _assign_wires(
    lifetimes: Sequence[ScratchLifetime], pinned: Set[int]
) -> Tuple[Dict[int, Dict[int, int]], int]:
    """Intervallfärbung der (nach Start sortierten) Lebensdauern auf die kleinsten nicht gepinnten Drähte.
    Rückgabe: (Op-Index -> {altes Qubit: Draht}, höchste Zahl gleichzeitig belegter Drähte).
    """
    unused_wires = (w for w in range(_WIRE_INDEX_LIMIT) if w not in pinned)
    free: List[int] = []  # Heap wieder freigegebener Drähte
    active: List[Tuple[int, int]] = []  # Heap (Ende, Draht) der laufenden Lebensdauern
    rename: Dict[int, Dict[int, int]] = defaultdict(dict)
    peak = 0
    for start, end, q, idxs in lifetimes:
        while active and active[0][0] < start:
            heapq.heappush(free, heapq.heappop(active)[1])
        wire = heapq.heappop(free) if free else next(unused_wires)
        heapq.heappush(active, (end, wire))
        peak = max(peak, len(active))
        for i in idxs:
            rename[i][q] = wire
    return rename, peak


def pass_repack(
    ops: Sequence[Op], layout: Layout, dom: Domain
) -> Tuple[List[Op], Dict[str, int]]:
    """Qubit-Repacking. Ein Draht ist frei, sobald das Qubit auf der ganzen Domäne |0> ist - egal ob durch HMR,
    R oder reversibles Uncompute. Die Lebensdauern werden per Intervallfärbung auf möglichst wenige Drähte mit
    den kleinsten Indizes gelegt (optimal bei fester Gatterreihenfolge). Q im Score ist max. Index + 1.
    """
    touches = trace_touches(ops, layout, dom)
    lifetimes, drop = lifetimes_of(ops, touches)
    old_q = compute_metrics(ops).num_qubits
    rename, peak = _assign_wires(lifetimes, layout.pinned)
    out = [
        op.renamed(rename[i]) if i in rename else op
        for i, op in enumerate(ops)
        if i not in drop
    ]
    new_q = compute_metrics(out).num_qubits
    stats = {
        "q_before": old_q,
        "q_after": new_q,
        "peak_scratch": peak,
        "lifetimes": len(lifetimes),
        "dropped_idle_R": len(drop),
    }
    if new_q >= old_q:
        return list(ops), stats
    return out, stats


# =====================================================================
# 5b. EXAKTER INVSQRT-SCORE (WIE DER OFFIZIELLE VERIFIER GERECHNET) UND ROTATIONS-TRIMMEN
# =====================================================================

# Die Phase liegt im Simulator in 128 Bit-Ebenen vor (Einheit 2^-128 Umdrehungen). Der offizielle Verifier
# vergleicht nur die oberen 64 Ebenen, also die Phase in Einheiten von 2^-64 Umdrehungen.
_PHASE_PLANES = 128
_PHASE_WORD_BITS = 64
_PHASE_WORD_MASK = (1 << _PHASE_WORD_BITS) - 1
_PHASE_WORD_SCALE = 2.0**_PHASE_WORD_BITS  # Phasenwort -> Umdrehungen

# Toleranz des Benchmarks: 2^-24/sqrt(x) Umdrehungen, in Phasenworten also 2^40/sqrt(x).
_TOLERANCE_NUMERATOR = 2.0**40
# Sollphase round(2^64/sqrt(x)) über die Ganzzahlwurzel von 2^130/x (ein Bit Reserve zum Runden).
_IDEAL_RADICAND = 1 << 130

# Offizielle Synthesekosten einer feinen Rotation: 0.56*log2(1/eps) + 5.3 T-Gatter; 4 T = 1 Toffoli.
_ROT_T_PER_LOG2_INV_EPS = 0.56
_ROT_T_OFFSET = 5.3
_T_PER_TOFFOLI = 4.0

_ZPOW_LEVEL_FINE = 3  # Stufe aus `zpow_info`: feine Rotation
_TRIM_MAX_ANGLE = (
    1 << 50
)  # nur Winkel unter 2^-14 Umdrehungen kommen fürs Streichen in Frage
_TRIM_MIN_RELATIVE_GAIN = 1e-12  # Score muss echt sinken, nicht nur im Rundungsrauschen
_TRIM_DEFAULT_MAX_RATIO = 0.95

# (Index der Instruktion, Lanes auf denen die Rotation wirkt, unbedingt?)
RotationTrace = Tuple[int, int, bool]
# (Score, Kosten C, eps, T je Rotation, schlechtestes Fehler/Toleranz-Verhältnis, dessen Index in der Domäne)
ScoreTerms = Tuple[float, float, float, float, float, int]

_IDEAL_CACHE: Dict[Tuple[int, int], Tuple[Any, Any]] = {}


def _lane_bits(v: int, n: int) -> Any:
    """Zerlegt eine Lane-Ganzzahl in ein numpy-Array aus n Bits (Lane 0 zuerst)."""
    raw = _np.frombuffer(v.to_bytes((n + 7) // 8, "little"), dtype=_np.uint8)
    return _np.unpackbits(raw, bitorder="little")[:n]


def _invsqrt_ideal(lo: int, hi: int) -> Tuple[Any, Any]:
    """Sollphase 1/sqrt(x) und Toleranz 2^-24/sqrt(x), beide in Einheiten von 2^-64 Umdrehungen."""
    if (lo, hi) not in _IDEAL_CACHE:
        ideal = _np.array(
            [
                ((math.isqrt(_IDEAL_RADICAND // x) + 1) >> 1) & _PHASE_WORD_MASK
                for x in range(lo, hi + 1)
            ],
            dtype=_np.uint64,
        )
        tol = _TOLERANCE_NUMERATOR / _np.sqrt(_np.arange(lo, hi + 1, dtype=_np.float64))
        _IDEAL_CACHE[(lo, hi)] = (ideal, tol)
    return _IDEAL_CACHE[(lo, hi)]


@dataclass
class ScoreReport:
    """Exakter Benchmark-Score eines invsqrt-Schaltkreises samt der Größen, aus denen er sich zusammensetzt."""

    q: int
    toffoli: float  # Mittel pro Shot
    t: float
    rot: float
    eps: float  # Syntheseschranke je Rotation: pi * min_x(tol - |Fehler|) / n_rot
    rot_t: float  # T-Gatter je feiner Rotation: 0.56*log2(1/eps) + 5.3
    cost: float  # Toffoli-Äquivalente C
    score: float  # Q x C
    worst_ratio: float  # max_x |Fehler| / Toleranz  (muss < 1 sein)
    worst_x: int
    diff: Any = None  # vorzeichenbehafteter Phasenfehler je x (2^-64 Umdrehungen)
    tol: Any = None
    rots: Optional[List[RotationTrace]] = None

    def line(self) -> str:
        """Einzeilige Zusammenfassung für Protokoll und Audit."""
        return (
            f"Score={self.score:,.2f} = Q {self.q} x C {self.cost:.3f} "
            f"(Toffoli {self.toffoli:.2f} + T {self.t:g}/4 + {self.rot:g} Rot. x "
            f"{self.rot_t / _T_PER_TOFFOLI:.3f}) | "
            f"Fehler/Toleranz max. {self.worst_ratio:.4f} bei x={self.worst_x} | eps={self.eps:.3e}"
        )


def _score_terms(
    q: int, tof: float, t: float, nrot: float, diff: Any, tol: Any
) -> ScoreTerms:
    """Score aus Qubits, mittleren Gatterzahlen und dem Phasenfehler je x.

    Die Reserve min_x(tol - |Fehler|) wird gleichmäßig auf die Rotationen verteilt; je kleiner sie ist, desto
    genauer (teurer) muss jede Rotation synthetisiert werden. Ohne Reserve sind die Kosten unendlich.
    """
    err = _np.abs(diff.astype(_np.float64))
    ratio = err / tol
    worst_index = int(ratio.argmax())
    margin = float((tol - err).min()) / _PHASE_WORD_SCALE
    if nrot <= 0:
        eps, rot_t = float("inf"), 0.0
    elif margin <= 0:
        eps, rot_t = 0.0, float("inf")
    else:
        eps = math.pi * margin / nrot
        rot_t = _ROT_T_PER_LOG2_INV_EPS * math.log2(1.0 / eps) + _ROT_T_OFFSET
    cost = tof + (t + (nrot * rot_t if nrot > 0 else 0.0)) / _T_PER_TOFFOLI
    return q * cost, cost, eps, rot_t, float(ratio[worst_index]), worst_index


def _simulate_tracing_fine_rotations(
    ops: Sequence[Op], dom: Domain, seed: Any, trace: bool
) -> Tuple[State, List[RotationTrace]]:
    """Zählender Simulationslauf; mit `trace` wird zu jeder feinen Z_POW-Rotation festgehalten, auf welchen
    Lanes sie wirkt (Wert des Qubits unter der aktiven Bedingung) und ob sie unbedingt ist.
    """
    cops = compile_ops(ops)
    st = State(dom, seed, count=True)
    rots: List[RotationTrace] = []
    # c = (Code, q0, q1, q2, Bit, Bedingung, Ebenen, Stufe), siehe compile_op
    for i, c in enumerate(cops):
        if trace and c[0] == C_ZPOW and c[7] == _ZPOW_LEVEL_FINE:
            m = cur_mask(st, c[5])
            v = st.q.get(c[1], 0)
            rots.append((i, v if m is None else v & m, m is None))
        step(st, c)
    return st, rots


def _phase_words(planes: Sequence[int], n: int) -> Any:
    """Obere 64 Phasenebenen je Lane als uint64 (Phase in 2^-64 Umdrehungen), so wie der Verifier sie liest."""
    theta = _np.zeros(n, dtype=_np.uint64)
    for j in range(_PHASE_PLANES - _PHASE_WORD_BITS, _PHASE_PLANES):
        if planes[j]:
            theta |= _lane_bits(planes[j], n).astype(_np.uint64) << _np.uint64(
                j - _PHASE_WORD_BITS
            )
    return theta


def invsqrt_score(
    ops: Sequence[Op], layout: Layout, dom: Domain, seed: Any = 0, detail: bool = False
) -> Optional[ScoreReport]:
    """Rechnet den Benchmark-Score aus wie der offizielle Verifier: Phase jedes x gegen 1/sqrt(x), Toleranz
    2^-24/sqrt(x), Rotationskosten aus der verbleibenden Reserve. An den veröffentlichten Verifier-Zahlen
    zweier Schaltkreise auf 9-12 Stellen nachgerechnet. Braucht numpy und die vollständige invsqrt-Domäne.
    """
    if _np is None or not layout.invsqrt or not dom.exhaustive:
        return None
    st, rots = _simulate_tracing_fine_rotations(ops, dom, seed, detail)
    n = dom.n
    theta = _phase_words(st.planes(), n)
    ideal, tol = _invsqrt_ideal(layout.lo, layout.hi)
    diff = (theta - ideal).astype(
        _np.int64
    )  # uint64-Differenz modulo 2^64, als int64 vorzeichenrichtig
    q = compute_metrics(ops).num_qubits
    tof, t, nrot = st.tof / n, st.tl / n, st.rot / n
    score, cost, eps, rot_t, worst, worst_index = _score_terms(
        q, tof, t, nrot, diff, tol
    )
    return ScoreReport(
        q,
        tof,
        t,
        nrot,
        eps,
        rot_t,
        cost,
        score,
        worst,
        layout.lo + worst_index,
        diff if detail else None,
        tol if detail else None,
        rots if detail else None,
    )


def _signed_rotation_angle(op: Op) -> int:
    """Winkel einer Z_POW-Rotation in 2^-64 Umdrehungen, vorzeichenbehaftet und kaufmännisch gerundet."""
    e = _zpow_full(op.args[1])[2]
    signed = e - (1 << _PHASE_PLANES) if e >= 1 << (_PHASE_PLANES - 1) else e
    return (signed + (1 << (_PHASE_WORD_BITS - 1))) >> _PHASE_WORD_BITS


def trim_rotations(
    ops: Sequence[Op],
    layout: Layout,
    dom: Domain,
    max_ratio: float = _TRIM_DEFAULT_MAX_RATIO,
) -> Tuple[List[Op], Dict[str, Any]]:
    """Streicht feine Z_POW-Rotationen, deren Beitrag kleiner ist als die Phasenreserve - aber nur, wenn der
    exakt gerechnete Score dadurch sinkt (weniger Rotationen, dafür teurere restliche, weil die Reserve schrumpft).
    Das ändert die Phase innerhalb der offiziellen Toleranz, ist also KEINE äquivalente Umformung.
    """
    rep = invsqrt_score(ops, layout, dom, detail=True)
    if rep is None or not rep.rots:
        return list(ops), {}
    diff, tol, nrot, best, n = rep.diff, rep.tol, rep.rot, rep.score, dom.n
    removed: List[int] = []
    # Gierig, kleinste Winkel zuerst: jede Streichung zehrt an der Reserve, die allen übrigen bleibt.
    for i, lanes, unconditional in sorted(
        rep.rots, key=lambda r: abs(_signed_rotation_angle(ops[r[0]]))
    ):
        angle = _signed_rotation_angle(ops[i])
        if (
            not unconditional or abs(angle) >= _TRIM_MAX_ANGLE
        ):  # nur unbedingte Rotationen mit winzigem Winkel
            continue
        trial_diff = diff - _np.int64(angle) * _lane_bits(lanes, n).astype(_np.int64)
        trial_score, _, _, _, worst, _ = _score_terms(
            rep.q, rep.toffoli, rep.t, nrot - 1, trial_diff, tol
        )
        if worst <= max_ratio and trial_score < best * (1 - _TRIM_MIN_RELATIVE_GAIN):
            diff, nrot, best = trial_diff, nrot - 1, trial_score
            removed.append(i)
    if not removed:
        return list(ops), {"removed": 0}
    gone = set(removed)
    return [o for i, o in enumerate(ops) if i not in gone], {
        "removed": len(removed),
        "score_before": rep.score,
        "score_after": best,
        "lines": [ops[i].fmt() for i in sorted(removed)],
    }


# =====================================================================
# 6. PIPELINE
# =====================================================================

_MIN_TOLERANCE_ROUNDS = (
    2  # Unabhängigkeit vom Messzufall braucht mindestens zwei Messrunden
)


@dataclass
class Options:
    """Schalter und Budgets der deterministischen Pipeline."""

    deep: bool = True
    mbu: bool = True
    repack: bool = True
    iters: int = 3
    final_rounds: int = 4
    budget_s: float = 180.0
    rot_weight: float = ROT_WEIGHT
    cancel_depth: int = 200
    trim: bool = (
        False  # feine Rotationen innerhalb der Toleranz streichen (nicht äquivalent!)
    )
    trim_max_ratio: float = (
        _TRIM_DEFAULT_MAX_RATIO  # dabei nie näher als so an die Toleranzgrenze gehen
    )
    sampled_facts: bool = (
        False  # faktenbasierte Pässe auch ohne vollständige Domäne zulassen
    )


class Session:
    """Hält Original, aktuellen Stand, Domänen und Prüfer; alle Änderungen laufen über `commit`."""

    def __init__(
        self,
        ops: List[Op],
        layout: Layout,
        dom: Domain,
        smp: Domain,
        opts: Options,
        log: Callable[[str], None] = print,
    ) -> None:
        self.orig, self.ops = list(ops), list(ops)
        self.layout, self.dom, self.smp = layout, dom, smp
        self.opts, self.log = opts, log
        self.oracle = Oracle(ops, layout, dom, log)
        self.audit: List[str] = []
        self.sig: Optional[FinalSig] = None
        self.clean = True
        self.trimmed: Optional[Dict[str, Any]] = (
            None  # gesetzt, sobald Rotationen gestrichen wurden
        )
        self.orig_sig: Optional[FinalSig] = None

    def baseline(self) -> None:
        """Simuliert das Original, merkt sich dessen Signatur und prüft, ob es den Kontrakt selbst erfüllt.
        Nur dann (`clean`) dürfen Pässe laufen, die sich auf sauberen Scratch verlassen.
        """
        t = time.time()
        self.sig = self.orig_sig = self.oracle.orig_sig(0)
        issues = self.oracle.self_check()
        self.clean = not issues
        sampling_note = (
            ""
            if self.dom.exhaustive
            else "  (Stichprobe: Fakten sind statistisch, nicht exakt)"
        )
        self.log(f"Domäne: {self.dom.label}" + sampling_note)
        verdict = (
            "Kontrakt erfüllt (Scratch sauber, Register erhalten, Phase deterministisch)"
            if not issues
            else "ACHTUNG: " + "; ".join(issues)
        )
        self.log(f"Basislauf in {time.time() - t:.1f}s: " + verdict)

    def score(self, ops: Sequence[Op], sig: Optional[FinalSig]) -> str:
        """Kennzahlenzeile; mit Signatur zusätzlich Toffoli je Shot und der geschätzte Score."""
        m = compute_metrics(ops)
        if sig is None:
            return m.summary()
        s = score_estimate(
            m.num_qubits, sig.tof_mean, sig.t_mean, sig.rot_mean, self.opts.rot_weight
        )
        return f"{m.summary()} | Toffoli/Shot={sig.tof_mean:.2f} | Score≈{s:,.0f}"

    def exact(self, ops: Sequence[Op]) -> Optional[ScoreReport]:
        """Exakter invsqrt-Score oder None, wenn er hier nicht berechenbar ist (siehe `invsqrt_score`)."""
        return invsqrt_score(ops, self.layout, self.dom)

    def tolerance_check(self, ops: Sequence[Op], rounds: int) -> Tuple[bool, str]:
        """Kontraktprüfung ohne Bezug aufs Original: Register erhalten, Scratch sauber, Phase vom Messzufall
        unabhängig und für jedes x innerhalb der offiziellen Toleranz."""
        rounds = max(_MIN_TOLERANCE_ROUNDS, rounds)
        init = tuple(
            _digest(self.dom.init_q.get(q, 0)) for q in sorted(self.layout.pinned)
        )
        cops, first = compile_ops(ops), None
        for seed in range(rounds):
            sig = final_sig(simulate(cops, self.dom, f"tol{seed}"), self.layout)
            if sig.reg != init or not sig.scratch_clean or sig.depth:
                return (
                    False,
                    "Register, Scratch oder Bedingungsstapel verletzen den Kontrakt",
                )
            if first is not None and sig.planes != first:
                return False, "Phase hängt vom Messzufall ab"
            first = sig.planes
        rep = self.exact(ops)
        if rep is None:
            return False, "exakter Score nicht verfügbar"
        if not rep.worst_ratio < 1.0:  # bewusst negiert: auch NaN fällt durch
            return False, "Phase außerhalb der Toleranz"
        return (
            True,
            f"Kontrakt erfüllt auf {self.dom.label} x {rounds} Messrunden; {rep.line()}",
        )

    def trim(self) -> Optional[Dict[str, Any]]:
        """Optionaler letzter Schritt (--trim-rotations). Danach ist der Stand die neue Vergleichsbasis."""
        new_ops, st = trim_rotations(
            self.ops, self.layout, self.dom, self.opts.trim_max_ratio
        )
        if not st.get("removed"):
            return None
        ok, msg = self.tolerance_check(new_ops, self.opts.final_rounds)
        self._record(
            f"[{'OK' if ok else 'VERWORFEN'}] Rotations-Trimmen: {st['removed']} Z_POW gestrichen | {msg}"
        )
        if not ok:
            return None
        self.ops, self.trimmed = new_ops, st
        self.oracle = Oracle(new_ops, self.layout, self.dom, self.log)
        self.sig = self.oracle.orig_sig(0)
        return st

    def commit(
        self, name: str, new_ops: List[Op], detail: str, seeds: Sequence[int] = (0,)
    ) -> bool:
        """Übernimmt `new_ops` nur, wenn der End-to-End-Prüfer sie gegen das Original bestätigt; protokolliert
        Annahme wie Ablehnung im Audit."""
        ok, msg, sig = self.oracle.check(new_ops, seeds)
        if ok:
            self.ops, self.sig = new_ops, sig
        self._record(f"[{'OK' if ok else 'VERWORFEN'}] {name}: {detail} | {msg}")
        return ok

    def _record(self, entry: str) -> None:
        self.audit.append(entry)
        self.log("  " + entry)

    def run_passes(self) -> Dict[str, Any]:
        """Lässt die deterministischen Pässe bis zum Fixpunkt (höchstens `iters` Runden) laufen, danach einmal
        das Qubit-Repacking. Jeder Schritt geht einzeln durch `commit`."""
        summary: Dict[str, Any] = {}
        facts = self.dom.exhaustive or self.opts.sampled_facts
        if not facts:
            self.log(
                "  Keine vollständige Eingabedomäne: Es laufen nur die rein syntaktischen Pässe. "
                "Simulationsgestützte Pässe wären hier nur statistisch abgesichert (--allow-sampled-facts)."
            )
        for _ in range(self.opts.iters):
            changed = self._cancel_step(summary)
            if facts:
                changed |= self._sim_reduce_step(summary)
                changed |= self._mbu_step(summary)
            if not changed:
                break
        if facts:
            self._repack_step(summary)
        return summary

    def _cancel_step(self, summary: Dict[str, Any]) -> bool:
        """Faltung, Auslöschung kommutierender Paare und Phasenfusion (rein syntaktisch)."""
        folded, n_folds = pass_fold(self.ops)
        cancelled, n_pairs, n_merged = pass_cancel(folded, self.opts.cancel_depth)
        if not (n_folds or n_pairs or n_merged):
            return False
        ok = self.commit(
            "Auslöschung",
            cancelled,
            f"{n_pairs} Paare gelöscht, {n_merged} Phasengatter zusammengefasst, {n_folds} Faltungen",
        )
        summary["cancelled"] = summary.get("cancelled", 0) + n_pairs
        summary["phase_merged"] = summary.get("phase_merged", 0) + n_merged
        return ok

    def _sim_reduce_step(self, summary: Dict[str, Any]) -> bool:
        """Simulationsgeführte Reduktion; HMR ohne Wirkung fallen nur bei sauberem Original weg."""
        o = self.opts
        reduced, st = pass_sim_reduce(
            self.ops,
            self.layout,
            self.dom,
            self.smp,
            o.deep,
            o.budget_s,
            drop_idle_hmr=self.clean,
        )
        if len(reduced) == len(self.ops) and all(
            x is y for x, y in zip(reduced, self.ops)
        ):
            return False
        ok = self.commit(
            "Simulationsgeführte Reduktion", reduced, json.dumps(st, ensure_ascii=False)
        )
        summary["sim"] = st
        return ok

    def _mbu_step(self, summary: Dict[str, Any]) -> bool:
        """Measurement-Based Uncomputation; setzt sauberen Scratch im Original voraus."""
        if not (self.opts.mbu and self.clean):
            return False
        rewritten, st = pass_mbu(self.ops, self.layout, self.dom)
        if not st.get("chains"):
            return False
        ok = self.commit("Measurement-Based Uncomputation", rewritten, json.dumps(st))
        summary["mbu"] = st
        return ok

    def _repack_step(self, summary: Dict[str, Any]) -> None:
        """Qubit-Repacking; wird nur übernommen, wenn die Qubitzahl tatsächlich sinkt."""
        if not (self.opts.repack and self.clean):
            return
        repacked, st = pass_repack(self.ops, self.layout, self.dom)
        if st["q_after"] < st["q_before"]:
            self.commit("Qubit-Repacking", repacked, json.dumps(st))
        else:
            self.log(
                f"  Qubit-Repacking: kein Gewinn (Q={st['q_before']}, Scratch-Spitze {st['peak_scratch']})"
            )
        summary["repack"] = st

    def final_check(self) -> Tuple[bool, str]:
        """Abschließender End-to-End-Vergleich über `final_rounds` Messrunden."""
        ok, msg, sig = self.oracle.check(self.ops, range(self.opts.final_rounds))
        if ok:
            self.sig = sig
        return ok, msg


# =====================================================================
# 7. WERKBANK FÜR DEN AGENTEN (TOOLS)
# =====================================================================

ToolResult = Dict[str, Any]  # JSON-serialisierbare Antwort eines Werkbank-Tools
ChatMessage = Dict[str, Any]  # Nachricht im OpenAI-Chat-Format
ToolSchema = Dict[str, Any]  # Tool-Beschreibung im OpenAI-Function-Calling-Format
WindowSpan = Tuple[int, int]  # Fenster [start, ende], beide Grenzen eingeschlossen
LaneVectors = Dict[
    int, int
]  # Qubit -> Lane-Vektor (Bit i = Wert des Qubits in Trajektorie i)

SEGMENT_ENTER_TAG = "@enter:"
SEGMENT_EXIT_TAG = "@exit:"
PROFILE_CHUNK_COUNT = 20  # ohne Tags: Profil in so vielen gleich großen Abschnitten
PROFILE_PATH_DEPTH = (
    2  # mit Tags: so viele Ebenen des @enter-Pfads bilden den Segmentnamen
)


def _follow_segment_tag(path: List[str], tag_op: Op) -> None:
    """Führt den @enter/@exit-Pfad über eine INFO_TAG-Instruktion (mit Text) fort."""
    tag = tag_op.text.strip('"')
    if tag.startswith(SEGMENT_ENTER_TAG):
        path.append(tag[len(SEGMENT_ENTER_TAG) :])
    elif tag.startswith(SEGMENT_EXIT_TAG) and path:
        path.pop()


def profile_segments(ops: Sequence[Op], max_rows: int = 40) -> List[Dict[str, Any]]:
    """Toffoli-Profil entlang der INFO_TAG-Struktur (@enter/@exit); ohne Tags in gleich großen Abschnitten."""
    rows: Dict[str, Dict[str, Any]] = {}
    path: List[str] = []
    tagged = any(
        o.name == "INFO_TAG" and o.text and SEGMENT_ENTER_TAG in o.text for o in ops
    )
    chunk = max(1, len(ops) // PROFILE_CHUNK_COUNT)
    for i, o in enumerate(ops):
        if o.name == "INFO_TAG" and o.text:
            _follow_segment_tag(path, o)
            continue
        if tagged:
            key = "/".join(path[:PROFILE_PATH_DEPTH]) or "(oberste Ebene)"
        else:
            key = f"idx {i // chunk * chunk}..{min(len(ops), (i // chunk + 1) * chunk) - 1}"
        row = rows.setdefault(
            key, {"segment": key, "toffoli": 0, "instruktionen": 0, "von": i, "bis": i}
        )
        row["toffoli"] += o.name in TOFFOLI_LIKE
        row["instruktionen"] += 1
        row["bis"] = i
    ranked = sorted(rows.values(), key=lambda row: -row["toffoli"])
    return ranked[:max_rows]


# ---- Hotspot-Suche (find_hotspots) ----

HOTSPOT_KIND_ERROR = "kind muss runs, pairs, dense, peak oder conditional sein"
HOTSPOT_LIMIT_MAX = 50
HOTSPOT_RUN_INDEX_PREVIEW = (
    12  # so viele CCX-Indizes einer Gruppe werden dem Modell gezeigt
)
HOTSPOT_PAIR_MAX_DISTANCE = 40
HOTSPOT_DENSE_WINDOW = 40
HOTSPOT_PEAK_LIFETIMES = (
    12  # so viele der längsten Lebensdauern an der Qubit-Spitze werden gezeigt
)


def _hotspot_ccx_runs(ops: Sequence[Op], depths: Sequence[int]) -> List[ToolResult]:
    """Gruppen mehrerer unbedingter CCX auf dasselbe Ziel, zwischen denen das Ziel nicht gelesen wird.

    Eine offene Gruppe endet, sobald ihr Ziel als Kontrolle eines schlichten X-artigen Gatters oder von irgendeiner
    anderen Instruktion berührt wird. Größte Gruppen zuerst, bei Gleichstand die kompakteren.
    """
    open_runs: Dict[int, List[int]] = {}
    closed: List[List[int]] = []
    for i, o in enumerate(ops):
        if o.name in META_OPS or not o.qs:
            continue
        plain = _plain_xt(o, depths[i])
        for q in (o.qs[:-1] if plain else o.qs):
            run = open_runs.pop(q, None)
            if run and len(run) > 1:
                closed.append(run)
        if plain and o.name == "CCX":
            open_runs.setdefault(o.qs[-1], []).append(i)
    closed += [run for run in open_runs.values() if len(run) > 1]
    closed.sort(key=lambda run: (-(len(run)), run[-1] - run[0]))
    return [
        {
            "ziel": f"q{ops[run[0]].qs[-1]}",
            "ccx_indizes": run[:HOTSPOT_RUN_INDEX_PREVIEW],
            "anzahl": len(run),
            "spanne": run[-1] - run[0] + 1,
        }
        for run in closed
    ]


def _hotspot_ccx_pairs(ops: Sequence[Op]) -> List[ToolResult]:
    """Identische unbedingte CCX-Tripel in kurzer Distanz, engste Paare zuerst."""
    positions: Dict[Tuple, List[int]] = defaultdict(list)
    for i, o in enumerate(ops):
        if o.name == "CCX" and o.cond is None:
            positions[o.key()].append(i)
    hits: List[ToolResult] = []
    for indices in positions.values():
        for a, b in zip(indices, indices[1:]):
            if b - a <= HOTSPOT_PAIR_MAX_DISTANCE:
                hits.append(
                    {"gatter": ops[a].fmt(), "start": a, "ende": b, "distanz": b - a}
                )
    hits.sort(key=lambda hit: hit["distanz"])
    return hits


def _hotspot_dense_windows(ops: Sequence[Op]) -> List[ToolResult]:
    """Halb überlappende Fenster fester Breite, absteigend nach Toffoli-Zahl (Fenster ohne Toffoli entfallen)."""
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


def _hotspot_conditional_toffolis(
    ops: Sequence[Op], depths: Sequence[int]
) -> List[ToolResult]:
    """Toffoli-artige Gatter unter klassischer Bedingung (if bN oder innerhalb eines PUSH_CONDITION-Blocks)."""
    return [
        {"idx": i, "gatter": o.fmt(), "tiefe": depths[i]}
        for i, o in enumerate(ops)
        if o.name in TOFFOLI_LIKE and (o.cond is not None or depths[i])
    ]


# ---- Fensteranalyse (analyze_window) ----

WINDOW_MAX_SPAN = 300  # größte Differenz end - start, die analyze_window annimmt
WINDOW_PAIRWISE_FACT_QUBITS = (
    18  # AND-/Disjunktheitsfakten nur bis zu so vielen nichtkonstanten Qubits (kubisch)
)
WINDOW_REACHABLE_CAP = 4096  # Zählung erreichbarer Zustände bricht darüber ab
WINDOW_STATE_LIST_MAX = (
    24  # bis zu so vielen erreichbaren Zuständen wird die Liste ausgegeben
)
WINDOW_FACTS_MAX = 60
WINDOW_CLEAN_ANCILLAS_MAX = 8
WINDOW_EXACT_MAX_VARS = (
    20  # Variablengrenze des exakten Fensterbeweises (Vorgabe von check_exact)
)
WINDOW_SAMPLE_HINT = "Fakten stammen aus der Stichprobe; beim Einreichen wird auf der ganzen Domäne geprüft."


def _taint_before(ops: Sequence[Op], pos: int) -> Taint:
    """Statische Messabhängigkeit unmittelbar vor Instruktion `pos`."""
    taint = Taint()
    for o in ops[:pos]:
        taint.advance(o)
    return taint


def _constant_value_facts(
    qubits: Sequence[int], vec: LaneVectors, tainted: Set[int], all_lanes: int
) -> List[str]:
    """Fakten über messabhängige und über konstante Qubits (0 bzw. 1 in jeder Trajektorie)."""
    facts: List[str] = []
    for q in qubits:
        if q in tainted:
            facts.append(f"q{q} hängt von Messergebnissen ab")
        elif vec[q] == 0:
            facts.append(f"q{q} = 0 (auf allen Stichproben)")
        elif vec[q] == all_lanes:
            facts.append(f"q{q} = 1")
    return facts


def _linear_relation_facts(
    varying: Sequence[int], vec: LaneVectors, all_lanes: int
) -> List[str]:
    """XOR-Beziehungen: jedes Qubit, das in der GF(2)-Hülle der Konstanten 1 und der vorherigen Qubits liegt."""
    facts: List[str] = []
    basis = XorBasis()
    basis.add(ONE, all_lanes)
    for q in varying:
        combination = basis.solve(vec[q])
        if combination is not None:
            facts.append(
                f"q{q} = "
                + " ^ ".join("1" if term == ONE else f"q{term}" for term in combination)
            )
        else:
            basis.add(q, vec[q])
    return facts


def _pairwise_relation_facts(varying: Sequence[int], vec: LaneVectors) -> List[str]:
    """AND-Beziehungen qT = qA & qB und Paare, die nie gleichzeitig 1 sind."""
    facts: List[str] = []
    for t in varying:
        for i, a in enumerate(varying):
            for b in varying[i + 1 :]:
                if t not in (a, b) and vec[a] & vec[b] == vec[t]:
                    facts.append(f"q{t} = q{a} & q{b}")
    for i, a in enumerate(varying):
        for b in varying[i + 1 :]:
            if vec[a] & vec[b] == 0:
                facts.append(f"q{a} & q{b} = 0 (nie gleichzeitig 1)")
    return facts


def _window_entry_facts(
    qubits: Sequence[int], vec: LaneVectors, tainted: Set[int], all_lanes: int
) -> List[str]:
    """Alle Fakten über die Fenster-Qubits am Eingang: Konstanten, lineare, AND- und Disjunktheitsbeziehungen.
    Beziehungen werden nur zwischen messunabhängigen, nichtkonstanten Qubits gesucht."""
    facts = _constant_value_facts(qubits, vec, tainted, all_lanes)
    varying = [q for q in qubits if q not in tainted and vec[q] not in (0, all_lanes)]
    facts += _linear_relation_facts(varying, vec, all_lanes)
    if len(varying) <= WINDOW_PAIRWISE_FACT_QUBITS:
        facts += _pairwise_relation_facts(varying, vec)
    return facts


def _reachable_lane_groups(
    qubits: Sequence[int], vec: LaneVectors, all_lanes: int
) -> List[int]:
    """Zerlegt die Lanes in Gruppen gleicher Belegung der Fenster-Qubits (eine Lane-Maske je erreichbarem Zustand).
    Bricht ab, sobald mehr als WINDOW_REACHABLE_CAP Gruppen entstehen; die Liste ist dann nur eine untere Schranke.
    """
    groups = [all_lanes]
    for q in qubits:
        refined = []
        for group in groups:
            for part in (group & vec[q], group & ~vec[q]):
                if part:
                    refined.append(part)
        groups = refined
        if len(groups) > WINDOW_REACHABLE_CAP:
            break
    return groups


# ---- Rewrite-Vorschläge (propose_rewrite) ----

REWRITE_COST_DECIMALS = (
    9  # Rundung der mittleren Toffoli-Kosten vor dem Vergleich (Gleitkomma-Rauschen)
)
REWRITE_RATIONALE_MAX = 160
REWRITE_SHIFT_HINT = "Indizes hinter dem Fenster haben sich verschoben."
REGISTER_DECLARATIONS = ("REGISTER", "APPEND_TO_REGISTER")
NOTE_MAX_CHARS = 500
OVERVIEW_PROFILE_ROWS = 15
OVERVIEW_NOTES = 10
READ_LINES_MAX = 200


def _rewrite_rejection(reason: str) -> ToolResult:
    """Antwort von propose_rewrite bei Ablehnung."""
    return {"accepted": False, "reason": reason}


def _window_structure_error(window: Sequence[Op], who: str) -> Optional[str]:
    """Ein Fenster darf keine Register deklarieren und muss PUSH/POP_CONDITION in sich ausgleichen."""
    if any(o.name in REGISTER_DECLARATIONS for o in window):
        return f"{who} enthält Register-Deklarationen"
    depth = 0
    for o in window:
        depth += (o.name == "PUSH_CONDITION") - (o.name == "POP_CONDITION")
        if depth < 0:
            return f"{who}: POP_CONDITION ohne passendes PUSH im Fenster"
    if depth:
        return f"{who}: PUSH/POP im Fenster nicht ausgeglichen"
    return None


def _rewrite_shape_error(
    ops: Sequence[Op], orig_w: Sequence[Op], cand_w: Sequence[Op]
) -> Optional[str]:
    """Statische Vorbedingungen eines Rewrites: Fensterstruktur beider Seiten, und der Kandidat darf Q nicht erhöhen."""
    for window, who in ((orig_w, "Originalfenster"), (cand_w, "Kandidat")):
        reason = _window_structure_error(window, who)
        if reason is not None:
            return reason
    num_qubits = compute_metrics(ops).num_qubits
    if any(q >= num_qubits for o in cand_w for q in o.qs):
        return f"Kandidat nutzt Qubits >= q{num_qubits}; das würde Q erhöhen"
    return None


def _window_dead_bits(
    ops: Sequence[Op],
    end: int,
    orig_w: Sequence[Op],
    cand_w: Sequence[Op],
    layout: Layout,
    depths: Sequence[int],
) -> Set[int]:
    """Bits, die eines der Fenster schreibt und die hinter dem Fenster niemand mehr liest. Bits, die im Schaltkreis
    sonst gar nicht vorkommen (frische Messbits des Kandidaten), sind per Definition tot.
    """
    known_bits = {o.bit for o in ops if o.bit is not None} | {
        o.cond for o in ops if o.cond is not None
    }
    touched = _op_bits_written(orig_w) | _op_bits_written(cand_w)
    return dead_bits_after(ops, end, touched & known_bits, layout, depths) | (
        touched - known_bits
    )


def _static_window_cost(window: Sequence[Op]) -> Tuple[int, int]:
    """(Toffoli-artige Gatter, Instruktionen) eines Fensters, ohne Rücksicht auf Bedingungen."""
    return sum(o.name in TOFFOLI_LIKE for o in window), len(window)


class Workbench:
    """Werkzeuge, die der LLM-Agent aufruft. Jede Änderung wird verifiziert, bevor sie übernommen wird."""

    STRIDE = 2000  # Abstand der Zustands-Schnappschüsse (Instruktionen) auf der Stichprobendomäne

    def __init__(
        self, session: Session, context_rounds: int = 4, exact_only: bool = False
    ) -> None:
        self.s = session
        self.rounds = context_rounds
        self.exact_only = (
            exact_only  # nur Beweise über ALLE Belegungen annehmen (keine Don't-Cares)
        )
        self.snaps: List[Tuple[int, State]] = []
        self.undo_stack: List[List[Op]] = []
        self.notes: List[str] = []
        self.accepted = 0
        self.finished: Optional[str] = None
        self._exh: Optional[Tuple[int, State]] = None

    # ---- Zustände an einer Position ----
    def _invalidate(self, pos: int) -> None:
        """Verwirft zwischengespeicherte Zustände hinter `pos` (der Schaltkreis hat sich ab dort geändert)."""
        self.snaps = [(p, s) for p, s in self.snaps if p <= pos]
        if self._exh and self._exh[0] > pos:
            self._exh = None

    def state_at(self, pos: int, exhaustive: bool = False) -> State:
        """Simulatorzustand unmittelbar vor Instruktion `pos`.

        Stichprobendomäne: startet am letzten Schnappschuss davor und legt alle STRIDE Instruktionen einen neuen ab.
        Volle Domäne (`exhaustive`): merkt sich nur den zuletzt berechneten Zustand, weil eine Kopie teuer ist.
        """
        ops = self.s.ops
        if exhaustive:
            if self._exh and self._exh[0] <= pos:
                start, st = self._exh[0], self._exh[1].copy()
            else:
                start, st = 0, State(self.s.dom, "W")
        else:
            cand = [(p, s) for p, s in self.snaps if p <= pos]
            start, st = (
                (cand[-1][0], cand[-1][1].copy())
                if cand
                else (0, State(self.s.smp, "W"))
            )
        for i in range(start, pos):
            if not exhaustive and i % self.STRIDE == 0 and i > start:
                self.snaps.append((i, st.copy()))
                self.snaps.sort(key=lambda t: t[0])
            step(st, compile_op(ops[i]))
        if exhaustive:
            self._exh = (pos, st.copy())
        return st

    # ---- Tools ----
    def overview(self) -> ToolResult:
        """Tool: Kennzahlen des aktuellen Stands und des Originals, Register, Toffoli-Profil und letzte Notizen."""
        s = self.s
        original = compute_metrics(s.orig)
        return {
            "stand": s.score(s.ops, s.sig),
            "original": original.summary(),
            "register": {
                s.layout.names.get(r, f"r{r}"): len(t)
                for r, t in s.layout.registers.items()
            },
            "domäne": s.dom.label,
            "angenommene_rewrites": self.accepted,
            "profil_top": profile_segments(s.ops, OVERVIEW_PROFILE_ROWS),
            "notizen": self.notes[-OVERVIEW_NOTES:],
        }

    def read_lines(self, start: int, count: int = 60) -> ToolResult:
        """Tool: Instruktionen ab Index `start` (höchstens READ_LINES_MAX), jeweils mit ihrem Index."""
        ops = self.s.ops
        start = max(0, min(start, len(ops)))
        end = min(len(ops), start + max(1, min(count, READ_LINES_MAX)))
        return {
            "gesamt": len(ops),
            "zeilen": [f"{i}: {ops[i].fmt()}" for i in range(start, end)],
        }

    def find_hotspots(self, kind: str = "runs", limit: int = 15) -> ToolResult:
        """Tool: lohnende Stellen der Art `kind` (runs, pairs, dense, peak, conditional), beste zuerst."""
        ops = self.s.ops
        if kind == "runs":
            hits = _hotspot_ccx_runs(ops, push_depths(ops))
        elif kind == "pairs":
            hits = _hotspot_ccx_pairs(ops)
        elif kind == "dense":
            hits = _hotspot_dense_windows(ops)
        elif kind == "peak":
            hits = self._hotspot_qubit_peak()
        elif kind == "conditional":
            hits = _hotspot_conditional_toffolis(ops, push_depths(ops))
        else:
            return {"fehler": HOTSPOT_KIND_ERROR}
        return {
            "art": kind,
            "treffer": len(hits),
            "liste": hits[: max(1, min(limit, HOTSPOT_LIMIT_MAX))],
        }

    def _hotspot_qubit_peak(self) -> List[ToolResult]:
        """Wo liegt die Scratch-Qubit-Spitze, und welche Lebensdauern tragen sie (längste zuerst)?"""
        ops = self.s.ops
        lifetimes, _ = lifetimes_of(ops, trace_touches(ops, self.s.layout, self.s.smp))
        events = sorted(
            [(a, 1) for a, _, _, _ in lifetimes]
            + [(b + 1, -1) for _, b, _, _ in lifetimes]
        )
        live = peak = peak_idx = 0
        for idx, delta in events:
            live += delta
            if live > peak:
                peak, peak_idx = live, idx
        peak_idx = min(peak_idx, len(ops) - 1)
        carriers = sorted(
            ((b - a, q, a, b) for a, b, q, _ in lifetimes if a <= peak_idx <= b),
            reverse=True,
        )
        return [
            {
                "spitze_bei_idx": peak_idx,
                "scratch_gleichzeitig": peak,
                "segment": self._segment_of(peak_idx),
                "längste_lebensdauern": [
                    {"qubit": f"q{q}", "von": a, "bis": b}
                    for _, q, a, b in carriers[:HOTSPOT_PEAK_LIFETIMES]
                ],
            }
        ]

    def _segment_of(self, idx: int) -> str:
        """Voller @enter-Pfad, in dem Instruktion `idx` liegt."""
        path: List[str] = []
        for o in self.s.ops[:idx]:
            if o.name == "INFO_TAG" and o.text:
                _follow_segment_tag(path, o)
        return "/".join(path) or "(unbekannt)"

    def analyze_window(self, start: int, end: int) -> ToolResult:
        """Tool: Zeilen des Fensters [start, end] und was die Stichprobe über seine Qubits am Eingang weiß
        (Fakten, erreichbare Zustände, freie saubere Ancillas, ob ein exakter Beweis in Reichweite ist).
        """
        ops = self.s.ops
        if not (0 <= start <= end < len(ops)):
            return {"fehler": f"Indizes außerhalb 0..{len(ops) - 1}"}
        if end - start > WINDOW_MAX_SPAN:
            return {"fehler": "Fenster zu groß (max. 300 Instruktionen)"}
        window = ops[start : end + 1]
        entry = self.state_at(start)
        tainted = _taint_before(ops, start).tq
        qubits = sorted({q for o in window for q in o.qs})
        vec = {q: entry.q.get(q, 0) for q in qubits}
        facts = _window_entry_facts(qubits, vec, tainted, entry.ALL)
        groups = _reachable_lane_groups(qubits, vec, entry.ALL)
        reach: Any = (
            f">{len(groups)}" if len(groups) > WINDOW_REACHABLE_CAP else len(groups)
        )
        states = None
        if isinstance(reach, int) and reach <= WINDOW_STATE_LIST_MAX:
            states = [
                "".join(str((vec[q] >> _first_lane(group)) & 1) for q in qubits)
                for group in groups
            ]
        depths = push_depths(ops)
        clean = [
            q
            for q in range(compute_metrics(ops).num_qubits)
            if q not in self.s.layout.pinned
            and q not in qubits
            and entry.q.get(q, 0) == 0
            and q not in tainted
        ]
        exact_vars = len(_exact_keys(window, window, depths[start]))
        return {
            "zeilen": [f"{start + i}: {o.fmt()}" for i, o in enumerate(window)],
            "qubits": [f"q{q}" for q in qubits],
            "toffoli": sum(o.name in TOFFOLI_LIKE for o in window),
            "bedingungstiefe_am_eingang": depths[start],
            "fakten_am_eingang": facts[:WINDOW_FACTS_MAX],
            "erreichbare_zustände": reach,
            "von_möglichen": f"2^{len(qubits)}",
            "zustandsliste(q-Reihenfolge wie 'qubits')": states,
            "freie_saubere_ancillas": [
                f"q{q}" for q in clean[:WINDOW_CLEAN_ANCILLAS_MAX]
            ],
            "exakter_beweis_möglich": exact_vars <= WINDOW_EXACT_MAX_VARS,
            "hinweis": WINDOW_SAMPLE_HINT,
        }

    def propose_rewrite(
        self,
        start: int,
        end: int,
        new_lines: List[str],
        rationale: str = "",
        neutral_ok: bool = False,
    ) -> ToolResult:
        """Tool: ersetzt das Fenster [start, end] durch `new_lines`, wenn die Kosten sinken und der Verifier zustimmt.

        Reihenfolge: statische Vorbedingungen, Kostenvergleich auf der Stichprobe, dann der Beweis (exakt über alle
        Belegungen, sonst kontextuell auf der ganzen Domäne). `neutral_ok` lässt auch kostengleiche Fenster zu,
        nie aber solche mit mehr Toffoli pro Shot."""
        s, ops = self.s, self.s.ops
        if not (0 <= start <= end < len(ops)):
            return _rewrite_rejection(f"Indizes außerhalb 0..{len(ops) - 1}")
        orig_w = ops[start : end + 1]
        try:
            cand_w = parse_lines(new_lines)
        except KmxError as e:
            return _rewrite_rejection(f"Syntaxfehler: {e}")
        shape_error = _rewrite_shape_error(ops, orig_w, cand_w)
        if shape_error is not None:
            return _rewrite_rejection(shape_error)
        depths = push_depths(ops)
        dead = _window_dead_bits(ops, end, orig_w, cand_w, s.layout, depths)
        rough = off_grid_phase((*orig_w, *cand_w))
        if rough is not None:
            return _rewrite_rejection(
                f"{rough.fmt()!r} liegt nicht auf dem 2^-127-Phasenraster; "
                "ein solches Fenster lässt sich nicht bitgenau vergleichen"
            )
        entry = self.state_at(start)
        sample_ok, sample_msg, (c_old, c_new) = check_context(
            entry, orig_w, cand_w, dead, s.smp, self.rounds
        )
        static_old, static_new = _static_window_cost(orig_w), _static_window_cost(
            cand_w
        )
        cost_old = (round(c_old, REWRITE_COST_DECIMALS), *static_old)
        cost_new = (round(c_new, REWRITE_COST_DECIMALS), *static_new)
        worse = cost_new[:2] > cost_old[:2]
        if worse or (not neutral_ok and cost_new >= cost_old):
            return _rewrite_rejection(
                f"keine Kostensenkung: Toffoli/Shot {c_old:.3f} -> {c_new:.3f}, "
                f"statisch {static_old[0]} -> {static_new[0]}"
            )
        proof, rejection = self._prove_rewrite(
            start, orig_w, cand_w, dead, depths[start], sample_ok, sample_msg
        )
        if proof is None:
            return rejection
        self.undo_stack.append(list(ops))
        s.ops = ops[:start] + cand_w + ops[end + 1 :]
        self._invalidate(start)
        self.accepted += 1
        entry_log = (
            f"[REWRITE] idx {start}..{end}: Toffoli {static_old[0]} -> {static_new[0]} "
            f"({c_old:.2f} -> {c_new:.2f}/Shot) | {rationale[:REWRITE_RATIONALE_MAX]} | {proof}"
        )
        s.audit.append(entry_log)
        s.log("  " + entry_log)
        return {
            "accepted": True,
            "message": proof,
            "neue_länge": len(s.ops),
            "hinweis": REWRITE_SHIFT_HINT,
        }

    def _prove_rewrite(
        self,
        start: int,
        orig_w: Sequence[Op],
        cand_w: Sequence[Op],
        dead: Set[int],
        entry_depth: int,
        sample_ok: bool,
        sample_msg: str,
    ) -> Tuple[Optional[str], Optional[ToolResult]]:
        """Äquivalenzbeweis für ein Fenster. Rückgabe (Beweistext, None) oder (None, Ablehnung).

        Ein exakter Beweis (L1) gilt für alle Belegungen und genügt allein. Sonst muss das Fenster kontextuell (L2)
        halten: erst auf der Stichprobe (`sample_ok`/`sample_msg` vom Aufrufer), dann auf der ganzen Domäne. Mit
        `exact_only` wird der kontextuelle Weg gar nicht erst versucht."""
        status, exact_msg = check_exact(orig_w, cand_w, entry_depth, dead)
        if status == "proved":
            return exact_msg, None
        if self.exact_only:
            return None, _rewrite_rejection(
                "Kein Beweis über alle Belegungen möglich (--exact-only): " + exact_msg
            )
        if not sample_ok:
            return None, {
                "accepted": False,
                "reason": "Verifier-Ablehnung (erreichbarer Zustand): " + sample_msg,
                "hinweis": "Das Gegenbeispiel ist ein real auftretender Zustand. "
                + (exact_msg if status == "refuted" else ""),
            }
        entry_full = self.state_at(start, exhaustive=True)
        full_ok, full_msg, _ = check_context(
            entry_full, orig_w, cand_w, dead, self.s.dom, max(2, self.rounds // 2)
        )
        if not full_ok:
            return None, _rewrite_rejection(
                "Stichprobe bestanden, aber auf der ganzen Domäne widerlegt: "
                + full_msg
            )
        return "kontextuell verifiziert: " + full_msg, None

    def run_passes(self) -> ToolResult:
        """Tool: deterministische Pässe der Sitzung; ein geänderter Stand wird rücknehmbar gemacht."""
        before = list(self.s.ops)
        summary = self.s.run_passes()
        if len(before) != len(self.s.ops) or any(
            a is not b for a, b in zip(before, self.s.ops)
        ):
            self.undo_stack.append(before)
            self._invalidate(0)
        return {
            "zusammenfassung": summary,
            "stand": self.s.score(self.s.ops, self.s.sig),
        }

    def full_check(self) -> ToolResult:
        """Tool: End-to-End-Prüfung gegen das Original; schlägt sie fehl, wird schrittweise zurückgerollt."""
        ok, msg = self.s.final_check()
        while (
            not ok and self.undo_stack
        ):  # sollte nie passieren; zur Sicherheit zurückrollen
            self.s.ops = self.undo_stack.pop()
            self._invalidate(0)
            ok, msg = self.s.final_check()
            self.s.audit.append(
                "[ROLLBACK] End-to-End-Prüfung schlug fehl; letzter Schritt zurückgenommen"
            )
        return {"ok": ok, "meldung": msg, "stand": self.s.score(self.s.ops, self.s.sig)}

    def undo(self) -> ToolResult:
        """Tool: nimmt die letzte angenommene Änderung (Rewrite oder Pass-Lauf) zurück."""
        if not self.undo_stack:
            return {"ok": False, "meldung": "nichts zum Zurücknehmen"}
        self.s.ops = self.undo_stack.pop()
        self._invalidate(0)
        return {"ok": True, "länge": len(self.s.ops)}

    def note(self, text: str) -> ToolResult:
        """Tool: hält eine Erkenntnis im gemeinsamen Notizbuch fest."""
        self.notes.append(text[:NOTE_MAX_CHARS])
        return {"ok": True}

    def finish(self, summary: str = "") -> ToolResult:
        """Tool: beendet die laufende Agentensitzung."""
        self.finished = summary or "fertig"
        return {"ok": True}

    def dispatch(self, name: str, args: Dict[str, Any]) -> ToolResult:
        """Ruft das Tool `name` mit den Argumenten des Modells auf; Fehler werden zur Antwort statt zum Absturz."""
        fn = {
            "overview": self.overview,
            "read_lines": self.read_lines,
            "find_hotspots": self.find_hotspots,
            "analyze_window": self.analyze_window,
            "propose_rewrite": self.propose_rewrite,
            "run_passes": self.run_passes,
            "full_check": self.full_check,
            "undo": self.undo,
            "note": self.note,
            "finish": self.finish,
        }.get(name)
        if fn is None:
            return {"fehler": f"unbekanntes Tool {name}"}
        try:
            return fn(**args)
        except TypeError as e:
            return {"fehler": f"falsche Argumente für {name}: {e}"}
        except (
            Exception
        ) as e:  # Tool-Fehler gehen als Rückmeldung ans Modell, nicht als Absturz
            return {"fehler": f"{type(e).__name__}: {e}"}


def _tool(
    name: str, desc: str, props: Dict[str, Any], required: Sequence[str] = ()
) -> ToolSchema:
    """Tool-Beschreibung im OpenAI-Function-Calling-Format."""
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": desc,
            "parameters": {
                "type": "object",
                "properties": props,
                "required": list(required),
            },
        },
    }


_INT = {"type": "integer"}
TOOLS = [
    _tool(
        "overview",
        "Kennzahlen, Score-Schätzung, Register und Toffoli-Profil nach Abschnitten.",
        {},
    ),
    _tool(
        "read_lines",
        "Liest Instruktionen ab Index start (0-basiert, Kommentare/Leerzeilen sind entfernt).",
        {"start": _INT, "count": _INT},
        ["start"],
    ),
    _tool(
        "find_hotspots",
        "Sucht lohnende Stellen. kind: runs (mehrere CCX auf dasselbe Ziel), pairs (gleiche CCX-Tripel), "
        "dense (Toffoli-dichte Fenster), peak (wo die Qubit-Spitze liegt), conditional (klassisch bedingte "
        "Toffolis).",
        {
            "kind": {
                "type": "string",
                "enum": ["runs", "pairs", "dense", "peak", "conditional"],
            },
            "limit": _INT,
        },
        ["kind"],
    ),
    _tool(
        "analyze_window",
        "Analysiert das Fenster [start, end]: Zeilen, Fakten über die Qubit-Werte am Eingang "
        "(Konstanten, lineare und AND-Beziehungen, nie gleichzeitig gesetzte Paare), Zahl erreichbarer Zustände, "
        "freie Ancillas.",
        {"start": _INT, "end": _INT},
        ["start", "end"],
    ),
    _tool(
        "propose_rewrite",
        "Ersetzt das Fenster [start, end] durch new_lines, WENN der Verifier Äquivalenz bestätigt und die "
        "Kosten sinken. Bei Ablehnung kommt ein konkretes Gegenbeispiel zurück.",
        {
            "start": _INT,
            "end": _INT,
            "new_lines": {"type": "array", "items": {"type": "string"}},
            "rationale": {"type": "string"},
            "neutral_ok": {
                "type": "boolean",
                "description": "true = auch kostengleiche Umordnung annehmen "
                "(z. B. um die Qubit-Spitze zu senken)",
            },
        },
        ["start", "end", "new_lines"],
    ),
    _tool(
        "run_passes",
        "Lässt die deterministischen Pässe laufen (Auslöschung, simulationsgeführte Reduktion, MBU, Repacking).",
        {},
    ),
    _tool(
        "full_check", "End-to-End-Prüfung gegen das Original auf der ganzen Domäne.", {}
    ),
    _tool("undo", "Nimmt die letzte angenommene Änderung zurück.", {}),
    _tool(
        "note",
        "Hält eine Erkenntnis fest; nachfolgende Modelle sehen sie.",
        {"text": {"type": "string"}},
        ["text"],
    ),
    _tool(
        "finish",
        "Beendet die Sitzung mit einer kurzen Zusammenfassung.",
        {"summary": {"type": "string"}},
    ),
]

AGENT_SYSTEM = """Du optimierst einen kickmix-Quantenschaltkreis (.kmx) für den Kaggle-Wettbewerb \
"Google Quantum AI - Verifiable Quantum Circuit Compilation". Du arbeitest ausschließlich über die Tools; \
jede Änderung wird maschinell verifiziert, raten kostet also nichts außer Schritten.

KOSTEN (kleiner ist besser):  S = Q x (Toffoli + T/4)
- Q = größter Qubit-Index + 1 über den ganzen Schaltkreis.
- Toffoli = CCX, CCZ, CSWAP, gezählt als MITTEL pro Shot: klassisch bedingte Gatter (if bN, PUSH_CONDITION) zählen nur,
  wenn sie ausgeführt werden. X, CX, SWAP, Z, CZ, NEG, HMR, R und Bit-Operationen sind kostenlos.
- Z_POW: Clifford-Winkel frei, T-Winkel 1 T, feinere Winkel ca. 27 T. Z_POW-Gatter nicht anfassen, außer du sparst \
eines ein.

SEMANTIK
- X/CX/CCX/SWAP/CSWAP permutieren Basiszustände; Z/CZ/CCZ/NEG/Z_POW ändern nur die Phase.
- HMR q b: misst q in der X-Basis, schreibt ein Zufallsbit nach b, setzt q auf |0>. Phasen-Kickback (-1)^(b*Wert von q)
  muss mit klassisch bedingten Z/CZ/CCZ/NEG korrigiert werden. R q: Reset, nur auf Qubits, die schon |0> sind.
- "OP ... if bN" führt OP nur aus, wenn bN = 1. PUSH_CONDITION if bN ... POP_CONDITION bedingt einen Block.
- Am Ende müssen alle Scratch-Qubits |0> sein, das Eingaberegister unverändert, die Phase exakt wie im Original.

BEWÄHRTE UMFORMUNGEN
1. Measurement-Based Uncomputation: t = a AND b wird nicht mit CCX a b t zurückgerechnet, sondern mit
   "HMR t b0" + "CZ a b if b0" (0 Toffoli). Gilt für jede Uncompute-Kette, deren Phasenfunktion mit Z/CZ darstellbar \
ist.
2. Gleiche Ziele zusammenfassen: CCX a b t + CCX a c t = CX b c; CCX a c t; CX b c.
   Allgemein: Summe von Produkten mit kleinem Rang, z. B. ab ^ ac ^ bc = (a^c)(b^c) ^ c  (1 statt 3 Toffoli).
3. Don't-Cares der Domäne: analyze_window nennt Konstanten, lineare Beziehungen, AND-Beziehungen und Paare, die nie
   gleichzeitig 1 sind. Ein CCX, dessen Kontrollprodukt so ausdrückbar ist, wird zu CX-Gattern oder entfällt.
4. Klassische Kontrolle statt Quantenkontrolle: hängt eine Kontrolle nur von Messbits ab, ist das Gatter "if bN" und \
gratis
   bzw. zählt nur anteilig.
5. CSWAP mit bekanntem Partner (|0> oder gleicher Wert) vereinfachen; aufeinanderfolgende CSWAPs mit gleicher \
Kontrolle prüfen.
6. Qubit-Spitze senken: Ancillas später berechnen oder früher freigeben (find_hotspots kind=peak), damit Repacking Q \
senkt.
   Dafür sind auch kostenneutrale Umordnungen sinnvoll (propose_rewrite mit neutral_ok=true), wenn danach
   run_passes ein kleineres Q meldet.

VORGEHEN
overview -> find_hotspots -> analyze_window -> propose_rewrite. Lies bei einer Ablehnung das Gegenbeispiel und \
korrigiere
gezielt. Halte Muster, die funktionieren oder sicher nicht funktionieren, mit note fest. Rufe zwischendurch run_passes \
auf,
weil deine Änderungen Folgevereinfachungen freilegen, und am Ende full_check und finish.
Antworte knapp; die Arbeit passiert in den Tool-Aufrufen."""


LOCAL_LLM_URL = "http://192.168.212.81:8000/v1/chat/completions"  # lokale Weinstadt-KI (keyless, OpenAI-kompatibel)
LOCAL_LLM_MODEL = "qwen3.8-27b"
# Qwen3.x denkt sonst privat und liefert leeres content; fremden Endpunkten wird nichts untergeschoben.
LOCAL_LLM_EXTRA_BODY = '{"chat_template_kwargs":{"enable_thinking":false}}'
LOCAL_LLM_TIMEOUT_S = 60
LOCAL_LLM_TEMPERATURE = 0.1
REMOTE_LLM_TIMEOUT_S = 300
LLM_DEFAULT_MAX_TOKENS = 8192
LLM_DEFAULT_MAX_CALLS = 40
LLM_ATTEMPTS = 4
LLM_RETRYABLE_HTTP = (408, 409, 429, 500, 502, 503, 504)
LLM_BACKOFF_BASE_S = (
    2  # Wartezeit nach Versuch n (ab 0): min(LLM_BACKOFF_MAX_S, 2^n * Basis)
)
LLM_BACKOFF_MAX_S = 30
LLM_ERROR_BODY_CHARS = 300


class LLMError(RuntimeError):
    """Fehlgeschlagener LLM-Aufruf; `code` ist der HTTP-Status, falls es einen gab."""

    def __init__(self, msg: str, code: Optional[int] = None) -> None:
        super().__init__(msg)
        self.code = code


class LLMClient:
    """Client für OpenAI-kompatible Chat-Completions. Ohne Konfiguration spricht er die lokale Weinstadt-KI an
    (kein Schlüssel nötig); mit LLM_API_URL / --api-url jeden anderen Endpunkt (OpenRouter, OpenAI, LiteLLM, vLLM).
    Aufrufbudget (LLM_MAX_CALLS) und Circuit-Breaker: Ist der Server weg, wird nicht weiter probiert.
    """

    def __init__(
        self,
        api_url: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: Optional[float] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        max_calls: Optional[int] = None,
    ) -> None:
        env = os.environ
        self.api_url = api_url or env.get("LLM_API_URL") or LOCAL_LLM_URL
        self.local_default = self.api_url == LOCAL_LLM_URL
        self.api_key = (
            api_key
            or env.get("LLM_API_KEY")
            or env.get("OPENROUTER_API_KEY")
            or env.get("OPENAI_API_KEY")
        )
        default_timeout = (
            LOCAL_LLM_TIMEOUT_S if self.local_default else REMOTE_LLM_TIMEOUT_S
        )
        self.timeout = float(timeout or env.get("LLM_TIMEOUT") or default_timeout)
        self.max_tokens = int(
            max_tokens or env.get("LLM_MAX_TOKENS") or LLM_DEFAULT_MAX_TOKENS
        )
        self.max_calls = int(
            max_calls
            if max_calls is not None
            else env.get("LLM_MAX_CALLS") or LLM_DEFAULT_MAX_CALLS
        )
        temp = temperature if temperature is not None else env.get("LLM_TEMPERATURE")
        default_temperature = LOCAL_LLM_TEMPERATURE if self.local_default else None
        self.temperature = (
            float(temp) if temp not in (None, "") else default_temperature
        )
        default_extra_body = LOCAL_LLM_EXTRA_BODY if self.local_default else "{}"
        self.extra_body = json.loads(env.get("LLM_EXTRA_BODY") or default_extra_body)
        self.extra_headers = json.loads(env.get("LLM_EXTRA_HEADERS", "{}"))
        self.calls = 0
        self.dead = False

    def default_models(self) -> List[str]:
        """Modelle aus LLM_MODEL (kommagetrennt); ohne Angabe das lokale Standardmodell (nur am lokalen Endpunkt)."""
        env = [m for m in os.environ.get("LLM_MODEL", "").split(",") if m.strip()]
        return env or ([LOCAL_LLM_MODEL] if self.local_default else [])

    def reachable(self, timeout: float = 3.0) -> bool:
        """Kurzer TCP-Test, damit ein nicht erreichbarer Server nicht erst nach dem vollen Timeout auffällt."""
        u = urllib.parse.urlparse(self.api_url)
        port = u.port or (443 if u.scheme == "https" else 80)
        try:
            with socket.create_connection((u.hostname, port), timeout=timeout):
                return True
        except OSError:
            self.dead = True
            return False

    def exhausted(self) -> bool:
        """Kein weiterer Aufruf möglich: Server weg oder Aufrufbudget verbraucht."""
        return self.dead or self.calls >= self.max_calls

    def _request_body(
        self, model: str, messages: List[ChatMessage], tools: Optional[List[ToolSchema]]
    ) -> Dict[str, Any]:
        body: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "max_tokens": self.max_tokens,
        }
        if tools:
            body["tools"], body["tool_choice"] = tools, "auto"
        if self.temperature is not None:
            body["temperature"] = self.temperature
        if isinstance(self.extra_body, dict):
            body.update(self.extra_body)
        return body

    def _request_headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json", **self.extra_headers}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def chat(
        self,
        model: str,
        messages: List[ChatMessage],
        tools: Optional[List[ToolSchema]] = None,
    ) -> ChatMessage:
        """Ein Chat-Completion-Aufruf; liefert die Antwortnachricht des Modells.

        Vorübergehende Fehler (Timeout, unlesbare Antwort, LLM_RETRYABLE_HTTP) werden mit wachsender Wartezeit
        wiederholt. Ein Verbindungsfehler schaltet den Client dauerhaft ab (`dead`). Jeder Aufruf zählt gegen das
        Budget, unabhängig von der Zahl der Versuche."""
        if self.dead:
            raise LLMError("LLM-Endpunkt nicht erreichbar")
        if self.calls >= self.max_calls:
            raise LLMError(f"LLM-Budget erschöpft (LLM_MAX_CALLS={self.max_calls})")
        self.calls += 1
        body = self._request_body(model, messages, tools)
        headers = self._request_headers()
        last, code = "", None
        for attempt in range(LLM_ATTEMPTS):
            req = urllib.request.Request(
                self.api_url, data=json.dumps(body).encode("utf-8"), headers=headers
            )
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                if not data.get("choices"):
                    raise LLMError(
                        f"Antwort ohne 'choices': {json.dumps(data)[:LLM_ERROR_BODY_CHARS]}"
                    )
                return data["choices"][0]["message"]
            except urllib.error.HTTPError as e:
                last = f"HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:LLM_ERROR_BODY_CHARS]}"
                code = e.code
                if e.code not in LLM_RETRYABLE_HTTP:
                    break
            except urllib.error.URLError as e:
                self.dead = True
                raise LLMError(f"LLM-Endpunkt nicht erreichbar: {e.reason}")
            except (TimeoutError, json.JSONDecodeError) as e:
                last = f"{type(e).__name__}: {e}"
            time.sleep(min(LLM_BACKOFF_MAX_S, 2**attempt * LLM_BACKOFF_BASE_S))
        raise LLMError(f"LLM-Aufruf fehlgeschlagen ({model}): {last}", code)


# ---- Tool-Calling-Agent ----

AGENT_PLAYBOOK_MAX_CHARS = 30000
AGENT_NOTEBOOK_ENTRIES = 30  # so viele Notizen und ...
AGENT_AUDIT_ENTRIES = 8  # ... so viele Audit-Einträge bekommt ein Modell zum Start
AGENT_TOOL_RESULT_MAX_CHARS = 9000
AGENT_REJECTION_LOG_CHARS = 110
AGENT_NUDGE = "Arbeite mit den Tools weiter oder rufe finish auf."
TOOLS_UNSUPPORTED_HTTP = (
    400,
    404,
    422,
    501,
)  # so lehnen Server den 'tools'-Parameter ab
HISTORY_KEEP_HEAD = 2  # System-Prompt und Auftrag werden nie gekürzt
HISTORY_KEEP_TAIL = 6  # die jüngsten Nachrichten ebenfalls nicht
HISTORY_TRIM_MIN_CHARS = 200  # kürzere Tool-Ergebnisse lohnen das Kürzen nicht
HISTORY_PLACEHOLDER = '{"hinweis": "älteres Tool-Ergebnis gekürzt"}'
HISTORY_PLACEHOLDER_COST = (
    40  # angesetzte Länge des Platzhalters in der Größenschätzung
)


def _trim_history(messages: List[ChatMessage], budget_chars: int) -> None:
    """Ersetzt alte Tool-Ergebnisse durch Platzhalter, wenn der Verlauf zu lang wird (Struktur bleibt gültig)."""
    size = sum(len(json.dumps(m, ensure_ascii=False)) for m in messages)
    for m in messages[HISTORY_KEEP_HEAD:-HISTORY_KEEP_TAIL]:
        if size <= budget_chars:
            return
        if (
            m.get("role") == "tool"
            and len(m.get("content") or "") > HISTORY_TRIM_MIN_CHARS
        ):
            size -= len(m["content"]) - HISTORY_PLACEHOLDER_COST
            m["content"] = HISTORY_PLACEHOLDER


def _agent_system_prompt(playbook: str) -> str:
    """System-Prompt des Agenten, auf Wunsch um das (gekürzte) Recherche-Playbook ergänzt."""
    if not playbook:
        return AGENT_SYSTEM
    return (
        AGENT_SYSTEM + "\n\nPLAYBOOK AUS DER RECHERCHE (Hypothesen, nicht geprüft):\n"
        f"{playbook[:AGENT_PLAYBOOK_MAX_CHARS]}"
    )


def _agent_opening_messages(wb: Workbench, system: str) -> List[ChatMessage]:
    """Frischer Verlauf für ein Modell: System-Prompt plus Auftrag mit Stand, Notizbuch und letzten Audit-Einträgen."""
    brief = {
        "auftrag": "Senke den Score. Beginne mit overview.",
        "stand": wb.s.score(wb.s.ops, wb.s.sig),
        "notizbuch": wb.notes[-AGENT_NOTEBOOK_ENTRIES:],
        "letzte_audit_einträge": wb.s.audit[-AGENT_AUDIT_ENTRIES:],
    }
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": json.dumps(brief, ensure_ascii=False)},
    ]


def _answer_tool_call(
    wb: Workbench, tool_call: Dict[str, Any]
) -> Tuple[str, ChatMessage]:
    """Führt einen Tool-Aufruf des Modells aus. Rückgabe: (Kurztext fürs Protokoll, Tool-Nachricht für den Verlauf).
    Zu lange Ergebnisse werden abgeschnitten, damit ein einzelnes Tool den Kontext nicht sprengt.
    """
    fn = tool_call.get("function", {})
    try:
        raw_args = fn.get("arguments") or "{}"
        args = raw_args if isinstance(raw_args, dict) else json.loads(raw_args)
        if not isinstance(args, dict):
            raise ValueError("Argumente müssen ein JSON-Objekt sein")
        result = wb.dispatch(str(fn.get("name", "")), args)
    except (json.JSONDecodeError, ValueError, TypeError) as e:
        result = {"fehler": f"Argumente nicht lesbar: {e}"}
    text = json.dumps(result, ensure_ascii=False)
    if len(text) > AGENT_TOOL_RESULT_MAX_CHARS:
        text = text[:AGENT_TOOL_RESULT_MAX_CHARS] + ' ...[gekürzt]"}'
    label = fn.get("name", "?")
    if label == "propose_rewrite":
        if result.get("accepted"):
            label += " -> angenommen"
        else:
            label += (
                " -> abgelehnt: "
                + str(result.get("reason"))[:AGENT_REJECTION_LOG_CHARS]
            )
    return label, {
        "role": "tool",
        "tool_call_id": tool_call.get("id", ""),
        "content": text,
    }


def _agent_session(
    wb: Workbench,
    client: LLMClient,
    model: str,
    messages: List[ChatMessage],
    steps: int,
    log: Callable[[str], None],
    history_chars: int,
) -> bool:
    """Eine Sitzung eines Modells: bis zu `steps` Antworten, jede mit beliebig vielen Tool-Aufrufen.

    Rückgabe False, wenn das Modell kein Tool-Calling beherrscht: Der Server lehnt den 'tools'-Parameter gleich beim
    ersten Aufruf ab, oder das Modell antwortet beim ersten Schritt in Prosa. Spätere Fehler beenden nur die Sitzung.
    """
    for stepno in range(steps):
        try:
            msg = client.chat(model, messages, TOOLS)
        except LLMError as e:
            log(f"  {e}")
            return not (stepno == 0 and e.code in TOOLS_UNSUPPORTED_HTTP)
        msg.setdefault("role", "assistant")
        messages.append(msg)
        calls = msg.get("tool_calls") or []
        if not calls:
            if stepno == 0:
                return False
            if wb.finished:
                return True
            messages.append({"role": "user", "content": AGENT_NUDGE})
            continue
        for tool_call in calls:
            label, tool_message = _answer_tool_call(wb, tool_call)
            messages.append(tool_message)
            log(f"  [{stepno + 1:02d}] {label}")
        if wb.finished:
            return True
        _trim_history(messages, history_chars)
    return True


def run_agent(
    wb: Workbench,
    client: LLMClient,
    models: Sequence[str],
    steps: int,
    relay_rounds: int,
    playbook: str = "",
    log: Callable[[str], None] = print,
    history_chars: int = 400_000,
) -> List[str]:
    """Staffellauf: jedes Modell bekommt eine frische Sitzung auf dem aktuellen Stand plus das gemeinsame Notizbuch.
    Was ein Modell verifiziert einbringt, bleibt; die nächsten bauen darauf auf.
    Rückgabe: Modelle, die kein Tool-Calling beherrschen (für sie gibt es den JSON-Modus).
    """
    no_tools: List[str] = []
    system = _agent_system_prompt(playbook)
    for rnd in range(relay_rounds):
        for model in models:
            if model in no_tools or client.exhausted():
                continue
            wb.finished = None
            start_accept = wb.accepted
            messages = _agent_opening_messages(wb, system)
            log(f"\n--- Agent {model} (Runde {rnd + 1}/{relay_rounds}) ---")
            if _agent_session(wb, client, model, messages, steps, log, history_chars):
                log(
                    f"  {model}: {wb.accepted - start_accept} verifizierte Rewrites"
                    + (f" | {wb.finished}" if wb.finished else "")
                )
            else:
                no_tools.append(model)
                log(f"  {model}: kein Tool-Calling verfügbar -> JSON-Modus")
    return no_tools


# ---- JSON-Modus (Modelle ohne Tool-Calling) ----

JSON_OPS = ("X", "CX", "CCX", "SWAP", "CSWAP", "Z", "CZ", "CCZ", "Z_POW")
JSON_HOTSPOT_LIMIT = 50
JSON_FACTS_MAX = 30
JSON_ATTEMPTS = 2  # erste Antwort plus genau eine Nachbesserung
JSON_RATIONALE = "LLM im JSON-Modus"
JSON_PROMPT = """Du bist ein Quanten-Compiler-Agent für das kickmix-Format (.kmx).
KOSTEN: Nur CCX, CCZ, CSWAP (je 1 Toffoli) und Z_POW mit feinem Winkel (je ca. {rot:.1f} Toffoli) kosten etwas.
X, CX, SWAP, Z, CZ und Clifford-Z_POW sind kostenlos.
AUFGABE: Ersetze den Block durch einen mit WENIGER CCX/CCZ/CSWAP, der auf allen gültigen Eingaben dasselbe bewirkt.
REGELN:
 1. Nur X, CX, CCX, SWAP, CSWAP, Z, CZ, CCZ, Z_POW. Keine "if"-Bedingungen, kein HMR/R/BIT_*/PUSH/POP, keine neuen \
Qubits.
 2. Die FAKTEN gelten am Blockeingang für jede gültige Eingabe; nutze sie aus. Beispiele: Sind zwei Kontrollen nie
    gleichzeitig 1, entfällt das CCX. Gilt qC = qA & qB, dann ist "CCX qA qB qT" dasselbe wie "CX qC qT".
    Zwei CCX mit gleicher Kontrolle und gleichem Ziel: CCX a b t + CCX a c t = CX b c; CCX a c t; CX b c.
 3. Antworte NUR mit einem JSON-Array der neuen .kmx-Zeilen. Kannst du die Kosten nicht senken, antworte mit [].
FAKTEN:
{facts}
BLOCK:
{block}"""


def _json_array(text: str) -> Optional[List[str]]:
    """Holt ein JSON-Array aus einer Modellantwort (auch wenn Prosa oder Code-Zäune drumherum stehen)."""
    for chunk in [text.strip()] + re.findall(r"\[[^\[\]]*\]", text, re.DOTALL):
        try:
            val = json.loads(chunk)
        except json.JSONDecodeError:
            continue
        if isinstance(val, list) and all(isinstance(x, str) for x in val):
            return [x.strip() for x in val if x.strip()]
    return None


def json_windows(wb: Workbench, max_span: int = 60) -> List[WindowSpan]:
    """Kandidatenfenster für den JSON-Modus: CCX-Gruppen auf einem Ziel und gleiche CCX-Paare, nur unbedingte
    Gatter; absteigend sortiert und überlappungsfrei, damit angenommene Rewrites spätere Indizes nicht verschieben.
    """
    ops = wb.s.ops
    depths = push_depths(ops)
    raw = [
        (h["ccx_indizes"][0], h["ccx_indizes"][0] + h["spanne"] - 1)
        for h in wb.find_hotspots("runs", JSON_HOTSPOT_LIMIT)["liste"]
    ]
    raw += [
        (h["start"], h["ende"])
        for h in wb.find_hotspots("pairs", JSON_HOTSPOT_LIMIT)["liste"]
    ]
    out: List[WindowSpan] = []
    for a, b in sorted(set(raw), reverse=True):
        if b - a > max_span or (out and b >= out[-1][0]):
            continue
        if all(
            ops[i].name in JSON_OPS and ops[i].cond is None and depths[i] == 0
            for i in range(a, b + 1)
        ):
            out.append((a, b))
    return out


def _json_window_prompt(
    wb: Workbench, start: int, end: int, window: Sequence[str]
) -> str:
    """Anfrage für ein Fenster: Kostenmodell, Regeln, Fakten am Fenstereingang und der Block selbst."""
    facts = wb.analyze_window(start, end).get("fakten_am_eingang") or [
        "(keine besonderen)"
    ]
    return JSON_PROMPT.format(
        rot=wb.s.opts.rot_weight,
        facts="\n".join(f"- {f}" for f in facts[:JSON_FACTS_MAX]),
        block="\n".join(window),
    )


def _json_rewrite_window(
    wb: Workbench,
    client: LLMClient,
    model: str,
    start: int,
    end: int,
    window: Sequence[str],
    log: Callable[[str], None],
) -> Optional[bool]:
    """Fragt das Modell nach einem Ersatz für ein Fenster; bei Ablehnung gibt es eine Nachbesserung mit dem
    Gegenbeispiel des Verifiers. True, wenn ein Rewrite angenommen wurde; None bei einem LLM-Fehler.
    """
    messages: List[ChatMessage] = [
        {"role": "user", "content": _json_window_prompt(wb, start, end, window)}
    ]
    for _ in range(JSON_ATTEMPTS):
        try:
            content = client.chat(model, messages).get("content") or ""
        except LLMError as e:
            log(f"  {e}")
            return None  # nicht memoisieren: nächstes Modell darf es erneut versuchen
        cand = _json_array(content)
        if not cand:
            return False
        res = wb.propose_rewrite(start, end, cand, JSON_RATIONALE)
        if res.get("accepted"):
            return True
        messages += [
            {"role": "assistant", "content": content},
            {
                "role": "user",
                "content": f"Abgelehnt: {res.get('reason')} Korrigiere gezielt oder antworte mit [].",
            },
        ]
    return False


def run_json_llm(
    wb: Workbench,
    client: LLMClient,
    model: str,
    log: Callable[[str], None] = print,
    memo: Optional[Dict[Tuple[str, ...], bool]] = None,
) -> int:
    """Ein-Schuss-Modus für Modelle ohne Tool-Calling: je Fenster eine Anfrage mit den Fakten des Fensters,
    bei Ablehnung genau eine Nachbesserung mit dem Gegenbeispiel des Verifiers. Antworten werden memoisiert.
    """
    memo = {} if memo is None else memo
    accepted = 0
    for a, b in json_windows(wb):
        if client.exhausted():
            break
        window = [o.fmt() for o in wb.s.ops[a : b + 1]]
        if tuple(window) in memo:
            continue
        done = _json_rewrite_window(wb, client, model, a, b, window, log)
        if done is None:
            continue
        accepted += done
        memo[tuple(window)] = done
    log(
        f"  {model} (JSON-Modus): {accepted} verifizierte Rewrites, {client.calls} LLM-Aufrufe insgesamt"
    )
    return accepted


def llm_stage(
    s: Session, args: argparse.Namespace, log: Callable[[str], None] = print
) -> None:
    """LLM-Stufe: Tool-Calling-Agent, wo das Modell es kann; sonst JSON-Modus. LLM_MODE=auto|tools|json."""
    mode = os.environ.get("LLM_MODE", "auto").strip().lower() or "auto"
    client = LLMClient(
        args.api_url,
        timeout=args.llm_timeout,
        temperature=args.temperature,
        max_tokens=args.max_tokens,
    )
    models = [
        m.strip() for m in (args.models or "").split(",") if m.strip()
    ] or client.default_models()
    if not models:
        log("LLM-Stufe übersprungen: kein Modell angegeben (--models oder LLM_MODEL).")
        return
    if not os.environ.get("LLM_MAX_CALLS"):
        client.max_calls = max(1, args.steps * len(models) * args.relay)
    if not client.reachable():
        log(f"LLM-Stufe übersprungen: {client.api_url} ist nicht erreichbar.")
        return
    playbook = open(args.playbook, encoding="utf-8").read() if args.playbook else ""
    wb = Workbench(s, exact_only=args.exact_only)
    rest = (
        list(models)
        if mode == "json"
        else run_agent(wb, client, models, args.steps, args.relay, playbook, log)
    )
    if mode != "tools":
        memo: Dict[Tuple[str, ...], bool] = {}
        for model in rest:
            run_json_llm(wb, client, model, log, memo)
    if wb.accepted:
        wb.run_passes()
    res = wb.full_check()
    log(f"  Abschlussprüfung nach der LLM-Stufe: {res['meldung']}")


# =====================================================================
# 8. RESEARCH-BRIEF (BRÜCKE ZU DEEP-RESEARCH-WERKZEUGEN)
# =====================================================================

PROFILE_ROWS_SHOWN = 25  # Zeilen des Toffoli-Profils im Research-Brief und in `info`

BRIEF_TITLE_LINES = (
    "# Research-Auftrag: kickmix-Schaltkreis weiter verkleinern",
    "",
    "## Aufgabe und Bewertung",
    "Wettbewerb: Google Quantum AI - Verifiable Quantum Circuit Compilation (Kaggle), Paper arXiv:2610.23832.",
    "Score S = Q x (Toffoli + T/4), kleiner ist besser. Q = größter Qubit-Index + 1. Toffoli = CCX/CCZ/CSWAP im Mittel "
    "pro Shot (klassisch bedingte Gatter zählen nur bei Ausführung). CX, CZ, X, Z, SWAP, HMR sind frei. "
    "Feine Z_POW-Rotationen kosten 0.56*log2(1/eps)+5.3 T.",
)
BRIEF_PROFILE_HEADER_LINES = (
    "",
    "## Wo die Kosten liegen",
    "| Abschnitt | Toffoli | Instruktionen | Indexbereich |",
    "|---|---:|---:|---|",
)
BRIEF_CLOSING_LINES = (
    "",
    "## Bereits automatisch erledigt",
    "Kommutierende Auslöschung; Entfernen nie feuernder oder linear ausdrückbarer Toffolis auf der ganzen Domäne; "
    "Zusammenfassen von Toffoli-Gruppen mit Rang <= 1; Measurement-Based Uncomputation für reversible "
    "Uncompute-Ketten; "
    "optimale Drahtzuteilung bei fester Gatterreihenfolge.",
    "",
    "## Fragen an die Recherche",
    "1. Welche Konstruktionen senken die Toffoli-Zahl der teuersten Abschnitte oben strukturell (Addierer, "
    "Multiplizierer, "
    "Quadrierer, Tabellen-Lookup/QROM, Vergleicher, Schiebenetze)? Bitte mit Toffoli- und Ancilla-Formeln.",
    "2. Welche Tricks nutzen die Mittelwert-Bewertung aus (klassisch bedingte Arbeit, datenabhängiges Überspringen)?",
    "3. Wie lässt sich die Scratch-Spitze senken (Pebbling, Compute/Uncompute-Reihenfolge, Wiederverwendung über HMR)?",
    "4. Welche Genauigkeits- und Trunkierungsreserven sind bei dieser Aufgabe üblich, und wie prüft man sie exakt?",
    "5. Welche öffentlichen Lösungen oder Notebooks zu diesem Wettbewerb beschreiben konkrete Architekturen und "
    "Zahlen?",
    "",
    "## Gewünschtes Ergebnisformat (Playbook)",
    "Liste von Hypothesen. Je Hypothese: Idee in einem Satz; erwarteter Gewinn in Toffoli oder Qubits; betroffener "
    "Abschnitt; "
    "Rezept in kickmix-Instruktionen (X, CX, CCX, CSWAP, Z, CZ, CCZ, HMR, R, if bN); woran man erkennt, dass es nicht "
    "passt; Quelle.",
    "Speichere das Ergebnis als Textdatei und gib es dem Agenten mit --playbook mit.",
)


def peak_scratch_usage(session: Session) -> int:
    """Größte Zahl gleichzeitig lebender Scratch-Qubits (Sweep über Start- und Endereignisse der Lebensdauern).
    Bei gleichem Index sortiert das Ende (-1) vor dem Start (+1): ein frei gewordenes Qubit zählt nicht doppelt.
    """
    touches = trace_touches(session.ops, session.layout, session.smp)
    lifetimes, _ = lifetimes_of(session.ops, touches)
    events = sorted(
        [(start, 1) for start, _, _, _ in lifetimes]
        + [(end + 1, -1) for _, end, _, _ in lifetimes]
    )
    live = peak = 0
    for _, delta in events:
        live += delta
        peak = max(peak, live)
    return peak


def brief_status_lines(session: Session, peak_scratch: int) -> List[str]:
    """Register/Domäne und der aktuelle Stand (Schätzung, exakter Score falls verfügbar, Scratch-Spitze)."""
    layout = session.layout
    register_sizes = {
        layout.names.get(r, f"r{r}"): len(qubits)
        for r, qubits in layout.registers.items()
    }
    estimate = session.score(session.ops, session.sig)
    exact = session.exact(session.ops)
    return [
        f"Register: {register_sizes}; Domäne: {session.dom.label}.",
        "",
        "## Aktueller Stand",
        estimate,
        *(
            [f"Exakt wie der offizielle Verifier: {exact.line()}"]
            if exact is not None
            else []
        ),
        f"Scratch-Spitze (gleichzeitig belegte Hilfsqubits): {peak_scratch}; Register-Qubits: {len(layout.pinned)}.",
    ]


def brief_profile_rows(profile: Sequence[Dict[str, Any]]) -> List[str]:
    """Markdown-Tabellenzeilen des Toffoli-Profils (teuerste Abschnitte zuerst)."""
    return [
        f"| {r['segment']} | {r['toffoli']} | {r['instruktionen']} | {r['von']}..{r['bis']} |"
        for r in profile
    ]


def research_brief(session: Session) -> str:
    """Erzeugt den Markdown-Auftrag für ein Deep-Research-Werkzeug: Aufgabe, aktueller Stand, Kostenprofil,
    bereits Erledigtes, offene Fragen und das gewünschte Playbook-Format."""
    profile = profile_segments(session.ops, PROFILE_ROWS_SHOWN)
    peak_scratch = peak_scratch_usage(session)
    lines = [
        *BRIEF_TITLE_LINES,
        *brief_status_lines(session, peak_scratch),
        *BRIEF_PROFILE_HEADER_LINES,
        *brief_profile_rows(profile),
        *BRIEF_CLOSING_LINES,
    ]
    return "\n".join(lines) + "\n"


# =====================================================================
# 9. GEGENPRÜFUNG MIT DER OFFIZIELLEN KICKMIX-BIBLIOTHEK (OPTIONAL)
# =====================================================================

KICKMIX_SAMPLE_SEED = 7

KickmixRun = Tuple[
    Any, Dict[int, int], List[Any]
]  # (Circuit, Qubit -> Wert über alle Shots, Phase je Shot)


def kickmix_simulate(ops: Sequence[Op], dom: Domain) -> KickmixRun:
    """Lässt `ops` im offiziellen Simulator laufen, ein Shot je Lane der Domäne `dom`."""
    circ = _km.Circuit(format_ops(ops))
    sim = _km.Simulator(batch_size=dom.n, debug_print=False)
    for q, v in dom.init_q.items():
        sim.write_across_shots(_km.q(q), v)
    sim.do(circ)
    qvals = {
        q: sim.read_across_shots(_km.q(q), out=int) for q in range(circ.num_qubits)
    }
    phases = [sim.read_shot_phase(i) for i in range(dom.n)]
    return circ, qvals, phases


def kickmix_crosscheck_problems(
    reference: KickmixRun,
    candidate: KickmixRun,
    metrics: Metrics,
    layout: Layout,
    same_phase: bool,
) -> List[str]:
    """Vergleicht zwei kickmix-Läufe: eigene Kennzahlen gegen kickmix, Registerinhalt, Scratch und (nur wenn
    `same_phase`) die Phase je Shot modulo einer vollen Umdrehung."""
    _, q0, p0 = reference
    c1, q1, p1 = candidate
    problems = []
    if (
        c1.num_qubits != metrics.num_qubits
        or c1.operation_statistics().num_toffoli_like != metrics.toffoli
    ):
        problems.append("Kennzahlen weichen von kickmix ab")
    if any(q0.get(q, 0) != q1.get(q, 0) for q in layout.pinned):
        problems.append("Registerinhalt weicht ab")
    if any(v for q, v in q1.items() if q not in layout.pinned):
        problems.append("Scratch nicht sauber")
    bad = sum(1 for a, b in zip(p0, p1) if (a - b) % 2 != 0) if same_phase else 0
    if bad:
        problems.append(f"Phase weicht in {bad} Shots ab")
    return problems


def kickmix_crosscheck(
    orig: Sequence[Op],
    new: Sequence[Op],
    layout: Layout,
    shots: int = 4096,
    full: Optional[Domain] = None,
    same_phase: bool = True,
) -> str:
    """Unabhängige Kontrolle mit dem offiziellen Simulator: parst die Ausgabe, vergleicht Kennzahlen und prüft auf
    einer Stichprobe Registerinhalt, saubere Scratch-Qubits und die exakte Phase je Shot.
    """
    if _km is None:
        return "kickmix nicht installiert (pip install kickmix) - Gegenprüfung übersprungen"
    dom = (
        full if full is not None else sample_domain(layout, shots, KICKMIX_SAMPLE_SEED)
    )
    reference = kickmix_simulate(orig, dom)
    candidate = kickmix_simulate(new, dom)
    metrics = compute_metrics(new)
    problems = kickmix_crosscheck_problems(
        reference, candidate, metrics, layout, same_phase
    )
    if problems:
        return "kickmix-Gegenprüfung FEHLGESCHLAGEN: " + "; ".join(problems)
    return (
        f"kickmix-Gegenprüfung bestanden: Ausgabe geparst, Q={candidate[0].num_qubits}, Toffoli={metrics.toffoli}, "
        f"{dom.n:,} Shots ({dom.label}) mit identischem Register, sauberem Scratch"
        + (
            " und exakt gleicher Phase"
            if same_phase
            else " (Phase bewusst verändert, siehe Toleranzprüfung)"
        )
    )


# =====================================================================
# 10. KOMMANDOZEILE
# =====================================================================

CLI_EXIT_OK = 0
CLI_EXIT_ERROR = 1  # Datei fehlt, Formatfehler oder Selbsttest fehlgeschlagen
CLI_EXIT_REJECTED = 2  # Prüfung fehlgeschlagen oder Kosten gestiegen
CLI_EXIT_OFFICIAL_GATE = 3  # offizieller Verifier fehlt oder lehnt ab

KMB_SUFFIX = ".kmb"
KMB_NEEDS_KICKMIX = (
    "Das Binärformat .kmb braucht die kickmix-Bibliothek (pip install kickmix)."
)
COST_INCREASE_SLACK = 1e-12  # relative Rundungsreserve beim Vergleich nachher > vorher
OFFICIAL_VERIFY_DEFAULT_TIMEOUT = "3600"
OFFICIAL_VERIFY_OUTPUT_TAIL = (
    4000  # so viele Zeichen der Verifier-Ausgabe werden höchstens gezeigt
)
DIFF_CONTEXT_LINES = 2

RESEARCH_LLM_TIMEOUT = 900
RESEARCH_SYSTEM_PROMPT = (
    "Du bist Rechercheur für Quantenschaltkreis-Synthese. Belege Aussagen mit Quellen und "
    "trenne Gesichertes von Vermutungen."
)

CLI_COMMANDS = frozenset(
    {
        "optimize",
        "agent",
        "research",
        "check",
        "info",
        "selftest",
        "legacy",
        "-h",
        "--help",
    }
)
LEGACY_DEFAULT_ARGV = (
    "legacy",
    "invsqrt.kmx",
    "invsqrt_optimized.kmx",
    "invsqrt_optimization.diff",
)


def _require_kickmix_for_kmb() -> None:
    if _km is None:
        raise KmxError(KMB_NEEDS_KICKMIX)


def read_circuit(path: str) -> List[Op]:
    """Liest einen Schaltkreis: .kmx als Text, .kmb über die kickmix-Bibliothek."""
    if path.lower().endswith(KMB_SUFFIX):
        _require_kickmix_for_kmb()
        return parse_text(str(_km.Circuit.from_file(path, format="kmb")))
    with open(path, "r", encoding="utf-8") as f:
        return parse_text(f.read())


def write_circuit(path: str, ops: Sequence[Op]) -> None:
    """Schreibt einen Schaltkreis: .kmx als Text, .kmb über die kickmix-Bibliothek."""
    if path.lower().endswith(KMB_SUFFIX):
        _require_kickmix_for_kmb()
        _km.Circuit(format_ops(ops)).to_file(path, format="kmb")
        return
    with open(path, "w", encoding="utf-8") as f:
        f.write(format_ops(ops))


def options_from_args(args: argparse.Namespace) -> Options:
    """Übersetzt die Kommandozeile (und die gleichwertigen Umgebungsvariablen) in die Pass-Optionen."""
    return Options(
        deep=not args.no_deep,
        mbu=not args.no_mbu,
        repack=not args.no_repack,
        iters=args.iters,
        final_rounds=args.rounds,
        budget_s=args.budget,
        rot_weight=args.rot_weight,
        sampled_facts=args.allow_sampled_facts
        or os.environ.get("ALLOW_PROBABILISTIC_REWRITES") == "1",
        trim=args.trim_rotations or os.environ.get("TRIM_ROTATIONS") == "1",
        trim_max_ratio=args.trim_max_ratio,
    )


def load_session(path: str, args: argparse.Namespace) -> Session:
    """Liest die Eingabedatei, bestimmt Layout und Domänen und baut daraus die Sitzung."""
    ops = read_circuit(path)
    layout = analyze_layout(ops, args.input_register, args.range)
    for note in layout.notes:
        print("Hinweis:", note)
    dom, smp = build_domains(
        layout, args.max_exhaustive, args.sample_lanes, args.fallback_lanes
    )
    return Session(ops, layout, dom, smp, options_from_args(args))


def _unlink_if_present(path: str) -> None:
    try:
        os.unlink(path)
    except OSError:
        pass


def _apply_default_mode(path: str) -> None:
    """mkstemp erzeugt Dateien mit 0600; Ausgaben sollen wie mit open() angelegt lesbar sein (0666 & ~umask)."""
    umask = os.umask(0)
    os.umask(umask)
    os.chmod(path, 0o666 & ~umask)


def _atomic_write_text(path: str, text: str) -> None:
    """Schreibt `text` erst in eine Temporärdatei im Zielverzeichnis und ersetzt das Ziel dann atomar."""
    directory = os.path.dirname(os.path.abspath(path)) or "."
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".kmx-write-", dir=directory, text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        _apply_default_mode(tmp)
        os.replace(tmp, path)
    except BaseException:
        _unlink_if_present(tmp)
        raise


def official_verifier_shell_command(command: str, candidate_path: str) -> str:
    """Setzt den (shell-sicher zitierten) Kandidatenpfad für {candidate}/{out} ein; ohne Platzhalter wird er
    angehängt."""
    arg = shlex.quote(candidate_path)
    if "{candidate}" in command or "{out}" in command:
        return command.replace("{candidate}", arg).replace("{out}", arg)
    return f"{command} {arg}"


def run_official_verifier(command: str, candidate_path: str) -> Tuple[bool, str]:
    """Führt den konfigurierten offiziellen Verifier auf der Kandidatendatei aus. {candidate} oder {out} wird durch
    den Pfad ersetzt; ohne Platzhalter wird er angehängt. Der Befehl stammt aus deiner Konfiguration.
    """
    cmd = official_verifier_shell_command(command, candidate_path)
    try:
        proc = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=int(
                os.environ.get(
                    "OFFICIAL_VERIFY_TIMEOUT", OFFICIAL_VERIFY_DEFAULT_TIMEOUT
                )
            ),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, f"Verifier-Ausführung fehlgeschlagen: {exc}"
    out = (proc.stdout + proc.stderr).strip()[-OFFICIAL_VERIFY_OUTPUT_TAIL:]
    return proc.returncode == 0, out or f"Exit-Code {proc.returncode}"


def hint_trimmable_rotations(session: Session) -> None:
    """Ohne --trim-rotations: nur melden, wie viel das Trimmen bringen würde (der Stand bleibt unverändert)."""
    _, st = trim_rotations(
        session.ops, session.layout, session.dom, session.opts.trim_max_ratio
    )
    if st.get("removed"):
        print(
            f"HINWEIS : {st['removed']} feine Rotation(en) liegen unter der Phasenreserve. Mit --trim-rotations "
            f"sinkt der Score um weitere {100 * (1 - st['score_after'] / st['score_before']):.2f} % "
            "(ändert die Phase innerhalb der Toleranz, ist also keine äquivalente Umformung)."
        )


def estimated_costs(session: Session) -> Tuple[float, float]:
    """Geschätzte Kosten (vorher, nachher) aus den Simulationsmittelwerten - Ersatz, wenn kein exakter Score geht."""
    m0, m1 = compute_metrics(session.orig), compute_metrics(session.ops)
    sig0, sig1, rot_weight = session.orig_sig, session.sig, session.opts.rot_weight
    before = score_estimate(
        m0.num_qubits, sig0.tof_mean, sig0.t_mean, sig0.rot_mean, rot_weight
    )
    after = score_estimate(
        m1.num_qubits, sig1.tof_mean, sig1.t_mean, sig1.rot_mean, rot_weight
    )
    return before, after


def report_cost_comparison(
    session: Session, rep_old: Optional[ScoreReport], untrimmed_sig: Optional[FinalSig]
) -> Tuple[float, float]:
    """Druckt VORHER/NACHHER und liefert die Kosten (vorher, nachher): exakt wie der offizielle Verifier, wenn
    beide Berichte vorliegen, sonst geschätzt. `untrimmed_sig` ist die Signatur vor einem etwaigen Trimmen.
    """
    rep_new = session.exact(session.ops)
    print("VORHER : ", session.score(session.orig, session.orig_sig))
    print(
        "NACHHER: ",
        session.score(session.ops, session.sig if session.trimmed else untrimmed_sig),
    )
    if rep_old is None or rep_new is None:
        return estimated_costs(session)
    print("Exakt gerechnet wie der offizielle Verifier:")
    print("  vorher : ", rep_old.line())
    print("  nachher: ", rep_new.line())
    return rep_old.score, rep_new.score


def official_gate_accepts(verify_cmd: str, candidate_path: str) -> bool:
    """Offizielles Gate vor dem Schreiben; ohne konfigurierten Verifier nur ein Hinweis (und Annahme)."""
    if not verify_cmd:
        print(
            "HINWEIS : Nur lokale Prüfung; kein offizieller Gesamtverifier ausgeführt "
            "(OFFICIAL_VERIFY_CMD / --verify-cmd)."
        )
        return True
    good, verifier_msg = run_official_verifier(verify_cmd, candidate_path)
    print(f"OFFIZIELLER VERIFIER: {'PASS' if good else 'FAIL'} | {verifier_msg}")
    if not good:
        print("ABBRUCH : Kandidat nicht übernommen; Ausgabe bleibt unverändert.")
    return good


def replace_output_after_gate(
    ops: Sequence[Op], out_path: str, verify_cmd: str
) -> bool:
    """Kandidat zuerst in eine Temporärdatei; erst nach dem optionalen offiziellen Gate atomar ersetzen.
    Liefert False (und lässt `out_path` unberührt), wenn das Gate ablehnt."""
    out_dir = os.path.dirname(os.path.abspath(out_path)) or "."
    os.makedirs(out_dir, exist_ok=True)
    fd, candidate = tempfile.mkstemp(
        prefix=".kmx-candidate-",
        suffix=os.path.splitext(out_path)[1] or ".kmx",
        dir=out_dir,
    )
    os.close(fd)
    try:
        write_circuit(candidate, ops)
        if not official_gate_accepts(verify_cmd, candidate):
            return False
        _apply_default_mode(candidate)
        os.replace(candidate, out_path)
        candidate = ""
    finally:
        if candidate:
            _unlink_if_present(candidate)
    return True


def write_unified_diff(
    session: Session, in_path: str, out_path: str, diff_path: str
) -> None:
    """Schreibt den Unified-Diff Original -> Ergebnis (kanonisch formatierte Instruktionen) atomar."""
    a, b = [o.fmt() for o in session.orig], [o.fmt() for o in session.ops]
    diff = difflib.unified_diff(
        a, b, fromfile=in_path, tofile=out_path, lineterm="", n=DIFF_CONTEXT_LINES
    )
    _atomic_write_text(diff_path, "\n".join(diff) + "\n")


def write_outputs(
    s: Session,
    in_path: str,
    out_path: str,
    diff_path: Optional[str],
    args: argparse.Namespace,
) -> int:
    """Abschluss: End-to-End-Prüfung, exakter Score, optionales Trimmen, offizielles Gate, atomares Schreiben.
    Exit-Codes: 0 geschrieben, 2 Prüfung fehlgeschlagen oder Kosten gestiegen, 3 offizieller Verifier fehlt/lehnt ab.
    """
    ok, msg = s.final_check()
    print(
        f"\nEnd-to-End-Prüfung gegen das Original: {'BESTANDEN' if ok else 'FEHLGESCHLAGEN'} - {msg}"
    )
    if not ok:
        print(
            "ABBRUCH : Ausgabe wird nicht geschrieben; vorhandene Datei bleibt unverändert."
        )
        return CLI_EXIT_REJECTED
    untrimmed_sig = s.sig
    rep_old = invsqrt_score(s.orig, s.layout, s.dom)
    if s.opts.trim:
        s.trim()
    elif rep_old is not None:
        hint_trimmable_rotations(s)
    before, after = report_cost_comparison(s, rep_old, untrimmed_sig)
    change = 100 * (after / before - 1) if before else 0.0
    print(
        f"Kosten-Delta: {after - before:+,.2f} ({change:+.2f} %)"
        + ("" if after < before else "  -> keine Senkung")
    )
    if after > before * (1 + COST_INCREASE_SLACK):
        print(
            "ABBRUCH : Kandidat erhöht die Kosten; vorhandene Ausgabe bleibt unverändert."
        )
        return CLI_EXIT_REJECTED
    if not args.no_kickmix:
        full = s.dom if (args.kickmix_full and s.dom.exhaustive) else None
        print(
            kickmix_crosscheck(
                s.orig, s.ops, s.layout, full=full, same_phase=s.trimmed is None
            )
        )

    verify_cmd = (args.verify_cmd or os.environ.get("OFFICIAL_VERIFY_CMD", "")).strip()
    if not verify_cmd and os.environ.get("REQUIRE_OFFICIAL_VERIFY", "0") == "1":
        print("ABBRUCH : REQUIRE_OFFICIAL_VERIFY=1, aber OFFICIAL_VERIFY_CMD fehlt.")
        return CLI_EXIT_OFFICIAL_GATE
    if not replace_output_after_gate(s.ops, out_path, verify_cmd):
        return CLI_EXIT_OFFICIAL_GATE
    if diff_path:
        write_unified_diff(s, in_path, out_path, diff_path)
    print(f"Geschrieben: {out_path}" + (f" | Diff: {diff_path}" if diff_path else ""))
    return CLI_EXIT_OK


def cmd_optimize(args: argparse.Namespace) -> int:
    """Unterbefehle optimize/agent/legacy: Pässe bis zum Fixpunkt, optional die LLM-Stufe, dann Gate und Schreiben."""
    s = load_session(args.input, args)
    if os.environ.get("OPT_MODE") or os.environ.get("LEGACY_UNSAFE_PASSES") == "1":
        print(
            "Hinweis: OPT_MODE/BEAM_*/LEGACY_UNSAFE_PASSES werden nicht mehr ausgewertet; "
            "die Pässe laufen bis zum Fixpunkt."
        )
    if s.layout.invsqrt and _np is None:
        print(
            "Hinweis: numpy fehlt - der Score wird nur geschätzt (COST_ROT_WEIGHT), nicht exakt gerechnet."
        )
    print("VORHER : ", compute_metrics(s.ops).summary())
    s.baseline()
    t = time.time()
    s.run_passes()
    print(f"Pässe fertig in {time.time() - t:.1f}s ({s.oracle.runs} Simulationsläufe).")
    # LLM-Stufe: beim Unterbefehl "agent" immer, beim alten Aufruf wie in v3 automatisch (lokaler Endpunkt als
    # Standard).
    if getattr(args, "agent", False) or (
        args.command == "legacy" and os.environ.get("LLM_MAX_CALLS") != "0"
    ):
        llm_stage(s, args)
    out = args.output or re.sub(r"(\.km[xb])?$", "_optimized.kmx", args.input, count=1)
    return write_outputs(s, args.input, out, args.diff, args)


def request_playbook(brief: str, model: str, args: argparse.Namespace) -> str:
    """Schickt den Research-Brief an ein Modell und liefert dessen (ungeprüfte) Antwort als Playbook-Text."""
    client = LLMClient(
        args.api_url,
        timeout=args.llm_timeout or RESEARCH_LLM_TIMEOUT,
        max_tokens=args.max_tokens,
    )
    msg = client.chat(
        model,
        [
            {"role": "system", "content": RESEARCH_SYSTEM_PROMPT},
            {"role": "user", "content": brief},
        ],
    )
    return msg.get("content") or ""


def cmd_research(args: argparse.Namespace) -> int:
    """Unterbefehl research: Research-Brief schreiben und, mit --models, vom ersten Modell ein Playbook holen."""
    s = load_session(args.input, args)
    s.baseline()
    brief = research_brief(s)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(brief)
    print(f"Research-Brief geschrieben: {args.out}")
    if args.models:
        model = args.models.split(",")[0]
        playbook = request_playbook(brief, model, args)
        with open(args.playbook_out, "w", encoding="utf-8") as f:
            f.write(playbook)
        print(
            f"Playbook von {model} gespeichert: {args.playbook_out} "
            "(ungeprüft; der Agent behandelt es als Hypothesen)"
        )
    return CLI_EXIT_OK


def cmd_check(args: argparse.Namespace) -> int:
    """Unterbefehl check: Kandidat End-to-End gegen das Original prüfen. Ist er nicht äquivalent, zählt bei
    invsqrt ersatzweise die eigenständige Kontraktprüfung (Phase innerhalb der Toleranz). Exit 0 oder 2.
    """
    s = load_session(args.input, args)
    s.baseline()
    cand = read_circuit(args.candidate)
    ok, msg, sig = s.oracle.check(cand, range(args.rounds))
    print("ORIGINAL:", s.score(s.orig, s.oracle.orig_sig(0)))
    print("KANDIDAT:", s.score(cand, sig))
    for label, ops in (("ORIGINAL", s.orig), ("KANDIDAT", cand)):
        rep = s.exact(ops)
        if rep is not None:
            print(f"{label} exakt: {rep.line()}")
    print(("ÄQUIVALENT: " if ok else "NICHT ÄQUIVALENT: ") + msg)
    within_tolerance = False
    if not ok and s.layout.invsqrt:
        within_tolerance, tolerance_msg = s.tolerance_check(cand, args.rounds)
        print(
            "Eigenständige Kontraktprüfung des Kandidaten: "
            + ("BESTANDEN - " if within_tolerance else "FEHLGESCHLAGEN - ")
            + tolerance_msg
        )
    if (ok or within_tolerance) and not args.no_kickmix:
        print(kickmix_crosscheck(s.orig, cand, s.layout, same_phase=ok))
    return CLI_EXIT_OK if (ok or within_tolerance) else CLI_EXIT_REJECTED


def cmd_info(args: argparse.Namespace) -> int:
    """Unterbefehl info: Kennzahlen, Score (exakt, falls verfügbar) und Toffoli-Profil der Eingabe."""
    s = load_session(args.input, args)
    s.baseline()
    print(s.score(s.ops, s.sig))
    rep = s.exact(s.ops)
    if rep is not None:
        print("Exakt gerechnet wie der offizielle Verifier:", rep.line())
    for r in profile_segments(s.ops, PROFILE_ROWS_SHOWN):
        print(
            f"  {r['toffoli']:6d} Toffoli  {r['instruktionen']:7d} Instr.  "
            f"idx {r['von']}..{r['bis']}  {r['segment']}"
        )
    return CLI_EXIT_OK


# ---- Selbsttest: jede Prüfung liefert (bestanden, Beschriftung der Ausgabezeile) ----

SelftestOutcome = Tuple[bool, str]

SELFTEST_INPUT_REGISTER = "x"
SELFTEST_RANGE = "0:63"
SELFTEST_MAX_EXHAUSTIVE = 1 << 20
SELFTEST_LANES = 64
SELFTEST_HEAD = (
    "".join(f"APPEND_TO_REGISTER q{i} r0\n" for i in range(6)) + 'REGISTER r0 "x"\n'
)


def _selftest_domains(ops: Sequence[Op]) -> Tuple[Layout, Domain, Domain]:
    layout = analyze_layout(ops, SELFTEST_INPUT_REGISTER, SELFTEST_RANGE)
    dom, smp = build_domains(
        layout, SELFTEST_MAX_EXHAUSTIVE, SELFTEST_LANES, SELFTEST_LANES
    )
    return layout, dom, smp


def _selftest_optimized_session(ops: List[Op], final_rounds: int) -> Session:
    """Stumme Sitzung auf dem 6-Bit-Testregister, Basislauf und alle Pässe bereits ausgeführt."""
    layout, dom, smp = _selftest_domains(ops)
    session = Session(
        ops, layout, dom, smp, Options(final_rounds=final_rounds), log=lambda *_: None
    )
    session.baseline()
    session.run_passes()
    return session


def _selftest_toffoli_target(name: str, body: str, max_toffoli: int) -> SelftestOutcome:
    """Die Pässe müssen `body` End-to-End-geprüft auf höchstens `max_toffoli` Toffolis bringen."""
    ops = parse_text(SELFTEST_HEAD + body)
    session = _selftest_optimized_session(ops, final_rounds=8)
    ok, _ = session.final_check()
    before, after = compute_metrics(ops), compute_metrics(session.ops)
    good = ok and after.toffoli <= max_toffoli
    return good, (
        f"{name}: Toffoli {before.toffoli} -> {after.toffoli} (Ziel <= {max_toffoli}), "
        f"Q {before.num_qubits} -> {after.num_qubits}"
    )


def _selftest_mbu_uncompute() -> SelftestOutcome:
    return _selftest_toffoli_target(
        "MBU: reversibles Uncompute -> HMR + CZ",
        "CCX q0 q1 q8\nCX q8 q7\nCCX q7 q2 q9\nCZ q9 q3\nCCX q7 q2 q9\nCX q8 q7\nCCX q0 q1 q8\n",
        2,
    )


def _selftest_toffoli_group() -> SelftestOutcome:
    return _selftest_toffoli_target(
        "Gruppe: ab ^ ac ^ bc -> 1 Toffoli",
        "CCX q0 q1 q8\nCCX q0 q2 q8\nCCX q1 q2 q8\nCZ q8 q3\nCCX q1 q2 q8\nCCX q0 q2 q8\nCCX q0 q1 q8\n",
        1,
    )


def _selftest_difference_control() -> SelftestOutcome:
    return _selftest_toffoli_target(
        "Differenz-Kontrolle (X/CX zwischen CCX-Paar)",
        "CCX q0 q1 q8\nCX q2 q0\nX q0\nCCX q0 q1 q8\nX q0\nCX q2 q0\nCZ q8 q4\nCCX q2 q1 q8\nCX q1 q8\n",
        1,
    )


def _selftest_commuting_cancellation() -> SelftestOutcome:
    return _selftest_toffoli_target(
        "Auslöschung über kommutierende Gatter",
        "CCX q0 q1 q8\nCX q2 q8\nCX q3 q4\nCCX q0 q1 q8\nCX q2 q8\nCX q3 q4\n",
        0,
    )


def _selftest_uncorrected_hmr() -> SelftestOutcome:
    """Fehlende Phasenkorrektur muss auffallen."""
    bad = parse_text(SELFTEST_HEAD + "CCX q0 q1 q8\nCZ q8 q3\nHMR q8 b0\n")
    layout, dom, _ = _selftest_domains(bad)
    issues = Oracle(bad, layout, dom).self_check()
    return (
        any("Messzufall" in i for i in issues),
        "Negativtest: unkorrigierter HMR-Kickback wird erkannt",
    )


def _selftest_phase_fusion() -> SelftestOutcome:
    """Phasenfusion: syntaktisch (gleiches Qubit) und semantisch (wertgleiche Qubits); Ausgabe muss kickmix-gültig
    sein."""
    merged, _, n_merge = pass_cancel(
        parse_text(
            "Z_POW q0 0.0009765625\nCX q1 q2\nZ_POW q0 0.0009765625\nZ q3\nZ_POW q3 -0.75"
        )
    )
    texts = [o.fmt() for o in merged]
    fused = n_merge == 2 and texts == [
        "Z_POW q0 0.001953125",
        "CX q1 q2",
        "Z_POW q3 0.25",
    ]
    exponents = ((7, 4), (2, 1), (3, 1), (1, 1 << 40))
    formatted = [
        phase_op(0, Fraction(a, b), None) and phase_op(0, Fraction(a, b), None).fmt()
        for a, b in exponents
    ]
    exact_decimals = formatted == [
        "Z_POW q0 -0.25",
        None,
        "Z q0",
        "Z_POW q0 0.0000000000009094947017729282379150390625",
    ]
    if _km is not None:
        _km.Circuit(format_ops(merged))
    return fused and exact_decimals, f"Phasenfusion mit exakter Dezimalausgabe: {texts}"


def _selftest_equal_value_rotations() -> SelftestOutcome:
    ops = parse_text(
        SELFTEST_HEAD + "CX q0 q8\nZ_POW q8 0.125\nZ_POW q0 0.0625\nCX q0 q8\n"
    )
    session = _selftest_optimized_session(ops, final_rounds=4)
    good = (
        session.final_check()[0]
        and compute_metrics(session.ops).rotations == 1
        and compute_metrics(ops).rotations == 2
    )
    return good, "Rotationen auf wertgleichen Qubits werden eine Rotation"


def _selftest_v3_interfaces() -> SelftestOutcome:
    m = compute_metrics(
        ["# q999 nur Kommentar", "CSWAP q3 q61 q2", "CCX q3 q61 q2", "Z_POW q3 0.25"]
    )
    same = BitParallelKMXVerifier.verify_equivalence(["CCX q0 q1 q2"], ["CCX q0 q1 q2"])
    diff = BitParallelKMXVerifier.verify_equivalence(["X q0"], [])
    good = (
        m.num_qubits == 62
        and m.toffoli_cost == 2
        and m.t_like == 1
        and m.ops == 3
        and same.ok
        and same.exact
        and not diff.ok
        and _json_array('Text ```json\n["CX q0 q1"]\n```') == ["CX q0 q1"]
    )
    return (
        good,
        "v3-Schnittstellen (compute_metrics auf Zeilen, BitParallelKMXVerifier, JSON-Antworten)",
    )


def _selftest_exact_window_verifier() -> SelftestOutcome:
    status, msg = check_exact(
        parse_text("CCX q0 q1 q2\nCCX q0 q1 q2\nCX q0 q1"),
        parse_text("CX q0 q1"),
        0,
        set(),
    )
    status_wrong, _ = check_exact(
        parse_text("CCX q0 q1 q2"), parse_text("CX q0 q2"), 0, set()
    )
    # Differenzkegel: 3-Qubit-Umformung zwischen 24 unbeteiligten Qubits (sonst > 20 Variablen); falsche Variante
    # fällt durch
    spectators = [f"CX q{i} q{i + 1}" for i in range(10, 34, 2)] + ["Z_POW q40 0.125"]
    wide = ["CCX q0 q1 q2", *spectators, "X q0", "CCX q0 q1 q2"]
    cone_right = check_exact(
        parse_lines(wide), parse_lines([*spectators, "CX q1 q2", "X q0"]), 0, set()
    )[0]
    cone_wrong = check_exact(
        parse_lines(wide), parse_lines([*spectators, "CX q0 q2", "X q0"]), 0, set()
    )[0]
    global_phase = check_exact(
        parse_lines(["NEG", *spectators]), parse_lines(spectators), 0, set()
    )[0]
    tiny = (
        "Z_POW q0 0." + "0" * 45 + "1"
    )  # unter 2^-128: der Simulator würde auf 0 runden
    off_grid = check_exact(parse_lines([tiny]), [], 0, set())[0]
    good = (
        status == "proved"
        and status_wrong == "refuted"
        and cone_right == "proved"
        and cone_wrong == "refuted"
        and global_phase == "refuted"
        and off_grid == "na"
    )
    return good, f"Exakter Fenster-Verifier: {msg}"


SELFTEST_CHECKS: Tuple[Callable[[], SelftestOutcome], ...] = (
    _selftest_mbu_uncompute,
    _selftest_toffoli_group,
    _selftest_difference_control,
    _selftest_commuting_cancellation,
    _selftest_uncorrected_hmr,
    _selftest_phase_fusion,
    _selftest_equal_value_rotations,
    _selftest_v3_interfaces,
    _selftest_exact_window_verifier,
)


def cmd_selftest(_: argparse.Namespace) -> int:
    """Unterbefehl selftest: führt die eingebauten Prüfungen der Reihe nach aus; Exit 1, sobald eine fehlschlägt."""
    failed = 0
    for check in SELFTEST_CHECKS:
        good, label = check()
        failed += not good
        print(f"{'OK  ' if good else 'FAIL'} {label}")
    return CLI_EXIT_ERROR if failed else CLI_EXIT_OK


# ---- Argumentparser ----


def _add_domain_arguments(common: argparse.ArgumentParser) -> None:
    common.add_argument(
        "--input-register", default="x", help="Name des Eingaberegisters (Standard: x)"
    )
    common.add_argument(
        "--range", default=None, help="gültiger Wertebereich LO:HI des Eingaberegisters"
    )
    common.add_argument(
        "--max-exhaustive",
        type=int,
        default=1 << 23,
        help="bis zu dieser Domänengröße vollständig simulieren",
    )
    common.add_argument(
        "--sample-lanes",
        type=int,
        default=4096,
        help="Lanes der schnellen Stichproben-Domäne",
    )
    common.add_argument(
        "--fallback-lanes",
        type=int,
        default=65536,
        help="Lanes, falls keine vollständige Domäne möglich ist",
    )


def _add_pass_arguments(common: argparse.ArgumentParser) -> None:
    common.add_argument(
        "--rounds", type=int, default=4, help="Messrunden der Abschlussprüfung"
    )
    common.add_argument(
        "--iters", type=int, default=3, help="maximale Durchläufe der Pass-Schleife"
    )
    common.add_argument(
        "--budget",
        type=float,
        default=180.0,
        help="Zeitbudget (s) der Kandidatensuche je Durchlauf",
    )
    common.add_argument(
        "--rot-weight",
        type=float,
        default=ROT_WEIGHT,
        help="Toffoli-Äquivalente je feiner Rotation für die Schnellschätzung (oder COST_ROT_WEIGHT); "
        "für invsqrt wird der Score ohnehin exakt gerechnet",
    )
    common.add_argument(
        "--allow-sampled-facts",
        action="store_true",
        help="faktenbasierte Pässe auch dann, wenn die Domäne nur als Stichprobe simuliert werden kann",
    )
    common.add_argument(
        "--no-deep",
        action="store_true",
        help="ohne Suche über lineare Hüllen / Toffoli-Gruppen",
    )
    common.add_argument(
        "--no-mbu", action="store_true", help="ohne Measurement-Based Uncomputation"
    )
    common.add_argument("--no-repack", action="store_true", help="ohne Qubit-Repacking")


def _add_gate_arguments(common: argparse.ArgumentParser) -> None:
    common.add_argument(
        "--no-kickmix",
        action="store_true",
        help="ohne Gegenprüfung durch die kickmix-Bibliothek",
    )
    common.add_argument(
        "--kickmix-full",
        action="store_true",
        help="Gegenprüfung mit dem offiziellen Simulator auf der GANZEN Domäne statt 4096 Shots "
        "(ca. 1 min)",
    )
    common.add_argument(
        "--verify-cmd",
        default=None,
        help="offizieller Verifier als Gate VOR dem Schreiben (oder OFFICIAL_VERIFY_CMD), "
        "z. B. 'python verifiers/invsqrt/verify_submission_invsqrt.py {out} --max-workers 8'",
    )
    common.add_argument(
        "--trim-rotations",
        action="store_true",
        help="feine Z_POW streichen, wenn der exakte Score sinkt (Phase ändert sich innerhalb der "
        "Toleranz; oder TRIM_ROTATIONS=1)",
    )
    common.add_argument(
        "--trim-max-ratio",
        type=float,
        default=0.95,
        help="beim Trimmen höchstens diesen Anteil der Toleranz ausschöpfen",
    )


def _add_llm_arguments(common: argparse.ArgumentParser) -> None:
    common.add_argument(
        "--exact-only",
        action="store_true",
        default=os.environ.get("EXACT_ONLY") == "1",
        help="LLM-Rewrites nur annehmen, wenn sie über ALLE Belegungen bewiesen sind "
        "(keine Don't-Cares)",
    )
    common.add_argument(
        "--models",
        default=None,
        help="kommagetrennte Modell-IDs (oder LLM_MODEL; Standard lokal: qwen3.8-27b)",
    )
    common.add_argument(
        "--api-url",
        default=None,
        help="OpenAI-kompatibler Endpunkt (oder LLM_API_URL; Standard: lokale Weinstadt-KI)",
    )
    common.add_argument(
        "--steps", type=int, default=40, help="Tool-Schritte je Modell und Runde"
    )
    common.add_argument(
        "--relay", type=int, default=1, help="Staffelrunden über alle Modelle"
    )
    common.add_argument("--temperature", type=float, default=None)
    common.add_argument(
        "--max-tokens",
        type=int,
        default=None,
        help="Antwortlimit je LLM-Aufruf (oder LLM_MAX_TOKENS, Standard 8192)",
    )
    common.add_argument(
        "--llm-timeout",
        type=int,
        default=None,
        help="Timeout je LLM-Aufruf in Sekunden (oder LLM_TIMEOUT)",
    )
    common.add_argument(
        "--playbook",
        default=None,
        help="Textdatei mit Recherche-Ergebnissen für den Agenten",
    )


def build_common_options_parser() -> argparse.ArgumentParser:
    """Elternparser mit den Optionen, die alle dateibezogenen Unterbefehle teilen (Reihenfolge = Hilfetext)."""
    common = argparse.ArgumentParser(add_help=False)
    _add_domain_arguments(common)
    _add_pass_arguments(common)
    _add_gate_arguments(common)
    _add_llm_arguments(common)
    return common


def _add_optimize_subcommands(
    sub: argparse._SubParsersAction, common: argparse.ArgumentParser
) -> None:
    for name, hlp in (
        ("optimize", "deterministische Pässe"),
        ("agent", "Pässe + LLM-Agent"),
    ):
        sp = sub.add_parser(name, parents=[common], help=hlp)
        sp.add_argument("input")
        sp.add_argument("-o", "--output", default=None)
        sp.add_argument("--diff", default=None)
        sp.set_defaults(func=cmd_optimize, agent=(name == "agent"))


def _add_analysis_subcommands(
    sub: argparse._SubParsersAction, common: argparse.ArgumentParser
) -> None:
    sp = sub.add_parser(
        "research",
        parents=[common],
        help="Research-Brief (und optional Playbook) erzeugen",
    )
    sp.add_argument("input")
    sp.add_argument("--out", default="research_brief.md")
    sp.add_argument("--playbook-out", default="playbook.md")
    sp.set_defaults(func=cmd_research)
    sp = sub.add_parser(
        "check", parents=[common], help="zwei Dateien End-to-End vergleichen"
    )
    sp.add_argument("input")
    sp.add_argument("candidate")
    sp.set_defaults(func=cmd_check)
    sp = sub.add_parser("info", parents=[common], help="Kennzahlen und Profil")
    sp.add_argument("input")
    sp.set_defaults(func=cmd_info)
    sp = sub.add_parser("selftest", help="eingebaute Tests")
    sp.set_defaults(func=cmd_selftest)


def _add_legacy_subcommand(
    sub: argparse._SubParsersAction, common: argparse.ArgumentParser
) -> None:
    """Alter v3-Aufruf IN [OUT] [DIFF] mit Positionsargumenten."""
    sp = sub.add_parser("legacy", parents=[common])
    sp.add_argument("input")
    sp.add_argument("output", nargs="?", default=None)
    sp.add_argument("diff", nargs="?", default=None)
    sp.set_defaults(func=cmd_optimize, agent=False)


def build_parser() -> argparse.ArgumentParser:
    """Baut den Argumentparser mit allen Unterbefehlen; jeder setzt seine Funktion als `args.func`."""
    common = build_common_options_parser()
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="command")
    _add_optimize_subcommands(sub, common)
    _add_analysis_subcommands(sub, common)
    _add_legacy_subcommand(sub, common)
    return parser


def normalize_argv(argv: Sequence[str]) -> List[str]:
    """Bildet die v3-Aufrufformen auf Unterbefehle ab: --selftest, kein Argument (Standarddateien) und
    IN [OUT] [DIFF] ohne Unterbefehl."""
    argv = list(argv)
    if argv and argv[0] == "--selftest":
        return ["selftest"]
    if not argv:
        return list(LEGACY_DEFAULT_ARGV)
    if argv[0] not in CLI_COMMANDS:
        return ["legacy"] + argv
    return argv


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Einstiegspunkt: liefert den Exit-Code (1 bei fehlender Eingabedatei oder Formatfehler)."""
    args = build_parser().parse_args(
        normalize_argv(sys.argv[1:] if argv is None else argv)
    )
    for path in (getattr(args, "input", None), getattr(args, "candidate", None)):
        if path and not os.path.exists(path):
            print(f"Datei nicht gefunden: {path}")
            return CLI_EXIT_ERROR
    try:
        return args.func(args)
    except KmxError as e:
        print(f"Formatfehler: {e}")
        return CLI_EXIT_ERROR


if __name__ == "__main__":
    sys.exit(main())
