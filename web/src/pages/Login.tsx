import { useEffect, useState, type FormEvent } from "react";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { go } from "../lib/route";

export function Login() {
  const { login, register } = useAuth();
  const [cfg, setCfg] = useState<{ registration_open: boolean; first_account: boolean } | null>(null);
  const [mode, setMode] = useState<"in" | "up">("in");
  const [f, setF] = useState({ email: "", password: "", name: "", company: "" });
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => { api.authConfig().then((c) => { setCfg(c); if (c.first_account) setMode("up"); }).catch(() => setErr("Can't reach the server. Check your connection and try again.")); }, []);

  const submit = async (e: FormEvent) => {
    e.preventDefault(); setBusy(true); setErr("");
    try {
      if (mode === "in") await login(f.email, f.password); else await register(f);
      go({ name: "tenders" });
    } catch (x) { setErr(x instanceof Error ? x.message : "Something went wrong."); } finally { setBusy(false); }
  };
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement>) => setF({ ...f, [k]: e.target.value });
  const field = "mt-1 h-10 w-full border bg-background px-3 text-sm focus:border-primary";

  return (
    <div className="flex min-h-screen items-center justify-center px-4 py-10">
      <form onSubmit={submit} className="w-full max-w-sm" noValidate>
        <div className="mb-8">
          <div className="font-heading text-2xl font-black uppercase tracking-tight">Blackline QSi Pro</div>
          <div className="label mt-1">Civil &amp; commercial tenders</div>
        </div>
        <h1 className="text-xl">{mode === "in" ? "Sign in" : cfg?.first_account ? "Create your workspace" : "Create account"}</h1>
        {mode === "up" && cfg?.first_account && <p className="mt-2 text-sm text-muted-foreground">This is the first account, so it becomes the owner of the workspace.</p>}
        <div className="mt-6 space-y-4">
          {mode === "up" && (
            <>
              <label className="block"><span className="label">Your name</span><input className={field} value={f.name} onChange={set("name")} autoComplete="name" required /></label>
              <label className="block"><span className="label">Company</span><input className={field} value={f.company} onChange={set("company")} autoComplete="organization" required /></label>
            </>
          )}
          <label className="block"><span className="label">Email</span><input type="email" className={field} value={f.email} onChange={set("email")} autoComplete="email" required /></label>
          <label className="block"><span className="label">Password</span><input type="password" className={field} value={f.password} onChange={set("password")} autoComplete={mode === "in" ? "current-password" : "new-password"} required />
            {mode === "up" && <span className="mt-1 block text-xs text-muted-foreground">At least 10 characters.</span>}</label>
        </div>
        {err && <div role="alert" className="mt-4 border border-red-line bg-red-bg px-4 py-3 text-sm text-red-fg">{err}</div>}
        <button className="btn btn-solid mt-6 w-full !py-3" disabled={busy}>{busy ? "Please wait…" : mode === "in" ? "Sign in" : "Create account"}</button>
        {cfg?.registration_open && !cfg.first_account && (
          <button type="button" className="mt-4 text-sm underline underline-offset-4" onClick={() => { setMode(mode === "in" ? "up" : "in"); setErr(""); }}>
            {mode === "in" ? "Create an account" : "I already have an account"}
          </button>
        )}
        {cfg && !cfg.registration_open && mode === "in" && <p className="mt-6 text-xs text-muted-foreground">Accounts are by invitation. Ask your workspace owner to add you.</p>}
      </form>
    </div>
  );
}
