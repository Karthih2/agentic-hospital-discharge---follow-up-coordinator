// Same-origin calls to the FastAPI backend. Auth is httpOnly cookies; state-changing calls send the CSRF header.
export class ApiError extends Error {
  status: number;
  body?: unknown;
  constructor(status: number, message: string, body?: unknown) { super(message); this.status = status; this.body = body; }
}

function csrf(): string {
  const m = document.cookie.match(/(?:^|; )csrf_token=([^;]+)/);
  return m ? decodeURIComponent(m[1]) : "";
}

export async function api<T>(path: string, init: RequestInit & { json?: unknown } = {}): Promise<T> {
  const headers = new Headers(init.headers);
  let body = init.body;
  if (init.json !== undefined) { headers.set("Content-Type", "application/json"); body = JSON.stringify(init.json); }
  if ((init.method ?? "GET") !== "GET") headers.set("X-CSRF-Token", csrf());
  let res: Response;
  try {
    res = await fetch(path, { ...init, headers, body, credentials: "same-origin" });
  } catch {
    throw new ApiError(0, "Cannot reach the server. Check your connection and try again.");
  }
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    const d = (data as { detail?: unknown } | null)?.detail;
    throw new ApiError(res.status, typeof d === "string" ? d : "Something went wrong. Please try again.", data);
  }
  return data as T;
}

export type Role = "patient" | "family" | "doctor" | "admin";
export type Me = { id: string; name: string; role: Role; language: string; patient_code?: string; hubs?: string[] };

/** The words a person should read for a failed call, keeping the server's own message when it has one. */
export const errText = (x: unknown, fallback = "Something went wrong. Please try again.") =>
  x instanceof ApiError ? x.message : fallback;
