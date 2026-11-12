#!/usr/bin/env python3
"""Fokussierte Tests fuer die neuen Optimizer-Bausteine in main.py (Track A + B).

Laufbar OHNE Netzwerk (LLM wird per Stub ersetzt):
    .venv-qvc/bin/python test_main_optimizer.py

Deckung:
  - echtes Kostenmodell (CX/CZ/SWAP/X kostenlos, CCX/CCZ/Z_POW/T zaehlen)
  - Verifier-in-the-Loop: akzeptiert kostenreduzierende Aequivalenz,
    verwirft nicht-aquivalente Kandidaten
  - Beam-Suche: findet eine echte Reduktion; bleibt bei lokal-optimal inert
  - defensive Eingaben: None/leer/Whitespace crasht nirgends
"""
import sys

sys.path.insert(0, ".")
import main as M  # noqa: E402


# ---------------------------------------------------------------- Kostenmodell
def test_cost_model_ignores_free_gates():
    # CX/CZ/SWAP/X sind kostenlos
    a = M.compute_metrics(["CX q0 q1", "SWAP q0 q1", "X q0", "CZ q0 q1"])
    b = M.compute_metrics([])
    assert a.real_cost == b.real_cost == 0.0, (a.real_cost, b.real_cost)
    # CCX zaehlt
    c = M.compute_metrics(["CCX q0 q1 q2"])
    assert c.real_cost > 0.0


def test_zpow_classification():
    # zpow_info splittet Z_POW exakt in Clifford(frei) / T-artig(T/4) / fein(ROT_WEIGHT)
    m_cliff = M.compute_metrics(["Z_POW q0 0.5"])   # S-Gate -> Clifford -> gratis
    assert m_cliff.inner_cost == 0.0 and m_cliff.zpow_rot == 0 and m_cliff.zpow_t_like == 0
    m_t = M.compute_metrics(["Z_POW q0 0.25"])      # T-Gate -> T/4
    assert abs(m_t.inner_cost - 0.25) < 1e-9 and m_t.zpow_t_like == 1 and m_t.zpow_rot == 0
    m_fine = M.compute_metrics(["Z_POW q0 0.125"])  # Rz(pi/8) -> feine Rotation
    assert abs(m_fine.inner_cost - M.ROT_WEIGHT) < 1e-9 and m_fine.zpow_rot == 1
    # defensive: leer/None Exponent
    assert M.zpow_info("") == ((), 0)
    assert M.zpow_info(None) == ((), 0)


def test_deterministic_passes_use_kimi():
    # Starke Op-Paesse aktiv (kein Fallback) + gueltige Ausloeschung ueber kommutierendes CX
    assert M._kimi is not None, "kmx_agent_kimi.py nicht importierbar"
    tb = M.AgentToolbox(["CCX q0 q1 q2", "CX q3 q4", "CCX q0 q1 q2"])
    s = tb.run_deterministic_passes()
    assert "kimi" in s, s
    assert "CCX" not in " ".join(tb.lines), tb.lines


# ------------------------------------------------------- Verifier-in-the-Loop
def test_accepts_cost_reducing_equivalent_rewrite():
    # CCX(a,b,t); X a; CCX(a,b,t)  ==  CX(b,t); X a   (2 CCX -> 0 CCX)
    tb = M.AgentToolbox(["CCX q0 q1 q2", "X q0", "CCX q0 q1 q2"])
    res = tb.apply_verified_rewrite(0, 2, ["CX q1 q2", "X q0"], description="test")
    assert res["accepted"] is True, res
    assert tb.lines == ["CX q1 q2", "X q0"]


def test_rejects_non_equivalent_same_cost():
    tb = M.AgentToolbox(["CX q0 q1", "CX q0 q1"])  # = Identitaet
    res = tb.apply_verified_rewrite(0, 1, ["CX q0 q1"], description="test")
    assert res["accepted"] is False, res
    assert "Verifier" in res["reason"], res


def test_rejects_same_cost_reshuffle():
    # Gleich-teures Umordnen (CX bleibt CX) darf nicht als "Kosten-Sieg" durchgehen.
    tb = M.AgentToolbox(["CX q0 q1", "CX q1 q2"])
    res = tb.apply_verified_rewrite(0, 1, ["CX q1 q2", "CX q0 q1"], description="test")
    # Die beiden CX kommutieren NICHT (teilen q1) -> Kandidat ist nicht aequivalent,
    # UND inner_cost ist gleich -> muss abgelehnt werden.
    assert res["accepted"] is False, res


# ------------------------------------------------------------- defensive Input
def test_defensive_inputs():
    assert M.compute_metrics(None).total_lines == 0
    assert M.circuit_cost(None) == 0.0
    assert M.circuit_cost("") == 0.0
    assert M.circuit_cost(["   ", ""]) == 0.0

    tb = M.AgentToolbox(["X q0"])
    assert tb.apply_verified_rewrite(0, 0, None)["accepted"] is False
    assert tb.apply_verified_rewrite(0, 0, ["", "  "])["accepted"] is False
    assert tb.apply_verified_rewrite(5, 9, ["X q0"])["accepted"] is False  # Index-Guard

    ag = M.AutonomousKMXAgent(M.AgentToolbox(["X q0"]))
    assert ag.query_llm_for_window(None) is None      # kein Netzwerk-Call
    assert ag.query_llm_for_window([]) is None
    assert ag.query_llm_for_window(["   "]) is None
    assert ag.synthesize_algebraic_ccx_merge(None) is None
    assert ag.synthesize_algebraic_ccx_merge([]) is None


# ------------------------------------------------------------- Beam-Suche (A)
class _StubAgent:
    """Ersetzt das LLM deterministisch: liefert fuer ein bekanntes Muster den
    optimalen Kandidaten, sonst None. Testet die Beam-Plumbing ohne Netzwerk."""

    def __init__(self, responder):
        self._r = responder

    def synthesize_algebraic_ccx_merge(self, window):
        return None

    def query_llm_for_window(self, window):
        return self._r(window)


def test_beam_search_finds_reduction():
    def responder(window):
        w = [x.strip() for x in window]
        if w == ["CCX q0 q1 q2", "X q0", "CCX q0 q1 q2"]:
            return ["CX q1 q2", "X q0"]
        return None

    ag = _StubAgent(responder)
    opt = M.BeamSearchKMXOptimizer(ag, beam_width=3, max_iterations=4, use_llm=True)
    init = ["CCX q0 q1 q2", "X q0", "CCX q0 q1 q2"]
    out = opt.optimize(init)
    assert M.circuit_cost(out) < M.circuit_cost(init), (
        out, M.circuit_cost(out), M.circuit_cost(init))
    ok, _ = M.BitParallelKMXVerifier.verify_equivalence(init, out)
    assert ok, "Beam-Ergebnis nicht aequivalent zum Original"


def test_beam_search_locally_optimal_is_inert():
    ag = _StubAgent(lambda w: None)  # keine LLM-Zuege
    opt = M.BeamSearchKMXOptimizer(ag, beam_width=3, max_iterations=4, use_llm=True)
    init = ["CX q0 q1", "CX q1 q2", "CX q0 q2"]  # lokal optimal (keine CCX/Z_POW)
    out = opt.optimize(init)
    assert M.circuit_cost(out) == M.circuit_cost(init) == 0.0


def test_beam_search_empty_input():
    ag = _StubAgent(lambda w: None)
    opt = M.BeamSearchKMXOptimizer(ag)
    assert opt.optimize(None) == []
    assert opt.optimize([]) == []
    assert opt.optimize(["   "]) == []


def _run():
    fns = [v for k, v in sorted(globals().items())
           if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
        print(f"PASS  {fn.__name__}")
    print(f"\nALL {len(fns)} TESTS PASSED")


if __name__ == "__main__":
    _run()
