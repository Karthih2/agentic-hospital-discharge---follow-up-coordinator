export type Status = "Pending" | "Completed" | "Needs Review";
export type Level = "full" | "appointments" | "reminders";

export type Provider = {
  id: string; name: string; specialty: string; facility?: string; type: "hospital" | "clinic";
  lat: number; lng: number; contact?: string; distance_km?: number; label: string;
  languages?: string[]; facility_type?: string | null;
};

export type Appointment = { time: string | null; location: string | null; phone: string | null; doctor_name: string | null };

export type Task = {
  id: string;
  status: Status;
  locked?: boolean;
  message?: string | null;
  type?: string;
  title?: string;
  due_date?: string | null;
  due_date_text?: string | null;
  display_text?: string | null;
  medicine_card?: { rows: { key: string; label: string; value: string | null }[] } | null;
  appointment?: Appointment | null;
  source_line?: string;
  source_span?: { start: number; end: number } | null;
  flags?: { field: string; reason_code: string; note: string }[];
  reason?: string | null;
  provider_needed?: boolean;
  specialty?: string | null;
  provider?: Provider | null;
  provider_label?: string | null;
  reminder_enabled?: boolean;
  callback_completed?: boolean;
  can_listen?: boolean;
  doctor_edited?: boolean;
};

export type SummaryRow = {
  id: string; uploaded_at: string; status: string; error_code: string | null;
  counts: Record<Status, number>;
  /** draft until the matched doctor reviews and publishes the plan */
  plan_status?: "generating" | "draft" | "published" | null; doctor_name?: string | null; published_at?: string | null;
};

export type SummaryView = {
  id: string; raw_text: string; discharge_date: string | null;
  header: { admission_date?: string | null; attending_physician?: string | null; pcp?: string | null; disposition?: string | null };
  diagnoses: { admission?: string | null; discharge?: string | null; secondary?: string | null } | null;
  highlights: { task_id: string; type: string; status: string; start: number; end: number; color: string }[];
};

export type HubPatient = {
  patient_id: string; name: string; language: string; patient_code: string | null; is_child: boolean;
  access: "self" | Level | "none"; operate: boolean;
  counts: Record<Status, number> | null; next_due: string | null;
};
export type Hub = {
  id: string; name: string; manager_id: string; manager_name: string | null; my_roles: string[]; is_manager: boolean;
  members: { user_id: string; name: string; roles: string[] }[]; patients: HubPatient[]; pending_invites: number | null;
};

export const TYPE_LABEL: Record<string, string> = {
  appointment: "Appointment", test: "Test", referral: "Referral", medicine: "Medicine",
  care_instruction: "Care instruction", date: "Date", warning_sign: "Warning",
};
export const TYPE_ICON: Record<string, string> = {
  appointment: "appointment", test: "test", referral: "referral", medicine: "medicine",
  care_instruction: "care-instruction", date: "date", warning_sign: "warning",
};
export const LEVEL_LABEL: Record<string, string> = {
  self: "Your own plan", full: "Full plan", appointments: "Appointments only", reminders: "Reminders only", none: "No access yet",
};

export const fmtDate = (iso?: string | null) =>
  iso ? new Date(iso + (iso.length === 10 ? "T00:00:00" : "")).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" }) : "";
