"use client";
import type { JobSummary, Proposal, Review, ResearchData, ScoreResult, Selected, VerifyResult } from "@/lib/types";
import { Badge, Card, Dots, KV } from "./ui";

function viewDiscover(d: ResearchData, files: any, costUsd: number | null, onOpenReport: (abs: string) => void) {
  const byId: Record<string, Proposal> = {};
  (d.proposals || []).forEach(p => { byId[p.id] = p; });
  const crit: Record<string, Review> = {};
  (d.reviews || []).forEach(r => { crit[r.proposal_id] = r; });
  const sel: any = d.selection || {};
  const queue: Selected[] = sel.priority_queue || [];

  return (
    <>
      <div className="banner warn">⚠ <b>HYPOTHESEN NUR</b> — keine Idee wurde kompiliert oder offiziell verifiziert. {d.experiment_status || ""}</div>
      <Card title="Strategie">
        <p>{sel.research_strategy || ""}</p>
        <KV pairs={[
          ["Baseline (Plan)", (d.baseline_score_approx ?? 0).toFixed(4)],
          ["Top-10-Schwelle", "~" + (d.top10_target ?? 24).toFixed(0)],
          ["Stretch-Ziel", String(d.target_score)],
          ["Novelty-Status", <Badge tone="hyp">{d.novelty_status || "UNVERIFIED"}</Badge>],
          ["Kosten dieses Runs", costUsd != null ? <span className="cost-total"><b>${costUsd.toFixed(4)}</b></span> : "—"],
        ]} />
      </Card>
      <Card title="Prioritäts-Backlog">
        <table>
          <thead><tr><th>#</th><th>Idee</th><th>Task</th><th>Erster Schritt</th><th>Erfolg (offiziell)</th><th>Abbruch</th><th>Assets</th></tr></thead>
          <tbody>
            {queue.map((e, i) => {
              const p = byId[e.proposal_id] || ({} as Proposal);
              return (
                <tr key={i}>
                  <td>{i + 1}</td>
                  <td><b>{e.proposal_id}</b> {p.title || ""}</td>
                  <td>{p.task || ""}</td>
                  <td>{e.first_implementation_step || ""}</td>
                  <td>{e.success_threshold || ""}</td>
                  <td>{e.abort_condition || ""}</td>
                  <td className="small muted">{(e.required_assets || []).join(", ")}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </Card>
      <Card title="Alle Vorschläge & Debatte (Pro / Contra / Judge)">
        {(d.proposals || []).map(p => {
          const r = crit[p.id] || ({} as Review);
          const dv = (d.debates || {})[p.id] || {};
          const dm: any = dv.models || {};
          const sc = p.debate_scores || {};
          return (
            <div key={p.id} className={`tr open ${p.survives == null ? "" : p.survives ? "ok" : "bad"}`} style={{ marginBottom: 10 }}>
              <div className="hd">
                <Badge tone="info">{p.task}</Badge><b>{p.id}</b> {p.title || ""}
                <span className="muted small">· {p.origin_model || ""} ({p.origin_role || ""})</span>
                {p.survives != null && <Badge tone={p.survives ? "ok" : "warn"}>{p.survives ? "überlebt Debatte" : "gekillt"}</Badge>}
                <Badge tone="hyp">HYPOTHESIS ONLY</Badge>
              </div>
              <div className="bd">
                <h3>Mechanismus</h3><p>{p.novel_mechanism || ""}</p>
                <KV pairs={[
                  ["Analogie", p.analogy?.source_domain || ""],
                  ["Mapping", p.analogy?.formal_mapping || ""],
                  ["Grenze", p.analogy?.breakdown_conditions || ""],
                  ["Tradeoff", p.predicted_resource_tradeoff || ""],
                  ["Falsifikation", p.falsification_condition || ""],
                ]} />
                {(p.mathematical_invariants || []).length ? (<><h3>Invarianten</h3><ul>{p.mathematical_invariants.map((x, i) => <li key={i}>{x}</li>)}</ul></>) : null}
                {(p.implementation_plan || []).length ? (<><h3>Plan</h3><ol>{p.implementation_plan.map((x, i) => <li key={i}>{x}</li>)}</ol></>) : null}
                {r.thesis || dv.judge ? (
                  <>
                    <h3>Debatte <span className="muted small">(pro={dm.pro?.split("/").pop()} · con={dm.con?.split("/").pop()} · judge={dm.judge?.split("/").pop()})</span></h3>
                    <KV pairs={[
                      ["PRO (Steelman)", r.thesis],
                      ["CON (Kill-Shot)", r.antithesis],
                      ["Judge-Verdict", r.synthesis],
                      ["Feasibility", <Dots n={sc.feasibility ?? r.feasibility} />],
                      ["Impact", <Dots n={sc.impact ?? r.potential_impact} />],
                      ["Novelty", <Dots n={sc.novelty ?? 0} />],
                    ]} />
                  </>
                ) : null}
              </div>
            </div>
          );
        })}
      </Card>
      <Card title="Provenance (Modelle + Fallbacks)">
        <table>
          <thead><tr><th>Rolle</th><th>Served Model</th><th>Fallback-Fehler</th></tr></thead>
          <tbody>
            {Object.entries(d.generation_provenance || {}).map(([k, v]) => (
              <tr key={k}><td>{k}</td><td>{(v as any).model?.split("/").pop()}</td><td className="small muted">{((v as any).fallback_failures || []).join(" | ") || "—"}</td></tr>
            ))}
          </tbody>
        </table>
        {d.debate_provenance && Object.keys(d.debate_provenance).length ? (
          <>
            <h3 style={{ marginTop: 14 }}>Debatte (Pro / Contra / Judge je Idee)</h3>
            <table>
              <thead><tr><th>Idee</th><th>Pro</th><th>Contra</th><th>Judge</th></tr></thead>
              <tbody>
                {Object.entries(d.debate_provenance).map(([pid, m]) => (
                  <tr key={pid}><td>{pid}</td><td>{(m as any).pro?.split("/").pop()}</td><td>{(m as any).con?.split("/").pop()}</td><td>{(m as any).judge?.split("/").pop()}</td></tr>
                ))}
              </tbody>
            </table>
          </>
        ) : null}
      </Card>
      {files?.report_md ? (
        <Card title="report.md">
          <button className="btn sec" onClick={() => onOpenReport(files.report_md)}>Bericht öffnen</button>
        </Card>
      ) : null}
    </>
  );
}

function viewScore(r: ScoreResult) {
  return (
    <Card title="Score aus verifizierten Kosten">
      <div className={`banner ${r.above_target ? "info" : "warn"}`}>
        Score <b>{r.score.toFixed(4)}</b> · Ziel {r.target} · {r.above_target ? <Badge tone="ok">≥ Ziel</Badge> : <Badge tone="warn">unter Ziel</Badge>}
      </div>
      <table>
        <thead><tr><th>Task</th><th>Ratio</th></tr></thead>
        <tbody>{Object.entries(r.ratios).map(([k, v]) => <tr key={k}><td>{k}</td><td>{(+v).toFixed(4)}</td></tr>)}</tbody>
      </table>
    </Card>
  );
}

function viewVerify(r: VerifyResult) {
  const st = r.status;
  const bc = st === "ALL_CHECKS_PASS" ? "ok" : st === "DRY_RUN_ONLY" ? "info" : "err";
  const mode = r._precheck ? "PRE-CHECK" : "OFFIZIELL";
  return (
    <Card title={<span>Verify — {r.task} <Badge tone={r._precheck ? "warn" : "info"}>{mode}</Badge></span>}>
      <div className={`banner ${st === "NOT_VERIFIED" ? "warn" : "info"}`}>
        <Badge tone={bc as any}>{st}</Badge>{r.all_passed != null ? ` · all_passed=${r.all_passed}` : ""}
      </div>
      <KV pairs={[
        ["Kandidat", <span className="small">{r.candidate || ""}</span>],
        ["SHA-256", <span className="small" style={{ fontFamily: "var(--mono)" }}>{r.sha256 || ""}</span>],
        ["Quelle", r.source || ""],
        ["Executed", String(r.executed)],
      ]} />
      {r._precheck ? (
        <div className="banner warn" style={{ marginTop: 8 }}>⚠ PRE-CHECK: Stratified-x-Subset, Kosten = <b>Schätzung</b>. <b>Kein</b> offizieller Claim — für den Claim Modus OFFIZIELL (64 Shots) nutzen.</div>
      ) : null}
      {r.command_preview ? (<><h3>Kommando-Vorschau</h3><pre>{r.command_preview.map(c => c.join(" ")).join("\n")}</pre></>) : null}
      {r.runs?.length ? (
        <>
          <h3>Runs je Salt</h3>
          <table>
            <thead><tr><th>Salt</th><th>Status</th><th>{r._precheck ? "Cost (Est.)" : "Cost"}</th><th>Shots</th><th>Cached</th><th>Fehler / Detail</th></tr></thead>
            <tbody>
              {r.runs.map((x, i) => {
                const det: string[] = [];
                if (x.num_qubits != null) det.push("Q=" + x.num_qubits);
                if (x.worst_error_over_tolerance != null) det.push("worst/tol=" + (+x.worst_error_over_tolerance).toFixed(4));
                if (x.estimated_ratio != null) det.push("est.ratio=" + (+x.estimated_ratio).toFixed(4));
                return (
                  <tr key={i}>
                    <td>{x.salt}</td>
                    <td><Badge tone={x.status === "PASS" ? "ok" : "err"}>{x.status}</Badge></td>
                    <td>{x.cost != null ? (+x.cost).toExponential(4) : "—"}</td>
                    <td>{x.shots ?? "—"}</td>
                    <td>{x.cached ? "✓" : ""}</td>
                    <td className="small muted">{x.error || x.stderr_tail || det.join(" · ") || ""}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </>
      ) : null}
      {r.official_cost_if_identical_across_salts != null ? <p className="small">Offizieller Cost (identisch über alle Salts): <b>{(+r.official_cost_if_identical_across_salts).toExponential(4)}</b></p> : null}
      {r.warning ? <p className="small muted">{r.warning}</p> : null}
    </Card>
  );
}

interface Props {
  lastResult: { kind: string; result: any } | null;
  jobs: JobSummary[];
  loadJob: (id: string) => Promise<void>;
  openArtifact: (rel: string) => void;
}

export default function ResultsTab({ lastResult, jobs, loadJob, openArtifact }: Props) {
  let body: React.ReactNode;
  if (!lastResult) body = <p className="muted">Noch kein Ergebnis. Starte einen Run oder wähle einen Job unten.</p>;
  else if (lastResult.kind === "discover")
    body = viewDiscover(lastResult.result.data as ResearchData, lastResult.result.files, lastResult.result.cost_usd ?? null, abs => {
      const rel = abs.split("/runs/")[1];
      if (rel) openArtifact(rel);
    });
  else if (lastResult.kind === "score") body = viewScore(lastResult.result.result as ScoreResult);
  else if (lastResult.kind === "verify") body = viewVerify(lastResult.result.result as VerifyResult);
  else body = <pre>{JSON.stringify(lastResult.result, null, 2)}</pre>;

  return (
    <>
      {body}
      <Card title="Recent jobs">
        {jobs.length ? (
          <table>
            <thead><tr><th>ID</th><th>Kind</th><th>Status</th><th>Geschaffen (UTC)</th><th></th></tr></thead>
            <tbody>
              {jobs.map(j => (
                <tr key={j.id}>
                  <td style={{ fontFamily: "var(--mono)" }} className="small">{j.id}</td>
                  <td>{j.kind}</td>
                  <td><Badge tone={j.status === "done" ? "ok" : j.status === "error" ? "err" : "info"}>{j.status}</Badge></td>
                  <td className="small muted">{j.created ? new Date(j.created * 1000).toISOString().slice(11, 19) : ""}</td>
                  <td><button className="mini" onClick={() => loadJob(j.id)}>öffnen</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : <p className="muted small">keine Jobs in dieser Session</p>}
      </Card>
    </>
  );
}
