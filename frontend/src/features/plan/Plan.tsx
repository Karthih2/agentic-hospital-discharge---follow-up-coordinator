import { useMemo, useRef, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { motion, useReducedMotion, useScroll, useSpring } from "motion/react";
import { Icon } from "../../components/icons/Icon";
import { Chip, EmptyState, ErrorNote, ListSkeleton, PageTitle, StatusChip, Tabs, useDocTitle } from "../../components/ui";
import { api, errText } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { useI18n } from "../../lib/i18n";
import { fmtDate, TYPE_ICON, TYPE_LABEL, type Hub, type SummaryRow, type SummaryView, type Task } from "../../lib/types";
import PlanReviewNotice from "./PlanReviewNotice";

const HL: Record<string, string> = { blue: "#2f6fde", yellow: "#c98a10", red: "#c23b36", gray: "#9aa7b2" };
const HEADER_LABEL: Record<string, string> = { admission_date: "Date of Admission", attending_physician: "Attending Physician", pcp: "PCP", disposition: "Discharge Disposition" };
const DX_LABEL: Record<string, string> = { admission: "Admission Diagnosis", discharge: "Discharge Diagnosis", secondary: "Secondary Diagnoses" };

function TaskCard({ t, pid, canAct, canFlag, onChange }: { t: Task; pid: string; canAct: boolean; canFlag: boolean; onChange: () => void }) {
  const { lang } = useI18n();
  const [orig, setOrig] = useState(false);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState("");
  const audio = useRef<HTMLAudioElement | null>(null);
  const locked = t.status === "Needs Review";

  async function run(key: string, fn: () => Promise<unknown>, ok?: string) {
    setBusy(key); setNote("");
    try { await fn(); if (ok) setNote(ok); onChange(); } catch (x) { setNote(errText(x)); } finally { setBusy(""); }
  }
  async function listen() {
    setBusy("listen"); setNote("");
    try {
      const res = await fetch(`/tasks/${t.id}/audio?lang=${lang}`, { credentials: "same-origin" });
      if (!res.ok) throw new Error(res.status === 503 ? "Listen is not set up in this prototype yet (no voice is configured)." : "Could not play this item.");
      const url = URL.createObjectURL(await res.blob());
      audio.current?.pause(); audio.current = new Audio(url); await audio.current.play();
    } catch (x) { setNote(x instanceof Error ? x.message : "Could not play this item."); } finally { setBusy(""); }
  }

  if (t.locked && !t.title) {
    return (
      <article className="flex flex-col items-center gap-3 border-2 border-dashed border-ink bg-ground-deep p-8 text-center text-ink-soft" style={{ borderRadius: 4 }}>
        <Icon name="locked" size={48} /><p className="font-display text-2xl font-bold">{t.message ?? "Waiting for doctor review"}</p>
        <StatusChip status="Needs Review" /></article>);
  }
  return (
    <article className={`flex min-w-0 flex-col gap-5 p-5 sm:p-7 ${locked ? "border-2 border-dashed border-ink bg-ground-deep text-ink-soft" : "tile"}`} style={{ borderRadius: 4 }} aria-label={t.title}>
      <header className="flex flex-wrap items-center gap-3">
        <Icon name={locked ? "locked" : (TYPE_ICON[t.type ?? ""] ?? "text") as never} size={34} />
        {t.type && <Chip>{TYPE_LABEL[t.type] ?? "Task"}</Chip>}
        <span className="ml-auto"><StatusChip status={t.status} /></span>
      </header>
      {locked ? (
        <div><p className="font-display text-2xl font-bold">Waiting for doctor review</p><p className="mt-1 text-lg">{t.title}</p></div>
      ) : (<>
        <h2 className="font-display text-2xl font-bold leading-tight">{t.title}</h2>
        {t.medicine_card ? (
          <dl className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-6 gap-y-2 text-xl" aria-label="Medicine card">
            {t.medicine_card.rows.map((r) => (<div key={r.key} className="contents"><dt className="text-ink-soft">{r.label}</dt><dd className="font-semibold">{r.value ?? "Not stated"}</dd></div>))}
          </dl>
        ) : t.display_text ? <p lang={lang} className="text-2xl leading-snug">{t.display_text}</p> : null}
        {t.appointment && (t.appointment.time || t.appointment.location || t.appointment.phone) && (
          <dl className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-5 gap-y-1 text-lg">
            {t.appointment.time && <><dt className="text-ink-soft">Time</dt><dd className="font-semibold">{t.appointment.time}</dd></>}
            {t.appointment.location && <><dt className="text-ink-soft">Where</dt><dd className="font-semibold">{t.appointment.location}</dd></>}
            {t.appointment.phone && <><dt className="text-ink-soft">Phone</dt><dd className="font-semibold">{t.appointment.phone}</dd></>}
          </dl>)}
        <div className="flex flex-wrap items-center gap-3">
          {t.due_date && <span className="tile-quiet inline-flex items-center gap-2 px-3 py-1 font-display font-semibold"><Icon name="calendar" size={22} />{fmtDate(t.due_date)}</span>}
          {t.due_date && canAct && (
            <label className="inline-flex min-h-12 items-center gap-2 font-semibold">
              <input type="checkbox" className="h-5 w-5" checked={t.reminder_enabled !== false} disabled={busy === "rem"}
                onChange={(e) => void run("rem", () => api(`/tasks/${t.id}/reminder`, { method: "POST", json: { enabled: e.target.checked } }))} />Set reminder</label>)}
        </div></>)}

      {t.source_line && (
        <div>
          <button className="min-h-12 font-display font-semibold text-teal underline" aria-expanded={orig} onClick={() => setOrig((o) => !o)}>{orig ? "Hide original" : "Show original"}</button>
          {orig && <p className="mt-1 border-t border-line pt-2 text-lg italic">{t.source_line}</p>}
        </div>)}

      {!locked && (t.provider || t.provider_needed) && (
        <div className="tile-quiet flex flex-wrap items-center gap-4 p-4">
          <Icon name="referral" size={32} />
          <div className="min-w-0 flex-1 basis-48">
            {t.provider ? <><p className="font-display text-lg font-semibold">{t.provider.name}</p><p className="text-base">{t.provider.facility}, {t.provider.contact}</p></> : <p className="font-display text-lg font-semibold">Find a provider near you{t.specialty ? `, ${t.specialty}` : ""}</p>}
            <p className="text-sm text-ink-soft">Suggestion only, not a guarantee of availability or suitability</p>
          </div>
          {canAct && <Link className="btn btn-plain" to={`/hub/providers/${t.id}?specialty=${encodeURIComponent(t.specialty ?? "")}&pid=${pid}`}>{t.provider ? "Change" : "Find a provider"}</Link>}
        </div>)}

      {note && <p role="status" className="font-semibold text-ink">{note}</p>}

      <footer className="flex flex-wrap items-center gap-3 border-t border-line pt-4">
        {!locked && t.can_listen && <button className="btn btn-plain !min-h-14" disabled={busy === "listen"} onClick={listen}><Icon name="listen" size={22} />Listen</button>}
        {canAct && t.status === "Pending" && t.type !== "warning_sign" && <button className="btn btn-plain !min-h-14" onClick={() => void run("done", () => api(`/tasks/${t.id}/complete`, { method: "POST" }))}><Icon name="confirmed" size={22} />Mark done</button>}
        {canAct && t.status === "Completed" && <button className="btn btn-plain !min-h-14" onClick={() => void run("undo", () => api(`/tasks/${t.id}/undo`, { method: "POST" }))}>Undo</button>}
        {canFlag && t.status === "Pending" && <button className="min-h-12 px-2 font-display font-semibold text-ink-soft underline" onClick={() => void run("flag", () => api(`/tasks/${t.id}/flag`, { method: "POST", json: {} }), "Sent to a doctor for review.")}>Ask a doctor to review</button>}
        {!locked && canAct && <button className="btn btn-primary !min-h-14 ml-auto" disabled={busy === "cb"} onClick={() => void run("cb", () => api(`/tasks/${t.id}/callback`, { method: "POST" }), "Callback requested. The hospital will call you. Your number stays private.")}><Icon name="callback" size={22} className="duo-on-teal !text-ground" />Request callback</button>}
      </footer>
    </article>
  );
}

function TwoPanel({ tasks, original, pid, canAct, canFlag, onChange }: { tasks: Task[]; original?: SummaryView; pid: string; canAct: boolean; canFlag: boolean; onChange: () => void }) {
  const [focus, setFocus] = useState<string | null>(null);
  const body = useMemo(() => {
    if (!original) return null;
    const hs = [...original.highlights].sort((a, b) => a.start - b.start);
    const out: React.ReactNode[] = []; let pos = 0;
    hs.forEach((h) => {
      if (h.start < pos) return;
      out.push(original.raw_text.slice(pos, h.start));
      const c = HL[h.color] ?? HL.gray;
      out.push(<mark key={h.task_id} id={`hl-${h.task_id}`} style={{ background: `color-mix(in oklab, ${c} 18%, transparent)`, boxShadow: `inset 0 -3px 0 ${c}`, outline: focus === h.task_id ? "3px solid var(--color-ink)" : "none", color: "inherit" }}>{original.raw_text.slice(h.start, h.end)}</mark>);
      pos = h.end;
    });
    out.push(original.raw_text.slice(pos));
    return out;
  }, [original, focus]);
  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <section className="tile min-w-0 p-5 lg:sticky lg:top-24 lg:self-start" aria-label="Original summary">
        <h2 className="mb-1 font-display text-xl font-bold">Original summary</h2>
        <p className="mb-3 flex flex-wrap gap-4 text-sm"><span><span className="mr-1 inline-block h-3 w-3 bg-pending" />Appointments</span><span><span className="mr-1 inline-block h-3 w-3" style={{ background: HL.yellow }} />Medicines</span><span><span className="mr-1 inline-block h-3 w-3" style={{ background: HL.red }} />Warnings</span></p>
        {original ? <pre className="max-h-[70vh] overflow-auto whitespace-pre-wrap font-body text-lg leading-relaxed" data-allow-overflow>{body}</pre> : <p className="text-ink-soft">The original text is not available at your access level.</p>}
      </section>
      <section aria-label="Tasks" className="flex min-w-0 flex-col gap-4">
        {tasks.map((t) => (
          <div key={t.id} onClick={() => { setFocus(t.id); document.getElementById(`hl-${t.id}`)?.scrollIntoView({ block: "center" }); }}>
            <TaskCard t={t} pid={pid} canAct={canAct} canFlag={canFlag} onChange={onChange} /></div>))}
      </section>
    </div>
  );
}

/** Timeline: dated tasks in order on a line that draws itself as the page scrolls. */
function Timeline({ tasks }: { tasks: Task[] }) {
  const reduce = useReducedMotion();
  const ref = useRef<HTMLOListElement>(null);
  const { scrollYProgress } = useScroll({ target: ref, offset: ["start 80%", "end 60%"] });
  const grow = useSpring(scrollYProgress, { stiffness: 120, damping: 28 });
  const dated = tasks.filter((t) => t.due_date), undated = tasks.filter((t) => !t.due_date);
  const dot = (s: string) => (s === "Completed" ? "bg-done" : s === "Needs Review" ? "bg-review" : "bg-pending");
  return (
    <div>
      <ol ref={ref} className="relative flex flex-col gap-5 pl-10">
        <span aria-hidden className="absolute bottom-2 left-[0.8rem] top-2 w-0.5 bg-line" />
        <motion.span aria-hidden className="absolute bottom-2 left-[0.8rem] top-2 w-0.5 origin-top bg-ink" style={{ scaleY: reduce ? 1 : grow }} />
        {dated.map((t) => (
          <li key={t.id} className="relative min-w-0">
            <span className={`absolute -left-[2.35rem] top-1 h-5 w-5 border-2 border-ink ${dot(t.status)}`} style={{ borderRadius: 4 }} />
            <p className="font-display text-sm font-semibold text-ink-soft">{fmtDate(t.due_date)}{t.appointment?.time ? `, ${t.appointment.time}` : ""}</p>
            <p className="flex flex-wrap items-center gap-2 text-lg font-semibold">{t.locked && !t.title ? "Waiting for doctor review" : t.title}<StatusChip status={t.status} /></p>
          </li>))}
      </ol>
      {undated.length > 0 && <><h3 className="mb-2 mt-6 font-display text-lg font-bold">No date</h3>
        <ul className="flex flex-col gap-2">{undated.map((t) => <li key={t.id} className="flex flex-wrap items-center gap-2"><StatusChip status={t.status} />{t.locked && !t.title ? "Waiting for doctor review" : t.title}</li>)}</ul></>}
    </div>
  );
}

export default function Plan() {
  useDocTitle("Plan");
  const { pid = "" } = useParams();
  const [sp] = useSearchParams();
  const { me } = useAuth();
  const qc = useQueryClient();
  const isSelf = me?.id === pid;
  const hubs = useQuery({ queryKey: ["hubs"], queryFn: () => api<Hub[]>("/hubs") });
  const card = hubs.data?.flatMap((h) => h.patients).find((p) => p.patient_id === pid);
  const canAct = isSelf || !!card?.operate;
  const canFlag = isSelf || card?.access === "full";
  const [view, setView] = useState<"card" | "panel" | "timeline">(isSelf ? "card" : "panel");
  const [i, setI] = useState(0);
  const touch = useRef(0);
  const tasks = useQuery({ queryKey: ["tasks", pid], queryFn: () => api<Task[]>(`/patients/${pid}/tasks`) });
  const fullAccess = isSelf || card?.access === "full";
  const list = useQuery({ queryKey: ["summaries", pid], queryFn: () => api<SummaryRow[]>(`/patients/${pid}/summaries`), enabled: canAct });
  const sid = sp.get("summary") ?? list.data?.find((s) => s.status === "ready" && s.plan_status !== "draft")?.id;
  const original = useQuery({ queryKey: ["original", sid], queryFn: () => api<SummaryView>(`/summaries/${sid}`), enabled: fullAccess && !!sid, retry: false });
  const refresh = () => { void qc.invalidateQueries({ queryKey: ["tasks", pid] }); void qc.invalidateQueries({ queryKey: ["summaries", pid] }); void qc.invalidateQueries({ queryKey: ["hubs"] }); };
  const data = [...(tasks.data ?? [])].sort((a, b) => (a.due_date ?? "9999").localeCompare(b.due_date ?? "9999"));
  const idx = Math.min(i, Math.max(data.length - 1, 0));
  const done = data.filter((t) => t.status === "Completed").length;
  const o = original.data;

  return (
    <div>
      <PageTitle icon="follow-up-plan" sub={data.length ? `${card?.name ?? "Your"} plan: ${done} of ${data.length} tasks completed` : card?.name}>Follow-up plan</PageTitle>
      {o && (o.header.pcp || o.header.attending_physician) && (
        <section className="tile-quiet mb-6 p-4" aria-label="From your summary">
          <h2 className="font-display text-lg font-bold">From your summary</h2>
          <dl className="mt-2 grid gap-x-8 gap-y-1 sm:grid-cols-2">
            {Object.entries(o.header).map(([k, v]) => <div key={k} className="flex min-w-0 flex-wrap gap-x-2"><dt className="text-ink-soft">{HEADER_LABEL[k]}:</dt><dd>{v ?? "Not given"}</dd></div>)}
            {o.diagnoses && Object.entries(o.diagnoses).map(([k, v]) => v ? <div key={k} className="flex min-w-0 flex-wrap gap-x-2 sm:col-span-2"><dt className="text-ink-soft">{DX_LABEL[k]}:</dt><dd>{v}</dd></div> : null)}
          </dl>
        </section>)}
      <PlanReviewNotice pid={pid} enabled={canAct} />
      <div className="mb-6 flex flex-wrap items-center gap-4">
        <Tabs label="View" tabs={[{ id: "card", label: "Card View" }, { id: "panel", label: "Two-Panel View" }, { id: "timeline", label: "Timeline" }]} value={view} onChange={setView} />
        {canAct && <span className="ml-auto flex flex-wrap gap-3"><Link className="btn btn-plain" to={`/hub/upload/${pid}`}><Icon name="upload" size={22} />Upload</Link><Link className="btn btn-plain" to={`/hub/manual/${pid}`}>Add a task by hand</Link></span>}
      </div>
      {tasks.isLoading ? <ListSkeleton /> : tasks.error ? <ErrorNote action={<button className="btn btn-plain" onClick={() => void tasks.refetch()}>Try again</button>}>{errText(tasks.error, "Could not load the plan.")}</ErrorNote>
        : !data.length ? <EmptyState action={canAct ? <Link to={`/hub/upload/${pid}`} className="btn btn-primary">Upload a summary</Link> : undefined}>No tasks yet. A discharge summary creates the plan.</EmptyState>
        : view === "timeline" ? <Timeline tasks={data}/>
        : view === "card" ? (
          <div onTouchStart={(e) => { touch.current = e.touches[0].clientX; }} onTouchEnd={(e) => { const d = e.changedTouches[0].clientX - touch.current; if (Math.abs(d) > 60) setI(Math.max(0, Math.min(data.length - 1, idx + (d < 0 ? 1 : -1)))); }}>
            <p className="mb-3 font-display text-lg font-semibold" aria-live="polite">Task {idx + 1} of {data.length}</p>
            <TaskCard key={data[idx].id} t={data[idx]} pid={pid} canAct={canAct} canFlag={canFlag} onChange={refresh} />
            <div className="mt-5 flex justify-between gap-3">
              <button className="btn btn-plain" disabled={idx === 0} onClick={() => setI(idx - 1)}><Icon name="previous" size={22} />Previous</button>
              <button className="btn btn-plain" disabled={idx === data.length - 1} onClick={() => setI(idx + 1)}>Next<Icon name="next" size={22} /></button>
            </div>
          </div>
        ) : <TwoPanel tasks={data} original={o} pid={pid} canAct={canAct} canFlag={canFlag} onChange={refresh} />}
    </div>
  );
}
