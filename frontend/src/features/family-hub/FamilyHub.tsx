import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Icon } from "../../components/icons/Icon";
import CountUp from "../../components/motion/CountUp";
import { Chip, EmptyState, ErrorNote, Field, ListSkeleton, PageTitle, StatusChip, useDocTitle } from "../../components/ui";
import { api, errText } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { fmtDate, LEVEL_LABEL, type Hub, type HubPatient, type Level, type Status } from "../../lib/types";

type Invite = { id: string; hub_name: string; manager_name: string; patient_id: string; patient_name: string };

function Invites() {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["invites"], queryFn: () => api<Invite[]>("/me/invites"), refetchInterval: 10000 });
  const [lv, setLv] = useState<Record<string, Level>>({});
  const act = useMutation({
    mutationFn: (a: { id: string; ok: boolean }) => a.ok ? api(`/invites/${a.id}/approve`, { method: "POST", json: { level: lv[a.id] ?? "full" } }) : api(`/invites/${a.id}/deny`, { method: "POST" }),
    onSuccess: () => void qc.invalidateQueries(),
  });
  if (!q.data?.length) return null;
  return (
    <section aria-label="Invitations" className="mb-8 flex flex-col gap-3">
      {q.data.map((i) => (
        <div key={i.id} className="tile flex flex-col gap-3 p-4">
          <p className="flex items-center gap-3 font-display text-lg font-semibold"><Icon name="notification-new" size={30} />{i.manager_name} asks to add {i.patient_name} to {i.hub_name}</p>
          <div className="flex flex-wrap items-end gap-4">
            <Field label="They may see"><select className="field" value={lv[i.id] ?? "full"} onChange={(e) => setLv({ ...lv, [i.id]: e.target.value as Level })}>
              <option value="full">Full plan</option><option value="appointments">Appointments only</option><option value="reminders">Reminders only</option></select></Field>
            <button className="btn btn-primary" disabled={act.isPending} onClick={() => act.mutate({ id: i.id, ok: true })}>Approve</button>
            <button className="btn btn-plain" disabled={act.isPending} onClick={() => act.mutate({ id: i.id, ok: false })}>Deny</button>
          </div>
        </div>))}
    </section>
  );
}

function PatientSection({ p }: { p: HubPatient }) {
  const none = p.access === "none";
  return (
    <article className={`flex min-w-0 flex-col gap-4 p-5 ${none ? "border-2 border-dashed border-ink bg-ground-deep text-ink-soft" : "tile"}`} style={{ borderRadius: 4 }} aria-label={p.name}>
      <header className="flex flex-wrap items-center gap-3">
        <Icon name={p.is_child ? "child" : "patient"} size={34} /><h3 className="font-display text-2xl font-bold">{p.name}</h3>
        <Chip tone={p.access === "self" || p.access === "full" ? "teal" : "plain"}>{LEVEL_LABEL[p.access]}</Chip>
        {p.patient_code && <Chip>{p.patient_code}</Chip>}
      </header>
      {none ? <p className="flex items-center gap-2"><Icon name="locked" size={24} />Nothing is shared with you yet. {p.name} decides what you can see.</p> : (<>
        {p.counts ? (
          <dl className="grid grid-cols-3 gap-3">
            {(["Pending", "Completed", "Needs Review"] as Status[]).map((s) => (
              <div key={s} className="tile-quiet flex min-w-0 flex-col items-start gap-1 p-3"><dt><StatusChip status={s} /></dt><dd className="font-display text-4xl font-bold"><CountUp to={p.counts![s]} duration={0.9} /></dd></div>))}
          </dl>) : <p className="text-ink-soft">Counts are not part of your access level.</p>}
        <p className="flex items-center gap-2"><Icon name="calendar" size={22} />{p.next_due ? `Next due ${fmtDate(p.next_due)}` : "Nothing due soon"}</p>
        {p.counts && p.counts["Needs Review"] > 0 && <p className="flex items-center gap-2 text-review"><Icon name="needs-review" size={22} />{p.counts["Needs Review"]} waiting for doctor review</p>}
        <div className="flex flex-wrap gap-3">
          <Link to={`/hub/plan/${p.patient_id}`} className="btn btn-primary">Open plan</Link>
          {p.operate && <Link to={`/hub/upload/${p.patient_id}`} className="btn btn-plain"><Icon name="upload" size={22} />Upload summary</Link>}
        </div></>)}
    </article>
  );
}

function InvitePanel({ hub }: { hub: Hub }) {
  const qc = useQueryClient();
  const [code, setCode] = useState(""); const [login, setLogin] = useState(""); const [msg, setMsg] = useState(""); const [err, setErr] = useState("");
  const inv = useMutation({ mutationFn: () => api<{ status: string }>(`/hubs/${hub.id}/invite-patient`, { method: "POST", json: { patient_code: code.trim().toUpperCase() } }),
    onSuccess: (r) => { setErr(""); setMsg(r.status === "joined" ? "Added to the hub." : "Invitation sent. The patient must approve it."); setCode(""); void qc.invalidateQueries(); }, onError: (x) => { setMsg(""); setErr(errText(x)); } });
  const add = useMutation({ mutationFn: () => api(`/hubs/${hub.id}/viewers`, { method: "POST", json: { login } }),
    onSuccess: () => { setErr(""); setMsg("Added as a viewer. A patient must still give consent."); setLogin(""); void qc.invalidateQueries(); }, onError: (x) => { setMsg(""); setErr(errText(x)); } });
  const go = (fn: () => void) => (e: FormEvent) => { e.preventDefault(); fn(); };
  return (
    <section className="tile-quiet mt-6 grid gap-6 p-5 md:grid-cols-2" aria-label="Manage this hub">
      <form onSubmit={go(() => inv.mutate())} className="flex flex-col gap-3"><h3 className="font-display text-lg font-bold">Invite a patient by code</h3>
        <Field label="Patient code" hint="The patient sees it on their hub home."><input className="field" value={code} onChange={(e) => setCode(e.target.value)} placeholder="PAT-4101" pattern="[Pp][Aa][Tt]-\d{4,8}" required /></Field>
        <button className="btn btn-primary self-start" disabled={inv.isPending}>Send invitation</button></form>
      <form onSubmit={go(() => add.mutate())} className="flex flex-col gap-3"><h3 className="font-display text-lg font-bold">Add a viewer</h3>
        <Field label="Family login" hint="An existing family account."><input className="field" value={login} onChange={(e) => setLogin(e.target.value)} required minLength={3} /></Field>
        <button className="btn btn-plain self-start" disabled={add.isPending}>Add viewer</button></form>
      {(msg || err) && <div className="md:col-span-2">{err ? <ErrorNote>{err}</ErrorNote> : <p role="status" className="font-semibold">{msg}</p>}</div>}
    </section>
  );
}

export function HubHome() {
  useDocTitle("Family hub");
  const { me } = useAuth();
  const qc = useQueryClient();
  const [name, setName] = useState("");
  const hubs = useQuery({ queryKey: ["hubs"], queryFn: () => api<Hub[]>("/hubs") });
  const create = useMutation({ mutationFn: () => api("/hubs", { method: "POST", json: { name } }), onSuccess: () => { setName(""); void qc.invalidateQueries({ queryKey: ["hubs"] }); } });
  const code = me?.role === "patient" ? me.patient_code : null;
  return (
    <div>
      <PageTitle icon="hubs" sub={code ? <>Your patient code for invitations: <strong className="font-display text-ink">{code}</strong></> : "One shared home for one family. Each patient keeps a separate plan."}>Family hub</PageTitle>
      <Invites />
      {hubs.isLoading ? <ListSkeleton rows={2} /> : hubs.error ? <ErrorNote>Could not load your hubs.</ErrorNote> : (<>
        {me?.role === "patient" && !hubs.data?.some((h) => h.patients.some((p) => p.access === "self")) && (
          <p className="tile-quiet mb-6 flex flex-wrap items-center gap-4 p-4"><Icon name="follow-up-plan" size={30} />You are not in a hub yet.
            <Link to={`/hub/plan/${me.id}`} className="btn btn-plain">Open my own plan</Link><Link to={`/hub/upload/${me.id}`} className="btn btn-plain">Upload a summary</Link></p>)}
        {!hubs.data?.length && <EmptyState>You are not in a family hub yet. Create one below, or ask a hub manager to invite you.</EmptyState>}
        {hubs.data?.map((h) => (
          <section key={h.id} className="mb-10" aria-labelledby={`h-${h.id}`}>
            <div className="mb-4 flex flex-wrap items-center gap-3">
              <h2 id={`h-${h.id}`} className="font-display text-3xl font-bold">{h.name}</h2>
              {h.my_roles.map((r) => <Chip key={r} tone="ink">{r}</Chip>)}
              <span className="text-ink-soft">Manager: {h.manager_name}</span>
              {h.pending_invites ? <Chip>{h.pending_invites} invitation waiting</Chip> : null}
            </div>
            <div className="grid gap-5 md:grid-cols-2">{h.patients.map((p) => <PatientSection key={p.patient_id} p={p} />)}</div>
            {h.is_manager && <InvitePanel hub={h} />}
          </section>))}
        <form className="tile mt-8 flex max-w-xl flex-col gap-3 p-5" onSubmit={(e) => { e.preventDefault(); create.mutate(); }}>
          <h2 className="font-display text-xl font-bold">Create a family hub</h2>
          <Field label="Hub name"><input className="field" value={name} onChange={(e) => setName(e.target.value)} required minLength={2} maxLength={80} placeholder="Our family hub" /></Field>
          {create.error && <ErrorNote>{errText(create.error)}</ErrorNote>}
          <button className="btn btn-primary self-start" disabled={create.isPending}><Icon name="plus" size={22} className="duo-on-teal !text-ground" />Create hub</button>
        </form></>)}
    </div>
  );
}

type Cons = { hub_id: string; hub_name: string; grantee_id: string; name: string; hub_role: string; level: Level | null; guardian_consent: boolean };

function ConsentList({ pid, who }: { pid: string; who: string }) {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["consents", pid], queryFn: () => api<Cons[]>(`/patients/${pid}/consents`) });
  const act = useMutation({
    mutationFn: (a: { c: Cons; level: Level | "none" }) => a.level === "none"
      ? api(`/hubs/${a.c.hub_id}/patients/${pid}/consents/${a.c.grantee_id}`, { method: "DELETE" })
      : api(`/hubs/${a.c.hub_id}/patients/${pid}/consents/${a.c.grantee_id}`, { method: "PUT", json: { level: a.level } }),
    onSuccess: () => void qc.invalidateQueries(),
  });
  return (
    <section className="mb-8" aria-label={`Who can see ${who}`}>
      <h2 className="mb-3 font-display text-2xl font-bold">Who can see {who}</h2>
      {act.error && <div className="mb-3"><ErrorNote>{errText(act.error)}</ErrorNote></div>}
      {q.isLoading ? <ListSkeleton rows={2} /> : !q.data?.length ? <EmptyState>No one else is in a hub with {who} yet.</EmptyState> : (
        <ul className="flex flex-col gap-3">{q.data.map((c) => (
          <li key={c.hub_id + c.grantee_id} className="tile flex flex-wrap items-center gap-4 p-4">
            <Icon name="family-member" size={34} />
            <div className="min-w-0 flex-1 basis-48"><p className="font-display text-lg font-semibold">{c.name}</p><p className="text-base text-ink-soft">{c.hub_name}, {c.hub_role}{c.guardian_consent ? ", given by guardian" : ""}</p></div>
            <select aria-label={`Access for ${c.name}`} className="field !w-auto" value={c.level ?? "none"} onChange={(e) => act.mutate({ c, level: e.target.value as Level | "none" })}>
              <option value="none">No access</option>{c.hub_role === "manager" && <option value="full">Full plan</option>}<option value="appointments">Appointments only</option><option value="reminders">Reminders only</option></select>
            {c.level && <button className="btn btn-plain" onClick={() => { if (confirm(`Remove ${c.name}? Access ends immediately.`)) act.mutate({ c, level: "none" }); }}>Revoke</button>}
          </li>))}</ul>)}
    </section>
  );
}

/** Consent screen: the patient (or a guardian, for a child) decides. Everyone else sees who is in their hubs. */
export function Members() {
  useDocTitle("Members and consent");
  const { me } = useAuth();
  const hubs = useQuery({ queryKey: ["hubs"], queryFn: () => api<Hub[]>("/hubs") });
  const mine = new Map<string, string>();
  hubs.data?.forEach((h) => h.patients.forEach((p) => { if (p.access === "self" || (p.is_child && p.operate)) mine.set(p.patient_id, p.access === "self" ? "you" : p.name); }));
  return (
    <div>
      <PageTitle icon="consent" sub="Consent comes first. Revoking is immediate.">Members and consent</PageTitle>
      <Invites />
      {[...mine].map(([pid, who]) => <ConsentList key={pid} pid={pid} who={who} />)}
      {!mine.size && me?.role === "patient" && me && <ConsentList pid={me.id} who="you" />}
      <h2 className="mb-3 font-display text-2xl font-bold">People in your hubs</h2>
      {hubs.isLoading ? <ListSkeleton rows={2} /> : hubs.data?.map((h) => (
        <section key={h.id} className="tile-quiet mb-4 p-4"><h3 className="font-display text-lg font-bold">{h.name}</h3>
          <ul className="mt-2 flex flex-wrap gap-2">{h.members.map((m) => <li key={m.user_id}><Chip>{m.name}: {m.roles.join(", ")}</Chip></li>)}</ul></section>))}
    </div>
  );
}

type N = { id: string; text: string; sent_at: string; read: boolean; callback?: { status: string; masked_number: string | null } };
export function Notifications() {
  useDocTitle("Notifications");
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["notes"], queryFn: () => api<N[]>("/me/notifications"), refetchInterval: 20000 });
  const read = useMutation({ mutationFn: (id: string) => api(`/me/notifications/${id}/read`, { method: "POST" }), onSuccess: () => void qc.invalidateQueries({ queryKey: ["notes"] }) });
  return (
    <div>
      <PageTitle icon="notification">Notifications</PageTitle>
      {q.isLoading ? <ListSkeleton /> : !q.data?.length ? <EmptyState>Nothing new.</EmptyState>
        : <ul className="flex flex-col gap-3">{q.data.map((n) => (
          <li key={n.id} className={`flex flex-wrap items-center gap-4 p-4 ${n.read ? "tile-quiet" : "tile"}`}><Icon name={n.callback ? "callback" : "notification"} size={30} />
            <div className="min-w-0 flex-1 basis-48"><p className={n.read ? "" : "font-semibold"}>{n.text}</p><p className="text-sm text-ink-soft">{fmtDate(n.sent_at.slice(0, 10))}{n.callback?.masked_number ? `, masked number ${n.callback.masked_number}` : ""}</p></div>
            {!n.read && <button className="btn btn-plain !min-h-10" onClick={() => read.mutate(n.id)}>Mark read</button>}</li>))}</ul>}
    </div>
  );
}
