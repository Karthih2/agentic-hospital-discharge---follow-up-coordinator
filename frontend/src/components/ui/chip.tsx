import type { ReactNode } from "react";
import DrawCheck from "../motion/DrawCheck";
import type { Status } from "../../lib/types";

/** Status is a colour AND a word, never colour alone. A done task draws its check. */
export const StatusChip = ({ status }: { status: Status }) => (
  <span className={`status ${status === "Pending" ? "status-pending" : status === "Completed" ? "status-done" : "status-review"}`}>
    {status === "Completed" && <DrawCheck size={14} />}{status}
  </span>
);

/** Plain outlined label: a type, a role, an access level. */
export const Chip = ({ children, tone = "plain" }: { children: ReactNode; tone?: "plain" | "teal" | "ink" }) => (
  <span className={`inline-flex max-w-full items-center border-2 border-ink px-2 py-0.5 font-display text-sm font-semibold [overflow-wrap:anywhere] ${
    tone === "teal" ? "bg-teal text-ground" : tone === "ink" ? "bg-ink text-ground" : "bg-tile text-ink"}`} style={{ borderRadius: 4 }}>
    {children}
  </span>
);
