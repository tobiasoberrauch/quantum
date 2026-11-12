"""CEGIS-Runden des Labors: Direktor plant -> Teams schlagen parallel vor -> Quelltext
wird unter SHA-256 abgelegt -> Kritiker kommentiert (Veto nur beratend, mit konkretem
Grund) -> Richter bewertet IMMER -> Protokoll -> Gegenbeispiele gehen in die nächste
Runde -> Konferenz destilliert wiederverwendbare Einsichten.

Entschieden wird nur durch den Richter; ein Kritiker-Veto ist ein Kommentar neben dem
Urteil. Die Behauptung zu einem Kandidaten ist maschinell formuliert; die Begründung
des Teams steht nur als Notiz daneben (keine Beförderung durch Rhetorik). Rückmeldungen
an die Teams werden aus dem Protokoll gebildet (`team_feedback`), gelten also auch über
mehrere `lab run` hinweg.

Modellausgaben werden nur als Hypothesen und Notizen abgelegt; unlesbare Antworten
zählen als fehlgeschlagener Versuch (EV_ATTEMPT), nie als Absturz. Budgets: Runden,
höchstens `max_calls` LLM-Aufrufe (LLM_MAX_CALLS), Timeout je Aufruf im Client. Ist der
Endpunkt nicht erreichbar, endet der Lauf sauber mit Meldung; ebenso nach
`TRANSPORT_FAILURES_TO_STOP` Infrastrukturfehlern in Folge (HTTP 5xx/408/429, Timeout)
oder sobald die Planung des Direktors an der Infrastruktur scheitert.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Protocol

from kmx.agent.client import LLMError
from kmx.lab.claims import EV_ATTEMPT, EV_CRITIQUE, EV_ROUND
from kmx.lab.dossier import baseline_dossier, lab_dossier
from kmx.lab.judge import KIND_GENERATOR, Evaluation, Judge
from kmx.lab.llm_json import extract_json, message_text
from kmx.lab.paramsearch import CRASHED, JUDGED, outcome_note, params_text, search
from kmx.lab.registry import Registry
from kmx.lab.report import (
    PARSER_NOTE_PREFIX,
    counterexample_line,
    prompt_summary,
    team_feedback,
)
from kmx.lab.seeds import FRONTIER_NOTE
from kmx.lab.teams import (
    CRITIC,
    DIRECTOR,
    RESEARCH_TEAMS,
    Proposal,
    parse_critique,
    parse_focus,
    parse_insights,
    parse_proposal,
    system_prompt,
)

CANDIDATE_PREVIEW_CHARS = 3000
FEEDBACK_ITEMS = 6
RAW_EXCERPT_CHARS = 400
DEFAULT_FOCUS = "Follow your world view; propose one falsifiable step."
TRANSPORT_FAILURES_TO_STOP = 3
_TRANSIENT_HTTP = (408, 429)


def is_transport_error(e: LLMError) -> bool:
    """Infrastruktur statt Modell: kein HTTP-Status (Timeout, Verbindung, kaputte
    Antwort), 5xx, 408 oder 429."""
    code = getattr(e, "code", None)
    return code is None or code >= 500 or code in _TRANSIENT_HTTP


class ChatClient(Protocol):
    def chat(self, model: str, messages: list[dict[str, Any]]) -> dict[str, Any]: ...


class BudgetExhausted(RuntimeError):
    """LLM-Aufrufbudget verbraucht."""


@dataclass
class RunOptions:
    models: list[str]
    rounds: int = 1
    teams: tuple[str, ...] = RESEARCH_TEAMS
    max_calls: int = 40
    critic: bool = True
    conference: bool = True


@dataclass
class RunSummary:
    rounds_done: int = 0
    llm_calls: int = 0
    proposals: int = 0
    failed_attempts: int = 0
    vetoes: int = 0
    evaluations: list[Evaluation] = field(default_factory=list)
    stop_reason: str = ""


class LLMGate:
    """Threadsicheres Aufrufbudget vor dem Client; liefert (JSON, Fehler, Rohtext)."""

    def __init__(self, client: ChatClient, max_calls: int) -> None:
        self.client, self.max_calls = client, max_calls
        self.calls, self._lock = 0, threading.Lock()

    def ask(
        self, model: str, role: str, user: str
    ) -> tuple[dict[str, Any] | None, str, str]:
        with self._lock:
            if self.calls >= self.max_calls or getattr(self.client, "dead", False):
                raise BudgetExhausted(f"LLM-Budget erschöpft ({self.max_calls})")
            self.calls += 1
        messages = [
            {"role": "system", "content": system_prompt(role)},
            {"role": "user", "content": user},
        ]
        text = message_text(self.client.chat(model, messages))
        obj, err = extract_json(text)
        return obj, err, text


class LabRun:
    """Ein Lauf über mehrere Runden auf einem Labor."""

    def __init__(
        self,
        registry: Registry,
        judge: Judge,
        client: ChatClient,
        opts: RunOptions,
        spec_text: str,
        log: Callable[[str], None] = print,
    ) -> None:
        self.registry, self.judge, self.opts = registry, judge, opts
        self.gate = LLMGate(client, opts.max_calls)
        self.client, self.spec_text, self.log = client, spec_text, log
        # Behauptungen dieser Runde je Team (Konferenz: Teamname -> Kennungen)
        self.round_claims: dict[str, list[str]] = {}
        self.summary = RunSummary()
        self._transport_failures = 0
        self._lock = threading.Lock()
        self._baseline_dossier: str | None = None  # einmal je Lauf berechnet

    # Ablauf

    def run(self) -> RunSummary:
        reachable = getattr(self.client, "reachable", None)
        if reachable is not None and not reachable():
            url = getattr(self.client, "api_url", "?")
            self.summary.stop_reason = f"LLM-Endpunkt nicht erreichbar: {url}"
            self.log("STOPP: " + self.summary.stop_reason)
            return self.summary
        for r in range(1, self.opts.rounds + 1):
            self._round(r)
            self.summary.rounds_done = r
            if self.summary.stop_reason:
                break
            if getattr(self.client, "dead", False):
                self.summary.stop_reason = "LLM-Endpunkt nicht mehr erreichbar"
                break
        self.summary.llm_calls = self.gate.calls
        if self.summary.stop_reason:
            self.log("STOPP: " + self.summary.stop_reason)
        return self.summary

    def _round(self, r: int) -> None:
        self.log(f"=== Runde {r} ===")
        self.registry.append({"kind": EV_ROUND, "round": r, "phase": "start"})
        focus = self._plan(r)
        if self.summary.stop_reason:  # Infrastruktur oder Budget: keine Teamaufrufe
            self.registry.append({"kind": EV_ROUND, "round": r, "phase": "aborted"})
            return
        proposals = self._propose(r, focus)
        self.round_claims = {}
        digest: list[str] = []
        for p in proposals:
            digest += self._process(r, p)
        if self.opts.conference and digest:
            self._conference(r, digest)
        self.registry.append(
            {"kind": EV_ROUND, "round": r, "phase": "end", "llm_calls": self.gate.calls}
        )

    def _model(self, i: int) -> str:
        return self.opts.models[i % len(self.opts.models)]

    def _attempt_failed(self, role: str, r: int, error: str, raw: str = "") -> None:
        self.summary.failed_attempts += 1
        self.log(f"  {role}: Versuch fehlgeschlagen - {error}")
        self.registry.append(
            {
                "kind": EV_ATTEMPT,
                "round": r,
                "role": role,
                "error": error[:RAW_EXCERPT_CHARS],
                "raw_excerpt": raw[:RAW_EXCERPT_CHARS],
            }
        )

    def _ask(self, role: str, r: int, model: str, user: str) -> dict[str, Any] | None:
        """Ein Aufruf; Fehler werden protokolliert, ein erschöpftes Budget beendet den
        Lauf nach dieser Runde; ebenso eine gestörte Infrastruktur."""
        if self.summary.stop_reason:
            return None
        try:
            obj, err, raw = self.gate.ask(model, role, user)
        except BudgetExhausted as e:
            # keine weiteren LLM-Aufrufe; die Runde (Richter) läuft noch zu Ende
            self.summary.stop_reason = str(e)
            return None
        except LLMError as e:
            self._attempt_failed(role, r, str(e))
            if is_transport_error(e):
                self._transport_failure(role, str(e))
            return None
        with self._lock:
            self._transport_failures = 0
        if obj is None:
            self._attempt_failed(role, r, err, raw)
        return obj

    def _transport_failure(self, role: str, error: str) -> None:
        """Zählt Infrastrukturfehler in Folge; stoppt bei Schwelle oder sofort, wenn
        der Direktor (Planung/Konferenz) betroffen ist."""
        with self._lock:
            self._transport_failures += 1
            n = self._transport_failures
        if role == DIRECTOR or n >= TRANSPORT_FAILURES_TO_STOP:
            self.summary.stop_reason = (
                f"LLM-Infrastruktur gestört ({n} Fehler in Folge, zuletzt {role}): "
                + error[:RAW_EXCERPT_CHARS]
            )

    # Schritte

    def _dossier(self) -> str:
        with self._lock:
            if self._baseline_dossier is None:
                self._baseline_dossier = baseline_dossier(
                    self.judge.session,
                    self.judge.baseline_score,
                    self.judge.baseline_score_kind,
                )
        return lab_dossier(self._baseline_dossier, self.registry)

    def _context(self) -> str:
        return (
            f"{self.spec_text}\n{FRONTIER_NOTE}\n\n{self._dossier()}\n\nLAB STATE\n"
            + prompt_summary(self.registry, self.judge.baseline_score)
        )

    def _plan(self, r: int) -> dict[str, str]:
        user = f"MODE: plan\nROUND {r}\nTEAMS: {', '.join(self.opts.teams)}\n\n"
        obj = self._ask(DIRECTOR, r, self._model(0), user + self._context())
        focus = parse_focus(obj or {}, self.opts.teams)
        return {t: focus.get(t) or DEFAULT_FOCUS for t in self.opts.teams}

    def _team_prompt(self, team: str, focus: str) -> str:
        fb = team_feedback(self.registry, (team,))[team] or ["(none yet)"]
        return (
            f"{self._context()}\n\nYOUR FOCUS THIS ROUND: {focus}\n\n"
            "FEEDBACK ON YOUR LAST PROPOSALS (judge counterexamples, critic):\n"
            + "\n".join(f"  - {x}" for x in fb[-FEEDBACK_ITEMS:])
        )

    def _propose(self, r: int, focus: dict[str, str]) -> list[Proposal]:
        known = self.registry.claim_ids()

        def one(item: tuple[int, str]) -> Proposal | None:
            i, team = item
            obj = self._ask(
                team, r, self._model(i), self._team_prompt(team, focus[team])
            )
            return parse_proposal(team, obj, known) if obj is not None else None

        teams = list(enumerate(self.opts.teams))
        with ThreadPoolExecutor(max_workers=max(1, len(teams))) as pool:
            results = list(pool.map(one, teams))
        proposals = [p for p in results if p is not None]
        self.summary.proposals += len(proposals)
        return proposals

    def _register(self, r: int, p: Proposal) -> str | None:
        """Legt Behauptungen und Kandidat als Hypothesen an; Kennung der
        Kandidaten-Behauptung (oder None). Der Kandidatentext ist maschinell, die
        Begründung des Teams nur eine Notiz."""
        author = f"team:{p.team}"
        ids = [
            self.registry.add_hypothesis(c.claim, author, c.assumptions, c.supersedes)
            for c in p.claims
        ]
        notes = list(p.notes)
        cand_id = None
        if p.candidate is not None:
            cand_id = self.registry.add_hypothesis(
                f"Candidate ({p.candidate.kind}) from team {p.team}, round {r}, "
                "satisfies the task contract (decided only by kmx.lab.judge; "
                "score and delta are in its evaluation)",
                author,
                [f"round {r}"],
            )
            notes.insert(0, "team rationale (unchecked): " + p.candidate.rationale)
        self.round_claims.setdefault(p.team, []).extend(i for i in [*ids, cand_id] if i)
        anchor = cand_id or next((i for i in ids if i), None)
        for note in notes + [PARSER_NOTE_PREFIX + x for x in p.problems]:
            if anchor:
                self.registry.add_note(anchor, note, author)
        return cand_id

    def _store_source(self, p: Proposal) -> str:
        """Legt den Quelltext des Kandidaten VOR Kritik und Richter ab (SHA-256)."""
        cand = p.candidate
        assert cand is not None
        suffix = ".py" if cand.kind == KIND_GENERATOR else ".kmx"
        sha, _ = self.registry.store_candidate(cand.source.encode("utf-8"), suffix)
        return sha

    def _critique(self, r: int, p: Proposal, claim_id: str, source_sha: str) -> str:
        """Beratende Kritik; liefert eine Zeile für die Konferenz ('' ohne Veto und
        ohne Notizen)."""
        cand = p.candidate
        assert cand is not None
        user = (
            f"{self.spec_text}\n\nPROPOSAL from team {p.team}\nCLAIMS:\n"
            + "\n".join(f"  - {c.claim}" for c in p.claims)
            + f"\nCANDIDATE kind={cand.kind}\nRATIONALE: {cand.rationale}\n"
            f"SOURCE (first {CANDIDATE_PREVIEW_CHARS} chars):\n"
            + cand.source[:CANDIDATE_PREVIEW_CHARS]
        )
        obj = self._ask(CRITIC, r, self._model(0), user)
        if obj is None:
            return ""
        c = parse_critique(obj)
        self.registry.append(
            {
                "kind": EV_CRITIQUE,
                "claim_id": claim_id,
                "source_sha256": source_sha,
                "veto": c.veto,
                "advisory": True,
                "ignored_veto": c.ignored_veto,
                "reason": c.reason,
                "counterexample": c.counterexample,
                "notes": c.notes,
            }
        )
        if not c.veto:
            return ("critic notes: " + " | ".join(c.notes)) if c.notes else ""
        self.summary.vetoes += 1
        self.log(f"  {p.team}: Veto des Kritikers (beratend) - {c.reason}")
        return f"critic VETO (advisory): {c.reason} {c.counterexample}".strip()

    def _process(self, r: int, p: Proposal) -> list[str]:
        """Registriert einen Vorschlag, legt den Quelltext ab, lässt ihn
        kommentieren und IMMER vom Richter bewerten; liefert Zeilen für die
        Konferenz."""
        cand_id = self._register(r, p)
        lines = [f"{p.team}: " + "; ".join(c.claim[:200] for c in p.claims)]
        if p.candidate is None or cand_id is None:
            return lines
        source_sha = self._store_source(p)
        veto = self._critique(r, p, cand_id, source_sha) if self.opts.critic else ""
        if p.candidate.params:
            return lines + self._param_search(r, p, cand_id, veto)
        ev = self.judge.evaluate(p.candidate.kind, p.candidate.source)
        self.judge.record(cand_id, ev)
        self.summary.evaluations.append(ev)
        self.log(f"  {p.team} [{cand_id}]: {ev.line()}")
        result = (
            counterexample_line(ev.counterexample) if ev.counterexample else ev.line()
        )
        line = f"{p.team} candidate {cand_id}: judge: {result}"
        return lines + [line + (f" | {veto}" if veto else "")]

    def _param_search(self, r: int, p: Proposal, parent: str, veto: str) -> list[str]:
        """Parametersuche (kmx.lab.paramsearch): jede voll bewertete oder
        abgestürzte Variante bekommt eine eigene, maschinell formulierte Behauptung;
        alle übrigen nur eine Notiz an der Kandidaten-Behauptung (kein Status)."""
        cand = p.candidate
        assert cand is not None and cand.params is not None
        author, lines = f"team:{p.team}", []
        for o in search(self.judge, cand.source, cand.params):
            if o.outcome not in (JUDGED, CRASHED):
                self.registry.add_note(parent, outcome_note(o), "lab:paramsearch")
                continue
            cid = self.registry.add_hypothesis(
                f"Candidate (generator) from team {p.team}, round {r}, variant "
                f"{params_text(o.params)} satisfies the task contract (decided only "
                "by kmx.lab.judge; score and delta are in its evaluation)",
                author,
                [f"round {r}", f"variant of {parent}"],
            )
            if cid is None:
                continue
            self.round_claims.setdefault(p.team, []).append(cid)
            self.judge.record(cid, o.ev)
            self.summary.evaluations.append(o.ev)
            self.log(f"  {p.team} [{cid}] {params_text(o.params)}: {o.ev.line()}")
            cx = o.ev.counterexample
            result = counterexample_line(cx) if cx else o.ev.line()
            lines.append(f"{p.team} candidate {cid}: judge: {result}")
        if veto:
            lines.append(f"{p.team} candidate {parent}: {veto}")
        return lines

    def _conference(self, r: int, digest: list[str]) -> None:
        user = f"MODE: conference\nROUND {r}\n\nTHIS ROUND:\n" + "\n".join(
            f"  - {x}" for x in digest
        )
        obj = self._ask(DIRECTOR, r, self._model(0), user)
        if obj is None:
            return
        insights = parse_insights(obj, self.registry.claim_ids(), self.round_claims)
        for text, supports, dropped in insights:
            cid = self.registry.add_hypothesis(
                text, "conference", [f"round {r}"], sources=supports
            )
            if cid and dropped:
                self.registry.add_note(
                    cid,
                    f"{PARSER_NOTE_PREFIX}supports ohne Bezug verworfen: {dropped}",
                    "conference",
                )
