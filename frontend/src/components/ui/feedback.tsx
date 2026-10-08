import { useEffect, type ReactNode } from "react";
import { Icon, type IconName } from "../icons/Icon";
import { EmptyArt, ErrorArt } from "../illustrations/Illustrations";

export const ErrorNote = ({ children, action }: { children: ReactNode; action?: ReactNode }) => (
  <div role="alert" className="flex flex-wrap items-center gap-4 border-2 border-[#b3261e] bg-tile p-4 text-[#8c1d18]" style={{ borderRadius: 4 }}>
    <Icon name="error" size={32} /><p className="min-w-0 flex-1 font-semibold [overflow-wrap:anywhere]">{children}</p>{action}
  </div>
);

export const EmptyState = ({ children, action, error = false }: { children: ReactNode; action?: ReactNode; error?: boolean }) => (
  <div className="tile-quiet flex flex-col items-center gap-4 p-8 text-center">
    {error ? <ErrorArt className="max-w-40" /> : <EmptyArt className="max-w-40" />}
    <p className="max-w-[44ch] text-lg text-ink-soft">{children}</p>{action}
  </div>
);

export function useDocTitle(t: string) { useEffect(() => { document.title = `${t} | Follow-up Coordinator`; }, [t]); }

export const PageTitle = ({ icon, children, sub }: { icon: IconName; children: ReactNode; sub?: ReactNode }) => (
  <div className="mb-6 flex min-w-0 items-center gap-4">
    <span className="inline-flex h-14 w-14 shrink-0 items-center justify-center border-2 border-ink bg-tile" style={{ borderRadius: 4 }}><Icon name={icon} size={34} /></span>
    <div className="min-w-0"><h1 className="font-display text-3xl font-bold [overflow-wrap:anywhere]">{children}</h1>{sub && <p className="text-ink-soft [overflow-wrap:anywhere]">{sub}</p>}</div>
  </div>
);
