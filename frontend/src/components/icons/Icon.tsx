import {
  Alarm, Article, Baby, Bell, BellRinging, Buildings, CalendarBlank, CalendarCheck, CaretLeft, CaretRight, ChartBar,
  Check, CheckCircle, ClipboardText, Clock, ClockCountdown, Database, Eye, FileText, FilePdf, FirstAid, FolderOpen,
  Gear, Handshake, Heartbeat, Hospital, House, Hourglass, IdentificationCard, List, ListChecks, Lock, MapPin,
  PencilSimple, PhoneCall, Pill, Plus, Scroll, ShieldCheck, ShieldWarning, SignOut, SpeakerHigh, Stethoscope,
  TestTube, Translate, Trash, UploadSimple, User, Users, UsersThree, WarningCircle, WarningOctagon, X,
  type Icon as PhosphorIcon,
} from "@phosphor-icons/react";

/** The one place that knows which icon library is in use. Screens ask for a meaning, never for a library glyph. */
const MAP = {
  appointment: CalendarCheck, calendar: CalendarBlank, date: CalendarBlank, test: TestTube, referral: Handshake,
  medicine: Pill, "care-instruction": Heartbeat, warning: WarningOctagon, reminder: Alarm, notification: Bell,
  "notification-new": BellRinging, callback: PhoneCall, locked: Lock, "needs-review": Hourglass, success: CheckCircle,
  confirmed: Check, processing: Gear, upload: UploadSimple, view: Eye, text: Article, pdf: FilePdf,
  "discharge-summary": FileText, "safety-gate": ShieldCheck, doctor: Stethoscope, patient: User, family: UsersThree,
  "family-member": Users, admin: ShieldWarning, hospital: Hospital, "follow-up-plan": ClipboardText,
  consent: IdentificationCard, "manual-entry": PencilSimple, "missed-task": ClockCountdown, location: MapPin,
  error: WarningCircle, language: Translate, logout: SignOut, menu: List, close: X, plus: Plus, next: CaretRight,
  previous: CaretLeft, home: House, system: Database, overview: ChartBar, routing: ListChecks, hubs: Buildings,
  audit: Scroll, listen: SpeakerHigh, delete: Trash, clock: Clock, child: Baby, folder: FolderOpen, first_aid: FirstAid,
} satisfies Record<string, PhosphorIcon>;

export type IconName = keyof typeof MAP;

/** Duotone: 2px-style navy outline, mint fill (see .duo in index.css). Decorative unless a label is given. */
export function Icon({ name, size = 28, label, className = "" }: { name: IconName; size?: number; label?: string; className?: string }) {
  const C = MAP[name] ?? WarningCircle;
  return (
    <span className={`duo inline-flex shrink-0 text-ink ${className}`} role={label ? "img" : undefined}
      aria-label={label} aria-hidden={label ? undefined : true}>
      <C size={size} weight="duotone" />
    </span>
  );
}

/** Icon on its own flat tile, like a sticker. */
export function IconTile({ name, size = 28, label, tone = "tile" }: { name: IconName; size?: number; label?: string; tone?: "tile" | "deep" }) {
  const pad = Math.round(size * 0.3);
  return (
    <span className={`inline-flex shrink-0 items-center justify-center border-2 border-ink ${tone === "deep" ? "bg-ground-deep" : "bg-tile"}`}
      style={{ width: size + pad * 2 + 4, height: size + pad * 2 + 4, borderRadius: 4 }}>
      <Icon name={name} size={size} label={label} />
    </span>
  );
}

const SCRIPT: Record<string, string> = { en: "A", ta: "அ", hi: "अ", te: "అ", kn: "ಅ", ml: "അ" };
/** Language mark: the first letter of its own script on a tile. Replaces the old flag pictures. */
export function LangMark({ code, size = 40 }: { code: string; size?: number }) {
  return (
    <span aria-hidden className="inline-flex shrink-0 items-center justify-center border-2 border-ink bg-mint font-display font-bold text-ink"
      style={{ width: size, height: size, borderRadius: 4, fontSize: size * 0.55, lineHeight: 1 }} lang={code}>{SCRIPT[code] ?? "A"}</span>
  );
}
