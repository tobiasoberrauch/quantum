"""Eingebauter Selbsttest: jede Prüfung liefert (bestanden,
Beschriftung der Ausgabezeile)."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from fractions import Fraction

from kmx._optional import kickmix
from kmx.agent.json_mode import json_array
from kmx.cost import compute_metrics, phase_op
from kmx.domains import Domain, build_domains
from kmx.layout import Layout, analyze_layout
from kmx.ops import Op, format_ops, parse_lines, parse_text
from kmx.passes.cancel import pass_cancel
from kmx.session import Options, Session
from kmx.verify.compat import BitParallelKMXVerifier
from kmx.verify.oracle import Oracle
from kmx.verify.window import ExactStatus, check_exact

SelftestOutcome = tuple[bool, str]

SELFTEST_INPUT_REGISTER = "x"
SELFTEST_RANGE = "0:63"
SELFTEST_MAX_EXHAUSTIVE = 1 << 20
SELFTEST_LANES = 64
SELFTEST_HEAD = (
    "".join(f"APPEND_TO_REGISTER q{i} r0\n" for i in range(6)) + 'REGISTER r0 "x"\n'
)


def _selftest_domains(ops: Sequence[Op]) -> tuple[Layout, Domain, Domain]:
    layout = analyze_layout(ops, SELFTEST_INPUT_REGISTER, SELFTEST_RANGE)
    dom, sample_dom = build_domains(
        layout, SELFTEST_MAX_EXHAUSTIVE, SELFTEST_LANES, SELFTEST_LANES
    )
    return layout, dom, sample_dom


def _selftest_optimized_session(ops: list[Op], final_rounds: int) -> Session:
    """Stumme Sitzung auf dem 6-Bit-Testregister, Basislauf und alle
    Pässe bereits ausgeführt."""
    layout, dom, sample_dom = _selftest_domains(ops)
    session = Session(
        ops,
        layout,
        dom,
        sample_dom,
        Options(final_rounds=final_rounds),
        log=lambda *_: None,
    )
    session.run_baseline()
    session.run_passes()
    return session


def _selftest_toffoli_target(name: str, body: str, max_toffoli: int) -> SelftestOutcome:
    """Die Pässe müssen `body` End-to-End-geprüft auf höchstens
    `max_toffoli` Toffolis bringen."""
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
        "CCX q0 q1 q8\nCX q8 q7\nCCX q7 q2 q9\nCZ q9 q3\n"
        "CCX q7 q2 q9\nCX q8 q7\nCCX q0 q1 q8\n",
        2,
    )


def _selftest_toffoli_group() -> SelftestOutcome:
    return _selftest_toffoli_target(
        "Gruppe: ab ^ ac ^ bc -> 1 Toffoli",
        "CCX q0 q1 q8\nCCX q0 q2 q8\nCCX q1 q2 q8\nCZ q8 q3\n"
        "CCX q1 q2 q8\nCCX q0 q2 q8\nCCX q0 q1 q8\n",
        1,
    )


def _selftest_difference_control() -> SelftestOutcome:
    return _selftest_toffoli_target(
        "Differenz-Kontrolle (X/CX zwischen CCX-Paar)",
        "CCX q0 q1 q8\nCX q2 q0\nX q0\nCCX q0 q1 q8\nX q0\nCX q2 q0\n"
        "CZ q8 q4\nCCX q2 q1 q8\nCX q1 q8\n",
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
    """Phasenfusion: syntaktisch (gleiches Qubit) und semantisch (wertgleiche Qubits);
    Ausgabe muss kickmix-gültig sein."""
    merged, _, n_merge = pass_cancel(
        parse_text(
            "Z_POW q0 0.0009765625\nCX q1 q2\nZ_POW q0 0.0009765625\nZ q3\n"
            "Z_POW q3 -0.75"
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
    if kickmix is not None:
        kickmix.Circuit(format_ops(merged))
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


def _selftest_compat_interfaces() -> SelftestOutcome:
    """Alte API-Namen; die Ausgabezeile behält ihren historischen Text."""
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
        and json_array('Text ```json\n["CX q0 q1"]\n```') == ["CX q0 q1"]
    )
    return (
        good,
        "v3-Schnittstellen (compute_metrics auf Zeilen, BitParallelKMXVerifier, "
        "JSON-Antworten)",
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
    # Differenzkegel: 3-Qubit-Umformung zwischen 24 unbeteiligten Qubits (sonst > 20
    # Variablen); falsche Variante fällt durch
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
    # unter 2^-128: der Simulator würde auf 0 runden
    tiny = "Z_POW q0 0." + "0" * 45 + "1"
    off_grid = check_exact(parse_lines([tiny]), [], 0, set())[0]
    good = (
        status == ExactStatus.PROVED
        and status_wrong == ExactStatus.REFUTED
        and cone_right == ExactStatus.PROVED
        and cone_wrong == ExactStatus.REFUTED
        and global_phase == ExactStatus.REFUTED
        and off_grid == ExactStatus.UNDECIDED
    )
    return good, f"Exakter Fenster-Verifier: {msg}"


SELFTEST_CHECKS: tuple[Callable[[], SelftestOutcome], ...] = (
    _selftest_mbu_uncompute,
    _selftest_toffoli_group,
    _selftest_difference_control,
    _selftest_commuting_cancellation,
    _selftest_uncorrected_hmr,
    _selftest_phase_fusion,
    _selftest_equal_value_rotations,
    _selftest_compat_interfaces,
    _selftest_exact_window_verifier,
)
