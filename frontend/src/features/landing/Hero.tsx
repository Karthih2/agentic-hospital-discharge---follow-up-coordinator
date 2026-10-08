import { motion, useReducedMotion } from "motion/react";
import SplitText from "../../components/motion/SplitText";
import BlurText from "../../components/motion/BlurText";
import { Icon } from "../../components/icons/Icon";
import { EntryButtons } from "../../app/layouts";
import { useI18n } from "../../lib/i18n";

type Row = { when: string; what: string; state: "done" | "pending" | "review" | "later" };
// Synthetic plan, taken from the sample cardiac summary in backend/sample_data.
const ROWS: Row[] = [
  { when: "5 Nov", what: "Discharged from hospital", state: "done" },
  { when: "5 Nov", what: "Start Atorvastatin and Aspirin", state: "done" },
  { when: "7 Nov", what: "Change chest dressing", state: "pending" },
  { when: "15 Nov", what: "Lipid profile blood test", state: "pending" },
  { when: "19 Nov", what: "Cardiologist follow-up", state: "pending" },
  { when: "Awaiting", what: "Aspirin dose unclear", state: "review" },
];
const DOT: Record<Row["state"], string> = { done: "bg-done", pending: "bg-pending", review: "bg-review", later: "bg-line" };

function PlanPreview() {
  const reduce = useReducedMotion();
  return (
    <div className="tile p-5 sm:p-6" role="group" aria-label="Example follow-up plan, synthetic data">
      <div className="flex items-center gap-4 border-b border-line pb-4">
        <Icon name="patient" size={32} />
        <div>
          <p className="font-display text-xl font-bold leading-tight">Synthetic patient, follow-up plan</p>
          <p className="text-base text-ink-soft">Synthetic patient. Cardiac discharge.</p>
        </div>
      </div>
      <ol className="relative mt-5 flex flex-col gap-4">
        <span aria-hidden className="absolute left-[0.7rem] top-2 bottom-2 w-0.5 bg-line" />
        {ROWS.map((r, i) => (
          <motion.li key={r.what} className="relative flex items-start gap-4"
            initial={reduce ? false : { opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.9 + i * 0.12, duration: 0.6, ease: [0.16, 1, 0.3, 1] }}>
            <span className={`relative z-10 mt-1.5 h-[1.4rem] w-[1.4rem] shrink-0 border-2 border-ink ${DOT[r.state]}`} style={{ borderRadius: 4 }} />
            <div className="flex flex-1 flex-wrap items-baseline justify-between gap-x-3">
              <span className="font-display font-semibold">{r.what}</span>
              <span className="text-base text-ink-soft">{r.when}</span>
            </div>
          </motion.li>
        ))}
      </ol>
      <div className="mt-5 flex flex-wrap gap-x-5 gap-y-2 border-t border-line pt-4 text-base">
        <span className="inline-flex items-center gap-2"><span className="h-3 w-3 bg-done" />Completed</span>
        <span className="inline-flex items-center gap-2"><span className="h-3 w-3 bg-pending" />Pending</span>
        <span className="inline-flex items-center gap-2"><span className="h-3 w-3 bg-review" />Needs review</span>
      </div>
    </div>
  );
}

export default function Hero() {
  const { s, lang } = useI18n();
  return (
    <section className="container-page grid items-center gap-10 py-14 lg:grid-cols-[1.1fr_0.9fr] lg:gap-16 lg:py-20">
      <div className="flex min-w-0 flex-col gap-7">
        <SplitText key={`t-${lang}`} text={s("heroTitle")} tag="h1" splitType="words" delay={70} duration={0.9}
          ease="power3.out" from={{ opacity: 0, y: 28 }} to={{ opacity: 1, y: 0 }} textAlign="left" threshold={0}
          className="font-display text-[clamp(2.4rem,5.2vw,4.4rem)] font-bold leading-[1.05] text-ink" />
        <BlurText key={`s-${lang}`} text={s("heroSub")} animateBy="words" delay={25} direction="bottom"
          className="max-w-[60ch] text-xl leading-relaxed text-ink-soft" />
        <EntryButtons />
        <p className="flex items-center gap-3 text-base text-ink-soft">
          <Icon name="consent" size={30} />
          Prototype for the Acentra Hackathon. Synthetic data only.
        </p>
      </div>
      <PlanPreview />
    </section>
  );
}
