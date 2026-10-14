import { useEffect, useState } from "react";

export type Route =
  | { name: "login" }
  | { name: "tenders" }
  | { name: "timesheet" }
  | { name: "tender"; id: string; page: string; rev: number | null; sub?: string };

export function parse(hash: string): Route {
  const [path, query = ""] = hash.replace(/^#\/?/, "").split("?");
  const parts = path.split("/").filter(Boolean);
  if (parts[0] === "login") return { name: "login" };
  if (parts[0] === "timesheet") return { name: "timesheet" };
  if (parts[0] === "tenders" && parts[1]) {
    const rev = Number(new URLSearchParams(query).get("rev"));
    return { name: "tender", id: parts[1], page: parts[2] || "overview", rev: rev > 0 ? rev : null, sub: parts[3] };
  }
  return { name: "tenders" };
}
export const href = (r: Route): string =>
  r.name === "login" ? "#/login" : r.name === "tenders" ? "#/tenders" : r.name === "timesheet" ? "#/timesheet" : `#/tenders/${r.id}/${r.page}${r.sub ? `/${r.sub}` : ""}${r.rev ? `?rev=${r.rev}` : ""}`;
export const go = (r: Route) => { window.location.hash = href(r).slice(1); window.scrollTo(0, 0); };

export function useRoute(): Route {
  const [r, setR] = useState<Route>(parse(window.location.hash));
  useEffect(() => { const f = () => setR(parse(window.location.hash)); window.addEventListener("hashchange", f); return () => window.removeEventListener("hashchange", f); }, []);
  return r;
}
