"""Richter des Labors: bewertet Kandidaten deterministisch und rein lesend.

Ablauf je Kandidat: (Generator in der Sandbox ausführen) -> ablegen unter SHA-256 ->
parsen -> Kennzahlen -> Registerschema und Q -> Kontrakt auf der ganzen Domäne gegen die
Basis (äquivalent ODER bei invsqrt innerhalb der Toleranz) -> exakter Score (sonst
Schätzung) -> optional offizieller Verifier. Bei jedem Fehlschlag steht ein KONKRETES
Gegenbeispiel im Ergebnis (x und verletzte Eigenschaft). Der Richter ändert oder
repariert nie einen Kandidaten.

Ein Kandidat mit denselben Instruktionen wie die Basis wird nicht bewertet
(`no_change`, kein offizieller Verifier, kein Status). Das Registerschema muss der Basis
exakt entsprechen (Register, Qubits, Namen); stille Ersatzannahmen des Layouts (z. B.
ein unbenanntes Register) sind ein Fehlschlag. Texte aus der Ausgabe eines Generators
werden nie übernommen (`kmx.lab.untrusted`).
"""

from __future__ import annotations

import json
import re
import time
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from kmx.circuit_io import read_circuit
from kmx.cost import compute_metrics, score_estimate
from kmx.lab.claims import EV_EVALUATION, JUDGE_EVALUATOR, official_passed
from kmx.lab.counterexample import (
    OUTCOME_PATTERNS,
    PROP_OTHER,
    PROP_PARSE,
    PROP_Q,
    PROP_REGISTER,
    PROP_SANDBOX,
    Counterexample,
    locate,
    make_counterexample,
    measurement_problem,
)
from kmx.lab.official import run_official
from kmx.lab.registry import Event, Registry
from kmx.lab.sandbox import SandboxLimits, SandboxUnavailable, run_generator
from kmx.lab.untrusted import parse_error_summary, redact
from kmx.layout import analyze_layout
from kmx.ops import KmxError, Op, parse_text
from kmx.session import Session

KIND_KMX, KIND_GENERATOR = "kmx", "generator"
CANDIDATE_KINDS = (KIND_KMX, KIND_GENERATOR)
MAX_CANDIDATE_BYTES = 32 << 20
MAX_GENERATOR_CHARS = 200_000
MAX_CANDIDATE_QUBITS = 4096
GENERATOR_BASELINE_FILE = "baseline.kmx"
GENERATOR_PARAMS_FILE = "params.json"  # Variante einer Parametersuche (nur lesbar)
CONTRACT_EQUIVALENT, CONTRACT_TOLERANCE = "equivalent", "within_tolerance"
NO_CHANGE_MESSAGE = (
    "Kandidat ist identisch mit der Basis (keine Änderung): nicht bewertet, kein "
    "offizieller Verifier"
)
_OFFICIAL_X = re.compile(r"x=(\d+)")


@dataclass
class Evaluation:
    """Ergebnis einer Bewertung (so, wie es ins Protokoll geht)."""

    candidate_kind: str
    passed: bool = False
    candidate_sha256: str | None = None
    generator_sha256: str | None = None
    contract: str | None = None
    message: str = ""
    counterexample: Counterexample | None = None
    metrics: dict[str, Any] = field(default_factory=dict)
    score: float | None = None
    score_kind: str | None = None
    baseline_score: float | None = None
    official: dict[str, Any] | None = None
    duration_s: float = 0.0
    candidate_path: str | None = None  # Ablage im Labor (nicht im Protokoll)
    no_change: bool = False  # identisch mit der Basis: kein Urteil, kein Status
    params: dict[str, Any] | None = None  # Variante einer Parametersuche
    eval_id: str = field(default_factory=lambda: "e-" + uuid.uuid4().hex[:12])

    @property
    def score_delta(self) -> float | None:
        if self.score is None or self.baseline_score is None:
            return None
        return self.score - self.baseline_score

    def event(self, claim_id: str) -> Event:
        event: Event = {
            "kind": EV_EVALUATION,
            "evaluator": JUDGE_EVALUATOR,
            "claim_id": claim_id,
            "eval_id": self.eval_id,
            "candidate_kind": self.candidate_kind,
            "candidate_sha256": self.candidate_sha256,
            "generator_sha256": self.generator_sha256,
            "passed": self.passed,
            "no_change": self.no_change,
            "contract": self.contract,
            "message": self.message,
            "counterexample": self.counterexample,
            "metrics": self.metrics,
            "score": self.score,
            "score_kind": self.score_kind,
            "baseline_score": self.baseline_score,
            "score_delta": self.score_delta,
            "official": self.official,
            "duration_s": round(self.duration_s, 2),
        }
        if self.params is not None:
            event["params"] = self.params
        return event

    def line(self) -> str:
        """Einzeilige Zusammenfassung für die Konsole."""
        if self.no_change:
            return "KEINE ÄNDERUNG - " + NO_CHANGE_MESSAGE
        if not self.passed:
            cx = self.counterexample or {}
            return (
                f"DURCHGEFALLEN [{cx.get('property', '?')}] {cx.get('where', '')} "
                f"- {cx.get('detail', self.message)}"
            )
        delta = self.score_delta
        verdict = "BESTANDEN"
        if self.official is not None:
            ok = official_passed(self.official)
            verdict += " | offiziell " + ("PASS" if ok else "FAIL")
        score = (
            f"{self.score:,.2f} ({self.score_kind})" if self.score is not None else "?"
        )
        return f"{verdict} ({self.contract}) | Score {score}" + (
            f" | Delta {delta:+,.2f}" if delta is not None else ""
        )


class Judge:
    """Bewertet Kandidaten gegen die Basis einer Sitzung (`run_baseline` muss gelaufen
    sein) und legt sie im Labor ab."""

    def __init__(
        self,
        session: Session,
        registry: Registry,
        check_rounds: int = 2,
        verify_cmd: str | None = None,
        limits: SandboxLimits | None = None,
        log: Callable[[str], None] = print,
        input_register: str = "x",
        value_range: str | None = None,
    ) -> None:
        self.session, self.registry, self.log = session, registry, log
        self.rounds, self.verify_cmd = max(1, check_rounds), verify_cmd or None
        self.limits = limits or SandboxLimits()
        self.input_register, self.value_range = input_register, value_range
        self.baseline_score, self.baseline_score_kind = self._score(
            session.orig, session.orig_sig
        )

    def _score(self, ops: Sequence[Op], sig: Any) -> tuple[float | None, str | None]:
        rep = self.session.exact_score(ops)
        if rep is not None:
            return rep.score, "exact"
        if sig is None:
            return None, None
        q = compute_metrics(ops).num_qubits
        est = score_estimate(
            q, sig.tof_mean, sig.t_mean, sig.rot_mean, self.session.opts.rot_weight
        )
        return est, "estimate"

    # Einstieg

    def evaluate(self, kind: str, source: str | bytes) -> Evaluation:
        """Bewertet einen Kandidaten (Schaltkreistext/-bytes oder Generator-Quelltext);
        wirft nie wegen des Kandidaten."""
        ev = Evaluation(candidate_kind=kind, baseline_score=self.baseline_score)
        self._guarded(ev, lambda: self._evaluate_into(ev, kind, source))
        return ev

    def run_variant(
        self, source: str, params: Mapping[str, Any]
    ) -> tuple[Evaluation, bytes | None]:
        """Stufe 1 einer Parametersuche: den Generator mit `params.json` in der
        Sandbox ausführen (noch kein Urteil). Ausgabe None = Absturz, das Ergebnis
        trägt dann schon das Gegenbeispiel."""
        ev = Evaluation(
            candidate_kind=KIND_GENERATOR,
            baseline_score=self.baseline_score,
            params=dict(params),
        )
        extra = {GENERATOR_PARAMS_FILE: json.dumps(ev.params).encode("utf-8")}
        out: list[bytes | None] = [None]

        def step() -> None:
            out[0] = self._materialise(ev, KIND_GENERATOR, source, extra)

        self._guarded(ev, step)
        return ev, out[0]

    def judge_output(self, ev: Evaluation, data: bytes) -> Evaluation:
        """Stufe 2: volle Bewertung einer schon erzeugten Generator-Ausgabe."""
        self._guarded(ev, lambda: self._judge_data(ev, data))
        return ev

    def _guarded(self, ev: Evaluation, step: Callable[[], None]) -> None:
        t0 = time.time()
        try:
            step()
        except Exception as e:  # Kandidat darf den Richter nie abstürzen lassen
            ev.passed = False
            # Nur der Ausnahmetyp: der Text kann vom Kandidaten stammen
            # und ginge sonst an das LLM.
            ev.message = f"Bewertung abgebrochen: {type(e).__name__}"
            ev.counterexample = make_counterexample(PROP_OTHER, ev.message)
        ev.duration_s += time.time() - t0

    def record(self, claim_id: str, ev: Evaluation) -> Event:
        return self.registry.append(ev.event(claim_id))

    # Schritte

    def _fail(self, ev: Evaluation, prop: str, detail: str) -> None:
        ev.passed, ev.message = False, detail
        ev.counterexample = make_counterexample(prop, detail)

    def _evaluate_into(self, ev: Evaluation, kind: str, source: str | bytes) -> None:
        if kind not in CANDIDATE_KINDS:
            return self._fail(ev, PROP_PARSE, f"unbekannte Kandidatenart {kind!r}")
        data = self._materialise(ev, kind, source)
        if data is None:
            return None
        return self._judge_data(ev, data)

    def _judge_data(self, ev: Evaluation, data: bytes) -> None:
        if len(data) > MAX_CANDIDATE_BYTES:
            return self._fail(ev, PROP_PARSE, f"Kandidat zu groß ({len(data)} Bytes)")
        ops = self._store_and_parse(ev, data)
        if ops is None:
            return None
        prior = self._prior_refutation(ev.candidate_sha256)
        if prior is not None:
            # Byte-gleicher Kandidat schon widerlegt: Urteil übernehmen.
            ev.passed, ev.counterexample = False, prior
            short = str(ev.candidate_sha256)[:12]
            ev.message = f"identisch mit bereits widerlegtem Kandidaten {short}"
            return None
        self._judge_ops(ev, ops)
        return None

    def _prior_refutation(self, sha: str | None) -> dict[str, Any] | None:
        """Gegenbeispiel einer früheren Richter-Bewertung desselben Kandidaten-Hashs,
        die inhaltlich (nicht wegen Sandbox/Infrastruktur) durchfiel; sonst None."""
        found = None
        for e in self.registry.events():
            if (
                e.get("kind") == EV_EVALUATION
                and e.get("evaluator") == JUDGE_EVALUATOR
                and e.get("candidate_sha256") == sha
            ):
                cx = (
                    e.get("counterexample")
                    if isinstance(e.get("counterexample"), dict)
                    else None
                )
                official = (
                    e.get("official") if isinstance(e.get("official"), dict) else {}
                )
                failed = (not e.get("passed") and not e.get("no_change")) or (
                    official.get("verifier_status") == "FAIL"
                )
                if failed and cx and cx.get("property") != PROP_SANDBOX:
                    found = cx
        return found

    def _materialise(
        self,
        ev: Evaluation,
        kind: str,
        source: str | bytes,
        extra_inputs: Mapping[str, bytes] | None = None,
    ) -> bytes | None:
        """Schaltkreis-Bytes; Generatoren laufen dazu in der Sandbox."""
        if kind == KIND_KMX:
            return source.encode("utf-8") if isinstance(source, str) else source
        text = source.decode("utf-8") if isinstance(source, bytes) else source
        if len(text) > MAX_GENERATOR_CHARS:
            self._fail(ev, PROP_PARSE, f"Generator zu lang ({len(text)} Zeichen)")
            return None
        ev.generator_sha256, _ = self.registry.store_candidate(
            text.encode("utf-8"), ".py"
        )
        try:
            inputs = {**self._generator_inputs(), **(extra_inputs or {})}
            res = run_generator(text, self.limits, inputs=inputs)
        except SandboxUnavailable as e:
            self._fail(ev, PROP_SANDBOX, str(e))
            return None
        ev.metrics["generator_streams"] = {"stdout": res.stdout, "stderr": res.stderr}
        if not res.ok or res.output is None:
            # nie Rohtext des Generators (Leck über KERN_PROCARGS2, s. untrusted)
            self._fail(ev, PROP_SANDBOX, f"Generator: {res.failure()}")
            return None
        return res.output

    def _generator_inputs(self) -> dict[str, bytes]:
        """Schreibgeschützte Eingaben für Generatoren: die Basis als baseline.kmx."""
        with open(self.registry.baseline_path(), "rb") as f:
            return {GENERATOR_BASELINE_FILE: f.read()}

    def _store_and_parse(self, ev: Evaluation, data: bytes) -> list[Op] | None:
        """Legt den Kandidaten unverändert ab (.kmx oder .kmb) und parst ihn."""
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            text = None
        suffix = ".kmx" if text is not None else ".kmb"
        ev.candidate_sha256, path = self.registry.store_candidate(data, suffix)
        ev.candidate_path = path
        try:
            return parse_text(text) if text is not None else read_circuit(path)
        except KmxError as e:
            # Generator-Ausgabe: ohne zitierten Zeilentext (könnte Geheimnisse tragen)
            detail = parse_error_summary(str(e)) if ev.generator_sha256 else str(e)
            self._fail(ev, PROP_PARSE, f"Formatfehler: {detail}")
            return None

    def _schema_problem(self, ops: Sequence[Op]) -> tuple[str, str] | None:
        base = self.session.layout
        q = compute_metrics(ops).num_qubits
        if q > MAX_CANDIDATE_QUBITS:
            return (
                PROP_Q,
                f"Q über der Obergrenze {MAX_CANDIDATE_QUBITS}",
            )  # Wert nie zurückmelden (Leckkanal)
        try:
            cand = analyze_layout(ops, self.input_register, self.value_range)
        except KmxError:
            return PROP_REGISTER, "Registerschema ungültig"
        if cand.input_qubits != base.input_qubits or cand.pinned != base.pinned:
            return PROP_REGISTER, (
                "Registerschema weicht ab (Eingabe- oder Register-Qubits anders "
                "als in der Basis)"
            )
        if cand.names != base.names:
            return PROP_REGISTER, (
                "Registernamen weichen von der Basis ab (REGISTER-Deklaration mit "
                f"Name wie in der Basis, z. B. {_first_name(base.names)})"
            )
        if cand.registers != base.registers:
            return (
                PROP_REGISTER,
                "Registerdeklarationen (APPEND_TO_REGISTER) weichen ab",
            )
        extra = [n for n in cand.notes if n not in base.notes]
        if extra:
            return PROP_REGISTER, "Registerschema nur per Ersatzannahme: " + extra[0]
        return None

    def _is_baseline(self, ops: Sequence[Op]) -> bool:
        orig = self.session.orig
        return len(ops) == len(orig) and all(
            a.fmt() == b.fmt() for a, b in zip(ops, orig, strict=True)
        )

    def _judge_ops(self, ev: Evaluation, ops: list[Op]) -> None:
        if self._is_baseline(ops):
            ev.passed, ev.no_change, ev.message = False, True, NO_CHANGE_MESSAGE
            return None
        problem = self._schema_problem(ops)
        if problem:
            return self._fail(ev, *problem)
        # Kennzahlen erst nach den Schranken speichern, sonst trägt Q
        # beliebig große Zahlen nach außen.
        m = compute_metrics(ops)
        ev.metrics.update(q=m.num_qubits, toffoli=m.toffoli, n_ops=len(ops))
        seeds = range(self.rounds)
        ok, msg, sig = self.session.oracle.check(ops, seeds)
        if ok:
            ev.contract = CONTRACT_EQUIVALENT
        elif self.session.layout.invsqrt:
            tol_ok, msg = self.session.tolerance_check(ops, self.rounds)
            ev.contract = CONTRACT_TOLERANCE if tol_ok else None
        ev.message = msg
        if ev.contract is None:
            ev.passed = False
            ev.counterexample = locate(self.session, ops, seeds) or make_counterexample(
                PROP_OTHER, msg
            )
            return None
        problem_cx = measurement_problem(self.session, ops)
        if problem_cx is not None:
            ev.passed, ev.contract, ev.counterexample = False, None, problem_cx
            ev.message = problem_cx["detail"]
            return None
        ev.message = (
            f"{msg}; Messunabhängigkeit gestichprobt ({self.rounds} Zufallsrunden + "
            f"{len(OUTCOME_PATTERNS)} feste Muster), Endurteil: offizieller Verifier"
        )
        ev.passed = True
        ev.score, ev.score_kind = self._score(ops, sig)
        if sig is not None:
            ev.metrics.update(toffoli_mean=sig.tof_mean, rotations_mean=sig.rot_mean)
        if self.verify_cmd:
            self._run_official(ev)
        return None

    def _run_official(self, ev: Evaluation) -> None:
        self.log(f"  offizieller Verifier läuft: {self.verify_cmd}")
        ev.official = run_official(self.verify_cmd, ev.candidate_path or "")
        for warning in ev.official.get("warnings") or ():
            self.log(f"  WARNUNG: {warning}")
        code = ev.official.get("exit_code")
        if not official_passed(ev.official):
            tail = redact(
                str(ev.official.get("output_tail") or ev.official.get("error", ""))
            )
            hit = _OFFICIAL_X.search(tail)
            ev.counterexample = make_counterexample(
                "official",
                f"offizieller Verifier: Exit {code}, Urteil "
                f"{ev.official.get('verifier_status') or 'fehlt'}: {tail[-300:]}",
                int(hit.group(1)) if hit else None,
            )


def _first_name(names: dict[int, str]) -> str:
    if not names:
        return "(keine)"
    r = min(names)
    return f'REGISTER r{r} "{names[r]}"'
