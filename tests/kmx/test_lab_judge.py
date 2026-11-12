"""Labor: Richter mit konkreten Gegenbeispielen, offizieller Verifier mit Beleg und
robustes Auslesen von Modellantworten (kmx.lab.judge, kmx.lab.counterexample,
kmx.lab.official, kmx.lab.llm_json)."""

import os
import subprocess
import sys
import tempfile

import kmx.lab.judge as judge_mod
import kmx.lab.sandbox as sandbox
from kmx.lab.claims import EXPERIMENTAL, HYPOTHESIS, REFUTED, VERIFIED
from kmx.lab.llm_json import extract_json, message_text
from kmx.lab.registry import Registry
from kmx.lab.report import prompt_summary, team_feedback
from tests.kmx.helpers import HEAD, MBU_BODY, env, patched
from tests.kmx.lab_helpers import (
    BAD_PHASE_TEXT,
    BASE_TEXT,
    CLOBBER_TEXT,
    DIRTY_TEXT,
    GOOD_TEXT,
    fake_verifier_cmd,
    make_lab,
)


def _evaluate(text, verify_cmd=None, kind="kmx", check_rounds=2):
    with tempfile.TemporaryDirectory() as d:
        reg, judge = make_lab(d, verify_cmd, check_rounds)
        ev = judge.evaluate(kind, text)
        cid = reg.add_hypothesis("candidate", "team:phase")
        judge.record(cid, ev)
        return ev, reg.claims()[cid]


def test_equivalent_candidate_passes_and_is_experimental():
    ev, claim = _evaluate(GOOD_TEXT)
    assert ev.passed and ev.contract == "equivalent" and ev.counterexample is None
    assert ev.score == ev.baseline_score == 40.0 and ev.score_delta == 0.0
    assert ev.metrics["q"] == 10 and ev.metrics["toffoli"] == 4
    assert claim.status == EXPERIMENTAL and claim.best_score == 40.0


def test_counterexamples_name_x_and_property():
    cases = (
        (BAD_PHASE_TEXT, "phase", 1),  # Z q0: erste ungerade Eingabe
        (DIRTY_TEXT, "scratch", 4),  # CX q2 q9: erste Eingabe mit Bit 2
        (CLOBBER_TEXT, "register", 2),  # CX q1 q3: erste Eingabe mit Bit 1
    )
    for text, prop, x in cases:
        ev, claim = _evaluate(text)
        cx = ev.counterexample
        assert not ev.passed and cx["property"] == prop and cx["x"] == x, (prop, cx)
        assert cx["affected_lanes"] > 0 and cx["where"] == f"x={x}"
        assert claim.status == REFUTED and claim.counterexamples == [cx]
        assert ev.score is None


def test_parse_and_schema_failures():
    ev, _ = _evaluate(HEAD + "CX q3 q3\n")
    assert ev.counterexample["property"] == "parse" and "Formatfehler" in ev.message
    no_register = "\n".join(MBU_BODY) + "\n"
    ev, _ = _evaluate(no_register)
    assert ev.counterexample["property"] == "register"
    with patched(judge_mod, "MAX_CANDIDATE_QUBITS", 5):
        ev, _ = _evaluate(GOOD_TEXT)
    assert ev.counterexample["property"] == "Q"
    ev, _ = _evaluate(GOOD_TEXT, kind="python")
    assert not ev.passed and ev.counterexample["property"] == "parse"


def test_judge_never_modifies_the_candidate():
    with tempfile.TemporaryDirectory() as d:
        reg, judge = make_lab(d)
        text = GOOD_TEXT + "\n# Kommentar bleibt\n"
        ev = judge.evaluate("kmx", text)
        with open(ev.candidate_path, encoding="utf-8") as f:
            assert f.read() == text
        assert os.path.basename(ev.candidate_path) == ev.candidate_sha256 + ".kmx"


def test_official_verifier_evidence_makes_verified():
    with tempfile.TemporaryDirectory() as d:
        cmd = fake_verifier_cmd(d)
        ev, claim = _evaluate(GOOD_TEXT, cmd)
        script = os.path.join(d, "fake_verify.py")
    off = ev.official
    assert off["exit_code"] == 0 and off["candidate_sha256"] == ev.candidate_sha256
    assert len(off["output_sha256"]) == 64 and off["python_version"]
    assert off["kmx_version"] == "5" and "fake_verify.py" in off["command"]
    assert off["verifier_status"] == "PASS" and off["warnings"] == []
    assert len(off["tool_sha256"][script]) == 64
    assert claim.status == VERIFIED and claim.proof_artifacts == [off]
    assert "offiziell PASS" in ev.line()


def test_exit_zero_without_pass_verdict_is_not_verified():
    """Regression: `true`, `echo PASS` oder `verify ... | tail` (Exit 0) hoben die
    Behauptung auf verified, obwohl das Urteil FAIL war oder fehlte."""
    for cmd in ("true", "echo PASS", "grep -q CCX {out}"):
        ev, claim = _evaluate(GOOD_TEXT, cmd)
        assert claim.status == EXPERIMENTAL, (cmd, claim.status)
        assert "offiziell FAIL" in ev.line()
    fail = '{"status": "FAIL", "error": "Expected 22 x qubits, got 6."}'
    ev, claim = _evaluate(GOOD_TEXT, f"echo '{fail}' | tail -n 20; #")
    assert ev.official["exit_code"] == 0 and claim.status == REFUTED
    assert ev.official["warnings"] and ev.counterexample["property"] == "official"


def test_official_verifier_failure_refutes_with_counterexample():
    verdict = '{"status": "FAIL", "error": "x=77: bad"}'
    cmd = f"echo '{verdict}'; exit 1; #"
    ev, claim = _evaluate(GOOD_TEXT, cmd)
    assert ev.passed and ev.official["exit_code"] == 1
    assert ev.official["verifier_status"] == "FAIL"
    assert ev.counterexample["property"] == "official" and ev.counterexample["x"] == 77
    assert claim.status == REFUTED


def test_official_verifier_skipped_for_failed_contract():
    ev, _ = _evaluate(BAD_PHASE_TEXT, "true")
    assert ev.official is None and not ev.passed


def test_generator_candidate_is_judged_after_the_sandbox():
    gen = f"import sys\nopen(sys.argv[1], 'w').write({GOOD_TEXT!r})\n"
    if not sandbox.sandbox_available():
        ev, _ = _evaluate(gen, kind="generator")
        assert ev.counterexample["property"] == "sandbox"
        print("ÜBERSPRUNGEN: sandbox-exec fehlt; Generator wurde verweigert")
        return
    ev, claim = _evaluate(gen, kind="generator")
    assert ev.passed and ev.generator_sha256 and claim.status == EXPERIMENTAL
    ev, _ = _evaluate("raise RuntimeError('kaputt')\n", kind="generator")
    assert ev.counterexample["property"] == "sandbox"
    assert "RuntimeError in generator.py Zeile 1" in ev.message
    assert "kaputt" not in ev.message  # kein Rohtext des Generators


def test_sandbox_unavailable_refuses_generators():
    with patched(sandbox, "sandbox_available", lambda: False):
        ev, _ = _evaluate("print(1)", kind="generator")
    assert ev.counterexample["property"] == "sandbox" and "nicht" in ev.message


def test_extract_json_is_robust():
    assert extract_json('{"a": 1}') == ({"a": 1}, "")
    assert extract_json('text ```json\n{"a": [1, {"b": 2}]}\n``` more')[0] == {
        "a": [1, {"b": 2}]
    }
    assert extract_json('<think>{nope}</think> sure: {"ok": true} trailing')[0] == {
        "ok": True
    }
    assert extract_json("{kaputt")[0] is None
    assert extract_json("")[1] == "leere Antwort"
    assert extract_json("[1, 2]")[0] is None
    assert message_text({"content": None}) == "" and message_text(None) == ""
    assert message_text({"content": [{"text": "a"}, {"text": "b"}]}) == "ab"


def _conditioned_z(k):
    """GOOD_TEXT + k Messungen frischer Qubits + Z q0 nur wenn ALLE k Bits = 1."""
    lines = [f"HMR q{20 + i} b{i}" for i in range(k)]
    lines += [f"PUSH_CONDITION if b{i}" for i in range(k)] + ["Z q0"]
    lines += ["POP_CONDITION"] * k
    return GOOD_TEXT + "\n".join(lines) + "\n"


def test_phase_conditioned_on_many_measurements_is_refuted():
    """Regression: Z unter 12 verschachtelten Messbedingungen bestand als
    experimental, weil Zufallsrunden 'alle 12 Bits = 1' fast nie ziehen."""
    ev, claim = _evaluate(_conditioned_z(12), check_rounds=8)
    assert not ev.passed and claim.status == REFUTED, ev.line()
    cx = ev.counterexample
    assert cx["property"] == "measurement" and cx["x"] == 1, cx
    assert "alle Messbits 1" in cx["detail"]


def test_measurement_with_correction_still_passes():
    mbu = GOOD_TEXT + "CX q0 q20\nHMR q20 b1\nZ q0 if b1\nHMR q21 b2\n"
    ev, claim = _evaluate(mbu)
    assert ev.passed and claim.status == EXPERIMENTAL, ev.line()
    assert "gestichprobt" in ev.message


def test_unnamed_or_renamed_register_is_rejected():
    """Regression: aus REGISTER r0 "x" wurde REGISTER r0; das Layout fiel still auf
    r0 zurück, der Richter meldete BESTANDEN, der offizielle Verifier FAIL."""
    body = "\n".join(MBU_BODY + ["X q4", "X q4"]) + "\n"
    for head in (HEAD.replace(' "x"', ""), HEAD.replace('"x"', '"y"')):
        ev, claim = _evaluate(head + body, "true")
        assert not ev.passed and ev.counterexample["property"] == "register", ev
        assert ev.official is None and claim.status == REFUTED
        assert "Registernamen" in ev.message


def test_candidate_identical_to_baseline_is_not_judged():
    """Regression: Platzhalter (Kopie der Basis) liefen durch den offiziellen
    Verifier (~150 s) und wurden zu 'verified' mit Delta 0."""
    with tempfile.TemporaryDirectory() as d:
        cmd = fake_verifier_cmd(d)
        for text in (BASE_TEXT, BASE_TEXT + "# nur ein Kommentar\n"):
            ev, claim = _evaluate(text, cmd)
            assert ev.no_change and not ev.passed and ev.official is None, ev.line()
            assert ev.score is None and ev.counterexample is None
            assert claim.status == HYPOTHESIS and "KEINE ÄNDERUNG" in ev.line()
        os.mkdir(d + "/fb")
        reg, judge = make_lab(d + "/fb")
        cid = reg.add_hypothesis("candidate", "team:phase")
        judge.record(cid, judge.evaluate("kmx", BASE_TEXT))
        (item,) = team_feedback(reg, ("phase",))["phase"]
        assert "identical to the baseline" in item


LEAK_GENERATOR = """import ctypes, os, sys
libc = ctypes.CDLL("/usr/lib/libSystem.B.dylib")
mib = (ctypes.c_int * 3)(1, 49, os.getppid())  # CTL_KERN, KERN_PROCARGS2
size = ctypes.c_size_t(1 << 20)
buf = ctypes.create_string_buffer(size.value)
libc.sysctl(mib, 3, buf, ctypes.byref(size), None, 0)
leak = [x for x in buf.raw[: size.value].split(b"\\0") if b"KMX_LEAK_PROBE=" in x]
text = b" ".join(leak).decode()
print("EXFIL", text)
sys.stderr.write("EXFIL " + text + "\\n")
if MODE == "crash":
    raise ValueError("EXFIL " + text)
open(sys.argv[1], "w").write("LEAK " + text + "\\n")
"""

LEAK_DRIVER = """import sys
from tests.kmx.lab_helpers import make_lab
reg, judge = make_lab(sys.argv[1])
for mode in ("crash", "parse"):
    src = "MODE = %r\\n" % mode + open(sys.argv[2]).read()
    ev = judge.evaluate("generator", src)
    cid = reg.add_hypothesis("leak probe " + mode, "team:phase")
    judge.record(cid, ev)
    print(ev.line())
"""


def test_parent_environment_does_not_leak_via_procargs():
    """Regression (kritisch): ein Generator las per sysctl(KERN_PROCARGS2) die
    Start-Umgebung des Laborprozesses; über stdout/stderr landeten Schlüssel in
    Gegenbeispiel, events.jsonl und Prompts."""
    if not sandbox.sandbox_available():
        print("ÜBERSPRUNGEN: sandbox-exec fehlt")
        return
    marker = "KMX-LEAK-MARKER-7f3a91c2"
    with tempfile.TemporaryDirectory() as d:
        gen = os.path.join(d, "leak_gen.py")  # Datei, nicht argv (argv steht in
        with open(gen, "w", encoding="utf-8") as f:  # KERN_PROCARGS2 mit drin)
            f.write(LEAK_GENERATOR)
        proc = subprocess.run(
            [sys.executable, "-c", LEAK_DRIVER, d, gen],
            cwd=sandbox.PACKAGE_ROOT,
            env={**os.environ, "KMX_LEAK_PROBE": marker},
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert proc.returncode == 0, proc.stderr[-2000:]
        assert marker not in proc.stdout, proc.stdout
        reg = Registry.open(os.path.join(d, "lab"))
        with open(reg.events_path, encoding="utf-8") as f:
            events = f.read()
        assert marker not in events and "EXFIL" not in events
        assert marker not in prompt_summary(reg, 40.0)
        assert marker not in str(team_feedback(reg, ("phase",)))
        assert "ValueError" in events and "Zeile 1: unbekannte Instruktion" in events
        # Gegenprobe: der Generator konnte den Marker tatsächlich lesen
        stored = os.listdir(os.path.join(reg.lab_dir, "candidates"))
        texts = [
            open(os.path.join(reg.lab_dir, "candidates", n)).read() for n in stored
        ]
        assert any(marker in t for t in texts if t.startswith("LEAK"))


def test_registry_redacts_secret_environment_values():
    with tempfile.TemporaryDirectory() as d:
        reg, _ = make_lab(d)
        with env(LLM_API_KEY="sk-geheim-0123456789"):
            reg.append({"kind": "note", "text": "key sk-geheim-0123456789", "x": [1]})
        with open(reg.events_path, encoding="utf-8") as f:
            text = f.read()
    assert "sk-geheim" not in text and "[ENTFERNT]" in text


def test_candidate_values_never_reach_messages():
    """Regression (security r2, HIGH): ein Generator konnte Geheimnisse als riesigen
    Qubit-Index oder als Unicode-Ziffern kodieren; Q-Wert bzw. ValueError-Text landeten
    wörtlich in Gegenbeispiel, events.jsonl und damit im LLM-Prompt."""
    secret = "1009778563006007593019865891951649460861309926798606095507"
    for text in (f"X q{secret}\n", f"X q{secret[:20]}²\n", "X q4097\nX q0\n"):
        gen = f"import sys\nopen(sys.argv[1], 'w').write({(GOOD_TEXT + text)!r})\n"
        if not sandbox.sandbox_available():
            print("ÜBERSPRUNGEN: sandbox-exec fehlt")
            return
        ev, _ = _evaluate(gen, kind="generator")
        blob = ev.line() + str(ev.message) + str(ev.counterexample) + str(ev.metrics)
        assert not ev.passed, ev.line()
        assert secret[:12] not in blob and "4097" not in blob, blob


def test_truncated_reply_is_not_an_inner_object():
    """Regression (live): am Token-Limit abgeschnittene Antwort lieferte ein inneres
    Claim-Objekt als scheinbar gültigen Vorschlag."""
    cut = '{"claims": [{"claim": "a", "assumptions": []}, {"claim": "b", "assu'
    obj, why = extract_json(cut)
    assert obj is None and "abgeschnitten" in why


def test_identical_refuted_candidate_is_not_rejudged():
    """Regression (live): byte-gleicher, schon widerlegter Kandidat wurde erneut
    voll geprüft und als neue Widerlegung gezählt."""
    with tempfile.TemporaryDirectory() as d:
        reg, judge = make_lab(d)
        first = judge.evaluate("kmx", BAD_PHASE_TEXT)
        judge.record(reg.add_hypothesis("candidate", "team:phase"), first)
        second = judge.evaluate("kmx", BAD_PHASE_TEXT)
        cid = reg.add_hypothesis("candidate again", "team:phase")
        judge.record(cid, second)
        assert not second.passed and "bereits widerlegt" in second.message
        assert second.counterexample == first.counterexample
        assert reg.claims()[cid].status == REFUTED
