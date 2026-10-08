import { useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Icon, type IconName } from "../../components/icons/Icon";
import { ReviewArt } from "../../components/illustrations/Illustrations";
import { Chip, EmptyState, ErrorNote, Field, ListSkeleton, PageTitle, StatusChip, Tabs, useDocTitle } from "../../components/ui";
import { api, ApiError, errText } from "../../lib/api";
import { fmtDate, TYPE_ICON, TYPE_LABEL, type Status } from "../../lib/types";

/* ------------------------------------------------------------------ types */

type Counts = { total: number; needs_review: number; ready: number };
type PlanRow = {
  id: string; plan_status: "draft" | "published"; status: string; patient_id: string; patient_name: string | null;
  patient_code: string | null; age_label: string | null; uploaded_at: string; published_at: string | null;
  match_reason: string | null; extraction_method: string | null; counts: Counts;
};
type Med = { name?: string | null; dose?: string | null; route?: string | null; timing?: string | null; duration?: string | null; special?: string | null };
type PTask = {
  id: string; type: string; title: string; status: Status; due_date: string | null; due_date_text: string | null;
  source_line: string; source_span: { start: number; end: number } | null;
  fields: { doctor_name: string | null; specialty: string | null; instruction: string | null; medicine: Med | null; due_time: string | null; location: string | null; phone: string | null };
  reasons: { code: string; text: string }[]; confidence: number | null; entry_mode: string | null; doctor_edited: boolean;
  simple_text: string | null; medicine_card: { rows: { key: string; label: string; value: string | null }[] } | null;
  review_id: string | null; can_confirm: boolean;
};
type PlanDetail = {
  id: string; plan_status: "draft" | "published" | "generating"; status: string; uploaded_at: string; published_at: string | null;
  extraction_method: string | null;
  patient: { id: string; name: string | null; patient_code: string | null; language: string | null; age_label: string | null };
  match: { reason: string | null; attending: string | null; attending_specialty: string | null };
  summary: {
    raw_text: string; discharge_date: string | null; header: Record<string, string | null>; diagnoses: Record<string, string | null>;
    notices: { code: string; text: string; line: string | null }[];
    highlights: { task_id: string; type: string; status: string; color: string; start: number; end: number }[];
  };
  tasks: PTask[]; counts: Counts;
};
type Reason = { reason_code: string; text?: string };

const HL: Record<string, string> = { blue: "#2f6fde", yellow: "#c98a10", red: "#c23b36", gray: "#9aa7b2" };
const HEADER_LABEL: Record<string, string> = { admission_date: "Date of Admission", attending_physician: "Attending Physician", pcp: "PCP", disposition: "Discharge Disposition" };
const DX_LABEL: Record<string, string> = { admission: "Admission Diagnosis", discharge: "Discharge Diagnosis", secondary: "Secondary Diagnoses" };
const MED_KEYS: [keyof Med, string][] = [["name", "Medicine name"], ["dose", "Dose"], ["route", "Route"], ["timing", "Timing"], ["duration", "Duration"], ["special", "Special instructions"]];
const TYPES = ["appointment", "referral", "test", "medicine", "care_instruction", "date", "warning_sign"];
const LANG_NAME: Record<string, string> = { en: "English", ta: "Tamil", hi: "Hindi", te: "Telugu", kn: "Kannada", ml: "Malayalam" };

/** The server's "Still incomplete" answer, as a list of what is missing. */
function stillMissing(x: unknown): Reason[] | null {
  const det = x instanceof ApiError ? (x.body as { detail?: { reasons?: Reason[] } } | null)?.detail : null;
  return det && typeof det === "object" && det.reasons ? det.reasons : null;
}
function detailMessage(x: unknown): string {
  const det = x instanceof ApiError ? (x.body as { detail?: { message?: string } | string } | null)?.detail : null;
  return det && typeof det === "object" && det.message ? det.message : errText(x);
}

const Bullet = ({ tone = "bg-review" }: { tone?: string }) => <span aria-hidden className={`mt-2.5 h-2 w-2 shrink-0 ${tone}`} />;

/* ------------------------------------------------------------------ list */

export function DoctorPlans() {
  useDocTitle("Plans to review");
  const [tab, setTab] = useState<"draft" | "published">("draft");
  const q = useQuery({ queryKey: ["plans", tab], queryFn: () => api<PlanRow[]>(`/plans?status=${tab}`), refetchInterval: 15000 });
  const waiting = useQuery({ queryKey: ["plans", "draft"], queryFn: () => api<PlanRow[]>("/plans?status=draft"), enabled: tab !== "draft" });
  const nDraft = (tab === "draft" ? q.data : waiting.data)?.length ?? 0;
  return (
    <div>
      <PageTitle icon="follow-up-plan" sub={`${nDraft} waiting for your review. Patients see a plan only after you publish it.`}>Plans to review</PageTitle>
      <div className="mb-5"><Tabs label="Plans" value={tab} onChange={setTab} tabs={[{ id: "draft", label: "Waiting for review" }, { id: "published", label: "Published" }]} /></div>
      {q.isLoading ? <ListSkeleton /> : q.error ? <ErrorNote>Could not load your plans.</ErrorNote> : !q.data?.length
        ? <EmptyState>{tab === "draft" ? "No plans waiting. A new discharge summary for one of your patients appears here." : "You have not published a plan yet."}</EmptyState>
        : <ul className="flex flex-col gap-3">{q.data.map((p) => (
          <li key={p.id}><Link to={`/doctor/plans/${p.id}`} className="tile flex flex-wrap items-center gap-4 p-4 text-ink no-underline">
            <Icon name={p.plan_status === "draft" ? "follow-up-plan" : "success"} size={34} />
            <div className="min-w-0 flex-1 basis-64">
              <p className="font-display text-lg font-semibold">{p.patient_name ?? "Patient"} <span className="text-base font-normal text-ink-soft">{p.patient_code}{p.age_label ? `, ${p.age_label}` : ""}</span></p>
              {p.match_reason && <p className="text-base text-ink-soft">Matched to you: {p.match_reason}</p>}
            </div>
            <span className="flex flex-wrap items-center gap-2">
              <Chip>{p.counts.total} items</Chip>
              {p.counts.needs_review > 0 && <span className="inline-flex items-center gap-1"><StatusChip status="Needs Review" />{p.counts.needs_review}</span>}
              {p.extraction_method === "rules" && <Chip>Read by rules</Chip>}
            </span>
            <span className="text-base text-ink-soft">{p.plan_status === "published" && p.published_at ? `Published ${fmtDate(p.published_at.slice(0, 10))}` : `Received ${fmtDate(p.uploaded_at.slice(0, 10))}`}</span>
          </Link></li>))}</ul>}
    </div>
  );
}

/* ------------------------------------------------------------------ editor pieces */

type Form = Record<string, string>;
const formFrom = (t: PTask): Form => ({
  title: t.title ?? "", due_date: t.due_date ?? "", due_time: t.fields.due_time ?? "", location: t.fields.location ?? "",
  phone: t.fields.phone ?? "", doctor_name: t.fields.doctor_name ?? "", specialty: t.fields.specialty ?? "",
  instruction: t.fields.instruction ?? "",
  ...Object.fromEntries(MED_KEYS.map(([k]) => ["m_" + k, t.fields.medicine?.[k] ?? ""])),
});

/** Only the values that changed, in the shape the API takes. An emptied field is sent as null (cleared). */
function changes(type: string, before: Form, after: Form): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const k of ["title", "due_date", "due_time", "location", "phone", "doctor_name", "specialty", "instruction"]) {
    if ((after[k] ?? "") !== (before[k] ?? "")) out[k] = after[k] ? after[k] : null;
  }
  if (type === "medicine") {
    const med: Record<string, string | null> = {};
    for (const [k] of MED_KEYS) if ((after["m_" + k] ?? "") !== (before["m_" + k] ?? "")) med[k] = after["m_" + k] || null;
    if (Object.keys(med).length) out.medicine = med;
  }
  if (out.title === null) delete out.title;
  return out;
}

function ItemFields({ type, v, set }: { type: string; v: Form; set: (f: Form) => void }) {
  const inp = (k: string, label: string, kind = "text", hint?: string) => (
    <Field label={label} hint={hint}><input className="field" type={kind} value={v[k] ?? ""} onChange={(e) => set({ ...v, [k]: e.target.value })} /></Field>);
  const appt = type === "appointment" || type === "referral";
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      <div className="sm:col-span-2">{inp("title", "Title")}</div>
      {type !== "medicine" && type !== "care_instruction" && type !== "warning_sign" && inp("due_date", "Date", "date")}
      {appt && inp("due_time", "Time", "text", "For example 10:30 AM")}
      {appt && <>{inp("doctor_name", "Doctor")}{inp("specialty", "Specialty")}{inp("location", "Location")}{inp("phone", "Phone")}</>}
      {type === "medicine" && MED_KEYS.map(([k, label]) => <div key={k}>{inp("m_" + k, label)}</div>)}
      {type !== "medicine" && <div className="sm:col-span-2"><Field label="Instruction"><textarea className="field !min-h-24" value={v.instruction ?? ""} onChange={(e) => set({ ...v, instruction: e.target.value })} /></Field></div>}
    </div>
  );
}

const StillBox = ({ still }: { still: Reason[] }) => still.length ? (
  <div role="alert" className="border-2 border-review bg-ground-deep p-3" style={{ borderRadius: 4 }}>
    <p className="font-display font-semibold">Still missing:</p>
    <ul className="flex flex-col gap-1">{still.map((r, i) => <li key={i} className="flex gap-2"><Bullet />{r.text ?? r.reason_code}</li>)}</ul>
  </div>) : null;

function Values({ t }: { t: PTask }) {
  const rows: [string, string | null | undefined][] = [
    ["Date", t.due_date ? fmtDate(t.due_date) : t.due_date_text ? `"${t.due_date_text}"` : null],
    ["Time", t.fields.due_time], ["Doctor", t.fields.doctor_name], ["Specialty", t.fields.specialty],
    ["Location", t.fields.location], ["Phone", t.fields.phone],
  ];
  const shown = rows.filter(([, v]) => v);
  return (
    <dl className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-6 gap-y-1">
      {shown.map(([k, v]) => <div key={k} className="contents"><dt className="text-ink-soft">{k}</dt><dd>{v}</dd></div>)}
      {t.type === "medicine" && MED_KEYS.map(([k, label]) => <div key={k} className="contents"><dt className="text-ink-soft">{label}</dt><dd className={t.fields.medicine?.[k] ? "" : "font-semibold text-review"}>{t.fields.medicine?.[k] ?? "Not stated"}</dd></div>)}
      {t.type !== "medicine" && t.fields.instruction && <><dt className="text-ink-soft">Instruction</dt><dd>{t.fields.instruction}</dd></>}
    </dl>
  );
}

function PlanItem({ t, pid, draft, focused, onFocus, onDone }: { t: PTask; pid: string; draft: boolean; focused: boolean; onFocus: () => void; onDone: () => void }) {
  const [mode, setMode] = useState<"view" | "edit" | "remove">("view");
  const [v, setV] = useState<Form>(() => formFrom(t));
  const [still, setStill] = useState<Reason[]>([]);
  const [err, setErr] = useState("");
  const fail = (x: unknown) => { const s = stillMissing(x); if (s) { setStill(s); setErr(""); } else setErr(detailMessage(x)); };
  const ok = () => { setMode("view"); setStill([]); setErr(""); onDone(); };
  const save = useMutation({ mutationFn: () => api(`/plans/${pid}/tasks/${t.id}`, { method: "PATCH", json: changes(t.type, formFrom(t), v) }), onSuccess: ok, onError: fail });
  const confirm = useMutation({ mutationFn: () => api(`/plans/${pid}/tasks/${t.id}/confirm`, { method: "POST" }), onSuccess: ok, onError: fail });
  const remove = useMutation({ mutationFn: () => api(`/plans/${pid}/tasks/${t.id}`, { method: "DELETE" }), onSuccess: ok, onError: fail });
  const flagged = t.status === "Needs Review";
  const busy = save.isPending || confirm.isPending || remove.isPending;
  return (
    <article id={`item-${t.id}`} className={`${flagged ? "tile" : "tile-quiet"} flex flex-col gap-4 p-5`} style={focused ? { outline: "3px solid var(--color-ink)", outlineOffset: 2 } : undefined}
      aria-label={`${TYPE_LABEL[t.type] ?? "Item"}: ${t.title}`}>
      <div className="flex flex-wrap items-center gap-3">
        <Icon name={(TYPE_ICON[t.type] ?? "follow-up-plan") as IconName} size={34} />
        <h3 className="min-w-0 flex-1 basis-48 font-display text-xl font-bold">{t.title}</h3>
        <StatusChip status={t.status} /><Chip>{TYPE_LABEL[t.type] ?? "Item"}</Chip>
        {t.entry_mode === "doctor" ? <Chip tone="teal">Added by you</Chip> : t.doctor_edited ? <Chip tone="teal">Edited by you</Chip> : null}
      </div>

      {flagged && t.reasons.length > 0 && (
        <div><p className="font-display font-semibold">Why it needs your review</p>
          <ul className="mt-1 flex flex-col gap-1">{t.reasons.map((r) => <li key={r.code} className="flex gap-2"><Bullet />{r.text}</li>)}</ul></div>)}

      {mode !== "edit" && <Values t={t} />}

      <button type="button" onClick={onFocus} className="text-left" aria-label="Show this line in the original summary">
        <span className="font-display text-sm font-semibold text-ink-soft">{t.entry_mode === "doctor" ? "Your entry" : "From the summary"}</span>
        <span className="mt-0.5 block text-lg italic">{t.source_line}</span>
      </button>

      {t.simple_text && mode === "view" && (
        <p className="border-t border-line pt-3 text-base"><span className="font-display font-semibold">The patient will read: </span>{t.simple_text}</p>)}

      {mode === "edit" && (
        <section className="flex flex-col gap-4 border-t border-line pt-4" aria-label="Edit item">
          <ItemFields type={t.type} v={v} set={setV} />
          <StillBox still={still} />
        </section>)}
      {mode === "remove" && (
        <div role="alert" className="border-2 border-ink bg-ground-deep p-4" style={{ borderRadius: 4 }}>
          <p className="font-display font-semibold">Remove this item from the plan?</p>
          <p className="text-base text-ink-soft">The patient will not see it. The original line stays in the summary and in the change history.</p>
        </div>)}
      {err && <ErrorNote>{err}</ErrorNote>}

      {draft && (
        <div className="flex flex-wrap gap-3">
          {mode === "view" && <>
            {flagged && t.can_confirm && <button className="btn btn-primary" disabled={busy} onClick={() => { setErr(""); confirm.mutate(); }}><Icon name="confirmed" size={22} className="duo-on-teal !text-ground" />Confirm as written</button>}
            <button className={flagged && !t.can_confirm ? "btn btn-primary" : "btn btn-plain"} onClick={() => { setV(formFrom(t)); setMode("edit"); setErr(""); }}><Icon name="manual-entry" size={22} />Edit</button>
            <button className="btn btn-plain" onClick={() => { setMode("remove"); setErr(""); }}><Icon name="delete" size={22} />Remove</button></>}
          {mode === "edit" && <>
            <button className="btn btn-primary" disabled={busy} onClick={() => { setErr(""); setStill([]); save.mutate(); }}>{flagged ? "Save and approve" : "Save changes"}</button>
            <button className="btn btn-plain" onClick={() => { setMode("view"); setStill([]); setErr(""); }}>Cancel</button></>}
          {mode === "remove" && <>
            <button className="btn btn-primary" disabled={busy} onClick={() => remove.mutate()}>Yes, remove it</button>
            <button className="btn btn-plain" onClick={() => setMode("view")}>Keep it</button></>}
        </div>)}
    </article>
  );
}

function AddItem({ pid, onDone }: { pid: string; onDone: () => void }) {
  const [open, setOpen] = useState(false);
  const [type, setType] = useState("appointment");
  const [v, setV] = useState<Form>({});
  const [still, setStill] = useState<Reason[]>([]);
  const [err, setErr] = useState("");
  const add = useMutation({
    mutationFn: () => {
      const body: Record<string, unknown> = { type, title: v.title ?? "" };
      for (const k of ["due_date", "due_time", "location", "phone", "doctor_name", "specialty", "instruction"]) if (v[k]) body[k] = v[k];
      if (type === "medicine") body.medicine = Object.fromEntries(MED_KEYS.map(([k]) => [k, v["m_" + k] || null]));
      return api(`/plans/${pid}/tasks`, { method: "POST", json: body });
    },
    onSuccess: () => { setOpen(false); setV({}); setStill([]); setErr(""); onDone(); },
    onError: (x) => { const s = stillMissing(x); if (s) { setStill(s); setErr(""); } else setErr(detailMessage(x)); },
  });
  if (!open) return <button className="btn btn-plain self-start" onClick={() => setOpen(true)}><Icon name="plus" size={22} />Add an item the summary missed</button>;
  return (
    <section className="tile flex flex-col gap-4 p-5" aria-label="Add an item">
      <h3 className="font-display text-xl font-bold">Add an item</h3>
      <Field label="Type"><select className="field" value={type} onChange={(e) => setType(e.target.value)}>{TYPES.map((x) => <option key={x} value={x}>{TYPE_LABEL[x]}</option>)}</select></Field>
      <ItemFields type={type} v={v} set={setV} />
      <StillBox still={still} />
      {err && <ErrorNote>{err}</ErrorNote>}
      <div className="flex flex-wrap gap-3">
        <button className="btn btn-primary" disabled={add.isPending || !(v.title ?? "").trim()} onClick={() => { setStill([]); setErr(""); add.mutate(); }}>Add to plan</button>
        <button className="btn btn-plain" onClick={() => { setOpen(false); setStill([]); setErr(""); }}>Cancel</button>
      </div>
      <p className="text-sm text-ink-soft">It is labelled "Added by your doctor" for the patient.</p>
    </section>
  );
}

function PublishBar({ plan, onDone }: { plan: PlanDetail; onDone: () => void }) {
  const [ask, setAsk] = useState<null | "publish" | "keep">(null);
  const pub = useMutation({
    mutationFn: (keep: boolean) => api(`/plans/${plan.id}/publish`, { method: "POST", json: { keep_in_review: keep } }),
    onSuccess: () => { setAsk(null); onDone(); },
  });
  const n = plan.counts.needs_review;
  const who = plan.patient.name ?? "the patient";
  return (
    <section className="tile flex flex-col gap-4 p-5" aria-label="Publish">
      <div className="flex flex-wrap items-center gap-4">
        <div className="min-w-0 flex-1 basis-64">
          <h2 className="font-display text-xl font-bold">{n ? `${n} item${n > 1 ? "s" : ""} still need${n > 1 ? "" : "s"} your review` : "Ready to publish"}</h2>
          <p className="text-base text-ink-soft">{n
            ? "Confirm, edit or remove each flagged item. Then publish the plan to the patient."
            : `${plan.counts.total} items checked. Publishing shows the plan to ${who} and their family within the access they gave, and starts the reminders.`}</p>
        </div>
        {!ask && <span className="flex flex-wrap gap-3">
          <button className="btn btn-primary" disabled={!!n || pub.isPending || !plan.counts.total} onClick={() => setAsk("publish")}><Icon name="success" size={22} className="duo-on-teal !text-ground" />Publish plan</button>
          {n > 0 && <button className="btn btn-plain" onClick={() => setAsk("keep")}>Publish, keep {n} with me</button>}
        </span>}
      </div>
      {ask && (
        <div role="alert" className="border-2 border-ink bg-ground-deep p-4" style={{ borderRadius: 4 }}>
          <p className="font-display font-semibold">{ask === "publish" ? `Publish this plan to ${who}?` : `Publish now and keep ${n} item${n > 1 ? "s" : ""} in your review queue?`}</p>
          <p className="text-base text-ink-soft">{ask === "publish" ? "You cannot edit it here afterwards. Later questions from the family reach you through the review queue."
            : `${who} sees those items as "Waiting for doctor review" until you resolve them from the review queue.`}</p>
          <div className="mt-3 flex flex-wrap gap-3">
            <button className="btn btn-primary" disabled={pub.isPending} onClick={() => pub.mutate(ask === "keep")}>Yes, publish</button>
            <button className="btn btn-plain" onClick={() => setAsk(null)}>Not yet</button>
          </div>
        </div>)}
      {pub.error && <ErrorNote>{detailMessage(pub.error)}</ErrorNote>}
    </section>
  );
}

/* ------------------------------------------------------------------ editor */

export function PlanEditor() {
  useDocTitle("Review plan");
  const { id = "" } = useParams();
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["plan", id], queryFn: () => api<PlanDetail>(`/plans/${id}`) });
  const [filter, setFilter] = useState<"all" | "review">("all");
  const [focus, setFocus] = useState<string | null>(null);
  const refresh = () => { void qc.invalidateQueries({ queryKey: ["plan", id] }); void qc.invalidateQueries({ queryKey: ["plans"] }); void qc.invalidateQueries({ queryKey: ["queue"] }); };
  const body = useMemo(() => {
    const s = q.data?.summary;
    if (!s) return null;
    const hs = [...s.highlights].sort((a, b) => a.start - b.start);
    const out: React.ReactNode[] = []; let pos = 0;
    hs.forEach((h) => {
      if (h.start < pos) return;
      out.push(s.raw_text.slice(pos, h.start));
      const c = h.status === "Needs Review" ? "#a8530c" : HL[h.color] ?? HL.gray;
      out.push(<mark key={h.task_id} id={`hl-${h.task_id}`} onClick={() => { setFocus(h.task_id); document.getElementById(`item-${h.task_id}`)?.scrollIntoView({ block: "center" }); }}
        style={{ background: `color-mix(in oklab, ${c} 18%, transparent)`, boxShadow: `inset 0 -3px 0 ${c}`, outline: focus === h.task_id ? "3px solid var(--color-ink)" : "none", color: "inherit", cursor: "pointer" }}>{s.raw_text.slice(h.start, h.end)}</mark>);
      pos = h.end;
    });
    out.push(s.raw_text.slice(pos));
    return out;
  }, [q.data, focus]);

  if (q.isLoading) return <ListSkeleton rows={3} />;
  if (q.error || !q.data) return <ErrorNote action={<Link to="/doctor/plans" className="btn btn-plain">Back to plans</Link>}>This plan is not available to you.</ErrorNote>;
  const p = q.data, draft = p.plan_status === "draft";
  const shown = filter === "review" ? p.tasks.filter((t) => t.status === "Needs Review") : p.tasks;
  const sum = p.summary;
  return (
    <div className="grid gap-6 lg:grid-cols-[1.15fr_1fr]">
      <div className="flex min-w-0 flex-col gap-5">
        <div>
          <Link to="/doctor/plans" className="mb-3 inline-flex items-center gap-1 font-display font-semibold text-ink"><Icon name="previous" size={20} />All plans</Link>
          <PageTitle icon="follow-up-plan" sub={[p.patient.name, p.patient.patient_code, p.patient.age_label, p.patient.language ? `reads ${LANG_NAME[p.patient.language] ?? p.patient.language}` : null].filter(Boolean).join(", ")}>
            {draft ? "Review plan" : "Published plan"}</PageTitle>
        </div>

        <section className="tile-quiet flex flex-col gap-2 p-4" aria-label="Why this plan is yours">
          <p className="flex flex-wrap items-center gap-2"><Icon name="doctor" size={26} /><span className="font-display font-semibold">Matched to you:</span>{p.match.reason ?? "Assigned by the hospital desk"}</p>
          <p className="flex flex-wrap gap-x-6 gap-y-1 text-base text-ink-soft">
            <span>Received {fmtDate(p.uploaded_at.slice(0, 10))}</span>
            {sum.discharge_date && <span>Discharged {fmtDate(sum.discharge_date)}</span>}
            <span>{p.extraction_method === "rules" ? "Read by the rule-based reader (no AI)" : p.extraction_method === "model" ? "Read by the AI reader, checked by fixed rules" : ""}</span>
            {p.published_at && <span>Published {fmtDate(p.published_at.slice(0, 10))}</span>}
          </p>
        </section>

        {draft ? <PublishBar plan={p} onDone={refresh} /> : (
          <section className="tile flex flex-wrap items-center gap-4 p-5" aria-label="Published">
            <Icon name="success" size={34} />
            <div className="min-w-0 flex-1"><h2 className="font-display text-xl font-bold">Published to the patient</h2>
              <p className="text-base text-ink-soft">This plan is locked. New questions from the patient or family arrive in your <Link to="/doctor" className="font-semibold text-teal">review queue</Link>.</p></div>
          </section>)}

        <div className="flex flex-wrap items-center gap-4">
          <Tabs label="Show" value={filter} onChange={setFilter} tabs={[{ id: "all", label: `All items (${p.counts.total})` }, { id: "review", label: `Needs review (${p.counts.needs_review})` }]} />
        </div>

        {!shown.length ? <EmptyState>{filter === "review" ? "Nothing flagged. Every item is clear." : "This plan has no items yet. Add the follow-up items from the summary below."}</EmptyState>
          : <div className="flex flex-col gap-4">{shown.map((t) => (
            <PlanItem key={t.id + (t.doctor_edited ? "e" : "") + t.status} t={t} pid={p.id} draft={draft} focused={focus === t.id}
              onFocus={() => { setFocus(t.id); document.getElementById(`hl-${t.id}`)?.scrollIntoView({ block: "center" }); }} onDone={refresh} />))}</div>}

        {draft && <AddItem pid={p.id} onDone={refresh} />}
        {draft && p.counts.total > 3 && <PublishBar plan={p} onDone={refresh} />}
        <p className="text-sm text-ink-soft">Each change is checked by the same fixed safety rules and kept in the change history. The original summary line is never rewritten.</p>
      </div>

      <aside className="min-w-0 lg:sticky lg:top-24 lg:self-start">
        <ReviewArt className="mb-3 max-w-[10rem]" />
        <section className="tile mb-4 p-4" aria-label="From the summary"><h2 className="font-display text-lg font-bold">From the summary</h2>
          <dl className="mt-1 grid grid-cols-[auto_minmax(0,1fr)] gap-x-4 gap-y-1 text-base">{Object.entries(sum.header).map(([k, val]) => <div key={k} className="contents"><dt className="text-ink-soft">{HEADER_LABEL[k] ?? k}</dt><dd>{val ?? "Not given"}</dd></div>)}
            {Object.entries(sum.diagnoses).map(([k, val]) => val ? <div key={k} className="contents"><dt className="text-ink-soft">{DX_LABEL[k] ?? k}</dt><dd>{val}</dd></div> : null)}</dl></section>
        {sum.notices.length > 0 && (
          <section className="tile-quiet mb-4 p-4" aria-label="Template notices"><h2 className="font-display text-base font-bold">Template notices</h2>
            <ul className="mt-1 flex flex-col gap-1 text-base text-ink-soft">{sum.notices.map((n, i) => <li key={i} className="flex gap-2"><Bullet tone="bg-ink-soft" />{n.text}{n.line ? ` (${n.line})` : ""}</li>)}</ul></section>)}
        <section className="tile p-4" aria-label="Original summary"><h2 className="font-display text-lg font-bold">Original summary</h2>
          <p className="mb-2 mt-1 flex flex-wrap gap-4 text-sm"><span><span className="mr-1 inline-block h-3 w-3 bg-pending" />Appointments</span><span><span className="mr-1 inline-block h-3 w-3" style={{ background: HL.yellow }} />Medicines</span><span><span className="mr-1 inline-block h-3 w-3" style={{ background: HL.red }} />Warnings</span><span><span className="mr-1 inline-block h-3 w-3 bg-review" />Needs review</span></p>
          <pre className="max-h-[70vh] overflow-auto whitespace-pre-wrap font-body text-base leading-relaxed" data-allow-overflow>{body}</pre></section>
      </aside>
    </div>
  );
}
