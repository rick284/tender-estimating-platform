import { useCallback, useEffect, useState } from "react";
import { importWorkbook, loadDemo } from "./lib/api";
import type { Estimate } from "./lib/types";
import { NAV, Shell, type PageId } from "./components/Shell";
import { Overview } from "./pages/Overview";
import { Consolidated } from "./pages/Consolidated";
import { Tender } from "./pages/Tender";
import { QSTakeoff } from "./pages/QSTakeoff";
import { BuildUp } from "./pages/BuildUp";
import { Weather } from "./pages/Weather";
import { RateLibrary } from "./pages/Library";
import { ImportScreen } from "./pages/Import";

const ids = NAV.map((n) => n.id) as string[];
const fromHash = (): PageId => { const h = window.location.hash.replace(/^#\/?/, ""); return (ids.includes(h) ? h : "overview") as PageId; };

export default function App() {
  const [est, setEst] = useState<Estimate | null>(null);
  const [page, setPage] = useState<PageId>(fromHash());
  const [code, setCode] = useState("all");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [demo, setDemo] = useState(false);

  useEffect(() => { const f = () => setPage(fromHash()); window.addEventListener("hashchange", f); return () => window.removeEventListener("hashchange", f); }, []);
  useEffect(() => { fetch("/api/demo").then((r) => setDemo(r.ok)).catch(() => setDemo(false)); }, []);
  const go = useCallback((p: PageId) => { window.location.hash = `/${p}`; setPage(p); }, []);

  const run = async (fn: () => Promise<Estimate>) => {
    setBusy(true); setError("");
    try { setEst(await fn()); } catch (e) { setError(e instanceof Error ? e.message : "Something went wrong."); } finally { setBusy(false); }
  };

  if (!est) return <ImportScreen busy={busy} error={error} demoAvailable={demo} onFile={(f) => run(() => importWorkbook(f))} onDemo={() => run(loadDemo)} />;

  return (
    <Shell est={est} page={page} onGo={go} onReset={() => { setEst(null); setCode("all"); }}>
      {page === "overview" && <Overview est={est} go={go} />}
      {page === "consolidated" && <Consolidated est={est} />}
      {page === "tender" && <Tender est={est} />}
      {page === "qs" && <QSTakeoff est={est} openRows={(c) => { setCode(c); go("buildup"); }} />}
      {page === "buildup" && <BuildUp est={est} code={code} setCode={setCode} />}
      {page === "weather" && <Weather est={est} />}
      {page === "library" && <RateLibrary est={est} />}
    </Shell>
  );
}
