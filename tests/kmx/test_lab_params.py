"""Labor: deterministische Parametersuche über ein Raster eines Generators
(kmx.lab.teams.parse_param_grid, kmx.lab.paramsearch, LabRun)."""

import atexit
import shutil
import tempfile

import kmx.lab.sandbox as sandbox
from kmx.lab.claims import EV_EVALUATION, EXPERIMENTAL, HYPOTHESIS, REFUTED
from kmx.lab.paramsearch import BUDGET_NOTE, FULL_JUDGE_TOP_K, rank_variants
from kmx.lab.rounds import LabRun, RunOptions
from kmx.lab.teams import MAX_VARIANTS, param_variants, parse_proposal
from tests.kmx.fakes import RoutingFakeClient
from tests.kmx.lab_helpers import TEAM_KEYS, make_lab, reply

K = TEAM_KEYS
# hängt 2k Kopien von CCX q0 q1 q8 an (heben sich auf): äquivalent, Toffoli 4 + 2k
GEN = (
    "import json, sys\n"
    'p = json.load(open("params.json"))\n'
    'k = int(p["k"])\n'
    'base = open("baseline.kmx").read()\n'
    'open(sys.argv[1], "w").write(base + "CCX q0 q1 q8\\n" * (2 * k))\n'
)


def _cand(params, kind="generator", source=GEN):
    return {"kind": kind, "source": source, "rationale": "r", "params": params}


def _parse(params, kind="generator"):
    return parse_proposal("numerical", {"candidate": _cand(params, kind)}, set())


def test_param_grid_limits():
    ok = _parse({"k": [1, 2], "mode": ["a", "b"], "eps": [0.5]})
    assert ok.candidate.params == {"k": [1, 2], "mode": ["a", "b"], "eps": [0.5]}
    assert not ok.problems
    assert param_variants(ok.candidate.params) == [
        {"k": 1, "mode": "a", "eps": 0.5},
        {"k": 1, "mode": "b", "eps": 0.5},
        {"k": 2, "mode": "a", "eps": 0.5},
        {"k": 2, "mode": "b", "eps": 0.5},
    ]
    bad = (
        {f"k{i}": [1] for i in range(5)},  # > 4 Schlüssel
        {"k": list(range(9))},  # > 8 Werte
        {"a": [1, 2, 3], "b": [1, 2, 3], "c": [1, 2]},  # 18 > MAX_VARIANTS
        {"k": [[1, 2]]},  # kein Skalar
        {"k": [{"x": 1}]},
        {"../x": [1]},  # kein Bezeichner
        {"k": []},
        {"k": [float("inf")]},
        {"k": ["x" * 200]},
        [1, 2],
        {},
    )
    for params in bad:
        p = _parse(params)
        assert p.candidate is not None and p.candidate.params is None, params
        assert any("params verworfen" in x for x in p.problems), (params, p.problems)
    assert 3 * 3 * 2 > MAX_VARIANTS
    p = _parse({"k": [1]}, kind="kmx")
    assert p.candidate.params is None and any("params" in x for x in p.problems)
    p = parse_proposal("numerical", {"candidate": _cand(None)}, set())
    assert p.candidate.params is None and not p.problems


def test_ranking_uses_estimate_only_for_order_and_dedupes():
    # (Index, Ausgabe-SHA, Schätzung); None = nicht schätzbar (zuletzt)
    items = [(0, "a", 50.0), (1, "b", 30.0), (2, "a", 50.0), (3, "c", None)]
    items += [(4, "d", 40.0), (5, "e", 10.0)]
    judged, duplicates, skipped = rank_variants(items, FULL_JUDGE_TOP_K)
    assert judged == [5, 1, 4] and duplicates == {2: 0} and skipped == [0, 3]


def _run_with(params, source=GEN):
    d = tempfile.mkdtemp()
    atexit.register(shutil.rmtree, d, True)
    reg, judge = make_lab(d)
    obj = {"claims": [], "candidate": _cand(params, source=source)}
    routes = {
        K["director"]: [reply({"focus": {}})],
        K["numerical"]: [reply(obj)],
    }
    run = LabRun(
        reg,
        judge,
        RoutingFakeClient(routes),
        RunOptions(["m"], 1, ("numerical",), 10, critic=False, conference=False),
        "SPEC",
        log=lambda *_: None,
    )
    return run.run(), reg


def _skip():
    if sandbox.sandbox_available():
        return False
    print("ÜBERSPRUNGEN: sandbox-exec fehlt; Parametersuche nicht ausgeführt")
    return True


def test_param_search_judges_only_the_cheapest_variants():
    if _skip():
        return
    summary, reg = _run_with({"k": [5, 1, 4, 2, 3]})
    evals = [e for e in reg.events() if e.get("kind") == EV_EVALUATION]
    # params.json erreichte den Generator: die Toffoli-Zahl folgt k
    judged = sorted(e["params"]["k"] for e in evals)
    assert judged == [1, 2, 3] and len(summary.evaluations) == FULL_JUDGE_TOP_K
    assert all(
        e["passed"] and e["metrics"]["toffoli"] == 4 + 2 * e["params"]["k"]
        for e in evals
    )
    claims = list(reg.claims().values())
    team = [c for c in claims if c.introduced_by == "team:numerical"]
    exp = [c for c in team if c.status == EXPERIMENTAL]
    assert len(exp) == 3 and all('"k":' in c.claim for c in exp)
    (parent,) = [c for c in team if c.status == HYPOTHESIS]
    budget = [n for n in parent.notes if BUDGET_NOTE in n]
    assert len(budget) == 2 and any('"k": 5' in n for n in budget), parent.notes
    assert all("Schätzung" in n for n in budget)


def test_param_search_judges_identical_outputs_once_and_keeps_crashes():
    if _skip():
        return
    summary, reg = _run_with({"k": [1, "boom"], "unused": [0, 1]})
    evals = [e for e in reg.events() if e.get("kind") == EV_EVALUATION]
    passed = [e for e in evals if e["passed"]]
    assert len(passed) == 1 and passed[0]["params"] == {"k": 1, "unused": 0}
    crashed = [e for e in evals if not e["passed"]]
    assert len(crashed) == 2  # Absturz wie bisher: Gegenbeispiel 'sandbox'
    assert all(e["counterexample"]["property"] == "sandbox" for e in crashed)
    assert all("ValueError" in e["message"] for e in crashed)
    claims = reg.claims().values()
    assert sum(c.status == REFUTED for c in claims if "variant" in c.claim) == 2
    notes = [n for c in claims for n in c.notes]
    assert any("byte-gleich" in n and '"unused": 1' in n for n in notes), notes
