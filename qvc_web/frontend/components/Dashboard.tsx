"use client";
import { useState } from "react";
import { useQvc } from "@/lib/useQvc";
import RunsTab from "./RunsTab";
import LiveTab from "./LiveTab";
import ResultsTab from "./ResultsTab";
import ArtifactsTab from "./ArtifactsTab";
import ConfigTab from "./ConfigTab";
import TeamTab from "./TeamTab";

const TABS: [string, string][] = [
  ["runs", "Runs"], ["team", "Team"], ["live", "Live"], ["results", "Results"],
  ["artifacts", "Artifacts"], ["config", "Config"],
];

export default function Dashboard() {
  const q = useQvc();
  const [tab, setTab] = useState<string>("runs");
  const [selArtifact, setSelArtifact] = useState<string | null>(null);

  const openArtifact = (rel: string) => { setSelArtifact(rel); setTab("artifacts"); };

  return (
    <>
      <header>
        <span className="brand">AI&nbsp;Pioneers</span>
        <h1>QVC Discovery</h1>
        <span className="sub">debug surface für <code>qvc_discovery.py</code> · Verifiable Quantum Circuit Compilation</span>
        <span className="spacer" />
        <span className={`pill ${q.status?.key_present ? "ok" : "err"}`}>key: {q.status?.key_present ? "✓ gesetzt" : "✗ fehlt"}</span>
        <span className={`pill ${q.status?.openrouter_installed ? "ok" : "err"}`}>sdk: {q.status?.openrouter_installed ? "✓" : "✗"}</span>
        <span className="pill">baseline: {q.status ? q.status.baseline_score.toFixed(3) : "…"}</span>
        <span className="pill cost">kosten: {q.lastResult?.result?.cost_usd != null ? "$" + Number(q.lastResult.result.cost_usd).toFixed(4) : "—"}</span>
      </header>
      <nav>
        {TABS.map(([id, label]) => (
          <button key={id} className={tab === id ? "active" : ""} onClick={() => setTab(id)}>{label}</button>
        ))}
      </nav>
      <main>
        {tab === "runs" && <RunsTab submit={q.submit} goLive={() => setTab("live")} status={q.status} />}
        {tab === "team" && <TeamTab submit={q.submit} activeJob={q.activeJob} lastResult={q.lastResult} />}
        {tab === "live" && <LiveTab activeJob={q.activeJob} trace={q.trace} logs={q.logs} stopPolling={q.stopPolling} />}
        {tab === "results" && <ResultsTab lastResult={q.lastResult} jobs={q.jobs} loadJob={q.loadJob} openArtifact={openArtifact} />}
        {tab === "artifacts" && <ArtifactsTab artifacts={q.artifacts} refreshArtifacts={q.refreshArtifacts} selected={selArtifact} onSelect={setSelArtifact} />}
        {tab === "config" && <ConfigTab status={q.status} />}
      </main>
    </>
  );
}
