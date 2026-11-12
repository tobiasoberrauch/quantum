"""Forschungsgedächtnis: ein Laborverzeichnis mit append-only Ereignisprotokoll
(events.jsonl), Konfiguration (lab.json), Kopie des Basisschaltkreises und den geprüften
Kandidaten (candidates/<sha256>.<endung>).

Behauptungen und ihr Status entstehen beim Lesen aus dem Protokoll (`claims`); es gibt
keine Methode, die einen Status setzt. Sprachmodell-Ausgaben gelangen nur über
`add_hypothesis` und `add_note` hinein.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import os
import shutil
import threading
import time
import uuid
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Any

from kmx.circuit_io import atomic_write_text
from kmx.lab.claims import (
    EV_CLAIM,
    EV_CRITIQUE,
    EV_EVALUATION,
    EV_HISTORICAL,
    EV_LAB,
    EV_NOTE,
    SEED_EVALUATOR,
    Claim,
    derive_status,
    evaluation_status,
    is_sha256,
    safe_id,
    safe_id_list,
    safe_text,
    safe_text_list,
)
from kmx.lab.seeds import SEED_SOURCE, SEEDS
from kmx.lab.untrusted import redact

EVENTS_FILE, CONFIG_FILE, CANDIDATE_DIR = "events.jsonl", "lab.json", "candidates"
CANDIDATE_SUFFIXES = (".kmx", ".kmb", ".py")
Event = dict[str, Any]


class LabError(RuntimeError):
    """Laborverzeichnis fehlt, ist beschädigt oder existiert schon."""


@dataclass(frozen=True)
class LabConfig:
    """Inhalt von lab.json: woran das Labor forscht und wie der Richter prüft."""

    name: str
    baseline_file: str  # Dateiname im Laborverzeichnis
    baseline_sha256: str
    input_register: str = "x"
    value_range: str | None = None
    max_exhaustive: int = 1 << 23
    spec: str | None = None  # z. B. "invsqrt" (Paketdatei kmx/lab/spec_invsqrt.json)
    created: str = ""
    kmx_version: str = ""
    # bei `lab init` gepinnter offizieller Verifier (Werkzeug-Hashes wie tool_sha256);
    # fehlt in älteren lab.json: dann gibt es kein verified
    verifier_pin: dict[str, str] | None = None
    verifier_command: str | None = None


def now_iso() -> str:
    """Zeitstempel in UTC (Sekunden), wie er im Protokoll steht."""
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: str) -> str:
    with open(path, "rb") as f:
        return sha256_bytes(f.read())


class Registry:
    """Zugriff auf ein Laborverzeichnis. Schreiben ist threadsicher (ein Lock je
    Instanz) und hängt nur an; nichts wird je umgeschrieben."""

    def __init__(self, lab_dir: str) -> None:
        self.lab_dir = os.path.abspath(lab_dir)
        self.events_path = os.path.join(self.lab_dir, EVENTS_FILE)
        self.candidate_dir = os.path.join(self.lab_dir, CANDIDATE_DIR)
        self._lock = threading.Lock()
        self.corrupt_lines = 0

    # Anlegen und Öffnen

    @classmethod
    def create(cls, lab_dir: str, baseline_path: str, config: LabConfig) -> Registry:
        """Legt ein neues Labor an (Verzeichnis darf noch kein Protokoll haben),
        kopiert die Basis, schreibt lab.json und die Altbefunde."""
        reg = cls(lab_dir)
        if os.path.exists(reg.events_path):
            raise LabError(f"Labor existiert bereits: {reg.lab_dir}")
        os.makedirs(reg.candidate_dir, exist_ok=True)
        shutil.copyfile(baseline_path, os.path.join(reg.lab_dir, config.baseline_file))
        atomic_write_text(
            os.path.join(reg.lab_dir, CONFIG_FILE),
            json.dumps(dataclasses.asdict(config), indent=2, ensure_ascii=False) + "\n",
        )
        reg.append({"kind": EV_LAB, "action": "init", "config": config.name})
        reg._write_seeds()
        return reg

    @classmethod
    def open(cls, lab_dir: str) -> Registry:
        reg = cls(lab_dir)
        if not os.path.exists(reg.events_path):
            raise LabError(
                f"Kein Labor in {reg.lab_dir} (zuerst: main.py lab init --lab-dir ...)"
            )
        return reg

    def config(self) -> LabConfig:
        try:
            with open(os.path.join(self.lab_dir, CONFIG_FILE), encoding="utf-8") as f:
                raw = json.load(f)
            return LabConfig(**raw)
        except (OSError, ValueError, TypeError) as e:
            raise LabError(f"lab.json unlesbar: {e}") from e

    def verifier_pin(self) -> dict[str, str] | None:
        """Pin des Verifiers aus lab.json (None ohne Pin oder ohne lesbare
        Konfiguration: dann zählt kein offizielles PASS als verified)."""
        try:
            pin = self.config().verifier_pin
        except LabError:
            return None
        return pin if isinstance(pin, dict) and pin else None

    def baseline_path(self) -> str:
        cfg = self.config()
        if os.path.basename(cfg.baseline_file) != cfg.baseline_file:
            raise LabError("lab.json: baseline_file muss ein Dateiname sein")
        return os.path.join(self.lab_dir, cfg.baseline_file)

    def _write_seeds(self) -> None:
        for s in SEEDS:
            self.append(
                {
                    "kind": EV_CLAIM,
                    "claim_id": s.claim_id,
                    "claim": s.claim,
                    "assumptions": list(s.assumptions),
                    "sources": [SEED_SOURCE, *s.extra_sources],
                    "introduced_by": SEED_EVALUATOR,
                }
            )
            self.append(
                {
                    "kind": EV_HISTORICAL,
                    "claim_id": s.claim_id,
                    "status": s.status,
                    "evaluator": SEED_EVALUATOR,
                    "source": SEED_SOURCE,
                }
            )

    # Schreiben

    def append(self, event: Event) -> Event:
        """Hängt ein Ereignis an (mit Zeitstempel) und gibt es zurück."""
        # zweite Verteidigungslinie: keine Werte geheimer Umgebungsvariablen
        event = redact({"ts": now_iso(), **event})
        line = json.dumps(event, ensure_ascii=False, sort_keys=True)
        with self._lock, open(self.events_path, "a", encoding="utf-8") as f:
            f.write(line + "\n")
            f.flush()
            os.fsync(f.fileno())
        return event

    def add_hypothesis(
        self,
        claim: object,
        introduced_by: str,
        assumptions: object = None,
        supersedes: object = None,
        sources: object = None,
    ) -> str | None:
        """Neue Behauptung (immer Hypothese); Texte werden bereinigt, `supersedes`
        nur mit existierenden Kennungen übernommen. None bei leerem Text."""
        text = safe_text(claim)
        if not text:
            return None
        claim_id = "c-" + uuid.uuid4().hex[:12]
        self.append(
            {
                "kind": EV_CLAIM,
                "claim_id": claim_id,
                "claim": text,
                "assumptions": safe_text_list(assumptions),
                "supersedes": safe_id_list(supersedes, self.claim_ids()),
                "sources": safe_text_list(sources),
                "introduced_by": safe_text(introduced_by, 64),
            }
        )
        return claim_id

    def add_note(self, claim_id: object, text: object, author: str) -> bool:
        """Notiz an eine existierende Behauptung (False bei unbekannter Kennung)."""
        cid, body = safe_id(claim_id), safe_text(text)
        if not cid or not body or cid not in self.claim_ids():
            return False
        self.append(
            {"kind": EV_NOTE, "claim_id": cid, "text": body, "author": author[:64]}
        )
        return True

    def store_candidate(self, data: bytes, suffix: str) -> tuple[str, str]:
        """Legt einen Kandidaten unter seinem SHA-256 ab: (sha256, Pfad)."""
        if suffix not in CANDIDATE_SUFFIXES:
            raise LabError(f"unbekannte Kandidatenendung {suffix!r}")
        sha = sha256_bytes(data)
        path = os.path.join(self.candidate_dir, sha + suffix)
        if not os.path.exists(path):
            os.makedirs(self.candidate_dir, exist_ok=True)
            tmp = f"{path}.{uuid.uuid4().hex}.tmp"
            with open(tmp, "wb") as f:
                f.write(data)
            os.replace(tmp, path)
        return sha, path

    def candidate_ok(self, sha: str) -> bool:
        """Ob ein Kandidat mit genau diesem Hash im Labor liegt (Beleg für
        verified)."""
        if not is_sha256(sha):
            return False
        for suffix in (".kmx", ".kmb"):
            path = os.path.join(self.candidate_dir, sha + suffix)
            if os.path.exists(path) and sha256_file(path) == sha:
                return True
        return False

    # Lesen

    def events(self) -> Iterator[Event]:
        """Alle lesbaren Ereignisse; unlesbare Zeilen werden gezählt, nicht
        geworfen."""
        self.corrupt_lines = 0
        try:
            f = open(self.events_path, encoding="utf-8")
        except OSError:
            return
        with f:
            for line in f:
                try:
                    e = json.loads(line)
                except ValueError:
                    self.corrupt_lines += 1
                    continue
                if isinstance(e, dict):
                    yield e

    def claim_ids(self) -> set[str]:
        return {
            e["claim_id"]
            for e in self.events()
            if e.get("kind") == EV_CLAIM and isinstance(e.get("claim_id"), str)
        }

    def claims(self) -> dict[str, Claim]:
        """Alle Behauptungen mit abgeleitetem Status, in Anlegereihenfolge."""
        claims: dict[str, Claim] = {}
        per_claim: dict[str, list[Event]] = {}
        pin = self.verifier_pin()
        for e in self.events():
            cid = e.get("claim_id")
            if not isinstance(cid, str):
                continue
            if e.get("kind") == EV_CLAIM and cid not in claims:
                claims[cid] = _claim_from_event(e)
            if cid in claims:
                per_claim.setdefault(cid, []).append(e)
                _apply_event(claims[cid], e, self.candidate_ok, pin)
        for cid, c in claims.items():
            c.status = derive_status(per_claim[cid], self.candidate_ok, pin)
        return claims


def _claim_from_event(e: Event) -> Claim:
    def texts(key: str) -> list[str]:
        v = e.get(key)
        return [str(x) for x in v] if isinstance(v, list) else []

    return Claim(
        claim_id=e["claim_id"],
        claim=str(e.get("claim", "")),
        assumptions=texts("assumptions"),
        sources=texts("sources"),
        introduced_by=str(e.get("introduced_by", "")),
        supersedes=texts("supersedes"),
        created=str(e.get("ts", "")),
        updated=str(e.get("ts", "")),
    )


def _apply_event(
    c: Claim,
    e: Event,
    candidate_ok: Callable[[str], bool],
    pin: dict[str, str] | None = None,
) -> None:
    """Trägt Notizen, Experimente, Gegenbeispiele und Belege in die Sicht ein (der
    Status selbst kommt aus derive_status)."""
    c.updated = str(e.get("ts", c.updated))
    kind = e.get("kind")
    if kind == EV_NOTE:
        c.notes.append(f"[{e.get('author', '?')}] {e.get('text', '')}")
    elif kind == EV_CRITIQUE:
        notes = e.get("notes") if isinstance(e.get("notes"), list) else []
        text = " | ".join(str(x) for x in [e.get("reason"), *notes] if x)
        c.notes.append(f"[critic{' VETO' if e.get('veto') else ''}] {text}")
    elif kind == EV_EVALUATION:
        c.experiments.append(str(e.get("eval_id", "")))
        if e.get("counterexample"):
            c.counterexamples.append(e["counterexample"])
        if e.get("official"):
            c.proof_artifacts.append(e["official"])
        score = e.get("score")
        if (
            evaluation_status(e, candidate_ok, pin)
            and e.get("passed")
            and score is not None
        ):
            c.best_score = score if c.best_score is None else min(c.best_score, score)
