import { useEffect } from "react";
import { AuthProvider, useAuth } from "./lib/auth";
import { go, useRoute } from "./lib/route";
import { Shell } from "./components/Shell";
import { Login } from "./pages/Login";
import { Tenders } from "./pages/Tenders";
import { Workspace } from "./pages/Workspace";
import { Toaster } from "./lib/toast";

function Routes() {
  const { user, loading, logout } = useAuth();
  const route = useRoute();

  useEffect(() => {
    if (loading) return;
    if (!user && route.name !== "login") go({ name: "login" });
    if (user && route.name === "login") go({ name: "tenders" });
  }, [user, loading, route.name]);

  if (loading) return <div className="p-8 text-sm text-muted-foreground" aria-live="polite">Loading…</div>;
  if (!user) return route.name === "login" ? <Login /> : null;
  if (route.name === "tender") return <Workspace id={route.id} page={route.page} rev={route.rev} sub={route.sub} user={user} onLogout={logout} />;
  if (route.name === "tenders") return <Shell user={user} route={route} onLogout={logout}><Tenders /></Shell>;
  return null;
}

export default function App() {
  return <AuthProvider><Routes /><Toaster /></AuthProvider>;
}
