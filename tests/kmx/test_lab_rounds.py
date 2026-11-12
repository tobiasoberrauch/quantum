"""Labor: CEGIS-Runden mit Stub-LLM (kmx.lab.rounds, kmx.lab.teams, Prompt-Dateien)."""

import atexit
import shutil
import tempfile

import kmx.lab.sandbox as sandbox
from kmx.agent.client import LLMError
from kmx.lab.claims import EV_ATTEMPT, EV_CRITIQUE, EXPERIMENTAL, HYPOTHESIS, REFUTED
from kmx.lab.report import status_report
from kmx.lab.rounds import LabRun, RunOptions
from kmx.lab.teams import (
    PROMPT_FILES,
    RESEARCH_TEAMS,
    example_generator,
    parse_critique,
    parse_insights,
    parse_team_list,
    system_prompt,
)
from kmx.prompts import load_prompt
from tests.kmx.fakes import RoutingFakeClient
from tests.kmx.helpers import raises
from tests.kmx.lab_helpers import (
    BAD_PHASE_TEXT,
    GOOD_TEXT,
    TEAM_KEYS,
    make_lab,
    proposal,
    reply,
)

K = TEAM_KEYS
PLAN = reply({"focus": {"numerical": "segment the domain", "phase": "kickback"}})
NO_VETO = reply({"veto": False, "reason": ""})
CONFERENCE = reply({"insights": [{"insight": "Z on q0 breaks odd x", "supports": []}]})


def _run(routes, teams=("numerical", "phase"), rounds=1, max_calls=40, **opts):
    lab = opts.pop("lab", None)
    if lab is None:
        d = tempfile.mkdtemp()
        atexit.register(shutil.rmtree, d, True)
        lab = make_lab(d)
    reg, judge = lab
    client = RoutingFakeClient(routes, reachable=opts.pop("reachable", True))
    run = LabRun(
        reg,
        judge,
        client,
        RunOptions(["m1", "m2"], rounds, teams, max_calls, **opts),
        "SPEC",
        log=lambda *_: None,
    )
    return run.run(), reg, client


def _by_author(reg, author):
    return [c for c in reg.claims().values() if c.introduced_by == author]


def test_prompt_files_state_cost_model_schema_and_no_proof_claims():
    for role, name in PROMPT_FILES.items():
        text = load_prompt(name)
        assert "never" in text.lower() and "JSON" in text, role
        assert "Q" in text and "0.56" in text, role
        assert "{" in text and "}" in text, role
    assert parse_team_list(None) == ("numerical", "reversible", "phase", "architecture")
    assert parse_team_list("phase, numerical") == ("phase", "numerical")
    assert raises(ValueError, parse_team_list, "phase,../x")


def test_round_judges_candidates_and_records_hypotheses():
    routes = {
        K["director"]: [PLAN, CONFERENCE],
        K["numerical"]: [proposal(GOOD_TEXT, claim="baseline is a fixpoint")],
        K["phase"]: [proposal(BAD_PHASE_TEXT, claim="Z q0 is harmless")],
        K["critic"]: [NO_VETO],
    }
    summary, reg, client = _run(routes)
    assert summary.rounds_done == 1 and summary.proposals == 2
    assert len(summary.evaluations) == 2 and summary.llm_calls == client.calls == 6
    num = _by_author(reg, "team:numerical")
    phase = _by_author(reg, "team:phase")
    status = {c.claim[:30]: c.status for c in num + phase}
    assert status["baseline is a fixpoint"] == HYPOTHESIS
    assert status["Candidate (kmx) from team nume"] == EXPERIMENTAL
    assert status["Candidate (kmx) from team phas"] == REFUTED
    insight = _by_author(reg, "conference")
    assert len(insight) == 1 and insight[0].status == HYPOTHESIS
    # Fokus des Direktors erreicht das Team
    team_prompts = [m for k, m in client.seen if k == K["numerical"]]
    assert "segment the domain" in team_prompts[0][1]["content"]


def test_counterexample_is_fed_back_to_the_proposing_team():
    routes = {
        K["director"]: [PLAN, CONFERENCE],
        K["phase"]: [proposal(BAD_PHASE_TEXT)],
        K["critic"]: [NO_VETO],
    }
    summary, _, client = _run(routes, teams=("phase",), rounds=2)
    assert summary.rounds_done == 2
    prompts = [m[1]["content"] for k, m in client.seen if k == K["phase"]]
    assert "(none yet)" in prompts[0]
    assert "[phase] x=1" in prompts[1] and "RECENT COUNTEREXAMPLES" in prompts[1]
    # widerlegte Altbefunde stehen in jedem Prompt
    assert "seed-magnitude-shortcut" in prompts[0]


def test_critic_veto_needs_a_concrete_reason():
    concrete = {"veto": True, "reason": "x=1 gets phase -1 from Z q0, not 1/sqrt"}
    assert parse_critique(concrete).veto
    assert not parse_critique({"veto": True, "reason": "dubious"}).veto
    assert not parse_critique({"veto": "yes", "reason": concrete["reason"]}).veto
    veto, vague = reply(concrete), reply({"veto": True, "reason": "dubious"})
    for critic, is_veto in ((veto, True), (vague, False)):
        routes = {
            K["director"]: [PLAN, CONFERENCE],
            K["phase"]: [proposal(BAD_PHASE_TEXT)],
            K["critic"]: [critic],
        }
        summary, reg, _ = _run(routes, teams=("phase",))
        assert len(summary.evaluations) == 1  # der Richter läuft immer
        crit = [e for e in reg.events() if e.get("kind") == EV_CRITIQUE]
        assert len(crit) == 1 and crit[0]["veto"] == is_veto
        assert crit[0]["ignored_veto"] == (not is_veto) and crit[0]["advisory"]


def test_invalid_model_output_is_a_failed_attempt_not_a_crash():
    routes = {
        K["director"]: ["no json here at all", "{broken"],
        K["numerical"]: ["```json\n{not valid json\n```"],
        K["phase"]: [LLMError("HTTP 500: boom")],
        K["critic"]: [NO_VETO],
    }
    summary, reg, _ = _run(routes)
    assert summary.rounds_done == 1 and summary.proposals == 0
    attempts = [e for e in reg.events() if e.get("kind") == EV_ATTEMPT]
    assert summary.failed_attempts == len(attempts) == 3
    assert {a["role"] for a in attempts} == {"director", "numerical", "phase"}


def test_bad_candidate_fields_are_dropped():
    routes = {
        K["director"]: [PLAN, CONFERENCE],
        K["numerical"]: [proposal("X q0", kind="shell")],
        K["critic"]: [NO_VETO],
    }
    summary, reg, _ = _run(routes, teams=("numerical",))
    assert summary.evaluations == []
    notes = [n for c in reg.claims().values() for n in c.notes]
    assert any("candidate verworfen" in n for n in notes)


def test_budget_limits_llm_calls():
    routes = {
        K["director"]: [PLAN],
        K["numerical"]: [proposal(GOOD_TEXT)],
        K["phase"]: [proposal(GOOD_TEXT)],
        K["critic"]: [NO_VETO],
    }
    summary, _, client = _run(routes, rounds=3, max_calls=2)
    assert client.calls == summary.llm_calls == 2
    assert "Budget" in summary.stop_reason and summary.rounds_done == 1
    # der schon erhaltene Vorschlag wird trotzdem deterministisch bewertet
    assert summary.proposals == 1 and len(summary.evaluations) == 1


def test_unreachable_endpoint_stops_cleanly():
    summary, reg, client = _run({}, reachable=False)
    assert client.calls == 0 and summary.rounds_done == 0
    assert "nicht erreichbar" in summary.stop_reason


VETO = reply(
    {
        "veto": True,
        "reason": "x=0 breaks the phase of every even x",
        "counterexample": "x=0",
    }
)


def test_veto_is_advisory_and_source_is_stored_before_critique():
    """Regression: ein (falsches) Veto stoppte den Kandidaten vor dem Richter, und
    sein Quelltext ging verloren."""
    routes = {
        K["director"]: [PLAN, CONFERENCE],
        K["numerical"]: [proposal(GOOD_TEXT)],
        K["critic"]: [VETO],
    }
    summary, reg, client = _run(routes, teams=("numerical",))
    assert summary.vetoes == 1 and len(summary.evaluations) == 1
    ev = summary.evaluations[0]
    assert ev.passed  # der Richter widerlegt das Veto
    crit = next(e for e in reg.events() if e.get("kind") == EV_CRITIQUE)
    assert crit["source_sha256"] == ev.candidate_sha256
    events = list(reg.events())
    i_crit = events.index(crit)
    i_eval = next(i for i, e in enumerate(events) if e.get("kind") == "evaluation")
    assert i_crit < i_eval
    # Konferenz sieht Veto-Grund UND Richterurteil
    conf = [m[1]["content"] for k, m in client.seen if k == K["director"]][-1]
    assert "x=0 breaks the phase" in conf and "judge: BESTANDEN" in conf
    report = status_report(reg)
    assert "Vetos (beratend): 1" in report and "critic VETO, advisory" in report
    assert "x=0 breaks the phase" in report.split("Vetos des Kritikers")[1]


def test_candidate_claim_text_is_machine_generated():
    """Regression: die LLM-Begründung ('FORMALLY PROVED ... 10x better') wurde zum
    Text der Kandidaten-Behauptung und erschien so unter experimental."""
    rhetoric = "FORMALLY PROVED: score 4.0 (10x better than baseline)"
    obj = {
        "claims": [],
        "candidate": {"kind": "kmx", "source": GOOD_TEXT, "rationale": rhetoric},
    }
    routes = {
        K["director"]: [PLAN, CONFERENCE],
        K["numerical"]: [reply(obj)],
        K["critic"]: [NO_VETO],
    }
    _, reg, _ = _run(routes, teams=("numerical",))
    (cand,) = _by_author(reg, "team:numerical")
    assert cand.status == EXPERIMENTAL and "PROVED" not in cand.claim
    assert any(rhetoric in n and "unchecked" in n for n in cand.notes)
    report = status_report(reg)
    line = next(x for x in report.splitlines() if cand.claim_id in x and "score" in x)
    assert "Delta +0.00, keine Verbesserung" in line


def test_feedback_survives_a_new_run():
    """Regression: Rückmeldungen lebten nur im Speicher; ein neuer `lab run`
    begann mit '(none yet)'."""
    d = tempfile.mkdtemp()
    atexit.register(shutil.rmtree, d, True)
    lab = make_lab(d)
    routes = {
        K["director"]: [PLAN, CONFERENCE],
        K["phase"]: [proposal(BAD_PHASE_TEXT)],
        K["critic"]: [VETO],
    }
    _run(routes, teams=("phase",), lab=lab)
    _, _, client = _run(routes, teams=("phase",), lab=lab)
    prompt = [m[1]["content"] for k, m in client.seen if k == K["phase"]][0]
    assert "(none yet)" not in prompt
    assert "judge: [phase] x=1" in prompt and "critic VETO (advisory)" in prompt


def test_conference_supports_map_team_names_and_report_dropped():
    known = {"c-aaa"}
    obj = {"insights": [{"insight": "i", "supports": ["c-aaa", "phase", "nobody"]}]}
    ((text, ids, dropped),) = parse_insights(obj, known, {"phase": ["c-bbb"]})
    assert ids == ["c-aaa", "c-bbb"] and dropped == ["nobody"]
    conference = reply({"insights": [{"insight": "share", "supports": ["phase", "x"]}]})
    routes = {
        K["director"]: [PLAN, conference],
        K["phase"]: [proposal(BAD_PHASE_TEXT)],
        K["critic"]: [NO_VETO],
    }
    _, reg, _ = _run(routes, teams=("phase",))
    (insight,) = _by_author(reg, "conference")
    phase_ids = {c.claim_id for c in _by_author(reg, "team:phase")}
    assert insight.sources and set(insight.sources) <= phase_ids
    assert any("verworfen" in n and "x" in n for n in insight.notes)


def test_team_prompts_carry_the_kmx_cheat_sheet_and_a_valid_example():
    """Regression: die Teams kannten weder Token-Format noch Op-API; alle
    Kandidaten eines Live-Laufs waren Platzhalter oder stürzten ab."""
    for role in (*RESEARCH_TEAMS, "critic"):
        text = system_prompt(role)
        for needle in ("APPEND_TO_REGISTER", 'Op("CCX", ["q18"', "Z_POW", "if bN"):
            assert needle in text, (role, needle)
        assert "baseline.kmx" in text
    assert "APPEND_TO_REGISTER" not in system_prompt("director")
    if not sandbox.sandbox_available():
        print("ÜBERSPRUNGEN: sandbox-exec fehlt; Beispielgenerator nicht ausgeführt")
        return
    d = tempfile.mkdtemp()
    atexit.register(shutil.rmtree, d, True)
    _, judge = make_lab(d)
    ev = judge.evaluate("generator", example_generator())
    # das Beispiel reproduziert die Basis: läuft, wird aber als 'no change' erkannt
    assert ev.no_change and ev.counterexample is None, ev.line()


def test_critic_notes_are_stored_and_fed_back():
    """Regression: die 'notes' des Kritikers ohne Veto wurden verworfen (er hatte
    Platzhalter-Kandidaten erkannt)."""
    note = "The candidate is explicitly a placeholder; withdraw it"
    routes = {
        K["director"]: [PLAN, CONFERENCE],
        K["phase"]: [proposal(BAD_PHASE_TEXT)],
        K["critic"]: [reply({"veto": False, "reason": "", "notes": [note]})],
    }
    summary, reg, client = _run(routes, teams=("phase",), rounds=2)
    crit = [e for e in reg.events() if e.get("kind") == EV_CRITIQUE]
    assert crit and crit[0]["notes"] == [note] and not crit[0]["veto"]
    prompts = [m[1]["content"] for k, m in client.seen if k == K["phase"]]
    assert note in prompts[1]
    conf = [m[1]["content"] for k, m in client.seen if k == K["director"]]
    assert any("critic notes: " + note in c for c in conf)
    assert any(note in n for c in reg.claims().values() for n in c.notes)


def test_infrastructure_failures_stop_the_run():
    """Regression: bei HTTP 502 hinter einem Proxy wurden nach dem gescheiterten
    Direktor noch alle Teams aufgerufen (11 Minuten), Exit 0 mit 0 Vorschlägen."""
    down = LLMError("LLM-Aufruf fehlgeschlagen (m1): HTTP 502: Upstream", 502)
    routes = {K["director"]: [down], K["numerical"]: [down], K["phase"]: [down]}
    summary, reg, client = _run(routes, rounds=3)
    assert client.calls == 1 and summary.rounds_done == 1, client.seen
    assert "Infrastruktur" in summary.stop_reason and summary.proposals == 0
    routes = {
        K["director"]: [PLAN],
        K["numerical"]: [down],
        K["phase"]: [down],
        K["reversible"]: [down],
        K["critic"]: [NO_VETO],
    }
    teams = ("numerical", "phase", "reversible")
    summary, _, client = _run(routes, teams=teams, rounds=3)
    assert summary.rounds_done == 1 and client.calls == 4
    assert "3 Fehler in Folge" in summary.stop_reason
    # Modellfehler (HTTP 400) sind keine Infrastrukturstörung
    bad = LLMError("HTTP 400: bad request", 400)
    routes = {K["director"]: [PLAN], K["phase"]: [bad], K["critic"]: [NO_VETO]}
    summary, _, _ = _run(routes, teams=("phase",), rounds=2, conference=False)
    assert summary.rounds_done == 2 and not summary.stop_reason
