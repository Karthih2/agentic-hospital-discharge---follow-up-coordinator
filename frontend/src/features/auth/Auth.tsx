import { useEffect, useState, type FormEvent } from "react";
import { Navigate, useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { PageShell } from "../../app/layouts";
import { Icon, LangMark } from "../../components/icons/Icon";
import { HeroArt, LanguageArt } from "../../components/illustrations/Illustrations";
import { ErrorNote, Field, ListSkeleton, Tabs, useDocTitle } from "../../components/ui";
import { api, ApiError, errText } from "../../lib/api";
import { homeFor, useAuth } from "../../lib/auth";
import { LANGS, useI18n, type Lang } from "../../lib/i18n";

/** Sign in for patients, family members and doctors. Sign up exists only on the family side. */
export function AuthPage({ initial }: { initial: "login" | "register" }) {
  const [sp] = useSearchParams();
  const doctor = sp.get("as") === "doctor";
  useDocTitle(doctor ? "Doctor sign in" : initial === "login" ? "Sign in" : "Sign up");
  const nav = useNavigate();
  const loc = useLocation();
  const { me, refresh } = useAuth();
  const [tab, setTab] = useState<"login" | "register">(doctor ? "login" : initial);
  const [name, setName] = useState("");
  const [login, setLogin] = useState("");
  const [pw, setPw] = useState("");
  const [kind, setKind] = useState<"family" | "patient">("family");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [forgot, setForgot] = useState(false);
  if (me) return <Navigate to="/start" replace />;

  async function submit(e: FormEvent) {
    e.preventDefault();
    setErr(""); setBusy(true);
    try {
      if (tab === "login") await api("/auth/login", { method: "POST", json: { login, password: pw } });
      else await api("/auth/register", { method: "POST", json: { name, login, password: pw, role: kind, language: "en" } });
      await refresh();
      const from = (loc.state as { from?: string } | null)?.from;
      nav(from && from !== "/admin" && !from.startsWith("/admin/") ? from : "/start", { replace: true });
    } catch (x) {
      setErr(x instanceof ApiError ? (x.status === 401 ? "That login or password is not right." : x.status === 429 ? "Too many attempts. Please wait a little and try again." : x.message) : "Something went wrong.");
    } finally { setBusy(false); }
  }

  return (
    <PageShell>
      <main className="container-page grid min-h-[70vh] items-center gap-10 py-12 lg:grid-cols-[1fr_28rem]">
        <div className="hidden lg:block">
          <HeroArt className="max-w-md" />
          <h1 className="mt-6 max-w-[16ch] font-display text-5xl font-bold">{doctor ? "Your review queue is waiting." : "Welcome back to your plan."}</h1>
          <p className="mt-4 text-xl text-ink-soft">
            {doctor ? "Doctors see only the items assigned to them, one at a time." : "Patients and family members share one family hub. Each patient decides who sees what."}
          </p>
        </div>
        <form onSubmit={submit} className="tile flex min-w-0 flex-col gap-5 p-6" aria-labelledby="auth-h">
          <h2 id="auth-h" className="font-display text-2xl font-bold">{doctor ? "Doctor sign in" : tab === "login" ? "Sign in" : "Create an account"}</h2>
          {!doctor && <Tabs label="Account" tabs={[{ id: "login", label: "Sign In" }, { id: "register", label: "Sign Up" }]} value={tab} onChange={(t) => { setTab(t); setErr(""); }} />}
          {tab === "register" && (
            <fieldset className="flex flex-col gap-2">
              <legend className="mb-1 font-display font-semibold">I am</legend>
              {([["family", "A family member or hub manager"], ["patient", "A patient"]] as const).map(([k, l]) => (
                <label key={k} className={`flex min-h-12 items-center gap-3 border-2 border-ink px-3 ${kind === k ? "bg-ground-deep" : "bg-tile"}`} style={{ borderRadius: 4 }}>
                  <input type="radio" name="kind" className="h-5 w-5" checked={kind === k} onChange={() => setKind(k)} />{l}
                </label>))}
            </fieldset>)}
          {tab === "register" && <Field label="Name"><input className="field" value={name} onChange={(e) => setName(e.target.value)} required autoComplete="name" /></Field>}
          <Field label="Login"><input className="field" type="text" value={login} onChange={(e) => setLogin(e.target.value)} required autoComplete="username" minLength={3} /></Field>
          <Field label="Password" hint={tab === "register" ? "At least 8 characters." : undefined}>
            <input className="field" type="password" value={pw} onChange={(e) => setPw(e.target.value)} required minLength={tab === "register" ? 8 : 1} autoComplete={tab === "login" ? "current-password" : "new-password"} />
          </Field>
          {err && <ErrorNote>{err}</ErrorNote>}
          <button className="btn btn-primary" disabled={busy}>{busy ? "Please wait" : tab === "login" ? "Sign In" : "Sign Up"}</button>
          {tab === "login" && (
            <div>
              <button type="button" className="font-semibold text-teal underline" onClick={() => setForgot((f) => !f)}>Forgot password</button>
              {forgot && <p className="mt-2 text-base text-ink-soft">Password reset is not part of this prototype. Ask the hospital desk to reset your account.</p>}
            </div>)}
        </form>
      </main>
    </PageShell>
  );
}

/** Language selection, shown once after the first sign in. */
export function LanguagePage() {
  useDocTitle("Choose language");
  const nav = useNavigate();
  const { me, refresh } = useAuth();
  const { setLang } = useI18n();
  const [sel, setSel] = useState<Lang>((me?.language as Lang) || "en");
  const [err, setErr] = useState("");
  async function go() {
    try {
      await api("/me/language", { method: "PUT", json: { language: sel } });
      setLang(sel);
      try { localStorage.setItem(`langChosen:${me?.id}`, "1"); } catch { /* storage can be blocked */ }
      await refresh();
      nav("/start", { replace: true });
    } catch (x) { setErr(errText(x, "Could not save your language.")); }
  }
  return (
    <div className="mx-auto max-w-3xl">
      <LanguageArt className="mb-4 max-w-xs" />
      <h1 className="font-display text-3xl font-bold">Choose your language</h1>
      <p className="mt-1 text-ink-soft">Your tasks will be shown in this language. You can change it later.</p>
      <div role="radiogroup" aria-label="Language" className="mt-6 grid grid-cols-2 gap-4 sm:grid-cols-3">
        {LANGS.map((l) => (
          <button key={l.code} role="radio" aria-checked={sel === l.code} onClick={() => setSel(l.code)}
            className={`flex min-h-32 min-w-0 flex-col items-center justify-center gap-2 p-4 text-center ${sel === l.code ? "border-[4px] border-teal bg-ground-deep" : "tile"}`} style={{ borderRadius: 4 }}>
            <LangMark code={l.code} size={48} />
            <span lang={l.code} className="font-display text-2xl font-bold">{l.native}</span>
            <span className="text-base text-ink-soft">{l.name}</span>
          </button>))}
      </div>
      {err && <div className="mt-4"><ErrorNote>{err}</ErrorNote></div>}
      <button className="btn btn-primary mt-6 w-full sm:w-auto" disabled={!sel} onClick={go}><Icon name="confirmed" size={22} />Continue</button>
    </div>
  );
}

/** Where each role lands after sign in: the language once, then the role's own home. */
export function StartPage() {
  const { me } = useAuth();
  const [dest, setDest] = useState<string | null>(null);
  useEffect(() => {
    if (!me) return;
    let chosen = true;
    try { chosen = localStorage.getItem(`langChosen:${me.id}`) === "1"; } catch { /* treat as chosen */ }
    setDest(chosen || me.role === "admin" ? homeFor(me.role) : "/language");
  }, [me]);
  return dest ? <Navigate to={dest} replace /> : <ListSkeleton rows={2} />;
}
