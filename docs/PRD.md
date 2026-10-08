# Agentic Hospital Discharge & Follow-up Coordinator — PRD

## 1. Product Overview

A patient uploads a synthetic discharge summary and receives a trackable follow-up plan with tasks, dates, reminders, and a timeline — explained in simple language and their chosen language. The system organizes and explains. It never diagnoses, changes medicines, or recommends treatment.

**Contest:** Acentra Hackathon — Agentic Hospital Discharge & Follow-up Coordinator

**Core constraint:** The system may organize and explain discharge instructions, but must not diagnose a condition, change medication, recommend treatment, or present a synthetic provider match as a guarantee.

**Target users:** Patients (primary), elderly patients (via family-managed accounts), family members (view + notifications), doctor reviewers, management.

**Languages:** English, Tamil, Hindi (demo-polished). Telugu, Kannada, Malayalam (stretch goals).

**Data:** Synthetic only, everywhere. No real patient, provider, or clinical data.

## 2. Roles & Permissions

| Role | Access | Cannot Do |
| --- | --- | --- |
| **Patient** | Full control — upload summary, view plan, tick tasks, pick language, manage family access | Edit extracted medical instructions |
| **Family Member** | View plan (what patient allows), receive notifications, trigger callback on missed tasks | Edit instructions, resolve Needs Review |
| **Doctor Reviewer** | Resolve Needs Review items, confirm or correct wording | Self-assign; management assigns them |
| **Management** | Assign reviewers, monitor queue, handle fallback routing | Change clinical content |

**Elderly patient mode:** Patient account is primary but a family member operates it on their behalf. The patient owns the account; the family member is granted full operational access by the patient at setup.

**Family access rules:**

- Patient controls who sees what: full plan, appointments only, or reminders only
- Family members cannot edit instructions under any circumstance
- Needs Review items show as "Waiting for doctor review" to family
- If a task is missed, the system auto-notifies the designated family member
- Every view and action is logged

## 3. Core User Flow

1. **Sign in** — User picks a language and role. Family members are added by the patient with defined access levels.
2. **Upload summary** — Patient pastes or uploads a synthetic discharge summary. If input is blank, unstructured, or non-medical, the system shows a clear error and prompts manual entry.
3. **Extract** — System pulls 7 item types: appointments, tests, referrals, medicines, care instructions, dates, warning signs. Each item is saved with its exact source line as evidence.
4. **Safety gate** — Every extracted item is checked. Unclear, missing, or sensitive items → Needs Review. Clean items → Pending. See Section 5 for gate logic.
5. **Build plan** — Each item becomes a task with a date, status, reminder, and position on the timeline.
6. **Explain simply** — Care instructions and warnings are rewritten in plain language, then translated. The original source line stays visible beside every rewrite. Medicine lines use a fixed template only — never freely reworded.
7. **Suggest providers** — Referrals and follow-ups are matched to synthetic providers by specialty and live location (GPS) or manually selected city.
8. **Doctor review** — Needs Review items land in the doctor's queue with a visible reason. Doctor confirms or corrects. If unavailable, the item routes to the next assigned reviewer.
9. **Follow through** — Reminders go to the patient and, with consent, to family members. Tasks are ticked off and the timeline updates.
10. **Output** — Patient sees a timeline, checklist, reminders, and the evidence behind each item.

**Failure handling:** If extraction fails partially, the system flags the unread fields and prompts the user to fill them manually. The system never silently fails or auto-resolves ambiguous content.

## 4. Extraction & Evidence

**7 item types extracted:**

| Type | Example |
| --- | --- |
| Appointments | "Follow up with cardiologist in 2 weeks" |
| Tests | "Fasting blood sugar test on Day 7" |
| Referrals | "Refer to physiotherapist" |
| Medicines | "Tab. Metformin 500mg twice daily for 30 days" |
| Care instructions | "Change wound dressing every 48 hours" |
| Dates | "Return to ER if fever exceeds 38.5°C before Day 5" |
| Warning signs | "Seek immediate care if chest pain, breathlessness, or swelling occurs" |

Every extracted item is stored with its **exact source line** from the discharge summary. This is the evidence field — always visible to the user.

**UI — two views (toggleable):**

- **Card view (default):** One task at a time, large text, chosen language. Tap "Show original" to see source line. Default for patients and elderly users.
- **Two-panel view:** Left panel shows the original summary with extracted lines highlighted by color (appointments = blue, medicines = yellow, warnings = red). Right panel shows the generated tasks. Default for family members verifying extraction.

**Manual entry fallback:** If extraction fails or the user spots an error, they can manually add or correct a task using a structured form (type, date, doctor, medicine fields). Manual entries are also subject to the safety gate.

**Medicine card template (fixed — no free rewrite):**

```
Medicine name | Dose | Timing | Duration | Special instructions
```

## 5. Safety Gate Logic

Every extracted item passes through the safety gate before becoming a task. This is the system's primary responsible AI mechanism.

**An item is flagged Needs Review if ANY of the following is true:**

- Date, dose, timing, or doctor name is missing or ambiguous
- Describes a symptom or contains "what should I do if..."
- Involves a medicine change, stop order, or clash between two instructions
- Extraction confidence is below 70%
- Text does not fit any known extraction category

**Partial flagging:** If one field of a task is unclear but the rest is fine, only that field is flagged — the task is not blocked entirely. This keeps clean items moving.

**User-triggered flag:** The patient or family member can manually mark any item as Needs Review at any time.

**Hard rules (non-negotiable):**

- The safety gate never auto-resolves a Needs Review item
- Only the doctor reviewer can close a Needs Review item
- If the assigned doctor is unavailable, the item routes to the next assigned reviewer (management-controlled fallback)
- Needs Review items are visible to family as "Waiting for doctor review" — locked and grayed out

**Permanent footer on every screen:** *"This tool organizes your discharge instructions. It does not give medical advice. Ask your doctor about anything unclear."*

## 6. Task Card UI Requirements

**Every task card shows:**

- Simple-language version in the patient's chosen language
- Original source line (tap to expand — "Show original")
- Date, status badge (color-coded), and reminder
- Provider suggestion where relevant — always labeled "Suggestion, not a guarantee"
- "Request callback" button (masked synthetic number)
- "Listen" button (ElevenLabs reads approved text only — never generates new wording)

**Status badges:**

| Status | Color | Meaning |
| --- | --- | --- |
| Pending | Blue | Action required by patient |
| Completed | Green | Ticked off by patient or family |
| Needs Review | Orange | Locked — waiting for doctor |

**Missed task behavior:** If a Pending task passes its due date without being marked complete, the system auto-notifies the designated family member.

**For elderly users:** Callback and Listen buttons are the most prominent elements — placed at the top of the card, not the bottom.

**Medicine cards:** Displayed using the fixed template only (Medicine name / Dose / Timing / Duration / Special instructions). No free rewriting of medicine content under any circumstance.

**Needs Review card state:** Grayed out, locked, shows "Waiting for doctor review." Family sees this state. Only the doctor reviewer can unlock it.

**Permanent footer on every screen:** *"This tool organizes your discharge instructions. It does not give medical advice. Ask your doctor about anything unclear."*

## 7. Provider Matching & Map Discovery

When the discharge summary mentions a referral or follow-up (e.g., "see a cardiologist," "get an MRI"), the system suggests matching providers from a synthetic dataset and shows them on an interactive map.

**Location drill-down flow:** User selects State → District → Area (e.g., Tamil Nadu → Chennai → Perambur). The extracted specialty (e.g., Orthopedics) is auto-filled from the task. The map renders all matching synthetic providers in that area as pins.

**Map UI (Leaflet.js — no API key required):**

- Each provider pin shows: name, specialty, facility, distance, synthetic contact
- Pins are color-coded: hospitals (blue), local clinics/doctors (green)
- User taps a pin → provider card appears with a "Select this provider" button
- Selected provider is linked to the task as the suggestion
- Always labeled: *"Suggestion only — not a guarantee of availability or suitability"*

**Location input:**

- Primary: live GPS (browser geolocation)
- Fallback: manual drill-down — State → District → Area dropdown
- No location data stored beyond the session

**Matching logic:**

- Match by specialty extracted from the discharge item
- Filter by location — live GPS (primary) or manually selected area (fallback)
- Return top 3–5 suggestions ranked by proximity

**Synthetic provider dataset fields:**

| Field | Example |
| --- | --- |
| Provider name | Dr. Ramesh Kumar |
| Specialty | Orthopedics |
| Facility | Apollo Hospital |
| City / Area | Perambur, Chennai |
| Coordinates (synthetic) | 13.1067° N, 80.2206° E |
| Distance (synthetic) | 2.3 km |
| Contact (synthetic) | +91-XXXXX-XXXXX |
| Type | Hospital / Local clinic |

**Agent classification:** Provider matching is a **code agent** (DB query + proximity sort), not an AI agent. No model is called here.

**Hard rules:**

- Every suggestion labeled: *"Suggestion only — not a guarantee of availability or suitability"*
- The system never presents a match as a medical referral or endorsement
- Provider data is synthetic only — no real hospital or doctor data used
- The discharging hospital and the suggested providers are independent: suggestions come from the synthetic dataset, not from the discharging facility

## 8. Data Model

| Table | Key Fields |
| --- | --- |
| **User** | id, name, role, chosen\_language, login |
| **Family Member** | id, patient\_id (FK), access\_level (full / appointments / reminders), notify\_on\_miss |
| **Consent** | patient\_id, family\_member\_id, access\_level, granted\_at |
| **Discharge Summary** | id, patient\_id, raw\_text, uploaded\_at |
| **Task** | id, patient\_id, type, date, status, simple\_text, translated\_text, source\_line, confidence\_score, flagged\_reason |
| **Review Queue** | id, task\_id, reason\_flagged, assigned\_doctor\_id, fallback\_doctor\_id, outcome, resolved\_at |
| **Doctor** | id, specialty, availability, assigned\_patients\[\] |
| **Provider** (synthetic) | id, name, specialty, facility, city, distance\_km, contact |
| **Notification** | id, recipient\_id, task\_id, type, scheduled\_at, sent\_at |
| **Audit Log** | id, actor\_id, action, target\_id, timestamp |

**Key relationships:**

- Task → Discharge Summary (source)
- Task → Review Queue (when flagged)
- Task → Provider (suggestion, where applicable)
- Family Member → Patient (via Consent)
- Doctor → Review Queue (assigned)

**Security:** Patient and family data is encrypted at rest. Role-based access control enforced on every endpoint. Audit log is append-only.

## 9. Build Order

| Priority | What | Why |
| --- | --- | --- |
| **P1 — Must have** | Upload summary → extract 7 types with source line evidence → safety gate → tasks + timeline → plain language rewrite | Core loop judges evaluate |
| **P1 — Must have** | Doctor reviewer queue — view flagged items, confirm/correct, resolve | Responsible AI proof point |
| **P2 — Should have** | Language selection + translation (English, Tamil, Hindi) | Multilingual AI requirement |
| **P2 — Should have** | Synthetic provider suggestions with live GPS location | Provider matching requirement |
| **P2 — Should have** | Card view + two-panel toggle, family member access + notifications | End-to-end user journey |
| **P3 — Nice to have** | ElevenLabs voice (Listen button) | Accessibility layer |
| **P3 — Nice to have** | Request callback (masked synthetic number) | Escalation feature |
| **P3 — Nice to have** | Fallback doctor routing, management dashboard | Operational completeness |

## 11. Masked Call Feature

A patient can request a call from the hospital or doctor directly from any task card. Neither the patient nor the doctor sees the other's real number — calls are routed through a masked proxy number, exactly like Blinkit or Amazon delivery calls.

**Call flow:**

1. Patient taps "Request Callback" on a task card
2. System logs the request and notifies hospital management
3. Hospital management sees the request in their queue and initiates the call
4. Call is routed through a proxy number — patient sees a masked number, doctor/hospital sees a masked number
5. Both parties are connected without real number exposure
6. Call ends → system logs duration and marks the task as "Callback completed"

**Agent:** Notification agent handles the callback request trigger. Call routing itself uses a telephony integration (Twilio for production; synthetic/mocked for the prototype demo).

**Agent classification:** Code agent — no AI involved. Logic is: request → queue → route → connect → log.

**For the prototype demo:** Mock the call with a UI flow showing the masked number screen and a simulated "Connecting..." state. Real Twilio integration is a production layer.

**Roles in this flow:**

| Actor | Sees | Cannot See |
| --- | --- | --- |
| Patient | Masked hospital number | Doctor's real number |
| Hospital management | Callback request + patient masked number | Patient's real number |
| Doctor | Masked patient number | Patient's real number |

**Hard rules:**

- Only synthetic numbers used in the prototype
- Call logs are stored in the Audit Log (who called, when, duration — no call content)
- Patient must initiate — the system never calls the patient unprompted

## Agent Architecture

One orchestrator coordinates all agents. Only 2 use an AI model — the rest are code. This keeps the system predictable, cheap, and explainable to judges.

| Agent | Job | Type |
| --- | --- | --- |
| Orchestrator | Runs steps in order, routes unclear items, waits for human review | Light logic |
| Extraction agent | Reads summary, pulls 7 item types with source lines | AI (Claude) |
| Safety gate | Marks each item Pending or Needs Review | Fixed rules — NOT AI |
| Planner agent | Turns items into tasks, dates, reminders, timeline | Code |
| Simplify & translate agent | Rewrites in plain language + chosen language, fixed template for medicines | AI (Claude) |
| Provider matching agent | Matches referrals to synthetic providers by specialty + location, renders map | Code (DB query + Leaflet.js) |
| Review routing agent | Assigns doctor, reroutes if unavailable | Code |
| Notification agent | Sends reminders to patient + family at scheduled times | Code (Celery/cron) |
| Task scheduler | Fires missed-task alerts, triggers family notification | Code (Celery beat) |

**Why safety gate is fixed rules, not AI:** If a model decided what is safe, it could be wrong or inconsistent. Fixed rules give the same answer every time and can be explained — that is how the system fails safely.

**Recommended stack:** FastAPI orchestrator calling each agent as a function. LangGraph is an alternative if native "pause and wait for human" is preferred — it fits the doctor review step well.

---

**Demo strategy:** Get P1 fully working first. A clean end-to-end P1 demo beats a broken P3 feature every time. P2 adds depth to the story. P3 only if time permits and it works reliably.

## 10. Limitations & Responsible AI

**What this system does not do:**

- Does not diagnose any condition
- Does not change, recommend, or adjust medication
- Does not recommend treatment
- Does not present provider matches as guarantees of availability or suitability

**Known system limitations:**

- Works on synthetic discharge text only — not validated as a medical device
- Extraction can misread poorly structured summaries — evidence field and human review exist to catch this
- Translations of non-medicine text should be spot-checked; medicine lines use fixed templates to reduce translation risk
- Live GPS requires browser permission; falls back to manual city selection if denied
- Provider matches are based on a synthetic dataset and do not reflect real availability

**Human in the loop:**

- Every Needs Review item requires a human doctor to resolve — the AI never auto-resolves clinical ambiguity
- Patients and family members can manually flag any item at any time
- All actions are logged in the audit trail

**Failure behavior:**

- Partial extraction failure → user is shown what was read and prompted to fill missing fields manually
- Complete extraction failure → user is prompted to re-upload or enter manually; item is routed to Needs Review
- The system always fails visibly — never silently
