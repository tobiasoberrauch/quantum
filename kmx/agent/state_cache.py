"""Simulatorzustände an beliebigen Positionen des aktuellen Stands, mit Schnappschüssen
auf der Stichprobe und dem zuletzt berechneten Zustand auf der vollen Domäne."""

from __future__ import annotations

from kmx.session import Session
from kmx.simulator import State, compile_op, step

# Abstand der Zustands-Schnappschüsse (Instruktionen) auf der Stichprobendomäne
SNAPSHOT_STRIDE = 2000
# Startwert der Simulation (Messergebnisse) für Werkbank-Zustände
STATE_SEED = "W"


class StateCache:
    """Zustände unmittelbar vor einer Instruktion von `session.ops`. Nach jeder
    Änderung des Stands ab Position `pos` muss `invalidate(pos)` gerufen werden."""

    def __init__(self, session: Session, stride: int = SNAPSHOT_STRIDE) -> None:
        self.session = session
        self.stride = stride
        self.snaps: list[tuple[int, State]] = []
        self._exhaustive: tuple[int, State] | None = None

    def invalidate(self, pos: int) -> None:
        """Verwirft zwischengespeicherte Zustände hinter `pos` (der Schaltkreis hat
        sich ab dort geändert)."""
        self.snaps = [(p, s) for p, s in self.snaps if p <= pos]
        if self._exhaustive and self._exhaustive[0] > pos:
            self._exhaustive = None

    def state_at(self, pos: int, exhaustive: bool = False) -> State:
        """Simulatorzustand unmittelbar vor Instruktion `pos`.

        Stichprobendomäne: startet am letzten Schnappschuss davor und legt alle
        `stride` Instruktionen einen neuen ab. Volle Domäne (`exhaustive`): merkt sich
        nur den zuletzt berechneten Zustand, weil eine Kopie teuer ist.
        """
        ops = self.session.ops
        if exhaustive:
            if self._exhaustive and self._exhaustive[0] <= pos:
                start, st = self._exhaustive[0], self._exhaustive[1].copy()
            else:
                start, st = 0, State(self.session.dom, STATE_SEED)
        else:
            before = [(p, s) for p, s in self.snaps if p <= pos]
            if before:
                start, st = before[-1][0], before[-1][1].copy()
            else:
                start, st = 0, State(self.session.sample_dom, STATE_SEED)
        for i in range(start, pos):
            if not exhaustive and i % self.stride == 0 and i > start:
                self.snaps.append((i, st.copy()))
                self.snaps.sort(key=lambda t: t[0])
            step(st, compile_op(ops[i]))
        if exhaustive:
            self._exhaustive = (pos, st.copy())
        return st
