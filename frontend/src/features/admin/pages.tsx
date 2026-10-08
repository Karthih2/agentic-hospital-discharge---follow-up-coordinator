import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import CountUp from "../../components/motion/CountUp";
import { Chip, DataTable, EmptyState, ErrorNote, Field, ListSkeleton, PageTitle, Tabs, useDocTitle } from "../../components/ui";
import { api, errText } from "../../lib/api";
import { fmtDate, TYPE_LABEL } from "../../lib/types";

const Num = ({ n, label }: { n: number; label: string }) => (
  <div className="tile p-5"><p className="font-display text-5xl font-bold"><CountUp to={n} duration={1.2} /></p><p className="mt-1 text-ink-soft">{label}</p></div>
);

export function AdminOverview() {
  useDocTitle("Overview");
  const q = useQuery({ queryKey: ["a-over"], queryFn: () => api<{ open_reviews: Record<string, number>; open_total: number; unassigned_reviews: number; doctors_available: number; doctors_total: number; summaries_today: number; failures_today: number }>("/admin-api/overview"), refetchInterval: 20000 });
  const notes = useQuery({ queryKey: ["a-notes"], queryFn: () => api<{ summary_id: string; patient_code: string; notices: { code: string; text: string }[] }[]>("/admin-api/summary-notices") });
  const cbs = useQuery({ queryKey: ["a-cbs"], queryFn: () => api<{ id: string; status: string; requested_at: string; patient_mask: string | null }[]>("/admin-api/callbacks"), refetchInterval: 10000 });
  const qc = useQueryClient();
  const act = useMutation({ mutationFn: (p: string) => api(p, { method: "POST" }), onSuccess: () => void qc.invalidateQueries({ queryKey: ["a-cbs"] }) });
  const d = q.data;
  return (
    <div>
      <PageTitle icon="overview" sub="Counts only. Clinical text is never shown in this center.">Overview</PageTitle>
      {q.isLoading || !d ? <ListSkeleton rows={2} /> : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Num n={d.open_total} label="Open reviews" /><Num n={d.unassigned_reviews} label="Unassigned reviews" />
          <Num n={d.doctors_available} label={`Doctors available of ${d.doctors_total}`} /><Num n={d.summaries_today} label="Summaries processed today" />
          <Num n={d.failures_today} label="Failures today" /><Num n={d.open_reviews.under_24h} label="Reviews under 24 hours" />
          <Num n={d.open_reviews.one_to_three_days} label="Reviews 1 to 3 days" /><Num n={d.open_reviews.over_three_days} label="Reviews over 3 days" />
        </div>)}
      <h2 className="mb-3 mt-10 font-display text-2xl font-bold">Summary notices</h2>
      <DataTable rows={notes.data ?? []} rowKey={(r) => r.summary_id} empty={<EmptyState>No template notices.</EmptyState>}
        cols={[{ head: "Patient code", cell: (r) => r.patient_code }, { head: "Notices", cell: (r) => <ul className="flex flex-col gap-1">{r.notices.map((n, i) => <li key={i}>{n.text}</li>)}</ul> }]} />
      <h2 className="mb-3 mt-10 font-display text-2xl font-bold">Callback requests</h2>
      <DataTable rows={cbs.data ?? []} rowKey={(r) => r.id} empty={<EmptyState>No callback requests.</EmptyState>}
        cols={[{ head: "Status", cell: (r) => <Chip>{r.status}</Chip> }, { head: "Requested", cell: (r) => fmtDate(r.requested_at.slice(0, 10)) }, { head: "Masked number", cell: (r) => r.patient_mask ?? "none" },
          { head: "Action", cell: (r) => r.status === "requested" ? <button className="btn btn-primary" onClick={() => act.mutate(`/admin-api/callbacks/${r.id}/start`)}>Start call</button> : r.status === "connecting" ? <button className="btn btn-primary" onClick={() => act.mutate(`/admin-api/callbacks/${r.id}/complete`)}>End call</button> : null }]} />
    </div>
  );
}

type Doc = { doctor_id: string; name: string; specialty: string; clinic: string | null; area: string | null; available: boolean; switch_on: boolean; unavailable_until: string | null; fallback_doctor_id: string | null; fallback_name: string | null; open_reviews: number };

export function AdminDoctors() {
  useDocTitle("Doctors");
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["a-docs"], queryFn: () => api<Doc[]>("/admin-api/doctors") });
  const [until, setUntil] = useState<Record<string, string>>({});
  const act = useMutation({ mutationFn: (a: { path: string; json: unknown }) => api(a.path, { method: "PUT", json: a.json }), onSuccess: () => void qc.invalidateQueries() });
  const docs = q.data ?? [];
  return (
    <div>
      <PageTitle icon="doctor" sub="Availability, the date until which a doctor is away, and who takes over.">Doctors</PageTitle>
      {act.error && <div className="mb-4"><ErrorNote>{errText(act.error)}</ErrorNote></div>}
      {q.isLoading ? <ListSkeleton /> : <DataTable rows={docs} rowKey={(d) => d.doctor_id}
        cols={[{ head: "Doctor", cell: (d) => <><b>{d.name}</b><br /><span className="text-ink-soft">{d.specialty}, {d.area}</span></> },
          { head: "Open", cell: (d) => d.open_reviews },
          { head: "Status", cell: (d) => <Chip tone={d.available ? "teal" : "plain"}>{d.available ? "Available" : "Unavailable"}</Chip> },
          { head: "Availability", cell: (d) => (
            <div className="flex flex-col gap-2">
              <button className="btn btn-plain" onClick={() => act.mutate({ path: `/admin-api/doctors/${d.doctor_id}/availability`, json: { available: !d.switch_on } })}>{d.switch_on ? "Mark unavailable" : "Mark available"}</button>
              <Field label="Unavailable until"><input type="date" className="field" value={until[d.doctor_id] ?? d.unavailable_until?.slice(0, 10) ?? ""} onChange={(e) => setUntil({ ...until, [d.doctor_id]: e.target.value })} /></Field>
              <button className="btn btn-plain" disabled={!until[d.doctor_id]} onClick={() => act.mutate({ path: `/admin-api/doctors/${d.doctor_id}/availability`, json: { available: true, unavailable_until: `${until[d.doctor_id]}T23:59:00` } })}>Save date</button>
            </div>) },
          { head: "Fallback doctor", cell: (d) => (
            <select aria-label={`Fallback for ${d.name}`} className="field" value={d.fallback_doctor_id ?? ""} onChange={(e) => act.mutate({ path: `/admin-api/doctors/${d.doctor_id}/fallback`, json: { next_doctor_id: e.target.value || null } })}>
              <option value="">None</option>{docs.filter((x) => x.doctor_id !== d.doctor_id).map((x) => <option key={x.doctor_id} value={x.doctor_id}>{x.name}</option>)}
            </select>) }]} />}
    </div>
  );
}

type Rv = { id: string; status: string; reason_text: string; task_type: string | null; patient_code: string | null; assigned_doctor_id: string | null; assigned_name: string | null; age_hours: number; moves: number };

export function AdminRouting() {
  useDocTitle("Routing");
  const qc = useQueryClient();
  const [tab, setTab] = useState<"open" | "resolved">("open");
  const [hist, setHist] = useState<string | null>(null);
  const q = useQuery({ queryKey: ["a-rv", tab], queryFn: () => api<Rv[]>(`/admin-api/reviews?status=${tab}`) });
  const docs = useQuery({ queryKey: ["a-docs"], queryFn: () => api<Doc[]>("/admin-api/doctors") });
  const h = useQuery({ queryKey: ["a-hist", hist], enabled: !!hist, queryFn: () => api<{ name: string; reason: string; assigned_at: string }[]>(`/admin-api/reviews/${hist}/history`) });
  const act = useMutation({ mutationFn: (a: { id: string; doctor_id: string }) => api(`/admin-api/reviews/${a.id}/assign`, { method: "POST", json: { doctor_id: a.doctor_id } }), onSuccess: () => void qc.invalidateQueries() });
  return (
    <div>
      <PageTitle icon="routing" sub="Reassign one review at a time. There is no bulk reassign.">Review routing</PageTitle>
      <Tabs label="Reviews" value={tab} onChange={setTab} tabs={[{ id: "open", label: "Open" }, { id: "resolved", label: "Resolved" }]} />
      {act.error && <div className="mt-4"><ErrorNote>{errText(act.error)}</ErrorNote></div>}
      <div className="mt-6">{q.isLoading ? <ListSkeleton /> : <DataTable rows={q.data ?? []} rowKey={(r) => r.id} empty={<EmptyState>Nothing here.</EmptyState>}
        cols={[{ head: "Item", cell: (r) => <><b>{TYPE_LABEL[r.task_type ?? ""] ?? "Task"}</b>, {r.patient_code}<br /><span className="text-ink-soft">{r.reason_text}</span></> },
          { head: "Age", cell: (r) => `${r.age_hours} h${r.moves ? `, moved ${r.moves}x` : ""}` },
          { head: "Assigned", cell: (r) => r.status === "resolved" ? r.assigned_name : (
            <select aria-label="Assign doctor" className="field" value={r.assigned_doctor_id ?? ""} onChange={(e) => e.target.value && act.mutate({ id: r.id, doctor_id: e.target.value })}>
              <option value="">Unassigned</option>{docs.data?.map((d) => <option key={d.doctor_id} value={d.doctor_id}>{d.name}{d.available ? "" : " (unavailable)"}</option>)}</select>) },
          { head: "History", cell: (r) => <button className="font-semibold text-teal underline" onClick={() => setHist(hist === r.id ? null : r.id)}>{hist === r.id ? "Hide" : "Show"}</button> }]} />}</div>
      {hist && h.data && <ol className="tile mt-4 flex flex-col gap-1 p-4">{h.data.map((x, i) => <li key={i}>{x.name ?? "Unassigned"}: {x.reason}, {fmtDate(x.assigned_at.slice(0, 10))}</li>)}</ol>}
    </div>
  );
}

export function AdminHubs() {
  useDocTitle("Hubs");
  const q = useQuery({ queryKey: ["a-hubs"], queryFn: () => api<{ id: string; name: string; manager: string; members: { name: string; role: string }[]; consents: { patient: string; grantee: string; level: string; guardian: boolean }[] }[]>("/admin-api/hubs") });
  return (
    <div>
      <PageTitle icon="hubs" sub="Members and consent levels. No clinical text.">Family hubs</PageTitle>
      {q.isLoading ? <ListSkeleton /> : (q.data ?? []).map((h) => (
        <section key={h.id} className="tile mb-6 p-5">
          <h2 className="font-display text-xl font-bold">{h.name}</h2><p className="text-ink-soft">Manager: {h.manager}</p>
          <p className="mt-2 flex flex-wrap gap-2">{h.members.map((m, i) => <Chip key={i}>{m.name}: {m.role}</Chip>)}</p>
          <div className="mt-4"><DataTable rows={h.consents} rowKey={(c) => c.patient + c.grantee} empty={<p className="text-ink-soft">No consents.</p>}
            cols={[{ head: "Patient", cell: (c) => c.patient }, { head: "Person with access", cell: (c) => c.grantee }, { head: "Level", cell: (c) => <Chip>{c.level}{c.guardian ? ", guardian" : ""}</Chip> }]} /></div>
        </section>))}
    </div>
  );
}

export function AdminAudit() {
  useDocTitle("Audit log");
  const [actor, setActor] = useState(""); const [from, setFrom] = useState(""); const [to, setTo] = useState("");
  const people = useQuery({ queryKey: ["a-people"], queryFn: () => api<{ id: string; name: string; role: string }[]>("/admin-api/people") });
  const qs = new URLSearchParams({ ...(actor && { actor }), ...(from && { date_from: from }), ...(to && { date_to: to }) }).toString();
  const q = useQuery({ queryKey: ["a-audit", qs], queryFn: () => api<{ ts: string; actor: string | null; action: string; target_type: string | null; result: string }[]>(`/admin-api/audit?${qs}`) });
  return (
    <div>
      <PageTitle icon="audit" sub="Who did what and when. Metadata only.">Audit log</PageTitle>
      <div className="mb-5 grid gap-4 sm:grid-cols-3">
        <Field label="Actor"><select className="field" value={actor} onChange={(e) => setActor(e.target.value)}><option value="">Everyone</option>{people.data?.map((p) => <option key={p.id} value={p.id}>{p.name} ({p.role})</option>)}</select></Field>
        <Field label="From"><input type="date" className="field" value={from} onChange={(e) => setFrom(e.target.value)} /></Field>
        <Field label="To"><input type="date" className="field" value={to} onChange={(e) => setTo(e.target.value)} /></Field>
      </div>
      {q.isLoading ? <ListSkeleton /> : <DataTable rows={q.data ?? []} rowKey={(r) => r.ts + r.action + (r.actor ?? "")} empty={<EmptyState>No events match.</EmptyState>}
        cols={[{ head: "When", cell: (r) => new Date(r.ts).toLocaleString("en-IN") }, { head: "Actor", cell: (r) => r.actor ?? "unknown" }, { head: "Action", cell: (r) => r.action }, { head: "On", cell: (r) => r.target_type ?? "" }, { head: "Result", cell: (r) => <Chip>{r.result}</Chip> }]} />}
    </div>
  );
}

export function AdminSystem() {
  useDocTitle("System");
  const q = useQuery({ queryKey: ["a-sys"], queryFn: () => api<{ db: string; schema_version: number; collections: { name: string; count: number; older_schema: number }[]; jobs: { name: string; last_run: string | null; last_error: string | null }[] }>("/admin-api/system"), refetchInterval: 15000 });
  const health = useQuery({ queryKey: ["health"], queryFn: () => api<{ db: string }>("/health"), retry: false });
  const d = q.data;
  return (
    <div>
      <PageTitle icon="system" sub="Database status, collection counts and job runs.">System</PageTitle>
      <p className="mb-4 flex flex-wrap gap-2"><Chip tone={health.data?.db === "ok" ? "teal" : "plain"}>Database: {health.data?.db ?? (health.isError ? "down" : "checking")}</Chip>{d && <Chip>Schema version {d.schema_version}</Chip>}</p>
      {!d ? <ListSkeleton /> : <>
        <DataTable rows={d.collections} rowKey={(c) => c.name} cols={[{ head: "Collection", cell: (c) => c.name }, { head: "Documents", cell: (c) => c.count }, { head: "Older schema", cell: (c) => c.older_schema }]} />
        <h2 className="mb-3 mt-8 font-display text-2xl font-bold">Background jobs</h2>
        <DataTable rows={d.jobs} rowKey={(j) => j.name} empty={<EmptyState>No job has run yet.</EmptyState>}
          cols={[{ head: "Job", cell: (j) => j.name }, { head: "Last run", cell: (j) => j.last_run ? new Date(j.last_run).toLocaleString("en-IN") : "never" }, { head: "Error", cell: (j) => j.last_error ?? "none" }]} /></>}
    </div>
  );
}
