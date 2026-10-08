import type { ReactNode } from "react";

export function Field({ label, children, hint }: { label: string; children: ReactNode; hint?: string }) {
  return (
    <label className="flex min-w-0 flex-col gap-1.5">
      <span className="font-display font-semibold">{label}</span>
      {children}
      {hint && <span className="text-sm text-ink-soft">{hint}</span>}
    </label>
  );
}

export function Tabs<T extends string>({ tabs, value, onChange, label }: { tabs: { id: T; label: string }[]; value: T; onChange: (t: T) => void; label: string }) {
  return (
    <div role="tablist" aria-label={label} className="flex flex-wrap gap-2">
      {tabs.map((t) => (
        <button key={t.id} role="tab" aria-selected={value === t.id} onClick={() => onChange(t.id)}
          className={`min-h-12 border-2 border-ink px-5 font-display font-semibold ${value === t.id ? "bg-teal text-ground" : "bg-tile text-ink"}`} style={{ borderRadius: 4 }}>
          {t.label}
        </button>))}
    </div>
  );
}
