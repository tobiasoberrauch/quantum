"""Labor: kompaktes Dossier für die Teams (kmx.lab.dossier) und Q/C mit Pareto-Front
in `lab status` (kmx.lab.report)."""

import atexit
import shutil
import tempfile

import kmx.lab.dossier as dossier_mod
from kmx.lab.claims import EV_EVALUATION, EV_LAB, JUDGE_EVALUATOR
from kmx.lab.dossier import DOSSIER_MAX_CHARS, baseline_dossier, lab_dossier
from kmx.lab.report import pareto_front, status_report
from kmx.lab.rounds import LabRun, RunOptions
from tests.kmx.fakes import RoutingFakeClient
from tests.kmx.helpers import patched
from tests.kmx.lab_helpers import GOOD_TEXT, TEAM_KEYS, make_lab, proposal, reply

K = TEAM_KEYS


def _lab():
    d = tempfile.mkdtemp()
    atexit.register(shutil.rmtree, d, True)
    return make_lab(d)


def test_baseline_dossier_has_q_score_and_hotspots():
    reg, judge = _lab()
    text = baseline_dossier(judge.session, judge.baseline_score, "exact")
    assert "Q=10" in text and "C=4.00" in text and "40.00 (exact)" in text, text
    hot = [x for x in text.splitlines() if "Toffoli" in x and "idx" in x]
    assert hot and "1 Toffoli" in hot[0], text
    assert len(text) <= DOSSIER_MAX_CHARS
    full = lab_dossier(text, reg)
    assert "best experimental: -" in full
    ev = judge.evaluate("kmx", GOOD_TEXT)
    judge.record(reg.add_hypothesis("c", "team:phase"), ev)
    full = lab_dossier(text, reg)
    assert "best experimental: score 40.00, Q=10, C=4.00" in full, full
    with patched(dossier_mod, "DOSSIER_MAX_CHARS", 120):
        capped = lab_dossier(text, reg)
    assert len(capped) <= 120 and capped.startswith("BASELINE DOSSIER")


def test_team_prompt_contains_the_dossier():
    reg, judge = _lab()
    routes = {
        K["director"]: [reply({"focus": {}})],
        K["phase"]: [proposal(GOOD_TEXT)],
    }
    client = RoutingFakeClient(routes)
    opts = RunOptions(["m"], 1, ("phase",), 10, critic=False, conference=False)
    LabRun(reg, judge, client, opts, "SPEC", log=lambda *_: None).run()
    prompt = next(m[1]["content"] for k, m in client.seen if k == K["phase"])
    assert "BASELINE DOSSIER" in prompt and "Q=10" in prompt


def _ev(cid, sha, q, score, passed=True):
    return {
        "kind": EV_EVALUATION,
        "evaluator": JUDGE_EVALUATOR,
        "claim_id": cid,
        "candidate_sha256": sha,
        "passed": passed,
        "metrics": {"q": q},
        "score": score,
        "baseline_score": 40.0,
    }


def test_pareto_front_over_q_and_c():
    pts = [(10, 4.0, "Basis"), (8, 5.0, "a"), (12, 3.0, "b"), (9, 6.0, "c")]
    assert [p[2] for p in pareto_front(pts)] == ["a", "Basis", "b"]
    reg, _ = _lab()
    reg.append({"kind": EV_LAB, "action": "baseline", "baseline_score": 40.0, "q": 10})
    ids = [reg.add_hypothesis(n, "team:phase") for n in "abcd"]
    reg.append(_ev(ids[0], "1" * 64, 8, 40.0))
    reg.append(_ev(ids[1], "2" * 64, 12, 36.0))
    reg.append(_ev(ids[2], "3" * 64, 9, 54.0))
    reg.append(_ev(ids[3], "4" * 64, 7, 7.0, passed=False))  # zählt nicht
    report = status_report(reg)
    assert f"{ids[1]} Q=12 C=3.00 Score=36.00" in report, report
    front = next(x for x in report.splitlines() if x.startswith("Pareto-Front"))
    assert "Basis Q=10 C=4.00" in front and ids[0] in front and ids[1] in front
    assert ids[2] not in front and ids[3] not in report.split("Q/C")[1]
