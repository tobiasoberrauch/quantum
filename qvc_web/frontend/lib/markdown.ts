// Minimal markdown -> HTML (headings, bold/italic/inline-code, code fences, lists).
function inline(s: string): string {
  return s
    .replace(/[&<>]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c] as string))
    .replace(/\*\*(.+?)\*\*/g, "<b>$1</b>")
    .replace(/`([^`]+?)`/g, "<code>$1</code>")
    .replace(/\*(.+?)\*/g, "<i>$1</i>");
}

export function md(src?: string | null): string {
  const lines = String(src ?? "").split("\n");
  let out = "";
  let inCode = false;
  let list = "";
  const closeList = () => { if (list) { out += `</${list}>`; list = ""; } };
  for (const ln of lines) {
    if (ln.trim().startsWith("```")) { closeList(); out += inCode ? "</pre>" : "<pre>"; inCode = !inCode; continue; }
    if (inCode) { out += inline(ln) + "\n"; continue; }
    const h = ln.match(/^(#{1,6})\s+(.*)$/);
    if (h) { closeList(); out += `<h${h[1].length}>${inline(h[2])}</h${h[1].length}>`; continue; }
    const ul = ln.match(/^\s*[-*]\s+(.*)$/);
    const ol = ln.match(/^\s*\d+\.\s+(.*)$/);
    if (ul || ol) {
      const type = ul ? "ul" : "ol";
      if (list !== type) { closeList(); out += `<${type}>`; list = type; }
      out += `<li>${inline((ul || ol)![1])}</li>`;
      continue;
    }
    closeList();
    if (ln.trim() === "") continue;
    out += `<p>${inline(ln)}</p>`;
  }
  closeList();
  if (inCode) out += "</pre>";
  return out;
}
