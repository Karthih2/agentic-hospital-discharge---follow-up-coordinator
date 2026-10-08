import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { api, ApiError, type Me } from "./api";

type Auth = { me: Me | null; loading: boolean; refresh: () => Promise<void>; logout: () => Promise<void> };
const AuthCtx = createContext<Auth>(null!);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<Me | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try { setMe(await api<Me>("/me")); }
    catch (e) { if (!(e instanceof ApiError) || e.status !== 0) setMe(null); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { void refresh(); }, [refresh]);

  const logout = useCallback(async () => {
    try { await api("/auth/logout", { method: "POST" }); } catch { /* cookies are cleared server side when reachable */ }
    setMe(null);
  }, []);

  return <AuthCtx.Provider value={{ me, loading, refresh, logout }}>{children}</AuthCtx.Provider>;
}
export const useAuth = () => useContext(AuthCtx);

export const homeFor = (role: Me["role"]) =>
  ({ patient: "/hub", family: "/hub", doctor: "/doctor", admin: "/admin/overview" })[role];
