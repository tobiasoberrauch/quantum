#!/usr/bin/env python3
"""LLM-Trace-Proxy: protokolliert jeden Chat-Completions-Aufruf und zeigt ihn live im Browser.

Sitzt zwischen main.py (oder jedem OpenAI-kompatiblen Client) und dem echten Endpunkt:

    python3 qvc_ui/llm_trace_proxy.py                       # Viewer: http://127.0.0.1:8787/
    LLM_API_URL=http://127.0.0.1:8787/v1/chat/completions \\
    LLM_EXTRA_BODY='{"chat_template_kwargs":{"enable_thinking":false}}' LLM_TEMPERATURE=0.1 LLM_TIMEOUT=60 \\
        python3 main.py agent invsqrt.kmx -o out.kmx

(Die drei LLM_*-Variablen setzen, was main.py nur beim direkten Weinstadt-Endpunkt automatisch setzt.)

Je Aufruf: Modell, Dauer, Tokens, die Tool-Aufrufe der Antwort und die Tool-Ergebnisse, die mit der
Anfrage zurückkamen (also was der Agent als Antwort auf seinen letzten Schritt gesehen hat).
Alles landet zusätzlich in runs/llm_trace/<start>.jsonl. Nur Standardbibliothek, bindet nur an 127.0.0.1;
Authorization-Header werden weitergereicht, aber nie gespeichert.
"""
from __future__ import annotations

import hashlib
import json
import os
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List

UPSTREAM = os.environ.get("LLM_UPSTREAM", "http://192.168.212.81:8000").rstrip("/")
PORT = int(os.environ.get("LLM_TRACE_PORT", "8787"))
UPSTREAM_TIMEOUT_S = float(os.environ.get("LLM_TRACE_TIMEOUT", "900"))
LOG_DIR = Path(__file__).resolve().parents[1] / "runs" / "llm_trace"
FORWARDED_HEADERS = ("Content-Type", "Authorization", "HTTP-Referer", "X-Title")
PREVIEW_CHARS = 1500

_calls: List[Dict[str, Any]] = []
_lock = threading.Lock()
_log_file = LOG_DIR / time.strftime("%Y%m%d-%H%M%S.jsonl")


def _session_id(messages: List[Dict[str, Any]]) -> str:
    """Gleicher System-Prompt + erste Nutzernachricht = dieselbe Agenten-Sitzung."""
    head = json.dumps(messages[:2], sort_keys=True, ensure_ascii=False)
    return hashlib.sha1(head.encode("utf-8")).hexdigest()[:8]


def _incoming_tool_results(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Tool-Ergebnisse nach der letzten Assistenten-Nachricht, mit dem Namen des aufgerufenen Tools."""
    last = max((i for i, m in enumerate(messages) if m.get("role") == "assistant"), default=-1)
    if last < 0:
        return []
    names = {tc.get("id"): tc.get("function", {}).get("name", "?") for tc in messages[last].get("tool_calls") or []}
    calls = {tc.get("id"): tc.get("function", {}).get("arguments", "") for tc in messages[last].get("tool_calls") or []}
    out = []
    for m in messages[last + 1:]:
        if m.get("role") != "tool":
            continue
        content = m.get("content") or ""
        verdict = None
        try:
            parsed = json.loads(content)
            if isinstance(parsed, dict) and "accepted" in parsed:
                verdict = bool(parsed["accepted"])
        except (json.JSONDecodeError, TypeError):
            pass
        cid = m.get("tool_call_id")
        out.append({"name": names.get(cid, "?"), "arguments": calls.get(cid, ""), "content": content,
                    "accepted": verdict})
    return out


def _record(body: Dict[str, Any], status: int, response: Any, seconds: float, error: str = "") -> Dict[str, Any]:
    messages = body.get("messages") or []
    choice = (response or {}).get("choices", [{}])[0] if isinstance(response, dict) else {}
    reply = choice.get("message") or {}
    with _lock:
        rec = {
            "id": len(_calls) + 1,
            "ts": time.time(),
            "session": _session_id(messages),
            "step": sum(m.get("role") == "assistant" for m in messages) + 1,
            "model": body.get("model", "?"),
            "status": status,
            "seconds": round(seconds, 2),
            "usage": (response or {}).get("usage") if isinstance(response, dict) else None,
            "n_messages": len(messages),
            "tools_offered": len(body.get("tools") or []),
            "tool_results": _incoming_tool_results(messages),
            "reply_content": reply.get("content") or "",
            "reply_tool_calls": [{"name": tc.get("function", {}).get("name", "?"),
                                  "arguments": tc.get("function", {}).get("arguments", "")}
                                 for tc in reply.get("tool_calls") or []],
            "finish_reason": choice.get("finish_reason"),
            "error": error,
            "request": body,
            "response": response,
        }
        _calls.append(rec)
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        with open(_log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def _summary(rec: Dict[str, Any]) -> Dict[str, Any]:
    """Listenansicht ohne die vollständigen Nachrichten (die gibt es über /api/call/<id>)."""
    out = {k: v for k, v in rec.items() if k not in ("request", "response")}
    out["tool_results"] = [{**r, "content": r["content"][:PREVIEW_CHARS]} for r in rec["tool_results"]]
    out["reply_content"] = rec["reply_content"][:PREVIEW_CHARS]
    return out


class Handler(BaseHTTPRequestHandler):
    server_version = "llm-trace/1"

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 - leise; der Viewer ist das Protokoll
        pass

    def _send(self, status: int, payload: Any, ctype: str = "application/json") -> None:
        data = payload if isinstance(payload, bytes) else json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _forward(self, method: str, body: bytes | None) -> tuple[int, bytes]:
        headers = {h: self.headers[h] for h in FORWARDED_HEADERS if self.headers.get(h)}
        req = urllib.request.Request(UPSTREAM + self.path, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=UPSTREAM_TIMEOUT_S) as resp:
                return resp.status, resp.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()

    def do_GET(self) -> None:
        if self.path in ("/", "/index.html"):
            self._send(200, VIEWER_HTML.encode("utf-8"), "text/html; charset=utf-8")
        elif self.path.startswith("/api/calls"):
            since = int(self.path.partition("since=")[2] or 0)
            with _lock:
                self._send(200, {"upstream": UPSTREAM, "log": str(_log_file),
                                 "calls": [_summary(c) for c in _calls[since:]]})
        elif self.path.startswith("/api/call/"):
            idx = int(self.path.rsplit("/", 1)[1]) - 1
            with _lock:
                rec = _calls[idx] if 0 <= idx < len(_calls) else None
            self._send(200 if rec else 404, rec or {"error": "unbekannt"})
        elif self.path.startswith("/v1/"):
            try:
                status, data = self._forward("GET", None)
            except (urllib.error.URLError, OSError) as e:
                status, data = 502, json.dumps({"error": f"Upstream nicht erreichbar: {e}"}).encode()
            self._send(status, data)
        else:
            self._send(404, {"error": "nicht gefunden"})

    def do_POST(self) -> None:
        raw = self.rfile.read(int(self.headers.get("Content-Length") or 0))
        try:
            body = json.loads(raw or b"{}")
        except json.JSONDecodeError:
            body = {}
        t0 = time.time()
        try:
            status, data = self._forward("POST", raw)
        except (urllib.error.URLError, OSError) as e:
            status, data = 502, json.dumps({"error": f"Upstream nicht erreichbar: {e}"}).encode()
        try:
            parsed = json.loads(data)
        except json.JSONDecodeError:
            parsed = data.decode("utf-8", "replace")[:5000]
        if self.path.endswith("/chat/completions"):
            err = "" if status == 200 else (parsed if isinstance(parsed, str) else json.dumps(parsed))[:2000]
            _record(body, status, parsed if isinstance(parsed, dict) else None, time.time() - t0, err)
        self._send(status, data)


VIEWER_HTML = r"""<!doctype html>
<html lang="de"><head><meta charset="utf-8"><title>LLM-Trace</title>
<style>
:root{--bg:#0f1115;--panel:#161a21;--line:#262c36;--text:#d7dce4;--dim:#8a93a3;--acc:#e0a33a;
--ok:#4cc38a;--bad:#e5615b;--tool:#6aa9ff;font:13px/1.45 ui-monospace,SFMono-Regular,Menlo,monospace}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text)}
header{display:flex;gap:28px;align-items:baseline;padding:14px 20px;border-bottom:1px solid var(--line)}
header h1{font-size:15px;margin:0;color:var(--acc);letter-spacing:.02em}
.stat b{display:block;font-size:20px;color:var(--text)}.stat{color:var(--dim)}
main{display:grid;grid-template-columns:minmax(380px,40%) 1fr;height:calc(100vh - 64px)}
#list{overflow:auto;border-right:1px solid var(--line)}
.sess{padding:6px 14px;color:var(--dim);background:#12151b;border-bottom:1px solid var(--line);position:sticky;top:0}
.row{padding:8px 14px;border-bottom:1px solid var(--line);cursor:pointer}
.row:hover{background:#1b2029}.row.sel{background:#212835;box-shadow:inset 3px 0 var(--acc)}
.meta{display:flex;gap:10px;color:var(--dim)}.meta .err{color:var(--bad)}
.chips{margin-top:4px;display:flex;flex-wrap:wrap;gap:4px}
.chip{padding:1px 7px;border-radius:9px;background:#1e2633;color:var(--tool)}
.chip.ok{color:var(--ok);background:#15281f}.chip.bad{color:var(--bad);background:#2a1716}
#detail{overflow:auto;padding:16px 22px}#detail h2{font-size:13px;color:var(--acc);margin:18px 0 6px}
pre{white-space:pre-wrap;word-break:break-word;background:var(--panel);border:1px solid var(--line);
border-radius:6px;padding:10px;margin:4px 0}
details summary{cursor:pointer;color:var(--dim);margin:6px 0}.empty{color:var(--dim);padding:30px}
.role{color:var(--tool)}
</style></head><body>
<header><h1>LLM-Trace</h1>
<div class="stat"><b id="s-calls">0</b>Aufrufe</div><div class="stat"><b id="s-tools">0</b>Tool-Aufrufe</div>
<div class="stat"><b id="s-acc">0 / 0</b>Rewrites angenommen / vorgeschlagen</div>
<div class="stat"><b id="s-tok">0</b>Tokens</div><div class="stat"><b id="s-lat">–</b>Ø Dauer</div>
<div class="stat" id="s-up" style="margin-left:auto"></div></header>
<main><div id="list"><div class="empty">Warte auf den ersten Aufruf …</div></div>
<div id="detail"><div class="empty">Aufruf links anklicken.</div></div></main>
<script>
const calls=[];let sel=null;
const el=(t,c,x)=>{const e=document.createElement(t);if(c)e.className=c;if(x!=null)e.textContent=x;return e};
const fmtArgs=a=>{try{return JSON.stringify(JSON.parse(a),null,1)}catch{return a||''}};
function stats(){let tools=0,acc=0,prop=0,tok=0,sec=0;
 for(const c of calls){tools+=c.reply_tool_calls.length;sec+=c.seconds;tok+=(c.usage&&c.usage.total_tokens)||0;
  for(const r of c.tool_results)if(r.name==='propose_rewrite'){prop++;if(r.accepted)acc++}}
 document.getElementById('s-calls').textContent=calls.length;document.getElementById('s-tools').textContent=tools;
 document.getElementById('s-acc').textContent=acc+' / '+prop;document.getElementById('s-tok').textContent=tok.toLocaleString('de');
 document.getElementById('s-lat').textContent=calls.length?(sec/calls.length).toFixed(1)+' s':'–'}
function row(c){const r=el('div','row');r.onclick=()=>show(c.id,r);
 const m=el('div','meta');m.append(el('span',null,'#'+c.id),el('span',null,new Date(c.ts*1000).toLocaleTimeString('de')),
  el('span',null,'Schritt '+c.step),el('span',null,c.seconds+' s'),
  el('span',null,c.usage?(c.usage.prompt_tokens+'→'+c.usage.completion_tokens+' tok'):''));
 if(c.status!==200)m.append(el('span','err','HTTP '+c.status));r.append(m);
 const ch=el('div','chips');
 for(const t of c.tool_results)if(t.name==='propose_rewrite')ch.append(el('span','chip '+(t.accepted?'ok':'bad'),
  (t.accepted?'✓ ':'✗ ')+'Rewrite'));
 for(const t of c.reply_tool_calls)ch.append(el('span','chip','→ '+t.name));
 if(!c.reply_tool_calls.length&&c.reply_content)ch.append(el('span','chip','Text: '+c.reply_content.slice(0,60)));
 r.append(ch);return r}
function render(){const L=document.getElementById('list');L.textContent='';let last=null;
 for(const c of [...calls].reverse()){if(c.session!==last){L.append(el('div','sess','Sitzung '+c.session+' · '+c.model+
  (c.tools_offered?' · Tool-Calling':' · JSON-Modus')));last=c.session}
  const r=row(c);if(c.id===sel)r.classList.add('sel');L.append(r)}stats()}
async function show(id,r){sel=id;document.querySelectorAll('.row.sel').forEach(x=>x.classList.remove('sel'));if(r)r.classList.add('sel');
 const c=await (await fetch('/api/call/'+id)).json();const D=document.getElementById('detail');D.textContent='';
 D.append(el('h2',null,`#${c.id} · ${c.model} · Schritt ${c.step} · ${c.seconds} s · finish=${c.finish_reason}`));
 if(c.error)D.append(el('h2',null,'Fehler'),el('pre',null,c.error));
 if(c.tool_results.length){D.append(el('h2',null,'Eingang: Tool-Ergebnisse des letzten Schritts'));
  for(const t of c.tool_results){const d=el('details');d.open=true;
   d.append(el('summary',null,t.name+(t.accepted===null?'':(t.accepted?'  ✓ angenommen':'  ✗ abgelehnt'))+'  '+t.arguments.slice(0,140)));
   d.append(el('pre',null,fmtArgs(t.content)));D.append(d)}}
 if(c.reply_tool_calls.length){D.append(el('h2',null,'Antwort: Tool-Aufrufe'));
  for(const t of c.reply_tool_calls)D.append(el('pre',null,t.name+'\n'+fmtArgs(t.arguments)))}
 if(c.reply_content)D.append(el('h2',null,'Antwort: Text'),el('pre',null,c.reply_content));
 const all=el('details');all.append(el('summary',null,`Gesamte Anfrage (${c.n_messages} Nachrichten)`));
 for(const m of (c.request.messages||[])){const p=el('pre');p.append(el('span','role',m.role+(m.name?' '+m.name:'')+'\n'));
  p.append(document.createTextNode(typeof m.content==='string'?m.content:JSON.stringify(m.content||m.tool_calls,null,1)));all.append(p)}
 D.append(all);const raw=el('details');raw.append(el('summary',null,'Rohantwort (JSON)'),el('pre',null,JSON.stringify(c.response,null,1)));D.append(raw)}
async function poll(){try{const j=await (await fetch('/api/calls?since='+calls.length)).json();
 document.getElementById('s-up').textContent='→ '+j.upstream;if(j.calls.length){calls.push(...j.calls);render()}}catch(e){}
 setTimeout(poll,2000)}
poll();
</script></body></html>"""


def main() -> None:
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"LLM-Trace-Proxy: http://127.0.0.1:{PORT}/  ->  {UPSTREAM}   (Protokoll: {_log_file})", flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
