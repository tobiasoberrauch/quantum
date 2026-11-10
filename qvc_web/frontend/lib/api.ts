const BASE = "/api";

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(BASE + path, { cache: "no-store", ...init });
  if (!r.ok) {
    let d: string;
    try {
      const j = await r.json();
      d = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail);
    } catch {
      d = r.statusText;
    }
    throw new Error(d);
  }
  return r.json() as Promise<T>;
}

export const get = <T>(p: string) => req<T>(p);
export const post = <T>(p: string, body: unknown) =>
  req<T>(p, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
