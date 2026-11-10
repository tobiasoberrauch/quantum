"use client";
import { useEffect, useState } from "react";
import * as api from "@/lib/api";
import type { Artifact } from "@/lib/types";
import { md } from "@/lib/markdown";
import { Card } from "./ui";

interface Props {
  artifacts: Artifact[];
  refreshArtifacts: () => void;
  selected: string | null;
  onSelect: (p: string | null) => void;
}

export default function ArtifactsTab({ artifacts, refreshArtifacts, selected, onSelect }: Props) {
  const [content, setContent] = useState<{ path: string; size: number; truncated: boolean; text: string; json: any } | null>(null);

  useEffect(() => {
    if (!selected) { setContent(null); return; }
    api.get<any>("/artifact?path=" + encodeURIComponent(selected)).then(setContent).catch(() => setContent(null));
  }, [selected]);

  return (
    <div className="row">
      <Card title={<span>runs/ <button className="mini" onClick={refreshArtifacts}>↻</button></span>}>
        <div className="filetree">
          {artifacts.length ? artifacts.map(f => (
            <div key={f.path} className={f.path === selected ? "sel" : ""} onClick={() => onSelect(f.path)}>
              {f.path} <span className="muted small">({f.size})</span>
            </div>
          )) : <p className="muted small">leer</p>}
        </div>
      </Card>
      <Card title="Inhalt">
        {content ? (
          <>
            <div className="small muted" style={{ marginBottom: 6 }}>{content.path} · {content.size} B{content.truncated ? " · (gekürzt)" : ""}</div>
            {content.json != null
              ? <pre>{JSON.stringify(content.json, null, 2)}</pre>
              : content.path.endsWith(".md")
                ? <div className="md" dangerouslySetInnerHTML={{ __html: md(content.text) }} />
                : <pre>{content.text}</pre>}
          </>
        ) : <p className="muted small">Datei links wählen.</p>}
      </Card>
    </div>
  );
}
