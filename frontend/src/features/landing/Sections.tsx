import { useRef, useState } from "react";
import { motion, useReducedMotion, useScroll, useSpring } from "motion/react";
import ScrollReveal from "../../components/motion/ScrollReveal";
import ScrollVelocity from "../../components/motion/ScrollVelocity";
import { Icon, IconTile, LangMark, type IconName } from "../../components/icons/Icon";
import { EntryButtons } from "../../app/layouts";
import { LANGS } from "../../lib/i18n";
import Reveal from "../../components/motion/Reveal";
import LiveDemo from "./LiveDemo";

const h2 = "font-display text-[clamp(1.9rem,3.6vw,3rem)] font-bold text-ink";

export function Finds() {
  const items: [IconName, string, string][] = [
    ["appointment", "Appointments", "Follow up with cardiologist in 2 weeks"],
    ["test", "Tests", "Fasting blood sugar test on Day 7"],
    ["referral", "Referrals", "Refer to physiotherapist"],
    ["medicine", "Medicines", "Tab. Metformin 500 mg twice daily for 30 days"],
    ["care-instruction", "Care instructions", "Change wound dressing every 48 hours"],
    ["date", "Dates", "Review with orthopedic surgeon on 26 Nov 2026"],
    ["warning", "Warning signs", "Seek immediate care if chest pain or breathlessness occurs"],
  ];
  return (
    <section className="container-page py-16 lg:py-24">
      <Reveal className="max-w-3xl"><h2 className={h2}>Seven kinds of instruction, found and filed.</h2>
        <p className="mt-4 text-xl text-ink-soft">Every item is saved with the exact line of the summary it came from.</p></Reveal>
      <ul className="mt-10 grid gap-x-12 md:grid-cols-2">
        {items.map(([ic, name, ex], i) => (
          <Reveal soft as="li" key={name} delay={(i % 2) * 0.08} className="flex items-center gap-5 border-t border-line py-5">
            <IconTile name={ic} size={26} />
            <div><h3 className="font-display text-xl font-bold">{name}</h3><p className="text-base text-ink-soft">{ex}</p></div>
          </Reveal>
        ))}
      </ul>
    </section>
  );
}

export function How() {
  const reduce = useReducedMotion();
  const ref = useRef<HTMLOListElement>(null);
  const { scrollYProgress } = useScroll({ target: ref, offset: ["start 75%", "end 60%"] });
  const grow = useSpring(scrollYProgress, { stiffness: 120, damping: 28 });
  const steps: [IconName, string, string][] = [
    ["upload", "Upload", "Paste the text or add a PDF or text file. Blank, scanned or non-medical input stops here with a clear message and a form to enter tasks by hand."],
    ["discharge-summary", "Extract", "A model reads the summary and returns the seven kinds of item, each with the exact line it came from and a confidence score."],
    ["safety-gate", "Check", "Fixed rules decide what is clear. Anything missing, ambiguous or clinically sensitive is marked Needs Review."],
    ["care-instruction", "Explain", "Care instructions and warnings are rewritten in plain language and translated. Medicines keep a fixed card and are never reworded."],
    ["reminder", "Follow through", "Reminders go to you and, with your consent, to family. A missed task alerts the family member you chose."],
  ];
  return (
    <section id="how" className="bg-ground-deep">
      <div className="container-page py-16 lg:py-24">
        <Reveal className="max-w-3xl"><h2 className={h2}>From a sheet of paper to a plan, in five steps.</h2></Reveal>
        <ol ref={ref} className="relative mt-12 flex max-w-3xl flex-col gap-10">
          <span aria-hidden className="absolute left-[2.1rem] top-6 bottom-6 w-0.5 bg-line" />
          <motion.span aria-hidden className="absolute left-[2.1rem] top-6 bottom-6 w-0.5 origin-top bg-ink"
            style={{ scaleY: reduce ? 1 : grow }} />
          {steps.map(([ic, t, d], i) => (
            <Reveal soft as="li" key={t} className="relative flex gap-6">
              <span className="relative z-10"><IconTile name={ic} size={26} /></span>
              <div className="pt-1"><h3 className="font-display text-2xl font-bold">{i + 1}. {t}</h3><p className="mt-1 text-lg text-ink-soft">{d}</p></div>
            </Reveal>
          ))}
        </ol>
      </div>
    </section>
  );
}

export function Statement() {
  return (
    <section className="container-page py-20 lg:py-28">
      <ScrollReveal baseOpacity={0.12}
        textClassName="font-display text-[clamp(1.8rem,4vw,3.2rem)] font-bold leading-[1.2] text-ink">
        A model reads. Fixed rules decide. A doctor approves.
      </ScrollReveal>
    </section>
  );
}

export function Safety() {
  const flow: [IconName, string][] = [["text", "Item"], ["safety-gate", "Safety gate"], ["needs-review", "Needs Review"], ["doctor", "Doctor"], ["confirmed", "Pending"]];
  const rules = [
    "The gate is a set of fixed rules. It gives the same answer every time and can be explained.",
    "It flags a missing or unclear date, dose, timing or doctor name, a symptom question, a medicine change, stop or clash, extraction confidence under 70%, and text that fits no category.",
    "The system never resolves a flagged item. Only a doctor can close it.",
    "Family members see \"Waiting for doctor review\" and nothing more.",
  ];
  return (
    <section id="safety" className="bg-teal text-ground">
      <div className="container-page grid gap-12 py-16 lg:grid-cols-2 lg:py-24">
        <div>
          <Reveal><h2 className="font-display text-[clamp(1.9rem,3.6vw,3rem)] font-bold leading-tight">When the system is unsure, a person decides.</h2></Reveal>
          <ul className="mt-8 flex flex-col gap-4">
            {rules.map((r, i) => (
              <Reveal soft as="li" key={r} delay={i * 0.06} className="flex gap-4 text-lg">
                <span aria-hidden className="mt-2.5 h-2.5 w-2.5 shrink-0 bg-mint" /><span>{r}</span>
              </Reveal>))}
          </ul>
        </div>
        <Reveal className="flex flex-col justify-center">
          <ol className="grid grid-cols-3 gap-x-3 gap-y-6 sm:grid-cols-5">
            {flow.map(([ic, l], i) => (
              <motion.li key={l} className="flex flex-col items-center gap-2 text-center"
                initial={{ opacity: 0, y: 12 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }}
                transition={{ delay: 0.15 + i * 0.18, duration: 0.6, ease: [0.16, 1, 0.3, 1] }}>
                <IconTile name={ic} size={26} />
                <span className="font-display text-base font-semibold">{l}</span>
              </motion.li>))}
          </ol>
          <p className="mt-8 text-base text-ground/90">Clean items go straight to Pending. Flagged items wait for a doctor, who can confirm them or correct them. A correction is checked by the gate again before it is accepted.</p>
        </Reveal>
      </div>
    </section>
  );
}

export function Demo() {
  return (
    <section id="demo" className="container-page py-16 lg:py-24">
      <Reveal className="mb-10 max-w-3xl"><h2 className={h2}>See it work on a synthetic summary.</h2>
        <p className="mt-4 text-xl text-ink-soft">Lines are marked as they are read. Each becomes a task that keeps its original line one tap away. The Aspirin line has no dose, so it waits for a doctor.</p></Reveal>
      <LiveDemo />
    </section>
  );
}

const SAMPLE: Record<string, string> = {
  en: "See the cardiologist in 2 weeks.",
  ta: "2 வாரங்களில் இதய மருத்துவரை சந்திக்கவும்.",
  hi: "2 सप्ताह में कार्डियोलॉजिस्ट से मिलें।",
  te: "2 వారాల్లో కార్డియాలజిస్ట్‌ను కలవండి.",
  kn: "2 ವಾರಗಳಲ್ಲಿ ಕಾರ್ಡಿಯಾಲಜಿಸ್ಟ್‌ನನ್ನು ಭೇಟಿಯಾಗಿ.",
  ml: "2 ആഴ്ചകൾക്കുള്ളിൽ കാർഡിയോളജിസ്റ്റിനെ കാണുക.",
};

export function Languages() {
  const marquee = LANGS.map((l) => (
    <span key={l.code} className="inline-flex items-center gap-4 pr-12 font-display text-[2.6rem] font-bold text-ink">
      <LangMark code={l.code} size={56} />{l.native}
    </span>));
  return (
    <section id="languages" className="bg-ground-deep py-16 lg:py-24">
      <div className="container-page"><Reveal className="max-w-3xl"><h2 className={h2}>Six languages, one plan.</h2>
        <p className="mt-4 text-xl text-ink-soft">Every task is rewritten in plain language and translated. The numbers in each translation are checked against the original line, and the original stays one tap away.</p></Reveal></div>
      <div className="mt-10 overflow-hidden border-y-2 border-ink bg-ground py-5" aria-hidden="true">
        <ScrollVelocity texts={[marquee]} velocity={55} numCopies={4} className="whitespace-nowrap" />
      </div>
      <div className="container-page mt-10">
        <p className="mb-4 font-display text-lg font-semibold">One task from the sample summary, as the system wrote it:</p>
        <ul className="grid gap-x-12 md:grid-cols-2">
          {LANGS.map((l, i) => (
            <Reveal soft as="li" key={l.code} delay={(i % 2) * 0.06} className="flex items-center gap-4 border-t border-line py-4">
              <LangMark code={l.code} size={44} />
              <div><p lang={l.code} className="text-xl font-semibold">{SAMPLE[l.code]}</p><p className="text-sm text-ink-soft">{l.name}</p></div>
            </Reveal>))}
        </ul>
        <p className="mt-4 text-base text-ink-soft">Machine translated. Telugu, Kannada and Malayalam should be checked by a fluent reader before real use.</p>
      </div>
    </section>
  );
}

type RoleKey = "patient" | "family" | "doctor";
const ROLES: Record<RoleKey, { icon: IconName; name: string; can: string[]; cannot: string[] }> = {
  patient: { icon: "patient", name: "Patient", can: ["Upload a summary and see the full plan", "Tick tasks, pick a language, request a callback", "Choose which family members see what, and take it back at any time"], cannot: ["Edit the extracted medical instructions"] },
  family: { icon: "family", name: "Family member", can: ["Run a family hub and keep each patient plan separate", "Mark tasks done and set reminders, with full consent", "Get missed-task alerts as the hub manager"], cannot: ["Edit instructions or medicines, ever", "See anything a patient has not shared"] },
  doctor: { icon: "doctor", name: "Doctor reviewer", can: ["See only the items assigned to them", "Confirm an item or correct it, one at a time"], cannot: ["Assign themselves to a case", "Bulk approve or auto approve anything"] },
};
const LEVELS = [
  { id: "full", label: "Full plan", shows: ["Cardiologist follow-up, 16 Nov, Pending", "Metformin, fixed medicine card", "Fasting blood sugar test, 9 Nov", "Waiting for doctor review"] },
  { id: "appointments", label: "Appointments only", shows: ["Cardiologist follow-up, 16 Nov, Pending", "Fasting blood sugar test, 9 Nov, Pending"] },
  { id: "reminders", label: "Reminders only", shows: ["Title, due date and status for each task. Nothing else."] },
];

export function Roles() {
  const [role, setRole] = useState<RoleKey>("patient");
  const [level, setLevel] = useState("appointments");
  const r = ROLES[role];
  const lv = LEVELS.find((l) => l.id === level)!;
  return (
    <section id="family" className="container-page py-16 lg:py-24">
      <Reveal className="max-w-3xl"><h2 className={h2}>The patient owns the plan. Everyone else gets what they are given.</h2></Reveal>
      <div className="mt-10 grid gap-8 lg:grid-cols-[18rem_1fr]">
        <div role="tablist" aria-label="Roles" className="grid grid-cols-2 gap-2 lg:flex lg:flex-col">
          {(Object.keys(ROLES) as RoleKey[]).map((k) => (
            <button key={k} role="tab" aria-selected={role === k} onClick={() => setRole(k)}
              className={`flex min-h-14 items-center gap-3 border-2 border-ink px-3 py-2 text-left font-display font-semibold ${role === k ? "bg-teal text-ground" : "bg-tile text-ink"}`} style={{ borderRadius: 4 }}>
              <Icon name={ROLES[k].icon} size={36} />{ROLES[k].name}
            </button>))}
        </div>
        <div role="tabpanel" className="tile p-6">
          <div className="grid gap-6 md:grid-cols-2">
            <div><h3 className="font-display text-xl font-bold">Can</h3>
              <ul className="mt-3 flex flex-col gap-2">{r.can.map((x) => <li key={x} className="flex gap-3"><span aria-hidden className="mt-2.5 h-2 w-2 shrink-0 bg-teal" />{x}</li>)}</ul></div>
            <div><h3 className="font-display text-xl font-bold">Cannot</h3>
              <ul className="mt-3 flex flex-col gap-2">{r.cannot.map((x) => <li key={x} className="flex gap-3"><span aria-hidden className="mt-2.5 h-2 w-2 shrink-0 bg-review" />{x}</li>)}</ul></div>
          </div>
          {role === "family" && (
            <div className="mt-6 border-t border-line pt-5">
              <h3 className="font-display text-xl font-bold">Try an access level</h3>
              <div role="radiogroup" aria-label="Access level" className="mt-3 flex flex-wrap gap-2">
                {LEVELS.map((l) => (
                  <button key={l.id} role="radio" aria-checked={level === l.id} onClick={() => setLevel(l.id)}
                    className={`min-h-12 border-2 border-ink px-4 font-display font-semibold ${level === l.id ? "bg-ink text-ground" : "bg-tile text-ink"}`} style={{ borderRadius: 4 }}>{l.label}</button>))}
              </div>
              <ul className="mt-4 flex flex-col gap-2 bg-ground-deep p-4" aria-live="polite">
                {lv.shows.map((x) => <li key={x} className={x.startsWith("Waiting") ? "text-review font-semibold" : ""}>{x}</li>)}
              </ul>
              <p className="mt-2 text-base text-ink-soft">The server filters the response to this level. Hiding it in the interface is not what protects it.</p>
            </div>)}
        </div>
      </div>
    </section>
  );
}

export function Faq() {
  const qa: [string, string][] = [
    ["Does it give medical advice?", "No. It organizes and explains what the discharge summary already says. It does not diagnose, change a medicine, or recommend treatment."],
    ["Is any of this real patient data?", "No. The prototype runs on synthetic summaries, synthetic providers and synthetic phone numbers only. Please do not enter real patient information."],
    ["What happens when the system is unsure?", "The item is marked Needs Review, locked, and sent to a doctor reviewer with the reason. Nothing is guessed and nothing is resolved automatically."],
    ["Who can see my plan?", "You, and the family members you add, at the level you choose. Every view and action is written to an audit log you can read."],
    ["Are provider suggestions a recommendation?", "No. Providers come from a synthetic dataset and every match is labelled: Suggestion only, not a guarantee of availability or suitability."],
    ["Can I delete my data?", "Yes. A patient can delete the account and its data. The audit trail stays, because it is append only."],
  ];
  return (
    <section id="faq" className="bg-ground-deep">
      <div className="container-page grid gap-10 py-16 lg:grid-cols-[1fr_1.4fr] lg:py-24">
        <Reveal><h2 className={h2}>Questions people ask first.</h2></Reveal>
        <div className="flex flex-col">
          {qa.map(([q, a]) => (
            <details key={q} className="group border-t border-line py-4 last:border-b">
              <summary className="flex min-h-12 cursor-pointer list-none items-center justify-between gap-4 font-display text-xl font-semibold">
                {q}<span aria-hidden className="font-display text-2xl text-teal group-open:hidden">+</span><span aria-hidden className="hidden font-display text-2xl text-teal group-open:inline">&minus;</span>
              </summary>
              <p className="mt-2 text-lg text-ink-soft">{a}</p>
            </details>))}
        </div>
      </div>
    </section>
  );
}

export function CtaBand() {
  return (
    <section className="bg-teal-deep text-ground">
      <div className="container-page flex flex-col items-start gap-6 py-16 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h2 className="font-display text-[clamp(1.9rem,3.6vw,3rem)] font-bold leading-tight">Try it with a synthetic summary.</h2>
          <p className="mt-3 text-xl text-ground/90">Upload a synthetic discharge summary and see the plan it makes.</p>
        </div>
        <div className="flex flex-wrap gap-4">
          <EntryButtons />
        </div>
      </div>
    </section>
  );
}
