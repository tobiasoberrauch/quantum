"""Kompatibilitätsschnittstelle (alte API-Namen) auf den exakten Fenster-Verifier:
`VerificationResult` und `BitParallelKMXVerifier`.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from typing import Any

from kmx.ops import META_OPS, KmxError, Op, parse_lines
from kmx.verify.window import EXACT_MAX_VARIABLES, ExactStatus, check_exact, exact_keys


@dataclass(frozen=True)
class VerificationResult:
    """Alte API: Ergebnis einer lokalen Fensterprüfung; `exact` nur bei vollständigem
    Beweis."""

    ok: bool
    message: str
    exact: bool = False

    def __iter__(self) -> Iterator[Any]:
        """Erlaubt das alte Entpacken `ok, message = result`."""
        yield self.ok
        yield self.message


class BitParallelKMXVerifier:
    """Alte API auf den exakten Fenster-Verifier (L1). Anders als früher gibt es kein
    Fuzzing als Ersatz: Passt ein Fenster nicht in die Wahrheitstabelle, ist das
    Ergebnis 'nicht bewiesen'.
    """

    EXACT_QUBIT_LIMIT = EXACT_MAX_VARIABLES

    @staticmethod
    def _parse_window(lines: Sequence[str] | None) -> list[Op]:
        """Parst die Textzeilen eines Fensters; Einträge, die keine Zeichenketten
        sind, werden übergangen."""
        return parse_lines([line for line in (lines or []) if isinstance(line, str)])

    @classmethod
    def can_verify_window(cls, lines: Sequence[str] | None) -> tuple[bool, str]:
        """Passt das Fenster (für sich allein) in die Wahrheitstabelle? Rückgabe
        (ja/nein, Begründung)."""
        try:
            ops = cls._parse_window(lines)
        except KmxError as e:
            return False, str(e)
        if any(o.name in META_OPS for o in ops):
            return False, "Metadaten-Instruktion im Fenster"
        num_vars = len(exact_keys(ops, [], 0))
        fits = num_vars <= cls.EXACT_QUBIT_LIMIT
        return fits, (
            "OK" if fits else f"{num_vars} Variablen > {cls.EXACT_QUBIT_LIMIT}"
        )

    @classmethod
    def verify_equivalence(
        cls,
        orig_lines: Sequence[str] | None,
        cand_lines: Sequence[str] | None,
        num_batches: int = 0,
    ) -> VerificationResult:
        """Exakter Äquivalenzbeweis zweier Fenster. `num_batches` gibt es nur noch für
        alte Aufrufer (ohne Wirkung)."""
        try:
            orig_w = cls._parse_window(orig_lines)
            cand_w = cls._parse_window(cand_lines)
        except KmxError as e:
            return VerificationResult(False, f"Fenster ungültig: {e}")
        status, msg = check_exact(orig_w, cand_w, 0, set(), cls.EXACT_QUBIT_LIMIT)
        proved = status == ExactStatus.PROVED
        return VerificationResult(
            proved,
            msg
            if status != ExactStatus.UNDECIDED
            else f"kein exakter Beweis möglich ({msg})",
            proved,
        )
