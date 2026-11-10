"use client";
import { useEffect, useRef, useState } from "react";
import type { LogRec, TraceRec } from "@/lib/types";
import type { ActiveJob } from "@/lib/useQvc";
import { Badge, Card } from "./ui";

function TraceTimeline({ trace }: { trace: TraceRec[] }) {
  if (!trace.length) return <p className="muted small">Noch keine Modellaufrufe (verify/score nutzen kein LLM).</p>;
  return (
    <>
      {trace.slice(-60).map((t, i) => (
        <TraceItem key={i} t={t} />
      ))}
    </>
  );
}

function TraceItem({ t }: { t: TraceRec }) {
  const [open, setOpen] = useState(false);
  // in-flight: gestartet, aber noch kein Ergebnis (ok=false UND kein error) → nicht „FAIL"!
  const running = !t.ok && !t.error;
  const state: "ok" | "run" | "fail" = t.ok ? "ok" : running ? "run" : "fail";
  return (
    <div className={`tr ${state === "ok" ? "ok" : state === "fail" ? "bad" : "run"}`}>
      <div className="hd" onClick={() => setOpen(o => !o)}>
        {state === "run" ? <span className="spin" /> : null}
        <Badge tone={state === "ok" ? "ok" : state === "run" ? "info" : "err"}>
          {state === "ok" ? "OK" : state === "run" ? "RUNNING…" : "FAIL"}
        </Badge>
        <b>{t.schema}</b>
        <span className="muted">→ {t.served_model || (state === "run" ? "läuft…" : "n/a")}</span>
        {t.response_mode && <Badge tone="muted">{t.response_mode}</Badge>}
        {t.elapsed != null && <span className="muted small">{t.elapsed}s</span>}
        {t.usage && t.usage.cost > 0 ? <span className="cost-tag">${t.usage.cost.toFixed(4)}</span> : null}
        {t.attempts?.length ? <Badge tone="warn">{t.attempts.length} Fallback(s)</Badge> : null}
      </div>
      {open && (
        <div className="bd">
          <div className="kv" style={{ marginBottom: 8 }}>
            <span className="k">chain</span><span>{(t.chain || []).join(" → ")}</span>
            <span className="k">requested</span><span>{t.requested_model || ""}</span>
          </div>
          {t.error && <div className="banner warn" style={{ margin: "6px 0" }}>{t.error}</div>}
          {t.attempts?.length ? (<><h3>Fallback-Versuche</h3><pre>{t.attempts.join("\n")}</pre></>) : null}
          <h3>Prompt</h3>
          <details><summary className="mini">anzeigen</summary><pre>{t.prompt || ""}</pre></details>
        </div>
      )}
    </div>
  );
}

function LogConsole({ logs }: { logs: LogRec[] }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => { if (ref.current) ref.current.scrollTop = ref.current.scrollHeight; }, [logs]);
  const last = logs.slice(-400);
  return (
    <div className="log" ref={ref}>
      {last.length ? last.map((l, i) => <div key={i} className={`lv-${l.level}`}>{l.msg}</div>) : <span className="muted small">(leer)</span>}
    </div>
  );
}

interface Props {
  activeJob: ActiveJob | null;
  trace: TraceRec[];
  logs: LogRec[];
  stopPolling: () => void;
}

export default function LiveTab({ activeJob, trace, logs, stopPolling }: Props) {
  const running = activeJob && activeJob.status !== "done" && activeJob.status !== "error";
  let statusNode: React.ReactNode;
  if (!activeJob) statusNode = <span className="muted">Kein aktiver Job.</span>;
  else if (activeJob.status === "done") statusNode = <><Badge tone="ok">DONE</Badge> {activeJob.kind} {activeJob.id}</>;
  else if (activeJob.status === "error") statusNode = <><Badge tone="err">ERROR</Badge> {activeJob.kind} {activeJob.id} · <span className="small">{activeJob.error || ""}</span></>;
  else statusNode = <><span className="spin" /> <Badge tone="info">{activeJob.status.toUpperCase()}</Badge> {activeJob.kind} {activeJob.id}</>;

  const totalCost = trace.reduce((s, t) => s + (t.usage?.cost || 0), 0);
  const totalTok = trace.reduce((s, t) => s + (t.usage?.total_tokens || 0), 0);

  return (
    <>
      <Card>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          {statusNode}
          <span className="spacer" />
          {running && <button className="btn sec" title="Hört nur auf, live mitzuverfolgen — der Job läuft im Hintergrund bis zum Ende weiter (echtes Abbrechen gibt es noch nicht)." onClick={stopPolling}>Anzeige stoppen</button>}
        </div>
      </Card>
      <div className="row">
        <Card
          title={<span>Model-Call Trace <span className="small muted">(welches Modell, Fallbacks, Fehler)</span></span>}
          right={totalCost > 0 ? <span className="cost-total">Kosten <b>${totalCost.toFixed(4)}</b> · {totalTok.toLocaleString()} tok</span> : null}
        >
          <TraceTimeline trace={trace} />
        </Card>
        <Card title="Logs"><LogConsole logs={logs} /></Card>
      </div>
    </>
  );
}
