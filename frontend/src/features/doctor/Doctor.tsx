import { useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Icon } from "../../components/icons/Icon";
import { ReviewArt } from "../../components/illustrations/Illustrations";
import { Chip, EmptyState, ErrorNote, Field, ListSkeleton, PageTitle, StatusChip, Tabs, useDocTitle } from "../../components/ui";
import { api, ApiError, errText } from "../../lib/api";
import { fmtDate, TYPE_LABEL, type Status } from "../../lib/types";

type QItem = { id: string; reason_text: string; task_type: string; patient_name?: string; patient_code?: string; created_at: string; age_hours: number };
type Filter = "all" | "medicine" | "appointment" | "test" | "care_instruction" | "warning_sign";

export function DoctorQueue() {
  useDocTitle("Review queue");
  const [f, setF] = useState<Filter>("all");
  const [sort, setSort] = useState<"flagged" | "age">("flagged");
  const q = useQuery({ queryKey: ["queue", f, sort], queryFn: () => api<QItem[]>(`/review/queue?sort=${sort}${f === "all" ? "" : `&type=${f}`}`), refetchInterval: 15000 });
  return (
    <div>
      <PageTitle icon="needs-review" sub={`${q.data?.length ?? 0} waiting for you`}>Review queue</PageTitle>
      <div className="mb-5 flex flex-wrap items-end gap-4">
        <Tabs label="Filter by type" value={f} onChange={setF} tabs={[{ id: "all", label: "All" }, { id: "medicine", label: "Medicines" }, { id: "appointment", label: "Appointments" }, { id: "test", label: "Tests" }, { id: "care_instruction", label: "Instructions" }, { id: "warning_sign", label: "Warnings" }]} />
        <Field label="Sort by"><select className="field" value={sort} onChange={(e) => setSort(e.target.value as "flagged" | "age")}><option value="flagged">Date flagged, newest first</option><option value="age">Age, oldest first</option></select></Field>
      </div>
      {q.isLoading ? <ListSkeleton /> : q.error ? <ErrorNote>Could not load the queue.</ErrorNote> : !q.data?.length ? <EmptyState>Nothing waiting. New flagged items appear here.</EmptyState> :
        <ul className="flex flex-col gap-3">{q.data.map((r) => (
          <li key={r.id}><Link to={`/doctor/review/${r.id}`} className="tile flex flex-wrap items-center gap-4 p-4 text-ink no-underline">
            <Icon name="needs-review" size={34} />
            <div className="min-w-0 flex-1 basis-56"><p className="font-display text-lg font-semibold">{r.patient_name ?? "Patient"} <span className="text-base font-normal text-ink-soft">{r.patient_code}</span></p><p className="text-base text-ink-soft">{r.reason_text}</p></div>
            <Chip>{TYPE_LABEL[r.task_type] ?? "Task"}</Chip>
            <span className="text-base text-ink-soft">{fmtDate(r.created_at.slice(0, 10))}, {r.age_hours} h old</span></Link></li>))}</ul>}
    </div>
  );
}

type Detail = {
  patient_name?: string; patient_code?: string; reason_list: { code: string; text: string }[]; user_note?: string | null;
  summary: null | { raw_text: string; source_span: { start: number; end: number } | null; header: Record<string, string | null>; diagnoses: Record<string, string | null>; notices: { code: string; text: string; line: string | null }[] };
  task: { id: string; type: string; title: string; source_line: string; due_date: string | null; fields: { doctor_name?: string; department?: string; instruction?: string; due_time?: string; location?: string; phone?: string; medicine?: Record<string, string | null> }; simple_text?: string | null };
};
const HEADER_LABEL: Record<string, string> = { admission_date: "Date of Admission", attending_physician: "Attending Physician", pcp: "PCP", disposition: "Discharge Disposition" };
const DX_LABEL: Record<string, string> = { admission: "Admission Diagnosis", discharge: "Discharge Diagnosis", secondary: "Secondary Diagnoses" };

export function ReviewDetail() {
  useDocTitle("Review item");
  const { id = "" } = useParams();
  const nav = useNavigate();
  const qc = useQueryClient();
  const d = useQuery({ queryKey: ["review", id], queryFn: () => api<Detail>(`/review/${id}`) });
  const [edit, setEdit] = useState(false);
  const [v, setV] = useState<Record<string, string>>({});
  const [still, setStill] = useState<{ reason_code: string; text?: string }[]>([]);
  const [err, setErr] = useState("");
  const res = useMutation({
    mutationFn: (body: unknown) => api(`/review/${id}/resolve`, { method: "POST", json: body }),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: ["queue"] }); nav("/doctor"); },
    onError: (x) => {
      const det = x instanceof ApiError ? (x.body as { detail?: { reasons?: { reason_code: string; text?: string }[] } } | null)?.detail : null;
      if (det && typeof det === "object" && det.reasons) { setStill(det.reasons); setErr(""); } else setErr(errText(x));
    },
  });
  const body = useMemo(() => {
    const s = d.data?.summary;
    if (!s) return null;
    const sp = s.source_span;
    if (!sp) return s.raw_text;
    return <>{s.raw_text.slice(0, sp.start)}<mark id="src" className="bg-mint px-0.5 text-ink" style={{ boxShadow: "inset 0 -3px 0 var(--color-teal)" }}>{s.raw_text.slice(sp.start, sp.end)}</mark>{s.raw_text.slice(sp.end)}</>;
  }, [d.data]);
  if (d.isLoading) return <ListSkeleton rows={2} />;
  if (d.error || !d.data) return <ErrorNote>This item is not available to you.</ErrorNote>;
  const t = d.data.task, sum = d.data.summary;
  const correct = () => {
    const cv: Record<string, unknown> = {};
    for (const k of ["due_date", "due_time", "location", "phone", "doctor_name", "specialty", "instruction"]) if (v[k]) cv[k] = v[k];
    const med = Object.fromEntries(["name", "dose", "route", "timing", "duration", "special"].filter((k) => v["m_" + k]).map((k) => [k, v["m_" + k]]));
    if (Object.keys(med).length) cv.medicine = med;
    setErr(""); setStill([]); res.mutate({ outcome: "corrected", corrected_values: cv });
  };
  const inp = (k: string, label: string, type = "text") => <Field label={label}><input className="field" type={type} value={v[k] ?? ""} onChange={(e) => setV({ ...v, [k]: e.target.value })} /></Field>;
  return (
    <div className="grid gap-6 lg:grid-cols-[1.1fr_1fr]">
      <div className="min-w-0">
        <PageTitle icon="needs-review" sub={`${d.data.patient_name ?? ""} ${d.data.patient_code ?? ""}`}>Review item</PageTitle>
        <section className="tile flex flex-col gap-4 p-5">
          <div><h2 className="font-display text-lg font-bold">Why it was flagged</h2>
            <ul className="mt-1 flex flex-col gap-1">{d.data.reason_list.map((r) => <li key={r.code} className="flex gap-2"><span aria-hidden className="mt-2.5 h-2 w-2 shrink-0 bg-review" />{r.text}</li>)}</ul>
            {d.data.user_note && <p className="mt-1 italic">Note from the family: {d.data.user_note}</p>}</div>
          <div><h2 className="font-display text-lg font-bold">Source line</h2><p className="mt-1 text-xl italic">{t.source_line}</p></div>
          <div><h2 className="font-display text-lg font-bold">Item as it stands</h2>
            <dl className="mt-1 grid grid-cols-[auto_minmax(0,1fr)] gap-x-6 gap-y-1"><dt className="text-ink-soft">Type</dt><dd>{TYPE_LABEL[t.type]}</dd><dt className="text-ink-soft">Title</dt><dd>{t.title}</dd>
              <dt className="text-ink-soft">Date</dt><dd>{t.due_date ? fmtDate(t.due_date) : "Not set"}</dd>
              {t.fields.due_time && <><dt className="text-ink-soft">Time</dt><dd>{t.fields.due_time}</dd></>}
              {t.fields.location && <><dt className="text-ink-soft">Location</dt><dd>{t.fields.location}</dd></>}
              {t.fields.doctor_name && <><dt className="text-ink-soft">Doctor</dt><dd>{t.fields.doctor_name}</dd></>}
              {t.fields.medicine && Object.entries(t.fields.medicine).map(([k, val]) => <div key={k} className="contents"><dt className="text-ink-soft capitalize">{k}</dt><dd>{val ?? "Not stated"}</dd></div>)}
              {t.fields.instruction && <><dt className="text-ink-soft">Instruction</dt><dd>{t.fields.instruction}</dd></>}</dl></div>
        </section>
        {sum && sum.notices.length > 0 && (
          <section className="tile-quiet mt-4 p-4" aria-label="Template notices"><h2 className="font-display text-base font-bold">Template notices</h2>
            <ul className="mt-1 flex flex-col gap-1 text-base text-ink-soft">{sum.notices.map((n, i) => <li key={i}>{n.text}{n.line ? ` (${n.line})` : ""}</li>)}</ul></section>)}
        {edit && (
          <section className="tile mt-5 flex flex-col gap-4 p-5" aria-label="Correction">
            <h2 className="font-display text-lg font-bold">Enter the correct or missing values</h2>
            {inp("due_date", "Date", "date")}{inp("due_time", "Time")}{inp("location", "Location")}{inp("phone", "Phone")}{inp("doctor_name", "Doctor")}{inp("specialty", "Specialty")}{inp("instruction", "Instruction")}
            {t.type === "medicine" && <>{inp("m_name", "Medicine name")}{inp("m_dose", "Dose")}{inp("m_route", "Route")}{inp("m_timing", "Timing")}{inp("m_duration", "Duration")}{inp("m_special", "Special instructions")}</>}
            {still.length > 0 && <div role="alert" className="border-2 border-review bg-ground-deep p-3"><p className="font-display font-semibold">Still missing:</p><ul className="list-disc pl-5">{still.map((r, i) => <li key={i}>{r.text ?? r.reason_code}</li>)}</ul></div>}
          </section>)}
        {err && <div className="mt-4"><ErrorNote>{err}</ErrorNote></div>}
        <div className="mt-5 flex flex-wrap gap-3">
          {!edit ? <>
            <button className="btn btn-primary" disabled={res.isPending} onClick={() => { setErr(""); res.mutate({ outcome: "confirmed" }); }}><Icon name="confirmed" size={22} className="duo-on-teal !text-ground" />Confirm</button>
            <button className="btn btn-plain" onClick={() => setEdit(true)}><Icon name="manual-entry" size={22} />Correct</button></>
            : <><button className="btn btn-primary" disabled={res.isPending} onClick={correct}>Save correction and confirm</button><button className="btn btn-plain" onClick={() => { setEdit(false); setStill([]); }}>Cancel</button></>}
        </div>
        <p className="mt-3 text-sm text-ink-soft">Each item is resolved on its own. There is no approve all.</p>
      </div>
      <aside className="min-w-0 lg:sticky lg:top-24 lg:self-start">
        <ReviewArt className="mb-3 max-w-[10rem]" />
        {sum && (<>
          <section className="tile mb-4 p-4" aria-label="From the summary"><h2 className="font-display text-lg font-bold">From the summary</h2>
            <dl className="mt-1 grid grid-cols-[auto_minmax(0,1fr)] gap-x-4 gap-y-1 text-base">{Object.entries(sum.header).map(([k, val]) => <div key={k} className="contents"><dt className="text-ink-soft">{HEADER_LABEL[k]}</dt><dd>{val ?? "Not given"}</dd></div>)}
              {Object.entries(sum.diagnoses).map(([k, val]) => val ? <div key={k} className="contents"><dt className="text-ink-soft">{DX_LABEL[k]}</dt><dd>{val}</dd></div> : null)}</dl></section>
          <section className="tile p-4" aria-label="Original summary"><h2 className="font-display text-lg font-bold">Original summary</h2>
            <pre className="mt-2 max-h-[32rem] overflow-auto whitespace-pre-wrap font-body text-base leading-relaxed" data-allow-overflow>{body}</pre></section></>)}
      </aside>
    </div>
  );
}

type MP = { patient_id: string; name: string; patient_code: string; counts: Record<Status, number>; appointments: { title: string; due_date: string | null; status: Status }[] };
export function DoctorPatients() {
  useDocTitle("My patients");
  const q = useQuery({ queryKey: ["my-pats"], queryFn: () => api<MP[]>("/review/patients") });
  return (
    <div>
      <PageTitle icon="patient" sub="Read only. Plans are changed only by resolving a review.">My patients</PageTitle>
      {q.isLoading ? <ListSkeleton /> : !q.data?.length ? <EmptyState>No patients assigned to you yet.</EmptyState> :
        <ul className="grid gap-4 md:grid-cols-2">{q.data.map((p) => (
          <li key={p.patient_id} className="tile flex flex-col gap-3 p-5"><div className="flex flex-wrap items-center gap-2"><h2 className="font-display text-xl font-bold">{p.name}</h2><Chip>{p.patient_code}</Chip></div>
            <p className="flex flex-wrap gap-2">{(Object.keys(p.counts) as Status[]).map((s) => <span key={s} className="inline-flex items-center gap-1"><StatusChip status={s} />{p.counts[s]}</span>)}</p>
            {p.appointments.length ? <ul className="flex flex-col gap-1">{p.appointments.map((a, i) => <li key={i} className="flex flex-wrap justify-between gap-2 border-t border-line pt-1"><span>{a.title}</span><span className="text-ink-soft">{fmtDate(a.due_date)}</span></li>)}</ul> : <p className="text-ink-soft">No appointments.</p>}
          </li>))}</ul>}
    </div>
  );
}
