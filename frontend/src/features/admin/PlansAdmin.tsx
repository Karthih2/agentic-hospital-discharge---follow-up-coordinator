import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { DataTable, EmptyState, ErrorNote, ListSkeleton, PageTitle, StatusChip, Tabs, useDocTitle } from "../../components/ui";
import { api, errText } from "../../lib/api";
import { fmtDate } from "../../lib/types";

type Row = {
  id: string; patient_code: string | null; plan_status: "draft" | "published"; doctor_id: string | null; doctor: string | null;
  uploaded_at: string; published_at: string | null; age_hours: number; items: number; flagged: number;
};
type Doc = { doctor_id: string; name: string; specialty: string; available: boolean };

/** Who reviews which plan. Patient code and counts only: the desk never sees clinical text. */
export function AdminPlans() {
  useDocTitle("Plans");
  const qc = useQueryClient();
  const [tab, setTab] = useState<"draft" | "published">("draft");
  const q = useQuery({ queryKey: ["a-plans", tab], queryFn: () => api<Row[]>(`/admin-api/plans?status=${tab}`) });
  const docs = useQuery({ queryKey: ["a-docs"], queryFn: () => api<Doc[]>("/admin-api/doctors") });
  const act = useMutation({
    mutationFn: (a: { id: string; doctor_id: string }) => api(`/admin-api/plans/${a.id}/assign`, { method: "POST", json: { doctor_id: a.doctor_id } }),
    onSuccess: () => void qc.invalidateQueries(),
  });
  return (
    <div>
      <PageTitle icon="follow-up-plan" sub="Every plan waits for its matched doctor before the patient sees it. Move a draft only when that doctor cannot review it.">Plan routing</PageTitle>
      <Tabs label="Plans" value={tab} onChange={setTab} tabs={[{ id: "draft", label: "Waiting for a doctor" }, { id: "published", label: "Published" }]} />
      {act.error && <div className="mt-4"><ErrorNote>{errText(act.error)}</ErrorNote></div>}
      <div className="mt-6">{q.isLoading ? <ListSkeleton /> : q.error ? <ErrorNote>Could not load the plans.</ErrorNote> :
        <DataTable rows={q.data ?? []} rowKey={(r) => r.id} empty={<EmptyState>Nothing here.</EmptyState>}
          cols={[
            { head: "Patient", cell: (r) => <><b>{r.patient_code ?? "Patient"}</b><br /><span className="text-ink-soft">Received {fmtDate(r.uploaded_at.slice(0, 10))}</span></> },
            { head: "Items", cell: (r) => <span className="inline-flex flex-wrap items-center gap-2">{r.items}{r.flagged > 0 && <><StatusChip status="Needs Review" />{r.flagged}</>}</span> },
            { head: tab === "draft" ? "Waiting" : "Published", cell: (r) => tab === "draft" ? `${r.age_hours} h` : fmtDate(r.published_at?.slice(0, 10)) },
            { head: "Doctor", cell: (r) => r.plan_status === "published" ? (r.doctor ?? "Unknown") : (
              <select aria-label="Reviewing doctor" className="field" value={r.doctor_id ?? ""} disabled={act.isPending}
                onChange={(e) => e.target.value && e.target.value !== r.doctor_id && act.mutate({ id: r.id, doctor_id: e.target.value })}>
                <option value="">No doctor yet</option>
                {docs.data?.map((d) => <option key={d.doctor_id} value={d.doctor_id}>{d.name}, {d.specialty}{d.available ? "" : " (unavailable)"}</option>)}
              </select>) },
          ]} />}</div>
    </div>
  );
}
