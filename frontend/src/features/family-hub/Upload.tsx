import { useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Icon } from "../../components/icons/Icon";
import { EmptyState, ErrorNote, Field, ListSkeleton, PageTitle, Tabs, useDocTitle } from "../../components/ui";
import { api, errText } from "../../lib/api";
import { fmtDate, type SummaryRow } from "../../lib/types";

const STEPS = ["Reading", "Extracting", "Checking", "Building plan", "Simplifying"];

function Progress({ step }: { step: number }) {
  return (
    <div className="tile p-5" aria-live="polite"><p className="mb-3 font-display text-lg font-semibold">Working on the summary</p>
      <ol className="flex flex-col gap-2">{STEPS.map((s, i) => (
        <li key={s} className={`flex items-center gap-3 ${i <= step ? "text-ink" : "text-ink-soft"}`}>
          <span className={`h-4 w-4 border-2 border-ink ${i < step ? "bg-done" : i === step ? "bg-pending" : "bg-tile"}`} style={{ borderRadius: 2 }} />{s}</li>))}</ol></div>
  );
}

/** Upload by paste or file for one patient. Only the patient, or a manager with full consent, reaches this. */
export function Upload() {
  useDocTitle("Upload summary");
  const { pid = "" } = useParams();
  const nav = useNavigate();
  const [tab, setTab] = useState<"paste" | "file">("paste");
  const [text, setText] = useState(""); const [file, setFile] = useState<File | null>(null); const [drag, setDrag] = useState(false);
  const [err, setErr] = useState<{ msg: string; manual: boolean } | null>(null); const [step, setStep] = useState(-1);
  const input = useRef<HTMLInputElement>(null);
  const summaries = useQuery({ queryKey: ["summaries", pid], queryFn: () => api<SummaryRow[]>(`/patients/${pid}/summaries`), retry: false });

  async function analyse() {
    setErr(null);
    const fd = new FormData();
    if (tab === "paste") fd.set("text", text); else if (file) fd.set("file", file);
    if (tab === "paste" ? !text.trim() : !file) return setErr({ msg: tab === "paste" ? "Paste the discharge summary text first." : "Choose a PDF or text file first.", manual: false });
    try {
      setStep(0);
      const r = await api<{ id: string; status: string; message?: string }>(`/patients/${pid}/summaries`, { method: "POST", body: fd });
      if (r.status === "needs_manual") { setStep(-1); return setErr({ msg: r.message ?? "This could not be read.", manual: true }); }
      for (let i = 0; i < 90; i++) {
        const st = await api<{ status: string; message?: string; steps: unknown[] }>(`/summaries/${r.id}/status`);
        setStep(Math.min(st.steps.length, STEPS.length - 1));
        if (st.status === "ready") return nav(`/hub/plan/${pid}?summary=${r.id}`);
        if (st.status === "needs_manual" || st.status === "failed") { setStep(-1); return setErr({ msg: st.message ?? "The summary could not be read automatically. You can enter the tasks by hand.", manual: true }); }
        await new Promise((res) => setTimeout(res, 2000));
      }
      setStep(-1); setErr({ msg: "This is taking longer than expected. Check back in a minute.", manual: false });
    } catch (x) { setStep(-1); setErr({ msg: errText(x), manual: false }); }
  }

  return (
    <div>
      <PageTitle icon="upload">Add a discharge summary</PageTitle>
      <section className="tile flex flex-col gap-4 p-5" aria-labelledby="up-h">
        <h2 id="up-h" className="sr-only">Upload</h2>
        <Tabs label="Input" tabs={[{ id: "paste", label: "Paste Text" }, { id: "file", label: "Upload PDF" }]} value={tab} onChange={setTab} />
        {tab === "paste" ? (
          <Field label="Discharge summary text" hint="Synthetic text only. Do not enter real patient information."><textarea className="field" value={text} onChange={(e) => setText(e.target.value)} /></Field>
        ) : (
          <div onDragOver={(e) => { e.preventDefault(); setDrag(true); }} onDragLeave={() => setDrag(false)} onDrop={(e) => { e.preventDefault(); setDrag(false); setFile(e.dataTransfer.files[0] ?? null); }}
            className={`flex min-h-48 flex-col items-center justify-center gap-3 border-2 border-dashed border-ink p-6 text-center ${drag ? "bg-ground-deep" : "bg-tile"}`} style={{ borderRadius: 4 }}>
            <Icon name="pdf" size={48} /><p className="font-display text-lg font-semibold">{file ? file.name : "Drag a PDF or text file here"}</p>
            <button type="button" className="btn btn-plain" onClick={() => input.current?.click()}>Browse</button>
            <input ref={input} type="file" accept=".pdf,.txt,text/plain,application/pdf" className="sr-only" onChange={(e) => setFile(e.target.files?.[0] ?? null)} aria-label="Choose file" />
          </div>)}
        {err && <ErrorNote action={err.manual ? <Link className="btn btn-plain" to={`/hub/manual/${pid}`}>Enter manually</Link> : undefined}>{err.msg}</ErrorNote>}
        {step >= 0 ? <Progress step={step} /> : <button className="btn btn-primary self-start" onClick={analyse}>Analyse</button>}
      </section>
      <section className="mt-10" aria-labelledby="prev-h">
        <h2 id="prev-h" className="font-display text-2xl font-bold">Previous summaries</h2>
        <div className="mt-4">{summaries.isLoading ? <ListSkeleton /> : summaries.error ? <ErrorNote>Could not load the summaries.</ErrorNote> : !summaries.data?.length ? <EmptyState>Nothing uploaded yet.</EmptyState>
          : <ul className="flex flex-col gap-3">{summaries.data.map((s) => (
            <li key={s.id}><Link to={`/hub/plan/${pid}?summary=${s.id}`} className="tile flex flex-wrap items-center gap-4 p-4 text-ink no-underline"><Icon name="discharge-summary" size={34} />
              <div className="min-w-0 flex-1"><p className="font-display text-lg font-semibold">{fmtDate(s.uploaded_at.slice(0, 10))}</p>
                <p className="text-base text-ink-soft">{s.status === "ready" ? `${s.counts.Pending} Pending, ${s.counts["Needs Review"]} Needs Review, ${s.counts.Completed} Completed` : s.status.replace("_", " ")}</p></div>
              <span className="font-display font-semibold text-teal underline">Open plan</span></Link></li>))}</ul>}</div>
      </section>
    </div>
  );
}
