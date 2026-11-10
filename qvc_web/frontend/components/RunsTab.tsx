"use client";
import { useEffect, useMemo, useState } from "react";
import * as api from "@/lib/api";
import type { Status } from "@/lib/types";
import { Badge, Card, Field } from "./ui";

interface Props {
  submit: (kind: string, params: any) => Promise<void>;
  goLive: () => void;
  status: Status | null;
}

const REF = { invsqrt: 2076774.23, dqi: 24439463583672.93, dfthcsos: 3355599588.32 };

/** Live-Vorschau des Scores aus den eingegebenen Kosten (ohne Provenance-Check). */
function scorePreview(text: string): { ratios: Record<string, number>; score: number } | null {
  try {
    const c = JSON.parse(text);
    if (!c || typeof c !== "object") return null;
    const ratios: Record<string, number> = {};
    for (const t of ["invsqrt", "dqi", "dfthcsos"]) {
      const cost = c?.[t]?.cost;
      if (typeof cost === "number" && cost > 0) ratios[t] = REF[t] / cost;
    }
    if (Object.keys(ratios).length < 3) return null;
    const prod = Object.values(ratios).reduce((a, b) => a * b, 1);
    return { ratios, score: Math.cbrt(prod) };
  } catch {
    return null;
  }
}

export default function RunsTab({ submit, goLive, status }: Props) {
  // discover
  const [dTask, setDTask] = useState("all");
  const [dTop, setDTop] = useState(3);
  const [dWorkers, setDWorkers] = useState(3);
  const [dRetries, setDRetries] = useState(2);
  const [dBriefText, setDBriefText] = useState("");
  const [dMemoryText, setDMemoryText] = useState("");
  const [dBriefFile, setDBriefFile] = useState("");
  const [dMemoryFile, setDMemoryFile] = useState("");
  // score
  const [sCosts, setSCosts] = useState("");
  // verify
  const [vTask, setVTask] = useState("invsqrt");
  const [vMode, setVMode] = useState("precheck");
  const [vAdapter, setVAdapter] = useState("qvc_web/backend/adapters/adapter_invsqrt_precheck.json");
  const [vCandidate, setVCandidate] = useState("work/frontier_1104/invsqrt/best/invsqrt.kmb");
  const [vPreN, setVPreN] = useState(512);
  const [vWorkers, setVWorkers] = useState(2);
  const [vExecute, setVExecute] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);

  const preview = useMemo(() => scorePreview(sCosts), [sCosts]);

  // ---- Wettbewerbs-Prompt (offizielle Beschreibung) vorausfüllen ----
  const [briefLoading, setBriefLoading] = useState(false);
  const [briefLoaded, setBriefLoaded] = useState(false);

  async function loadCompetitionBrief() {
    if (briefLoading) return;
    setBriefLoading(true);
    try {
      const r = await api.get<{ text?: string; chars?: number }>("/competition-brief");
      const t = (r?.text || "").trim();
      if (t) { setDBriefText(t); setBriefLoaded(true); }
    } catch (e: any) {
      alert("Wettbewerbs-Prompt nicht ladbar: " + (e?.message || e));
    } finally {
      setBriefLoading(false);
    }
  }

  // Einmalig beim Öffnen des Tabs: leeres Briefing mit dem offiziellen Prompt füllen.
  useEffect(() => {
    if (!dBriefText.trim()) void loadCompetitionBrief();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function run(kind: string, params: any) {
    if (busy) return;
    setBusy(kind);
    try {
      await submit(kind, params);
      goLive();
    } catch (e: any) {
      alert(`Start fehlgeschlagen: ${e?.message || e}`);
    } finally {
      setBusy(null);
    }
  }

  function onMode(m: string) {
    setVMode(m);
    setVAdapter(m === "official"
      ? "qvc_web/backend/adapters/adapter_invsqrt.json"
      : "qvc_web/backend/adapters/adapter_invsqrt_precheck.json");
  }

  async function loadExample() {
    try {
      const r = await api.get<{ examples: Record<string, any> }>("/examples");
      const c = r.examples["verified_costs_example.json"];
      if (c) setSCosts(JSON.stringify(c, null, 2));
    } catch (e: any) { alert("Beispiel nicht ladbar: " + (e?.message || e)); }
  }

  const noKey = status ? !status.key_present : true;

  return (
    <>
      {/* ================= DISCOVER ================= */}
      <Card
        title="Discover — KI-Hypothesen generieren & reviewen"
        intro={<>Die KI erfindet pro Aufgabe und pro <b>Linse</b> (analogisch · formal · outsider) je <b>eine</b> testbare Optimierungsidee, lässt jede Idee von einem <i>anderen</i> Modell kritisch reviewen (These / Antithese / Synthese) und wählt dann die <b>Top-N</b> für dein Backlog aus. Ergebnis ist ein <b>Hypothesen-Dokument</b> — hier wird nichts kompiliert oder verifiziert.</>}
      >
        <div className="row">
          <Field className="grow" label="Aufgabe" tip="Welche der drei Benchmarks bearbeitet wird. 'Alle' erzeugt 3 Aufgaben × 3 Linsen = 9 Ideen.">
            <select value={dTask} onChange={e => setDTask(e.target.value)}>
              <option value="all">Alle (9 Ideen)</option>
              <option value="invsqrt">invsqrt (3 Ideen)</option>
              <option value="dqi">dqi (3 Ideen)</option>
              <option value="dfthcsos">Chemie / dfthcsos (3 Ideen)</option>
            </select>
          </Field>
          <Field label="Top-N (Ideen im Backlog)" tip="Wie viele der generierten + reviewten Ideen am Ende in die priorisierte Liste aufgenommen werden (1–9). Standard: 3." desc="Mehr = breiteres Backlog, weniger = fokussierter.">
            <input type="number" min={1} max={9} value={dTop} onChange={e => setDTop(+e.target.value)} />
          </Field>
          <Field label="Parallele KI-Aufrufe" tip="Wie viele Modell-Aufrufe gleichzeitig laufen. Mehr = schneller, aber mehr Last auf die API (Rate-Limits, Kosten). Standard: 3." desc="1–9.">
            <input type="number" min={1} max={9} value={dWorkers} onChange={e => setDWorkers(+e.target.value)} />
          </Field>
          <Field label="Versuche pro Modell" tip="Wie oft dasselbe Modell erneut gefragt wird, bevor auf das nächste Modell in der Fallback-Kette gewechselt wird (bei Fehler oder ungültigem JSON). Standard: 2." desc="1–4.">
            <input type="number" min={1} max={4} value={dRetries} onChange={e => setDRetries(+e.target.value)} />
          </Field>
        </div>

        <Field label="Briefing (direkt eintippen / pasten)" tip="Freitext mit Kontext: Wettbewerbsregeln, aktuelle Baseline, bereits widerlegte Ideen, Ziele. Wird direkt in den KI-Prompt übernommen (max. ~12.000 Zeichen).">
          <div className="row" style={{ alignItems: "center", marginBottom: 6 }}>
            <button type="button" className="mini" disabled={briefLoading} onClick={() => void loadCompetitionBrief()}>
              {briefLoading ? "Lade…" : "⬇ Wettbewerbs-Prompt laden"}
            </button>
            <span className="muted small">Offizielle Wettbewerbsbeschreibung · Khattar et al., arXiv:2610.23832v2</span>
          </div>
          <textarea
            value={dBriefText}
            onChange={e => setDBriefText(e.target.value)}
            placeholder={"Wird beim Öffnen automatisch mit dem offiziellen Wettbewerbs-Prompt gefüllt …"}
            style={{ minHeight: 180 }}
          />
        </Field>
        <div className="row">
          <Field className="grow" label={<span className="muted">…oder Briefing aus Datei (Pfad, optional)</span>} tip="Alternativ zu obigem Freitext: Pfad zu einer Markdown-Datei. Wenn beide gefüllt sind, gewinnt der Freitext.">
            <input value={dBriefFile} onChange={e => setDBriefFile(e.target.value)} placeholder="z.B. work/PLAN_30.md" />
          </Field>
        </div>

        <details className="opt-block">
          <summary>Wissen aus früheren Experimenten mitgeben (optional)</summary>
          <Field label="Negative Ergebnisse / Memory (direkt)" tip="Bisher gescheiterte Ansätze und Befunde, damit die KI sie nicht erneut vorschlägt. Wird in den Prompt übernommen (max. ~11.000 Zeichen).">
            <textarea value={dMemoryText} onChange={e => setDMemoryText(e.target.value)} placeholder={"z.B.\n- Zeilen-Umordnung in Chemie: kein Gewinn\n- DQI-Kandidat e9f54be3: Phasenfehler bei 1/3 Salts → nicht robust\n- invsqrt P-A/P-B Redesigns: widerlegt"} style={{ minHeight: 90 }} />
          </Field>
          <Field label={<span className="muted">…oder Memory aus Datei (Pfad, optional)</span>}>
            <input value={dMemoryFile} onChange={e => setDMemoryFile(e.target.value)} placeholder="z.B. ~/.agent-memory/kaggle-qvc/… (absoluter Pfad)" />
          </Field>
        </details>

        <p className="small muted" style={{ marginTop: 10 }}>
          Benötigt <code>OPENROUTER_API_KEY</code> in <code>.env</code>.
          {noKey && <span style={{ marginLeft: 8 }}><Badge tone="err">Key fehlt — Discover startet nicht</Badge></span>}
        </p>
        <button className="btn" disabled={busy != null} onClick={() => run("discover", { task: dTask, top: dTop, workers: dWorkers, retries: dRetries, brief_text: dBriefText.trim() || null, memory_text: dMemoryText.trim() || null, brief: dBriefFile.trim() || null, memory: dMemoryFile.trim() || null })}>▶ Discover starten</button>
      </Card>

      {/* ================= SCORE ================= */}
      <Card
        title="Score — Gesamtscore aus verifizierten Kosten"
        intro={<>Rechnet deinen <b>Gesamtwettbewerbs-Score</b> aus den offiziellen Kosten deiner drei besten Schaltungen. Formel: <code>Score = (R_invsqrt × R_dqi × R_chem)^⅓</code>, wobei <code>R = Referenzkosten ÷ deine Kosten</code>. Die Kosten bekommst du vom offiziellen Verifier (siehe <b>Verify</b> unten). Die UI akzeptiert nur Werte mit <code>source=official_verifier</code> und <code>passed=true</code>; für dqi zusätzlich <code>shots=102400</code> und ≥5 unabhängige Salts — so wird verhindert, dass du einen Score aus ungeprüften Zahlen erhältst.</>}
      >
        <Field label="Kosten-JSON der drei Aufgaben" tip='Jede Aufgabe braucht ein Objekt mit "source":"official_verifier", "passed":true und "cost" (die offizielle Kostenzahl). dqi zusätzlich "shots":102400 und "independent_salts" (mindestens 5).'>
          <textarea value={sCosts} onChange={e => setSCosts(e.target.value)} placeholder={'{\n  "invsqrt":   { "source": "official_verifier", "passed": true, "cost": 95345.5 },\n  "dqi":       { "source": "official_verifier", "passed": true, "cost": 3.746e11, "shots": 102400,\n                 "independent_salts": ["a","b","c","d","e"] },\n  "dfthcsos":  { "source": "official_verifier", "passed": true, "cost": 299654754.9 }\n}'} style={{ minHeight: 150 }} />
        </Field>
        <div className="row" style={{ alignItems: "flex-end" }}>
          <div style={{ flex: 1 }}>
            {preview ? (
              <div className="score-preview">
                <span className="sp-label">Live-Vorschau <span className="muted small">(ohne Provenance-Check)</span>:</span>{" "}
                {Object.entries(preview.ratios).map(([k, v]) => <span key={k} className="sp-item">{k} {(+v).toFixed(2)}</span>)}
                <span className="sp-score">→ Score <b>{preview.score.toFixed(3)}</b></span>
              </div>
            ) : (
              <div className="score-preview muted small">Gib gültige Kosten für alle drei Aufgaben ein, um den Score live zu sehen.</div>
            )}
          </div>
          <button className="btn sec" onClick={loadExample}>Beispiel laden</button>
        </div>
        <button className="btn" disabled={busy != null} onClick={() => { let c: any; try { c = JSON.parse(sCosts); } catch { alert("Die Eingabe ist kein gültiges JSON-Objekt."); return; } run("score", { costs: c }); }}>▶ Score berechnen (mit Provenance-Check)</button>
      </Card>

      {/* ================= VERIFY ================= */}
      <Card
        title="Verify — Schaltung mit dem offiziellen Verifier prüfen"
        intro={<>Führt einen von dir konfigurierten <b>Adapter</b> aus, der den <b>unveränderten offiziellen Google-Verifier</b> aufruft (nie KI-Code). Zwei Modi: <b>PRE-CHECK</b> prüft eine Teilmenge der Eingaben in Sekunden (Kostenschätzung — zum schnellen Aussortieren kaputter Varianten); <b>OFFIZIELL</b> läuft der volle Verifier mit 64 Shots pro Eingabe (~10 Min) und ergibt den echten Claim-Wert.</>}
      >
        <div className="row">
          <Field label="Aufgabe" tip="Für welche Benchmark geprüft wird. Aktuell sind nur invsqrt-Adapter mitgeliefert.">
            <select value={vTask} onChange={e => setVTask(e.target.value)}>
              <option value="invsqrt">invsqrt</option>
              <option value="dqi">dqi</option>
              <option value="dfthcsos">dfthcsos</option>
            </select>
          </Field>
          <Field label="Modus" tip="PRE-CHECK = schnelle Teilmenge (~1 s, Kostenschätzung, kein offizieller Claim). OFFIZIELL = voller Verifier, 64 Shots/x (~10 Min, echter Wert).">
            <select value={vMode} onChange={e => onMode(e.target.value)}>
              <option value="precheck">PRE-CHECK (~1 s)</option>
              <option value="official">OFFIZIELL (~10 Min)</option>
            </select>
          </Field>
          <Field className="grow" label="Kandidat (.kmb)" tip="Pfad zur Schaltungsdatei, die geprüft werden soll (absolut oder relativ zum Repo).">
            <input value={vCandidate} onChange={e => setVCandidate(e.target.value)} />
          </Field>
        </div>
        <div className="row">
          <Field className="grow" label="Adapter-Konfig (Pfad)" tip="JSON, das das exakte Kommando definiert, welches den offiziellen Verifier aufruft. Wird automatisch mit dem Modus gesetzt — editierbar für eigene Adapter.">
            <input value={vAdapter} onChange={e => setVAdapter(e.target.value)} />
          </Field>
          <Field label="Pre-Check-Stichprobe" tip="Wie viele Eingaben der PRE-CHECK simuliert (Stratified-Subset). Nur im PRE-CHECK-Modus relevant. Standard: 512.">
            <input type="number" min={64} max={8192} value={vPreN} onChange={e => setVPreN(+e.target.value)} />
          </Field>
          <Field label="Worker" tip="Parallele Verifier-Prozesse. Bei 16–32 GB RAM max. 2 (jeder dqi-Worker ~6 GB RAM). Standard: 2.">
            <input type="number" min={1} max={16} value={vWorkers} onChange={e => setVWorkers(+e.target.value)} />
          </Field>
        </div>
        <label className="check-line">
          <input type="checkbox" checked={vExecute} onChange={e => setVExecute(e.target.checked)} />
          Ausführung starten <span className="muted small">(ohne Haken: nur sichere Kommando-Vorschau / DRY-RUN)</span>
        </label>
        <button className="btn" disabled={busy != null} onClick={() => run("verify", { adapter_file: vAdapter.trim(), task: vTask, candidate: vCandidate.trim(), execute: vExecute, workers: vWorkers, shots: 64, preN: vPreN })}>▶ Verify</button>
      </Card>
    </>
  );
}
