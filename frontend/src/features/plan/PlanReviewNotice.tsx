import { useQuery } from "@tanstack/react-query";
import { Icon } from "../../components/icons/Icon";
import { api } from "../../lib/api";
import { fmtDate, type SummaryRow } from "../../lib/types";

/** Shown while the newest discharge summary's plan is still with the doctor. The plan itself stays hidden until the
 * doctor publishes it, so this is the only thing the patient sees about it: who is reviewing it and since when. */
export default function PlanReviewNotice({ pid, enabled }: { pid: string; enabled: boolean }) {
  const list = useQuery({
    queryKey: ["summaries", pid], enabled, retry: false,
    queryFn: () => api<SummaryRow[]>(`/patients/${pid}/summaries`),
    refetchInterval: (q) => (q.state.data?.some((s) => s.plan_status === "draft" || s.plan_status === "generating") ? 20000 : false),
  });
  const waiting = list.data?.filter((s) => s.plan_status === "draft" || s.plan_status === "generating") ?? [];
  if (!waiting.length) return null;
  const s = waiting[0];
  const reading = s.plan_status === "generating";
  return (
    <section className="tile mb-6 flex flex-wrap items-center gap-4 p-5" aria-live="polite" aria-label="Plan in review">
      <span className="inline-flex h-14 w-14 shrink-0 items-center justify-center border-2 border-ink bg-ground-deep" style={{ borderRadius: 4 }}>
        <Icon name={reading ? "processing" : "doctor"} size={34} /></span>
      <div className="min-w-0 flex-1 basis-64">
        <h2 className="font-display text-xl font-bold">{reading ? "Reading your discharge summary" : `Your new plan is with ${s.doctor_name ?? "your doctor"} for review`}</h2>
        <p className="text-base text-ink-soft">{reading
          ? "This takes a minute. Your doctor checks the plan before you see it."
          : `Sent on ${fmtDate(s.uploaded_at.slice(0, 10))}. Your doctor checks every item first. The plan appears here as soon as they publish it, and you get a notification.`}</p>
        {waiting.length > 1 && <p className="text-base text-ink-soft">{waiting.length} summaries are waiting for review.</p>}
      </div>
      <span className="status status-review">In review</span>
    </section>
  );
}
