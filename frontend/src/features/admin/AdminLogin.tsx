import { useEffect, useState, type FormEvent } from "react";
import { Navigate } from "react-router-dom";
import { Brand } from "../../app/layouts";
import { ErrorNote, Field, useDocTitle } from "../../components/ui";
import { api, ApiError } from "../../lib/api";
import { useAuth } from "../../lib/auth";

/** Hospital admin center login. Own page, noindex, not linked from anywhere. */
export function AdminLogin() {
  useDocTitle("Admin");
  const { me, refresh } = useAuth();
  const [login, setLogin] = useState(""); const [pw, setPw] = useState(""); const [err, setErr] = useState("");
  useEffect(() => {
    const m = document.createElement("meta"); m.name = "robots"; m.content = "noindex, nofollow"; document.head.appendChild(m);
    return () => { m.remove(); };
  }, []);
  if (me?.role === "admin") return <Navigate to="/admin/overview" replace />;
  async function submit(e: FormEvent) {
    e.preventDefault(); setErr("");
    try { await api("/auth/login", { method: "POST", json: { login, password: pw } }); await refresh(); }
    catch (x) { setErr(x instanceof ApiError && x.status === 401 ? "That login or password is not right." : "Could not sign in."); }
  }
  return (
    <main className="container-page flex min-h-screen flex-col items-center justify-center gap-6 py-12">
      <Brand to={null} />
      <form onSubmit={submit} className="tile flex w-full max-w-md flex-col gap-5 p-6">
        <h1 className="font-display text-2xl font-bold">Hospital admin center</h1>
        {me && <ErrorNote>This account is not an admin account.</ErrorNote>}
        <Field label="Login"><input className="field" value={login} onChange={(e) => setLogin(e.target.value)} autoComplete="username" required /></Field>
        <Field label="Password"><input className="field" type="password" value={pw} onChange={(e) => setPw(e.target.value)} autoComplete="current-password" required /></Field>
        {err && <ErrorNote>{err}</ErrorNote>}
        <button className="btn btn-primary">Sign in</button>
      </form>
    </main>
  );
}
