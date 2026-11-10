"use client";
import type { Status } from "@/lib/types";
import { Card, KV } from "./ui";

export default function ConfigTab({ status }: { status: Status | null }) {
  if (!status) return <div className="card"><p className="muted">Status wird geladen…</p></div>;
  return (
    <>
      <Card title="Umgebung">
        <KV pairs={[
          ["key_present", status.key_present],
          ["openrouter_installed", status.openrouter_installed],
          ["jsonschema_installed", status.jsonschema_installed],
          ["venv_qvc", status.venv_qvc],
          ["venv_chem", status.venv_chem],
          ["runs_dir", status.runs_dir],
          ["adapters_dir", status.adapters_dir],
        ]} />
      </Card>
      <Card title="Referenzkosten & Baseline">
        <KV pairs={[
          ["reference_costs", JSON.stringify(status.reference_costs)],
          ["baseline_ratios", JSON.stringify(status.baseline_ratios)],
          ["baseline_score", status.baseline_score.toFixed(4)],
        ]} />
      </Card>
      <Card title="Modell-Chain je Rolle">
        {Object.entries(status.chains).map(([k, v]) => (
          <div key={k} className="kv" style={{ marginBottom: 6 }}>
            <span className="k">{k}</span><span>{v.join(" → ")}</span>
          </div>
        ))}
      </Card>
    </>
  );
}
