"""Parser für das kickmix-Textformat (.kmx, Version 2): Instruktion `Op`,
Instruktionstabellen, Parsen und Formatieren.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence

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
# selbstinverse Gatter (zwei gleiche heben sich auf); Z läuft über die Phasenfusion
SELF_INVERSE = ("X", "CX", "CCX", "CZ", "CCZ", "SWAP", "CSWAP", "NEG")
UNITARY_OPS = ("X", "CX", "CCX", "SWAP", "CSWAP", "Z", "CZ", "CCZ", "Z_POW", "NEG")
PHASE_GATES = ("Z", "CZ", "CCZ", "Z_POW")
CONDITION_STACK_OPS = ("PUSH_CONDITION", "POP_CONDITION")
REGISTER_DECLARATIONS = ("REGISTER", "APPEND_TO_REGISTER")
_EXP_RE = re.compile(r"^[-+]?\d+\.\d+$")  # wie kickmix: [-+]?[0-9]+.[0-9]+

QUBIT_PREFIX, BIT_PREFIX, REGISTER_PREFIX = "q", "b", "r"
COMMENT_MARKER = "#"
CONDITION_KEYWORD = "if"

OpKey = tuple[str, tuple[str, ...], int | None]


class KmxError(ValueError):
    """Syntaktisch oder strukturell ungültige kickmix-Eingabe (Meldung nennt
    Fundstelle und Instruktion)."""


def is_id(tok: str, prefix: str) -> bool:
    """Ist `tok` ein Bezeichner der Form <prefix><Dezimalzahl> (q7, b3, r0)?"""
    digits = tok[1:]
    # Nur ASCII-Ziffern, höchstens 7 Stellen: Unicode-Ziffern oder
    # Riesenindizes sind keine Bezeichner.
    return (
        tok[:1] == prefix
        and 0 < len(digits) <= 7
        and digits.isascii()
        and digits.isdigit()
    )


def qubit_token(q: int) -> str:
    """Bezeichner des Qubits `q` im .kmx-Text (q7)."""
    return f"{QUBIT_PREFIX}{q}"


def bit_token(b: int) -> str:
    """Bezeichner des klassischen Bits `b` im .kmx-Text (b3)."""
    return f"{BIT_PREFIX}{b}"


def register_token(r: int) -> str:
    """Bezeichner des Registers `r` im .kmx-Text (r0)."""
    return f"{REGISTER_PREFIX}{r}"


class Op:
    """Eine kickmix-Instruktion. `args` sind die Ziel-Token in Originalreihenfolge.

    `qs` sind die Qubit-Indizes in Argumentreihenfolge, `bit` das erste Bit-Argument
    (sonst None), `cond` das Bit einer `if bN`-Bedingung und `text` ein angehängter
    Quoted-Text samt Anführungszeichen.
    """

    __slots__ = ("name", "args", "cond", "text", "qs", "bit")

    def __init__(
        self,
        name: str,
        args: Sequence[str] = (),
        cond: int | None = None,
        text: str | None = None,
    ) -> None:
        self.name = name
        self.args = tuple(args)
        self.cond = cond
        self.text = text
        self.qs = tuple(int(a[1:]) for a in self.args if is_id(a, QUBIT_PREFIX))
        bits = [int(a[1:]) for a in self.args if is_id(a, BIT_PREFIX)]
        self.bit = bits[0] if bits else None

    def fmt(self) -> str:
        """Die Instruktion als kanonische .kmx-Zeile
        (v2-Schreibweise, ohne Zeilenende)."""
        parts = [self.name, *self.args]
        if self.cond is not None:
            parts += [CONDITION_KEYWORD, bit_token(self.cond)]
        if self.text is not None:
            parts.append(self.text)
        return " ".join(parts)

    __repr__ = fmt

    def renamed(self, qmap: dict[int, int]) -> Op:
        """Dieselbe Instruktion mit umbenannten Qubits; unverändert (dasselbe Objekt),
        wenn `qmap` keins betrifft."""
        if not any(q in qmap for q in self.qs):
            return self
        args = tuple(
            qubit_token(qmap.get(int(a[1:]), int(a[1:])))
            if is_id(a, QUBIT_PREFIX)
            else a
            for a in self.args
        )
        return Op(self.name, args, self.cond, self.text)

    def key(self) -> OpKey:
        """Kanonischer Schlüssel: gleiche Schlüssel = gleiche Operation.

        Argumente, deren Reihenfolge die Wirkung nicht ändert (beide Kontrollen von CCX,
        alle Ziele von CZ/CCZ/SWAP, das Tauschpaar von CSWAP), werden sortiert."""
        args = self.args
        if self.name in ("CZ", "CCZ", "SWAP"):
            args = tuple(sorted(args))
        elif self.name == "CCX":
            args = tuple(sorted(args[:2])) + args[2:]
        elif self.name == "CSWAP":
            args = args[:1] + tuple(sorted(args[1:]))
        return (self.name, args, self.cond)


def _gate_shape_error(op: Op) -> str | None:
    arity = GATE_ARITY[op.name]
    if len(op.args) != arity or len(op.qs) != arity:
        return f"{op.name} erwartet {arity} Qubit(s)"
    if len(set(op.qs)) != len(op.qs):
        return "dasselbe Qubit kommt mehrfach vor"
    return None


def _hmr_shape_error(op: Op) -> str | None:
    args = op.args
    if (
        len(args) != 2
        or not is_id(args[0], QUBIT_PREFIX)
        or not is_id(args[1], BIT_PREFIX)
    ):
        return "HMR erwartet 'HMR qN bN'"
    return None


def _zpow_shape_error(op: Op) -> str | None:
    args = op.args
    if len(args) != 2 or not is_id(args[0], QUBIT_PREFIX) or not _EXP_RE.match(args[1]):
        return "Z_POW erwartet 'Z_POW qN <dezimaler Exponent>'"
    return None


def _neg_shape_error(op: Op) -> str | None:
    return "NEG hat keine Ziele" if op.args else None


def _push_shape_error(op: Op) -> str | None:
    if op.args or op.cond is None:
        return "PUSH_CONDITION erwartet 'PUSH_CONDITION if bN'"
    return None


def _pop_shape_error(op: Op) -> str | None:
    if op.args or op.cond is not None:
        return "POP_CONDITION hat keine Argumente"
    return None


def _bit_op_shape_error(op: Op) -> str | None:
    if len(op.args) != 1 or not is_id(op.args[0], BIT_PREFIX):
        return f"{op.name} erwartet genau ein Bit"
    return None


def _no_shape_error(_: Op) -> str | None:
    return None


# Instruktionsname -> Prüfung von Anzahl und Art der Argumente; Meta-Instruktionen
# werden nicht geprüft, unbekannte Namen fehlen in der Tabelle.
_SHAPE_CHECKS: dict[str, Callable[[Op], str | None]] = {
    **dict.fromkeys(GATE_ARITY, _gate_shape_error),
    "HMR": _hmr_shape_error,
    "Z_POW": _zpow_shape_error,
    "NEG": _neg_shape_error,
    "PUSH_CONDITION": _push_shape_error,
    "POP_CONDITION": _pop_shape_error,
    **dict.fromkeys(BIT_OPS, _bit_op_shape_error),
    **dict.fromkeys(META_OPS, _no_shape_error),
}


def _operand_shape_error(op: Op) -> str | None:
    """Fehlertext, falls Anzahl oder Art der Argumente nicht zur Instruktion passen;
    None, wenn alles stimmt."""
    check = _SHAPE_CHECKS.get(op.name)
    return "unbekannte Instruktion" if check is None else check(op)


def _validate(op: Op, where: str = "") -> None:
    """Wirft KmxError, wenn `op` keine wohlgeformte Instruktion ist.
    Meta-Instruktionen werden nicht geprüft."""
    problem = _operand_shape_error(op)
    if problem is not None:
        raise KmxError(f"{where}{op.fmt()!r}: {problem}")


def _split_trailing_condition(
    tokens: list[str], raw: str, where: str
) -> tuple[int | None, list[str]]:
    """Trennt ein abschließendes `if bN` ab: (Bedingungsbit oder None, übrige Token)."""
    if len(tokens) < 2 or tokens[-2] != CONDITION_KEYWORD:
        return None, tokens
    if not is_id(tokens[-1], BIT_PREFIX):
        raise KmxError(f"{where}{raw!r}: Bedingung muss ein Bit sein")
    return int(tokens[-1][1:]), tokens[:-2]


def parse_line(raw: str, where: str = "") -> Op | None:
    """Parst eine .kmx-Zeile zu einer geprüften Instruktion; None für Leer-
    und reine Kommentarzeilen.

    `where` wird Fehlermeldungen vorangestellt (z. B. "Zeile 12: ")."""
    # Wie kickmix beim Lesen einer Datei: '#' innerhalb des Quoted-Texts ist ein
    # Zeichen, kein Kommentar.
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
        and is_id(rest[0], BIT_PREFIX)
    ):
        # v1-Schreibweise "PUSH_CONDITION bN" tolerieren, v2 ausgeben
        cond, rest = int(rest[0][1:]), []
    op = Op(name, rest, cond, text)
    _validate(op, where)
    return op


def parse_text(text: str) -> list[Op]:
    """Parst einen ganzen .kmx-Text; Fehlermeldungen nennen die
    1-basierte Zeilennummer."""
    ops = []
    for line_no, raw in enumerate(text.splitlines(), 1):
        op = parse_line(raw, f"Zeile {line_no}: ")
        if op is not None:
            ops.append(op)
    return ops


def parse_lines(lines: Sequence[str]) -> list[Op]:
    """Parst eine Liste einzelner Zeilen (z. B. aus einer LLM-Antwort); Fehlermeldungen
    nennen den 0-basierten Index.

    Die Einträge stammen aus nicht vertrauenswürdigem JSON, deshalb wird der
    Typ jedes Eintrags geprüft.
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
    """Serialisiert Instruktionen als .kmx-Text, eine je Zeile, mit
    abschließendem Zeilenumbruch."""
    return "\n".join(o.fmt() for o in ops) + "\n"


def is_plain_xt(op: Op, depth: int) -> bool:
    """X/CX/CCX ohne jede Bedingung (weder `if bN` noch innerhalb eines
    PUSH_CONDITION-Blocks); `depth` ist die Stapeltiefe vor `op`."""
    return op.name in X_TYPE and op.cond is None and depth == 0


def ops_unchanged(new: Sequence[Op], old: Sequence[Op]) -> bool:
    """Sind beide Folgen dieselben Op-Objekte in derselben Reihenfolge (Identität,
    nicht nur Gleichheit)? So erkennen Pässe "nichts geändert" ohne Textvergleich."""
    return len(new) == len(old) and all(a is b for a, b in zip(new, old, strict=True))
