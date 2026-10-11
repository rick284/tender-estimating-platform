import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api, setUnauthorizedHandler, tokenStore } from "./api";
import type { User } from "./types";

interface AuthCtx { user: User | null; loading: boolean; login: (e: string, p: string) => Promise<void>; register: (b: { email: string; password: string; name: string; company: string }) => Promise<void>; logout: () => void }
const Ctx = createContext<AuthCtx>(null as never);
export const useAuth = () => useContext(Ctx);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(!!tokenStore.get());
  const logout = useCallback(() => { tokenStore.clear(); setUser(null); window.location.hash = "/login"; }, []);

  useEffect(() => { setUnauthorizedHandler(logout); }, [logout]);
  useEffect(() => {
    if (!tokenStore.get()) return;
    api.me().then(setUser).catch(() => tokenStore.clear()).finally(() => setLoading(false));
  }, []);

  const value = useMemo<AuthCtx>(() => ({
    user, loading, logout,
    login: async (e, p) => { const r = await api.login(e, p); tokenStore.set(r.token); setUser(r.user); },
    register: async (b) => { const r = await api.register(b); tokenStore.set(r.token); setUser(r.user); },
  }), [user, loading, logout]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}
