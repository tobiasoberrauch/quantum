"""Werkbank-Tools des Agenten (kmx.agent.workbench)."""

import kmx
from tests.kmx.helpers import (
    CTX_BODY,
    MBU_BODY,
    NHEAD,
    TINY,
    WB_BODY,
    P,
    fmt,
    make_session,
    make_wb,
    toffoli,
)


def test_propose_rewrite_accepts_cost_reducing_equivalent_rewrite():
    wb = make_wb()
    res = wb.propose_rewrite(
        NHEAD, NHEAD + 2, ["CX q1 q8", "X q0"], rationale="CCX X CCX = CX X"
    )
    assert (
        res["accepted"] is True
        and "exakt bewiesen" in res["message"]
        and res["neue_länge"] == NHEAD + 4
    )
    assert fmt(wb.session.ops[NHEAD:]) == ["CX q1 q8", "X q0", "CX q1 q8", "X q0"]
    assert (
        wb.accepted == 1
        and wb.session.audit[-1].startswith("[REWRITE]")
        and "Toffoli 2 -> 0" in wb.session.audit[-1]
    )
    assert wb.full_check()["ok"] is True


def test_propose_rewrite_rejects_non_equivalent_candidate_with_counterexample():
    wb = make_wb()
    before = list(wb.session.ops)
    res = wb.propose_rewrite(NHEAD, NHEAD + 2, ["CX q0 q8", "X q0"])
    assert (
        res["accepted"] is False
        and "Verifier-Ablehnung" in res["reason"]
        and "Fenstereingang" in res["reason"]
    )
    assert "allgemeine Belegung verletzt" in res["hinweis"]
    assert wb.session.ops == before and wb.accepted == 0 and wb.undo_stack == []


def test_propose_rewrite_rejects_cost_neutral_unless_neutral_ok():
    wb = make_wb()
    swapped = ["X q0", "CX q1 q8"]
    strict = wb.propose_rewrite(NHEAD + 3, NHEAD + 4, swapped)
    same = wb.propose_rewrite(NHEAD, NHEAD + 2, WB_BODY[:3])
    worse = wb.propose_rewrite(
        NHEAD + 3,
        NHEAD + 4,
        ["CX q1 q8", "X q0", "CCZ q0 q1 q2", "CCZ q0 q1 q2"],
        neutral_ok=True,
    )
    relaxed = wb.propose_rewrite(NHEAD + 3, NHEAD + 4, swapped, neutral_ok=True)
    assert strict["accepted"] is False and "keine Kostensenkung" in strict["reason"]
    assert same["accepted"] is False and "keine Kostensenkung" in same["reason"]
    # teurer geht nie durch
    assert worse["accepted"] is False and "keine Kostensenkung" in worse["reason"]
    assert relaxed["accepted"] is True and fmt(wb.session.ops[NHEAD + 3 :]) == swapped


def test_propose_rewrite_rejects_syntax_errors_and_bad_indices():
    wb = make_wb()
    n = len(wb.session.ops)
    for lines in (["FOO q0"], ["CX q0 q0"], ["Z_POW q0 1/4"], ["CX q1 q8", 5]):
        res = wb.propose_rewrite(NHEAD, NHEAD + 2, lines)
        assert res["accepted"] is False and "Syntaxfehler" in res["reason"], lines
    for start, end in ((-1, 3), (5, 4), (0, n), (n, n)):
        res = wb.propose_rewrite(start, end, ["X q0"])
        assert res["accepted"] is False and "Indizes außerhalb" in res["reason"], (
            start,
            end,
        )
    assert len(wb.session.ops) == n


def test_propose_rewrite_rejects_qubits_that_would_raise_q():
    wb = make_wb()
    res = wb.propose_rewrite(NHEAD, NHEAD + 2, ["CX q1 q8", "X q0", "X q9", "X q9"])
    # q7 < Q=9 ist erlaubt
    ok = wb.propose_rewrite(NHEAD, NHEAD + 2, ["CX q1 q8", "X q0", "X q7", "X q7"])
    assert (
        res["accepted"] is False
        and "Q erhöhen" in res["reason"]
        and "q9" in res["reason"]
    )
    assert ok["accepted"] is True


def test_propose_rewrite_rejects_unbalanced_push_pop():
    wb = make_wb()
    opened = wb.propose_rewrite(
        NHEAD, NHEAD + 2, ["PUSH_CONDITION if b0", "CX q1 q8", "X q0"]
    )
    closed = wb.propose_rewrite(
        NHEAD, NHEAD + 2, ["POP_CONDITION", "CX q1 q8", "X q0", "PUSH_CONDITION if b0"]
    )
    assert (
        opened["accepted"] is False
        and "nicht ausgeglichen" in opened["reason"]
        and "Kandidat" in opened["reason"]
    )
    assert closed["accepted"] is False and "ohne passendes PUSH" in closed["reason"]
    wb2 = make_wb(["PUSH_CONDITION if b0", "CCZ q0 q1 q2", "POP_CONDITION"])
    orig_side = wb2.propose_rewrite(NHEAD, NHEAD + 1, [])
    assert orig_side["accepted"] is False and "Originalfenster" in orig_side["reason"]


def test_propose_rewrite_rejects_register_declarations():
    wb = make_wb()
    cand = wb.propose_rewrite(
        NHEAD, NHEAD + 2, ["CX q1 q8", "X q0", "APPEND_TO_REGISTER q8 r0"]
    )
    cand2 = wb.propose_rewrite(
        NHEAD, NHEAD + 2, ["CX q1 q8", "X q0", 'REGISTER r1 "y"']
    )
    orig = wb.propose_rewrite(NHEAD - 1, NHEAD + 2, ["CX q1 q8", "X q0"])
    assert (
        cand["accepted"] is False
        and "Kandidat enthält Register-Deklarationen" in cand["reason"]
    )
    assert cand2["accepted"] is False and "Register-Deklarationen" in cand2["reason"]
    assert (
        orig["accepted"] is False
        and "Originalfenster enthält Register-Deklarationen" in orig["reason"]
    )


def test_propose_rewrite_rejects_off_grid_zpow_on_either_side():
    wb = make_wb()
    cand = wb.propose_rewrite(NHEAD, NHEAD + 2, ["CX q1 q8", "X q0", TINY])
    wb2 = make_wb(["CCZ q0 q1 q2", TINY, "CCZ q0 q1 q2"])
    orig = wb2.propose_rewrite(NHEAD, NHEAD + 2, [TINY])
    assert cand["accepted"] is False and "Phasenraster" in cand["reason"]
    assert (
        orig["accepted"] is False
        and "Phasenraster" in orig["reason"]
        and toffoli(wb2.session.ops) == 2
    )


def test_propose_rewrite_contextual_proof_unless_exact_only():
    mbu = ["HMR q8 b0", "CZ q0 q1 if b0"]
    wb, strict = make_wb(CTX_BODY), make_wb(CTX_BODY, exact_only=True)
    res = wb.propose_rewrite(NHEAD + 2, NHEAD + 2, mbu)
    res_strict = strict.propose_rewrite(NHEAD + 2, NHEAD + 2, mbu)
    assert res["accepted"] is True and res["message"].startswith(
        "kontextuell verifiziert"
    )
    assert wb.full_check()["ok"] is True and toffoli(wb.session.ops) == 1
    assert (
        res_strict["accepted"] is False
        and "--exact-only" in res_strict["reason"]
        and toffoli(strict.session.ops) == 2
    )


def test_propose_rewrite_rejects_measurement_without_phase_correction():
    wb = make_wb(CTX_BODY)
    res = wb.propose_rewrite(NHEAD + 2, NHEAD + 2, ["HMR q8 b0"])
    assert (
        res["accepted"] is False
        and "Phase" in res["reason"]
        and toffoli(wb.session.ops) == 2
    )


def test_propose_rewrite_treats_later_read_bit_as_live():
    body = ["BIT_STORE1 b0", "CCZ q0 q1 q2", "CCZ q0 q1 q2", "Z q0 if b0"]
    # spart 2 Toffoli, kippt aber b0
    flipped = make_wb(body).propose_rewrite(NHEAD + 1, NHEAD + 2, ["BIT_INVERT b0"])
    same = make_wb(body)
    # b0 ist hier ohnehin 1
    kept = same.propose_rewrite(NHEAD + 1, NHEAD + 2, ["BIT_STORE1 b0"])
    assert flipped["accepted"] is False and "Bit b0" in flipped["reason"]
    assert (
        kept["accepted"] is True
        and kept["message"].startswith("kontextuell")
        and same.full_check()["ok"]
    )


def test_workbench_undo_restores_previous_circuit():
    wb = make_wb()
    before = fmt(wb.session.ops)
    assert wb.undo() == {"ok": False, "meldung": "nichts zum Zurücknehmen"}
    wb.propose_rewrite(NHEAD, NHEAD + 2, ["CX q1 q8", "X q0"])
    assert fmt(wb.session.ops) != before
    assert (
        wb.undo() == {"ok": True, "länge": len(before)}
        and fmt(wb.session.ops) == before
    )
    assert wb.undo()["ok"] is False


def test_workbench_run_passes_is_undoable_and_reports_state():
    wb = make_wb(MBU_BODY)
    res = wb.run_passes()
    after = toffoli(wb.session.ops)
    assert after <= 2 and "mbu" in res["zusammenfassung"] and "Q=9" in res["stand"]
    assert wb.undo()["ok"] and toffoli(wb.session.ops) == 4


def test_workbench_dispatch_unknown_tool_and_bad_arguments():
    wb = make_wb()
    assert wb.dispatch("nope", {}) == {"fehler": "unbekanntes Tool nope"}
    assert (
        "falsche Argumente für propose_rewrite"
        in wb.dispatch("propose_rewrite", {"start": NHEAD})["fehler"]
    )
    assert (
        "falsche Argumente für read_lines"
        in wb.dispatch("read_lines", {"start": 0, "bogus": 1})["fehler"]
    )
    # Tool-Fehler statt Absturz
    assert "fehler" in wb.dispatch("analyze_window", {"start": "a", "end": "b"})
    assert (
        wb.dispatch("note", {"text": "x" * 900}) == {"ok": True}
        and len(wb.notes[0]) == 500
    )
    assert wb.dispatch("finish", {}) == {"ok": True} and wb.finished == "fertig"
    assert set(t["function"]["name"] for t in kmx.TOOLS) == {
        "overview",
        "read_lines",
        "find_hotspots",
        "analyze_window",
        "propose_rewrite",
        "run_passes",
        "full_check",
        "undo",
        "note",
        "finish",
    }


def test_workbench_read_lines_and_overview():
    wb = make_wb()
    rows = wb.dispatch("read_lines", {"start": NHEAD, "count": 2})
    clamp = wb.read_lines(999)
    over = wb.dispatch("overview", {})
    assert rows == {
        "gesamt": NHEAD + 5,
        "zeilen": [f"{NHEAD}: CCX q0 q1 q8", f"{NHEAD + 1}: X q0"],
    }
    assert clamp["zeilen"] == []
    assert (
        over["register"] == {"x": 6}
        and over["angenommene_rewrites"] == 0
        and "64" in over["domäne"]
    )
    assert (
        "Toffoli-artig=2" in over["original"]
        and sum(r["toffoli"] for r in over["profil_top"]) == 2
    )


def test_analyze_window_reports_facts_from_entry_state():
    wb = make_wb(CTX_BODY)
    res = wb.analyze_window(NHEAD + 1, NHEAD + 2)
    assert res["zeilen"] == [f"{NHEAD + 1}: CZ q8 q2", f"{NHEAD + 2}: CCX q0 q1 q8"]
    assert res["qubits"] == ["q0", "q1", "q2", "q8"] and res["toffoli"] == 1
    assert "q8 = q0 & q1" in res["fakten_am_eingang"]
    assert (
        res["freie_saubere_ancillas"] == ["q6", "q7"]
        and res["exakter_beweis_möglich"] is True
    )
    assert res["bedingungstiefe_am_eingang"] == 0 and res["von_möglichen"] == "2^4"
    # q8 ist abhaengig
    assert (
        isinstance(res["erreichbare_zustände"], int)
        and res["erreichbare_zustände"] <= 8
    )


def test_analyze_window_uses_domain_dont_cares_and_measurement_taint():
    wb = make_wb(
        [
            "CCX q5 q0 q8",
            "CX q0 q8",
            "HMR q8 b0",
            "Z q0 if b0",
            "X q8 if b0",
            "X q8 if b0",
        ],
        "0:31",
    )
    facts = wb.analyze_window(NHEAD, NHEAD + 1)["fakten_am_eingang"]
    late = wb.analyze_window(NHEAD + 4, NHEAD + 5)
    assert (
        "q5 = 0 (auf allen Stichproben)" in facts
        and "q8 = 0 (auf allen Stichproben)" in facts
    )
    assert late["fakten_am_eingang"] == ["q8 = 0 (auf allen Stichproben)"]
    wb2 = make_wb(
        [
            "BIT_STORE1 b0",
            "PUSH_CONDITION if b0",
            "HMR q8 b1",
            "X q8",
            "X q8",
            "POP_CONDITION",
        ]
    )
    tainted = wb2.analyze_window(NHEAD + 3, NHEAD + 4)
    assert tainted["fakten_am_eingang"] == ["q8 hängt von Messergebnissen ab"]
    assert tainted["bedingungstiefe_am_eingang"] == 1


def test_analyze_window_rejects_bad_ranges():
    wb = make_wb()
    n = len(wb.session.ops)
    assert "fehler" in wb.analyze_window(-1, 2) and "fehler" in wb.analyze_window(3, 2)
    assert "fehler" in wb.analyze_window(0, n)
    big = kmx.Workbench(make_session(["X q0"] * 400))
    assert "zu groß" in big.analyze_window(0, 350)["fehler"]


def test_find_hotspots_runs_pairs_dense():
    wb = make_wb()
    runs, pairs, dense = (wb.find_hotspots(k) for k in ("runs", "pairs", "dense"))
    assert runs == {
        "art": "runs",
        "treffer": 1,
        "liste": [
            {"ziel": "q8", "ccx_indizes": [NHEAD, NHEAD + 2], "anzahl": 2, "spanne": 3}
        ],
    }
    assert pairs["liste"] == [
        {"gatter": "CCX q0 q1 q8", "start": NHEAD, "ende": NHEAD + 2, "distanz": 2}
    ]
    assert dense["liste"] == [{"start": 0, "ende": NHEAD + 4, "toffoli": 2}]
    # Ziel wird dazwischen gelesen
    no_run = make_wb(["CCX q0 q1 q8", "CX q8 q9", "CCX q0 q1 q8", "CX q8 q9"])
    assert (
        no_run.find_hotspots("runs")["treffer"] == 0
        and no_run.find_hotspots("pairs")["treffer"] == 1
    )


def test_find_hotspots_conditional_peak_and_invalid_kind():
    wb = make_wb(
        [
            "CCX q0 q1 q8",
            "CX q0 q9",
            "CX q0 q9",
            "CCX q0 q1 q8",
            "PUSH_CONDITION if b0",
            "CCZ q0 q1 q2",
            "POP_CONDITION",
            "CSWAP q0 q1 q2 if b1",
            "CSWAP q0 q1 q2 if b1",
        ]
    )
    cond, peak = wb.find_hotspots("conditional"), wb.find_hotspots("peak")
    assert cond["treffer"] == 3 and cond["liste"][0] == {
        "idx": NHEAD + 5,
        "gatter": "CCZ q0 q1 q2",
        "tiefe": 1,
    }
    assert cond["liste"][1] == {
        "idx": NHEAD + 7,
        "gatter": "CSWAP q0 q1 q2 if b1",
        "tiefe": 0,
    }
    assert peak["treffer"] == 1 and peak["liste"][0]["scratch_gleichzeitig"] == 2
    assert {d["qubit"] for d in peak["liste"][0]["längste_lebensdauern"]} == {
        "q8",
        "q9",
    }
    assert wb.find_hotspots("cond", limit=1)["fehler"].startswith("kind muss")
    assert len(wb.find_hotspots("conditional", limit=1)["liste"]) == 1
    assert make_wb().find_hotspots("conditional")["treffer"] == 0


def test_profile_segments_follows_info_tags():
    ops = P(
        'INFO_TAG "@enter:mul"',
        "CCX q0 q1 q2",
        "CCZ q0 q1 q2",
        'INFO_TAG "@exit:mul"',
        'INFO_TAG "@enter:add"',
        "CCX q0 q1 q2",
        "CX q0 q1",
        'INFO_TAG "@exit:add"',
        "X q0",
    )
    rows = kmx.profile_segments(ops)
    assert [(r["segment"], r["toffoli"], r["instruktionen"]) for r in rows] == [
        ("mul", 2, 2),
        ("add", 1, 2),
        ("(oberste Ebene)", 0, 1),
    ]


def test_propose_rewrite_rejects_clearing_a_live_bit():
    # Regression: Folge davon: propose_rewrite nimmt den (falschen) L1-"Beweis" und
    # ignoriert, dass check_context die Abweichung "Bit b0" bereits gefunden hat. Der
    # Rewrite loescht b0, das danach von "Z q0 if b0" gelesen wird; erst full_check (L3)
    # faellt durch und rollt zurueck ("sollte nie passieren").
    wb = make_wb(["BIT_STORE1 b0", "CCZ q0 q1 q2", "CCZ q0 q1 q2", "Z q0 if b0"])
    res = wb.propose_rewrite(NHEAD + 1, NHEAD + 2, ["BIT_STORE0 b0"])
    assert res["accepted"] is False, (res, wb.session.final_check())


def test_workbench_rejects_integer_zpow_exponent():
    # Regression: Folge des Parser-Befunds: der Rewrite wird angenommen, die Datei waere
    # fuer kickmix ungueltig.
    wb = make_wb(["CCZ q0 q1 q2", "Z q0", "CCZ q0 q1 q2"])
    res = wb.propose_rewrite(NHEAD, NHEAD + 2, ["Z_POW q0 1"])
    assert res["accepted"] is False, res
