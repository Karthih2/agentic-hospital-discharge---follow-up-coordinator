import type { ReactNode } from "react";

export type Col<T> = { head: string; cell: (row: T) => ReactNode; className?: string };

/** A table from md up; stacked label/value rows on a phone. Cells wrap, nothing forces the page wider. */
export function DataTable<T>({ cols, rows, rowKey, empty }: { cols: Col<T>[]; rows: T[]; rowKey: (r: T) => string; empty?: ReactNode }) {
  if (!rows.length) return <>{empty}</>;
  return (
    <div className="tile-quiet">
      <table className="hidden w-full table-fixed border-collapse md:table">
        <thead><tr className="border-b-2 border-ink bg-ground-deep text-left">
          {cols.map((c) => <th key={c.head} className={`px-3 py-2 font-display text-sm font-bold ${c.className ?? ""}`}>{c.head}</th>)}
        </tr></thead>
        <tbody>{rows.map((r) => (
          <tr key={rowKey(r)} className="border-b border-line align-top last:border-0">
            {cols.map((c) => <td key={c.head} className={`px-3 py-3 [overflow-wrap:anywhere] ${c.className ?? ""}`}>{c.cell(r)}</td>)}
          </tr>))}</tbody>
      </table>
      <ul className="flex flex-col md:hidden">{rows.map((r) => (
        <li key={rowKey(r)} className="flex flex-col gap-2 border-b border-line p-4 last:border-0">
          {cols.map((c) => (
            <div key={c.head} className="grid grid-cols-[7.5rem_minmax(0,1fr)] gap-3">
              <span className="font-display text-sm font-semibold text-ink-soft">{c.head}</span>
              <span className="min-w-0 [overflow-wrap:anywhere]">{c.cell(r)}</span>
            </div>))}
        </li>))}</ul>
    </div>
  );
}
