"use client";
import React, { useState } from "react";

export function Badge({ tone = "muted", children }: { tone?: "ok" | "err" | "warn" | "info" | "hyp" | "muted"; children: React.ReactNode }) {
  return <span className={`badge b-${tone}`}>{children}</span>;
}

export function Card({ title, right, intro, children }: { title?: React.ReactNode; right?: React.ReactNode; intro?: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="card">
      {title != null && <h2>{title}{right}</h2>}
      {intro != null && <div className="card-intro">{intro}</div>}
      {children}
    </div>
  );
}

export function Dots({ n }: { n?: number }) {
  const v = Math.max(0, Math.min(5, Math.floor(Number(n) || 0)));
  return (
    <span>
      <span className="dots">
        {[0, 1, 2, 3, 4].map(i => <span key={i} className={`dot ${i < v ? "on" : ""}`} />)}
      </span>{" "}
      {v || 0}
    </span>
  );
}

export function KV({ pairs }: { pairs: [React.ReactNode, React.ReactNode][] }) {
  return (
    <div className="kv">
      {pairs.map(([k, v], i) => (
        <React.Fragment key={i}>
          <span className="k">{k}</span>
          <span>{typeof v === "boolean" ? <Badge tone={v ? "ok" : "err"}>{String(v)}</Badge> : v}</span>
        </React.Fragment>
      ))}
    </div>
  );
}

/** Kleines „i"-Symbol mit Tooltip (Hover + Klick). */
export function InfoTip({ text }: { text: string }) {
  const [open, setOpen] = useState(false);
  return (
    <span className="infotip" onMouseEnter={() => setOpen(true)} onMouseLeave={() => setOpen(false)}>
      <button
        type="button"
        className="info-btn"
        aria-label="Erklärung"
        onClick={(e) => { e.stopPropagation(); setOpen(o => !o); }}
      >i</button>
      {open && <span className="info-pop">{text}</span>}
    </span>
  );
}

/** Formularfeld mit Label, optionalem Info-Tooltip und Beschreibung. */
export function Field({ label, tip, desc, children, className }: {
  label: React.ReactNode; tip?: string; desc?: React.ReactNode; children: React.ReactNode; className?: string;
}) {
  return (
    <div className={className}>
      <label className="field-label">
        {label}
        {tip ? <InfoTip text={tip} /> : null}
      </label>
      {children}
      {desc ? <div className="field-desc">{desc}</div> : null}
    </div>
  );
}
