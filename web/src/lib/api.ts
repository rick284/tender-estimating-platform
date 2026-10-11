import type { Estimate } from "./types";

const BASE = (import.meta.env.VITE_API_URL as string | undefined) ?? "";

async function parse(res: Response): Promise<Estimate> {
  if (!res.ok) {
    let msg = `Request failed (${res.status})`;
    try { const j = await res.json(); if (j.detail) msg = String(j.detail); } catch { /* ignore */ }
    throw new Error(msg);
  }
  return res.json();
}

export async function importWorkbook(file: File): Promise<Estimate> {
  const fd = new FormData();
  fd.append("file", file);
  return parse(await fetch(`${BASE}/api/estimates/import`, { method: "POST", body: fd }));
}

export async function loadDemo(): Promise<Estimate> {
  return parse(await fetch(`${BASE}/api/demo`));
}
