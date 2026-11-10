"use client";
import { useEffect, useState } from "react";
import * as api from "@/lib/api";
import type { Model, TeamAgent, TeamResult } from "@/lib/types";
import { md } from "@/lib/markdown";
import { Badge, Card, Field } from "./ui";

interface Props {
  submit: (kind: string, params: any) => Promise<void>;
  activeJob: { id: string; kind: string; status: string; error?: string | null } | null;
  lastResult: { kind: string; result: any } | null;
}

const EMPTY_NEW = { id: "", label: "", base_url: "", model: "", api_key_env: "", extra_body: "" };

export default function TeamTab({ submit, activeJob, lastResult }: Props) {
  const [models, setModels] = useState<Model[]>([]);
  const [agents, setAgents] = useState<TeamAgent[]>([
    { name: "Lokal", role: "Baut die konkrete technische Lösung aus und hält sie praktisch umsetzbar.", model_id: "local-qwen" },
    { name: "Cloud", role: "Kritisiert, findet Lücken und bringt eine andere Perspektive ein.", model_id: "cloud-gpt" },
  ]);
  const [prompt, setPrompt] = useState("");
  const [rounds, setRounds] = useState(1);
  const [synthModel, setSynthModel] = useState(""); // "" = auto (letzter Agent)
  const [temp, setTemp] = useState(0.5);
  const [busy, setBusy] = useState(false);
  const [showAdd, setShowAdd] = useState(false);
  const [nm, setNm] = useState(EMPTY_NEW);

  async function loadModels() {
    try { setModels((await api.get<{ models: Model[] }>("/models")).models); } catch { /* ignore */ }
  }
  useEffect(() => { loadModels(); }, []);

  function setAgent(i: number, patch: Partial<TeamAgent>) {
    setAgents(a => a.map((x, idx) => (idx === i ? { ...x, ...patch } : x)));
  }
  function addAgent() {
    setAgents(a => [...a, { name: `Agent ${a.length + 1}`, role: "", model_id: models[0]?.id || "local-qwen" }]);
  }
  function removeAgent(i: number) { setAgents(a => a.filter((_, idx) => idx !== i)); }

  async function run() {
    if (busy) return;
    if (!prompt.trim()) { alert("Bitte einen Ausgangsprompt eingeben."); return; }
    if (agents.length === 0) { alert("Mindestens ein Agent nötig."); return; }
    setBusy(true);
    try {
      await submit("team", {
        starting_prompt: prompt.trim(),
        agents: agents.map(a => ({ name: a.name.trim() || "Agent", role: a.role, model_id: a.model_id })),
        rounds, synthesis_model_id: synthModel || null, temperature: temp,
      });
    } catch (e: any) { alert("Start fehlgeschlagen: " + (e?.message || e)); }
    finally { setBusy(false); }
  }

  async function addModel() {
    const body: Record<string, unknown> = { ...nm };
    if (String(body.extra_body).trim()) {
      try { body.extra_body = JSON.parse(String(body.extra_body)); }
      catch { alert('Provider-Flags müssen gültiges JSON sein, z.B. {"chat_template_kwargs":{"enable_thinking":false}}'); return; }
    } else {
      delete body.extra_body;
    }
    try {
      await api.post("/models", body);
      setNm(EMPTY_NEW); setShowAdd(false); loadModels();
    } catch (e: any) { alert("Modell nicht gespeichert: " + (e?.message || e)); }
  }

  const running = activeJob?.kind === "team" && (activeJob.status === "running" || activeJob.status === "pending");
  const outer = lastResult?.kind === "team" ? lastResult.result : null;
  const result: TeamResult | null = outer?.result ?? null;

  return (
    <>
      <Card
        title="Agenten-Team — lokale + Cloud-Modelle diskutieren"
        intro={<>Definiere ein Team: jeder <b>Agent</b> hat eine <b>Rolle</b> und ein <b>Modell</b> (lokal auf deiner Hardware oder Cloud). Du gibst einen <b>Ausgangsprompt</b>, die Agenten diskutieren über mehrere Runden, und am Ende synthetisiert ein Modell die <b>beste Lösung</b>. Neue Modelle (z. B. ein frisch erschienenes Top-Modell) bindest du unten einfach als neuen Kollegen ein.</>}
      >
        {/* ---- team builder ---- */}
        <div className="field-label" style={{ marginBottom: 6 }}>Team ({agents.length} Agenten)</div>
        {agents.map((a, i) => (
          <div key={i} className="card" style={{ padding: 12, marginBottom: 8 }}>
            <div className="row">
              <Field label="Name">
                <input value={a.name} onChange={e => setAgent(i, { name: e.target.value })} style={{ width: 160 }} />
              </Field>
              <Field className="grow" label="Rolle / Perspektive" tip="Was dieser Kollege beitragen soll — je unterschiedlicher die Rollen, desto mehr neue Signale.">
                <input value={a.role} onChange={e => setAgent(i, { role: e.target.value })} placeholder="z.B. kritischer Physiker, Outsider-Analogie, Implementierer, Skeptiker" />
              </Field>
              <Field label="Modell">
                <select value={a.model_id} onChange={e => setAgent(i, { model_id: e.target.value })}>
                  {models.map(m => <option key={m.id} value={m.id}>{m.label}</option>)}
                </select>
              </Field>
              <button className="btn sec" style={{ alignSelf: "flex-end" }} onClick={() => removeAgent(i)} disabled={agents.length <= 1}>✕</button>
            </div>
          </div>
        ))}
        <button className="btn sec" onClick={addAgent}>+ Agent hinzufügen</button>

        {/* ---- starting prompt + params ---- */}
        <Field label="Ausgangsprompt" tip="Die gemeinsame Frage / das Ziel, auf das das Team diskutiert.">
          <textarea value={prompt} onChange={e => setPrompt(e.target.value)} style={{ minHeight: 110 }}
            placeholder={"z.B. 'Wie bauen wir den effizientesten Weg, um X zu lösen? Bringt konkrete Ansätze.'"} />
        </Field>
        <div className="row">
          <Field label="Runden" tip="Wie oft das ganze Team einmal drüber diskutiert. 1 = jeder spricht einmal, dann Synthese.">
            <input type="number" min={1} max={6} value={rounds} onChange={e => setRounds(+e.target.value)} />
          </Field>
          <Field label="Synthese-Modell" tip="Welches Modell am Ende die beste Lösung aus der Diskussion zieht. 'Auto' = letzter Agent.">
            <select value={synthModel} onChange={e => setSynthModel(e.target.value)}>
              <option value="">Auto (letzter Agent)</option>
              {models.map(m => <option key={m.id} value={m.id}>{m.label}</option>)}
            </select>
          </Field>
          <Field label="Temperatur" tip="Kreativität vs. Stabilität. Höher = mehr neue Ideen, niedriger = fokussierter.">
            <input type="number" min={0} max={2} step={0.1} value={temp} onChange={e => setTemp(+e.target.value)} />
          </Field>
        </div>
        <p className="small muted">
          Cloud-Modelle brauchen <code>OPENROUTER_API_KEY</code> in <code>.env</code>; lokale Modelle laufen keyless.
        </p>
        <button className="btn" disabled={busy || running} onClick={() => void run()}>▶ Team-Diskussion starten</button>
      </Card>

      {/* ---- add new model (easy onboarding) ---- */}
      <Card title="Neues Modell einbinden" intro={<>Ein frisch erschienenes Modell als neuen Kollegen hinzufügen. Es erscheint danach in allen Modell-Auswahlboxen. Der Key wird nur per <b>Env-Variablen-Namen</b> referenziert (nichts wird gespeichert).</>}
        right={<button className="mini" onClick={() => setShowAdd(s => !s)}>{showAdd ? "ausblenden" : "+ hinzufügen"}</button>}>
        {showAdd && (
          <>
            <div className="row">
              <Field label="ID (einzigartig)" tip="Kurzer technischer Bezeichner, z.B. fable-52.">
                <input value={nm.id} onChange={e => setNm({ ...nm, id: e.target.value })} placeholder="fable-52" />
              </Field>
              <Field className="grow" label="Anzeigename">
                <input value={nm.label} onChange={e => setNm({ ...nm, label: e.target.value })} placeholder="Fable 5.2 · Cloud" />
              </Field>
            </div>
            <div className="row">
              <Field className="grow" label="Base URL (OpenAI-kompatibel)" tip="z.B. https://openrouter.ai/api/v1 oder http://dein-host:8000/v1">
                <input value={nm.base_url} onChange={e => setNm({ ...nm, base_url: e.target.value })} placeholder="https://openrouter.ai/api/v1" />
              </Field>
              <Field className="grow" label="Modell-ID" tip="Wie der Endpoint das Modell kennt, z.B. vendor/fable-5.2">
                <input value={nm.model} onChange={e => setNm({ ...nm, model: e.target.value })} placeholder="vendor/fable-5.2" />
              </Field>
            </div>
            <div className="row">
              <Field label="Key-Env (Name)" tip="Name der Env-Variable mit dem API-Key. Leer = keyless (lokal).">
                <input value={nm.api_key_env} onChange={e => setNm({ ...nm, api_key_env: e.target.value })} placeholder="OPENROUTER_API_KEY" />
              </Field>
              <div style={{ alignSelf: "flex-end" }}>
                <button className="btn" onClick={() => void addModel()} disabled={!nm.id || !nm.base_url || !nm.model}>Modell speichern</button>
              </div>
            </div>
            <div className="row">
              <Field className="grow" label="Provider-Flags (JSON, optional)" tip="Zusätzliche OpenAI-Payload-Felder, z.B. um bei Reasoning-Modellen das private Thinking auszuschalten.">
                <input value={nm.extra_body} onChange={e => setNm({ ...nm, extra_body: e.target.value })} placeholder='{"chat_template_kwargs":{"enable_thinking":false}}' />
              </Field>
            </div>
          </>
        )}
      </Card>

      {/* ---- running indicator ---- */}
      {running && (
        <Card title={<span>Diskussion läuft … <Badge tone="info">{activeJob?.status}</Badge></span>}
          intro={<>Das Team diskutiert gerade. Einzelne Modell-Aufrufe siehst du im <b>Live</b>-Tab (Trace). Die fertige Diskussion + beste Lösung erscheinen hier unten.</>}>
          <div className="muted small">Job {activeJob?.id} · Runden: {rounds} · Agenten: {agents.length}</div>
        </Card>
      )}

      {/* ---- result: transcript + best solution ---- */}
      {result && (
        <>
          <Card title="Diskussion" intro={<>Alle Beiträge des Teams, Runde für Runde.</>}>
            {result.transcript.map((t, i) => (
              <div key={i} className="card" style={{ padding: 12, marginBottom: 8 }}>
                <div className="row" style={{ marginBottom: 6 }}>
                  <Badge tone={t.round === 1 ? "info" : "muted"}>R{t.round}</Badge>
                  <b>{t.agent}</b>
                  <span className="muted small">{t.role}</span>
                  <span className="spacer" />
                  {t.status === "error" && <Badge tone="err">Fehler</Badge>}
                  <Badge tone="hyp">{t.model}</Badge>
                </div>
                <div className="md-body" dangerouslySetInnerHTML={{ __html: md(t.content) }} />
              </div>
            ))}
          </Card>
          <Card title={<span>Beste Lösung <Badge tone="ok">Synthese</Badge></span>}
            intro={<>Das Ergebnis, das aus der Diskussion hervorgeht (gezogen von <code>{result.synthesis_model}</code>).</>}>
            <div className="md-body" style={{ borderLeft: "3px solid var(--ok, #2a9d8f)", paddingLeft: 14 }}
              dangerouslySetInnerHTML={{ __html: md(result.final_solution) }} />
          </Card>
        </>
      )}
    </>
  );
}
