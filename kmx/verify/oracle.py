"""L3: End-to-End-Prüfer. Vergleicht Original und Kandidat auf der ganzen Domäne
(Register, Scratch, 128-Bit-Phase) über Signaturen des Endzustands.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from kmx.domains import Domain, LaneVector, first_lane
from kmx.layout import Layout
from kmx.ops import Op
from kmx.simulator import State, compile_ops, simulate

DIGEST_BYTES = 16  # Länge der BLAKE2b-Fingerabdrücke von Lane-Vektoren


def digest(v: LaneVector) -> bytes:
    """Fingerabdruck eines Lane-Vektors (die Vektoren selbst sind Megabit-Zahlen)."""
    return hashlib.blake2b(
        v.to_bytes((v.bit_length() + 7) // 8 or 1, "little"), digest_size=DIGEST_BYTES
    ).digest()


@dataclass
class FinalSig:
    """Fingerabdruck eines Endzustands plus mittlere Kosten je Lane
    (Vergleichsgröße von L3)."""

    reg: tuple[bytes, ...]  # Register-Qubits, nach Index sortiert
    planes: tuple[bytes, ...]  # die 128 Phasenebenen
    bits: tuple[bytes, ...]  # Register-Bits
    scratch_clean: bool
    # Fingerabdruck der Scratch-Werte (zählt nur, wenn das Original nicht sauber endet)
    scratch: bytes
    depth: int  # Tiefe des Bedingungsstapels am Ende
    tof_mean: float
    t_mean: float
    rot_mean: float


def final_sig(st: State, layout: Layout) -> FinalSig:
    """Bildet die Signatur eines Endzustands; `st` muss mit count=True simuliert sein,
    sonst sind die Kosten 0."""
    reg = tuple(digest(st.q.get(q, 0)) for q in sorted(layout.pinned))
    dirty = sorted((q, v) for q, v in st.q.items() if v and q not in layout.pinned)
    scratch_hash = hashlib.blake2b(digest_size=DIGEST_BYTES)
    for q, v in dirty:
        scratch_hash.update(q.to_bytes(4, "little") + digest(v))
    planes = tuple(digest(p) for p in st.planes())
    bits = tuple(digest(st.b.get(b, 0)) for b in layout.reg_bits)
    return FinalSig(
        reg,
        planes,
        bits,
        not dirty,
        scratch_hash.digest(),
        len(st.stack),
        st.toffoli_lanes / st.n,
        st.t_lanes / st.n,
        st.rotation_lanes / st.n,
    )


def _final_sig_mismatch(sig: FinalSig, ref: FinalSig) -> str | None:
    """Erster Grund, aus dem ein Kandidat (`sig`) vom Original (`ref`) abweicht; None =
    gleichwertig. Scratch muss sauber enden, wenn das Original sauber endet; sonst
    müssen die Endwerte übereinstimmen.
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
    """End-to-End-Prüfer (L3): vergleicht jeden Kandidaten mit dem
    ORIGINAL auf der ganzen Domäne."""

    def __init__(
        self,
        orig_ops: Sequence[Op],
        layout: Layout,
        dom: Domain,
        log: Callable[[str], None] = print,
    ) -> None:
        self.orig_c = compile_ops(orig_ops)
        self.layout, self.dom, self.log = layout, dom, log
        self._sig: dict[int, FinalSig] = {}
        self.runs = 0

    def orig_sig(self, seed: int) -> FinalSig:
        """Signatur des Originals für eine Messrunde (je Startwert einmal
        simuliert, dann gemerkt)."""
        if seed not in self._sig:
            self._sig[seed] = final_sig(
                simulate(self.orig_c, self.dom, seed, count=True), self.layout
            )
            self.runs += 1
        return self._sig[seed]

    def self_check(self) -> list[str]:
        """Kontrakt-Selbsttest des Originals: Scratch sauber, x erhalten, Phase
        unabhängig vom Messzufall."""
        first, second = self.orig_sig(0), self.orig_sig(1)
        issues = []
        init = tuple(
            digest(self.dom.init_q.get(q, 0)) for q in sorted(self.layout.pinned)
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
    ) -> tuple[bool, str, FinalSig | None]:
        """Vergleicht `ops` je Messrunde mit dem Original. Rückgabe (gleichwertig,
        Text, letzte Signatur)."""
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
        """Nennt eine Beispiel-Lane, auf der `st` vom Original abweicht (Register,
        Phase, Scratch ungleich 0)."""
        ref = simulate(self.orig_c, self.dom, seed)
        diff = 0
        for q in self.layout.pinned:
            diff |= st.q.get(q, 0) ^ ref.q.get(q, 0)
        for x, y in zip(st.planes(), ref.planes(), strict=True):
            diff |= x ^ y
        for q, v in st.q.items():
            if q not in self.layout.pinned:
                diff |= v
        if not diff:
            return "Lane nicht lokalisierbar"
        return (
            f"z. B. {self.dom.describe(first_lane(diff))}, {diff.bit_count():,} "
            "betroffene Lanes"
        )
