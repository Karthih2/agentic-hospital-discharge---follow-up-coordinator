import { useState, type ReactNode } from "react";
import { Link, NavLink, Outlet } from "react-router-dom";
import { Icon, IconTile, LangMark, type IconName } from "../components/icons/Icon";
import RouteTransition from "../components/motion/RouteTransition";
import { useAuth } from "../lib/auth";
import { LANGS, useI18n, type Lang } from "../lib/i18n";
import type { Role } from "../lib/api";

export function Brand({ small = false, to = "/" }: { small?: boolean; to?: string | null }) {
  const inner = (
    <>
      <IconTile name="hospital" size={small ? 22 : 26} />
      <span className="font-display text-xl font-bold leading-none tracking-tight">Follow-up Coordinator</span>
    </>
  );
  return to ? (
    <Link to={to} className="inline-flex min-w-0 items-center gap-3 text-ink no-underline" aria-label="Follow-up Coordinator home">{inner}</Link>
  ) : <span className="inline-flex min-w-0 items-center gap-3 text-ink">{inner}</span>;
}

export function LangSelect({ className = "" }: { className?: string }) {
  const { lang, setLang } = useI18n();
  return (
    <label className={`inline-flex items-center gap-2 ${className}`}>
      <LangMark code={lang} size={34} />
      <span className="sr-only">Language</span>
      <select value={lang} onChange={(e) => setLang(e.target.value as Lang)}
        className="min-h-12 border-2 border-ink bg-tile px-3 font-display text-base font-semibold text-ink" style={{ borderRadius: 4 }}>
        {LANGS.map((l) => <option key={l.code} value={l.code}>{l.native}</option>)}
      </select>
    </label>
  );
}

export function DisclaimerBar() {
  const { s } = useI18n();
  return (
    <div className="bg-ink text-ground">
      <p className="container-page max-w-none py-5 text-base text-ground" data-testid="disclaimer">{s("disclaimer")}</p>
    </div>
  );
}

export function Footer() {
  return (
    <footer className="bg-ink text-ground">
      <div className="container-page grid gap-8 py-12 md:grid-cols-[1.4fr_1fr_1fr]">
        <div className="flex flex-col gap-4">
          <span className="inline-flex items-center gap-3 font-display text-xl font-bold"><Icon name="hospital" size={30} className="!text-ground duo-on-teal" />Follow-up Coordinator</span>
          <p className="text-ground/85">Built for the Acentra Hackathon. A prototype that runs on synthetic data only. Not a medical device.</p>
        </div>
        <nav aria-label="Legal" className="flex flex-col gap-2 font-display font-semibold">
          <Link to="/terms" className="text-ground">Terms of Service</Link>
          <Link to="/privacy" className="text-ground">Privacy Policy</Link>
        </nav>
        <LangSelect />
      </div>
      <div className="border-t border-ground/25"><DisclaimerBar /></div>
    </footer>
  );
}

/** The two doors into the product. The hospital admin center has no door here. */
export function EntryButtons({ className = "" }: { className?: string }) {
  const { s } = useI18n();
  return (
    <div className={`flex flex-wrap items-center gap-3 ${className}`}>
      <Link to="/login?as=family" className="btn btn-primary">{s("entryFamily")}</Link>
      <Link to="/login?as=doctor" className="btn btn-plain">{s("entryDoctor")}</Link>
    </div>
  );
}

export function Header() {
  const { s } = useI18n();
  const [open, setOpen] = useState(false);
  const links: [string, string][] = [["/#how", s("navHow")], ["/#safety", s("navSafety")], ["/#languages", s("navLanguages")], ["/#family", s("navFamily")], ["/#faq", s("navFaq")]];
  return (
    <header className="sticky top-0 z-30 border-b border-line bg-ground">
      <div className="container-wide flex min-h-[4.5rem] items-center justify-between gap-4">
        <Brand />
        <nav aria-label="Primary" className="hidden items-center gap-5 2xl:flex">
          {links.map(([h, l]) => <a key={h} href={h} className="font-display font-semibold text-ink no-underline">{l}</a>)}
        </nav>
        <div className="hidden items-center gap-3 xl:flex"><LangSelect /><EntryButtons /></div>
        <button className="btn btn-plain xl:hidden" aria-expanded={open} aria-controls="mobile-nav" onClick={() => setOpen((o) => !o)}>
          <Icon name={open ? "close" : "menu"} size={22} />{open ? "Close" : "Menu"}
        </button>
      </div>
      {open && (
        <div id="mobile-nav" className="border-t border-line bg-ground xl:hidden">
          <nav aria-label="Primary mobile" className="container-page flex flex-col gap-1 py-4">
            {links.map(([h, l]) => <a key={h} href={h} onClick={() => setOpen(false)} className="min-h-12 py-2 font-display text-lg font-semibold text-ink no-underline">{l}</a>)}
            <div className="mt-3 flex flex-col items-start gap-3"><LangSelect /><EntryButtons className="w-full" /></div>
          </nav>
        </div>
      )}
    </header>
  );
}

export function PageShell({ children }: { children: ReactNode }) {
  return (<><Header />{children}<Footer /></>);
}

type NavItem = { to: string; label: string; icon: IconName; end?: boolean };
const NAV: Record<Role, NavItem[]> = {
  patient: [{ to: "/hub", label: "Family hub", icon: "hubs", end: true }, { to: "/hub/members", label: "Members and consent", icon: "consent" }, { to: "/hub/notifications", label: "Notifications", icon: "notification" }],
  family: [{ to: "/hub", label: "Family hub", icon: "hubs", end: true }, { to: "/hub/members", label: "Members and consent", icon: "consent" }, { to: "/hub/notifications", label: "Notifications", icon: "notification" }],
  doctor: [{ to: "/doctor", label: "Review queue", icon: "needs-review", end: true }, { to: "/doctor/patients", label: "My patients", icon: "patient" }],
  admin: [{ to: "/admin/overview", label: "Overview", icon: "overview" }, { to: "/admin/doctors", label: "Doctors", icon: "doctor" }, { to: "/admin/routing", label: "Routing", icon: "routing" },
    { to: "/admin/hubs", label: "Hubs", icon: "hubs" }, { to: "/admin/audit", label: "Audit log", icon: "audit" }, { to: "/admin/system", label: "System", icon: "system" }],
};

const navClass = ({ isActive }: { isActive: boolean }) =>
  `inline-flex min-h-12 items-center gap-2 border-b-4 px-1 font-display font-semibold text-ink no-underline ${isActive ? "border-teal" : "border-transparent"}`;

/** Signed-in frame for every role. Admin has no public brand link and no language picker clutter. */
export function AppShell() {
  const { me, logout } = useAuth();
  const [open, setOpen] = useState(false);
  if (!me) return null;
  const items = NAV[me.role];
  return (
    <div className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-30 border-b border-line bg-ground">
        <div className="container-wide flex min-h-[4.5rem] items-center justify-between gap-4">
          <Brand small to={me.role === "admin" ? null : "/"} />
          <nav aria-label="App" className="hidden items-center gap-5 lg:flex">
            {items.map((i) => <NavLink key={i.to} to={i.to} end={i.end} className={navClass}><Icon name={i.icon} size={22} />{i.label}</NavLink>)}
          </nav>
          <div className="hidden items-center gap-3 lg:flex">
            <LangSelect /><span className="max-w-[12rem] truncate text-base text-ink-soft">{me.name}</span>
            <button className="btn btn-plain" onClick={() => void logout()}><Icon name="logout" size={22} />Log out</button>
          </div>
          <button className="btn btn-plain lg:hidden" aria-expanded={open} onClick={() => setOpen((o) => !o)}><Icon name={open ? "close" : "menu"} size={22} />{open ? "Close" : "Menu"}</button>
        </div>
        {open && (
          <nav aria-label="App mobile" className="container-page flex flex-col gap-1 border-t border-line py-3 lg:hidden">
            {items.map((i) => <NavLink key={i.to} to={i.to} end={i.end} onClick={() => setOpen(false)} className={navClass}><Icon name={i.icon} size={26} />{i.label}</NavLink>)}
            <p className="mt-2 text-base text-ink-soft">{me.name}</p>
            <div className="mt-1 flex flex-wrap items-center gap-3"><LangSelect /><button className="btn btn-plain" onClick={() => void logout()}>Log out</button></div>
          </nav>)}
      </header>
      <main className="container-wide flex-1 py-8"><RouteTransition><Outlet /></RouteTransition></main>
      <DisclaimerBar />
    </div>
  );
}
