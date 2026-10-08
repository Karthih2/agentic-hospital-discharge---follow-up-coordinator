import { useEffect, useRef, useState } from "react";
import { useInView, useReducedMotion } from "motion/react";
import { Icon, IconTile } from "../../components/icons/Icon";
import { Skeleton, StatusChip } from "../../components/ui";

type Line = {
  text: string; kind: string; icon: string; title: string; detail?: string;
  review?: string; card?: [string, string][]; mark: string;
};
// Synthetic summary and the plan the real backend produced for it (see backend/sample_data/01 and the live run).
const LINES: Line[] = [
  { text: "Follow up with cardiologist in 2 weeks.", kind: "Appointment", icon: "appointment", title: "Cardiologist follow-up", detail: "Due 16 Nov 2026", mark: "#0e7c7b" },
  { text: "Tab. Metformin 500 mg twice daily for 30 days after food.", kind: "Medicine", icon: "medicine", title: "Metformin", mark: "#0e7c7b",
    card: [["Medicine name", "Metformin"], ["Dose", "500 mg"], ["Route", "By mouth"], ["Timing", "Twice daily"], ["Duration", "30 days"], ["Special instructions", "After food"]] },
  { text: "Fasting blood sugar test on Day 7.", kind: "Test", icon: "test", title: "Fasting blood sugar test", detail: "Due 9 Nov 2026", mark: "#0e7c7b" },
  { text: "Change wound dressing every 48 hours.", kind: "Care instruction", icon: "care-instruction", title: "Change wound dressing", detail: "Every 48 hours", mark: "#0e7c7b" },
  { text: "Seek immediate care if chest pain or breathlessness occurs.", kind: "Warning sign", icon: "warning", title: "Warning signs", detail: "Seek immediate care if chest pain or breathlessness occurs.", mark: "#0e7c7b" },
  { text: "Tab. Aspirin once daily. Continue as advised.", kind: "Medicine", icon: "medicine", title: "Aspirin", mark: "#a8530c", review: "Dose is not mentioned. Duration is not mentioned. Date or duration is unclear." },
];

export default function LiveDemo() {
  const reduce = useReducedMotion();
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true, margin: "-15% 0px" });
  const [step, setStep] = useState(reduce ? LINES.length : -1); // -1: loading skeleton, n: n lines processed
  const [run, setRun] = useState(0);
  const [open, setOpen] = useState<number | null>(null);

  useEffect(() => {
    if (!inView || reduce) return;
    setStep(-1);
    const timers: number[] = [window.setTimeout(() => setStep(0), 900)];
    LINES.forEach((_, i) => timers.push(window.setTimeout(() => setStep(i + 1), 1500 + i * 950)));
    return () => timers.forEach(clearTimeout);
  }, [inView, run, reduce]);

  const active = step > 0 && step <= LINES.length ? step - 1 : -1;

  return (
    <div ref={ref} className="grid items-start gap-6 lg:grid-cols-2" aria-live="polite">
      <div className="tile flex flex-col lg:sticky lg:top-24">
        <div className="flex items-center gap-3 border-b-2 border-ink px-5 py-3">
          <Icon name="discharge-summary" size={32} />
          <h3 className="font-display text-lg font-bold">Discharge summary</h3>
          <span className="ml-auto text-sm text-ink-soft">Synthetic</span>
        </div>
        <ol className="flex flex-col gap-2 p-5 text-lg leading-snug">
          {LINES.map((l, i) => {
            const marked = step > i;
            return (
              <li key={l.text} className="px-2 py-1.5 transition-colors duration-700"
                style={{ background: marked ? `color-mix(in oklab, ${l.mark} 16%, transparent)` : "transparent",
                  boxShadow: marked ? `inset 0 -3px 0 ${l.mark}` : "none", borderRadius: 2 }}>
                {l.text}
              </li>
            );
          })}
        </ol>
      </div>

      <div className="tile-quiet flex flex-col">
        <div className="flex items-center gap-3 border-b border-line px-5 py-3">
          <Icon name="follow-up-plan" size={30} />
          <h3 className="font-display text-lg font-bold">Follow-up plan</h3>
          <button className="btn btn-plain ml-auto !min-h-10 !py-1 !text-base" onClick={() => { setOpen(null); setRun((r) => r + 1); if (reduce) setStep(LINES.length); }}>
            Replay
          </button>
        </div>
        <ul className="flex flex-col gap-3 p-5">
          {step < 1 && !reduce
            ? [0, 1, 2].map((i) => (
                <li key={i} className="flex items-center gap-4 p-3">
                  <Skeleton className="h-14 w-14" />
                  <div className="flex flex-1 flex-col gap-2"><Skeleton className="h-4 w-2/3" /><Skeleton className="h-3 w-1/3" /></div>
                </li>))
            : LINES.slice(0, Math.max(step, 0)).map((l, i) => {
                const review = !!l.review;
                return (
                  <li key={l.title} className={`flex flex-col gap-3 p-3 ${review ? "border-2 border-dashed border-review bg-ground-deep" : "tile"}`}
                    style={{ borderRadius: 4, animation: i === active && !reduce ? "rise 0.7s cubic-bezier(0.16,1,0.3,1)" : undefined }}>
                    <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
                      <IconTile name={(review ? "locked" : l.icon) as never} size={24} />
                      <div className="min-w-0 flex-1 basis-40">
                        <p className="font-display text-lg font-semibold leading-tight">{review ? "Waiting for doctor review" : l.title}</p>
                        <p className="text-base text-ink-soft">{review ? l.review : l.detail ?? l.kind}</p>
                      </div>
                      <StatusChip status={review ? "Needs Review" : "Pending"} />
                    </div>
                    {l.card && (
                      <dl className="grid grid-cols-[auto_1fr] gap-x-5 gap-y-1 border-t border-line pt-3 text-base">
                        {l.card.map(([k, v]) => (<div key={k} className="contents"><dt className="text-ink-soft">{k}</dt><dd className="font-semibold">{v}</dd></div>))}
                      </dl>
                    )}
                    {!review && (
                      <div>
                        <button className="text-base font-semibold text-teal underline" aria-expanded={open === i} onClick={() => setOpen(open === i ? null : i)}>
                          {open === i ? "Hide original" : "Show original"}
                        </button>
                        {open === i && <p className="mt-2 border-t border-line pt-2 text-base italic">{l.text}</p>}
                      </div>
                    )}
                  </li>
                );
              })}
        </ul>
      </div>
    </div>
  );
}
