import { useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, ApiError } from "../../lib/api";
import { TYPE_LABEL, type Task } from "../../lib/types";
import { ErrorNote, Field, PageTitle, useDocTitle } from "../../components/ui";

/** Manual entry. Goes through the same safety gate as extracted items. */
export default function Manual() {
  useDocTitle("Add a task");
  const { pid = "" } = useParams();
  const nav = useNavigate();
  const [f, setF] = useState({ type: "appointment", title: "", due_date: "", doctor_name: "", specialty: "", instruction: "", name: "", dose: "", route: "", timing: "", duration: "", special: "" });
  const [err, setErr] = useState(""); const [res, setRes] = useState<Task | null>(null); const [busy, setBusy] = useState(false);
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => setF({ ...f, [k]: e.target.value });
  const med = f.type === "medicine";

  async function submit(e: FormEvent) {
    e.preventDefault(); setErr(""); setBusy(true);
    const body: Record<string, unknown> = { type: f.type, title: f.title };
    if (f.due_date) body.due_date = f.due_date;
    if (f.doctor_name) body.doctor_name = f.doctor_name;
    if (f.specialty) body.specialty = f.specialty;
    if (f.instruction) body.instruction = f.instruction;
    if (med) body.medicine = { name: f.name || f.title, dose: f.dose || null, route: f.route || null, timing: f.timing || null, duration: f.duration || null, special: f.special || null };
    try { setRes(await api<Task>(`/patients/${pid}/tasks`, { method: "POST", json: body })); }
    catch (x) { setErr(x instanceof ApiError ? x.message : "Something went wrong."); } finally { setBusy(false); }
  }

  if (res) return (
    <div className="max-w-xl"><PageTitle icon="manual-entry">{res.status === "Needs Review" ? "Sent for doctor review" : "Task added"}</PageTitle>
      <p className="text-lg">{res.status === "Needs Review" ? "Something in this entry was missing or unclear, so a doctor will check it before it becomes a task." : "It is now on your plan."}</p>
      <div className="mt-5 flex gap-3"><button className="btn btn-primary" onClick={() => nav(`/hub/plan/${pid}`)}>Back to plan</button><button className="btn btn-plain" onClick={() => setRes(null)}>Add another</button></div></div>);

  return (
    <form onSubmit={submit} className="flex max-w-2xl flex-col gap-5">
      <PageTitle icon="manual-entry" sub="Use this when a summary could not be read or an item is wrong. A medicine typed by hand always waits for a doctor to confirm it.">Add a task by hand</PageTitle>
      <Field label="Type"><select className="field" value={f.type} onChange={set("type")}>{Object.entries(TYPE_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></Field>
      <Field label="Title"><input className="field" value={f.title} onChange={set("title")} required maxLength={200} /></Field>
      <Field label="Date"><input className="field" type="date" value={f.due_date} onChange={set("due_date")} /></Field>
      <Field label="Doctor"><input className="field" value={f.doctor_name} onChange={set("doctor_name")} /></Field>
      <Field label="Specialty"><input className="field" value={f.specialty} onChange={set("specialty")} /></Field>
      {med && <fieldset className="tile flex flex-col gap-4 p-4"><legend className="px-2 font-display font-semibold">Medicine</legend>
        <Field label="Medicine name"><input className="field" value={f.name} onChange={set("name")} /></Field>
        <Field label="Dose"><input className="field" value={f.dose} onChange={set("dose")} /></Field>
        <Field label="Route"><input className="field" value={f.route} onChange={set("route")} /></Field>
        <Field label="Timing"><input className="field" value={f.timing} onChange={set("timing")} /></Field>
        <Field label="Duration"><input className="field" value={f.duration} onChange={set("duration")} /></Field>
        <Field label="Special instructions"><input className="field" value={f.special} onChange={set("special")} /></Field></fieldset>}
      <Field label="Instructions"><textarea className="field !min-h-24" value={f.instruction} onChange={set("instruction")} /></Field>
      {err && <ErrorNote>{err}</ErrorNote>}
      <div className="flex gap-3"><button className="btn btn-primary" disabled={busy}>Save</button><Link className="btn btn-plain" to={`/hub/plan/${pid}`}>Cancel</Link></div>
    </form>
  );
}
