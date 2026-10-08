> **Update (Oct 2026):** the backend now runs on **SQLite** (one file, `backend/data/discharge.db`). MongoDB, Neo4j, Redis and Celery are no longer used; read their mentions below as history. Plans are drafts for the matched doctor until published. Current details: `backend/README.md` and `docs/DATA_MODEL.md`.

# Backend, Database and Application Flow

**Project:** Agentic Hospital Discharge & Follow-up Coordinator
**Based on:** PRD.md, SECURITY.md, Tech_Stack.md. MongoDB holds all content. Neo4j holds IDs and relationships only (consent paths, doctor assignment, fallback chain)
**Data:** Synthetic only, everywhere.

This document has three parts:

1. **Database design:** every MongoDB collection, its fields, indexes and rules
2. **Backend implementation:** services, pipeline, safety gate, APIs, jobs, and the order to build them
3. **Application flow:** screens and journeys for each role, and how each screen talks to the backend

Priorities match the PRD: **[P1]** must have, **[P2]** should have, **[P3]** nice to have.

---

# Part 1. Database design (MongoDB)

## 1.1 Design rules

| Rule | Why |
|---|---|
| One database, `discharge_coordinator` | Simple to run and back up |
| IDs are `ObjectId`, written `_id` | Native, fast, no extra library |
| Timestamps are UTC `datetime`. The UI shows IST | Avoids time zone bugs |
| Enums are checked twice: Pydantic and a MongoDB JSON-schema validator | A typo cannot create a fourth status |
| Fields marked **(enc)** are encrypted in the application with AES-GCM | Protects patient and family data at rest |
| Fields used in queries are never encrypted: ids, `status`, `type`, `due_date`, timestamps | Encrypted fields cannot be searched |
| No clinical text in `audit_log` or `notifications` | Keeps logs and reminders safe |
| Documents point to each other by id. No joins in the database | Consent, assignment and fallback are simple references |

Encrypted values are stored as one string: `v1:<nonce>:<ciphertext>` (base64). The key is `FIELD_ENC_KEY` in the backend environment. The `v1` prefix allows key rotation later.

## 1.2 How the collections connect

```
users ──────────────┬─────────────────────────────────────────────┐
 (patient)          │                                             │
   │                │                                             │
   │ 1..n           │ patient_id                                  │
   ▼                ▼                                             │
family_members ◄── consents                                       │
   (links a family user to a patient)                             │
                                                                  │
users (patient) ──► discharge_summaries ──► tasks ──► review_queue ──► doctors (users, role=doctor)
                                              │
                                              ├──► providers  (suggested provider, optional)
                                              └──► notifications (reminders, missed-task, callbacks)

locations (state > district > area) ──► used with providers for the map
audit_log  : written by every service, read by no one except the owner of the data
```

## 1.3 Collections

### `users`
Every person who can log in. The role decides what they can do.

| Field | Type | Notes |
|---|---|---|
| `_id` | ObjectId | |
| `name` | string (enc) | Synthetic name |
| `login` | string | Unique username or email, lower case |
| `password_hash` | string | Argon2id |
| `role` | enum | `patient`, `family`, `doctor`, `management` |
| `language` | enum | `en`, `ta`, `hi` (polished). `te`, `kn`, `ml` (stretch) |
| `phone` | string (enc) | Synthetic, `+91-XXXXX-XXXXX` format |
| `is_active` | bool | |
| `failed_logins` | int | Reset on success |
| `locked_until` | datetime or null | Set after 5 failures |
| `created_at` | datetime | |

Indexes: unique `login`; `role`.

### `family_members`
The link between a family user and a patient. Also marks the elderly-mode delegate.

| Field | Type | Notes |
|---|---|---|
| `_id` | ObjectId | |
| `patient_id` | ObjectId | The patient's user id |
| `user_id` | ObjectId | The family member's user id |
| `relationship` | string | "daughter", "son", and so on |
| `can_operate` | bool | True = elderly mode. They act on the patient's behalf |
| `notify_on_miss` | bool | Designated for missed-task alerts |
| `created_at` | datetime | |
| `revoked_at` | datetime or null | Set when the patient removes them. Takes effect at once |

Indexes: unique `(patient_id, user_id)`; `user_id`.

### `consents`
What each family member is allowed to see. One active record per link. Old records are kept as history.

| Field | Type | Notes |
|---|---|---|
| `_id` | ObjectId | |
| `patient_id` | ObjectId | |
| `family_member_id` | ObjectId | Points to `family_members._id` |
| `access_level` | enum | `full`, `appointments`, `reminders` |
| `granted_at` | datetime | |
| `revoked_at` | datetime or null | |

Index: `(patient_id, family_member_id, revoked_at)`.

> If `can_operate` is true, the access level is forced to `full`.

### `discharge_summaries`
One uploaded or pasted summary and the state of its processing.

| Field | Type | Notes |
|---|---|---|
| `_id` | ObjectId | |
| `patient_id` | ObjectId | |
| `uploaded_by` | ObjectId | The patient or the delegate |
| `source` | enum | `pdf`, `text`, `manual` |
| `raw_text` | string (enc) | Extracted text. The original file is deleted |
| `text_hash` | string | SHA-256 of the text, for duplicate detection |
| `discharge_date` | date or null | Read from the text, or entered by the user. Needed to resolve "in 2 weeks" |
| `status` | enum | `uploaded`, `extracting`, `gating`, `planning`, `simplifying`, `ready`, `needs_manual`, `failed` |
| `error_code` | string or null | `EMPTY_INPUT`, `NOT_MEDICAL`, `UNREADABLE_PDF`, `EXTRACTION_FAILED` |
| `pipeline_log` | array | `{step, started_at, ended_at, ok, note}` with no clinical text |
| `uploaded_at` | datetime | |

Indexes: `(patient_id, uploaded_at desc)`; `text_hash`.

### `tasks`  (the heart of the system)
One follow-up item, whether it came from extraction or manual entry.

| Field | Type | Notes |
|---|---|---|
| `_id` | ObjectId | |
| `patient_id` | ObjectId | |
| `summary_id` | ObjectId or null | Null for manual entries |
| `type` | enum | `appointment`, `test`, `referral`, `medicine`, `care_instruction`, `date`, `warning_sign` |
| `title` | string (enc) | Short label, such as "Cardiology follow-up" |
| `due_date` | date or null | Resolved by code, never by the AI |
| `due_date_text` | string or null | The wording found, such as "in 2 weeks" |
| `status` | enum | `Pending`, `Completed`, `Needs Review` |
| `source_line` | string (enc) | **Exact line from the summary. The evidence** |
| `source_span` | object | `{start, end}` character offsets, used to highlight in the two-panel view |
| `confidence` | float 0 to 1 | From the extraction agent |
| `fields` | object | Structured details, see below |
| `flags` | array | `{field, reason_code, note}`. Empty when clean |
| `simple_text` | string (enc) | Plain-language English |
| `translations` | object (enc values) | `{ "ta": "...", "hi": "..." }` |
| `medicine_card` | object or null | Medicine tasks only, see below |
| `provider_id` | ObjectId or null | Selected provider suggestion |
| `provider_needed` | bool | True for referrals and specialist follow-ups |
| `specialty` | string or null | Used to find providers |
| `entry_mode` | enum | `extracted`, `manual` |
| `supersedes` | ObjectId or null | A manual correction points to the task it replaces |
| `completed_at` | datetime or null | |
| `completed_by` | ObjectId or null | Who ticked it |
| `missed_notified_at` | datetime or null | Stops repeat missed-task alerts |
| `created_at`, `updated_at` | datetime | |

`fields` holds what the extraction agent found, by type:

```json
{ "doctor_name": "Dr. Meera Iyer", "department": "Cardiology",
  "test_name": "Fasting blood sugar", "instruction": "Change dressing every 48 hours",
  "trigger_text": "fever above 38.5 C before Day 5" }
```

`medicine_card` is the **fixed template** and is never reworded:

```json
{ "name": "Metformin", "dose": "500 mg", "timing": "Twice daily",
  "duration": "30 days", "special": "After food" }
```
Each value is copied from the source text. Labels such as "Dose" come from the language files, not from the AI.

Indexes:
- `(patient_id, status, due_date)`  main list and timeline
- `(patient_id, type)`
- `(summary_id)`
- `(status, due_date)` partial index where `status = "Pending"`, used by the missed-task job

### `review_queue`
Created whenever a task is flagged. Only a doctor can close one.

| Field | Type | Notes |
|---|---|---|
| `_id` | ObjectId | |
| `task_id` | ObjectId | |
| `patient_id` | ObjectId | |
| `reasons` | array | Reason codes copied from the task flags |
| `reason_text` | string | Visible, short, such as "Dose is not mentioned" |
| `raised_by` | enum | `gate`, `patient`, `family`, `system_failure` |
| `status` | enum | `open`, `in_review`, `resolved` |
| `assigned_doctor_id` | ObjectId or null | Set by management or auto-assignment |
| `fallback_doctor_ids` | array | Ordered. The next reviewers |
| `assignment_history` | array | `{doctor_id, assigned_at, reason}` |
| `outcome` | enum or null | `confirmed`, `corrected` |
| `corrected_values` | object (enc) | What the doctor changed, if anything |
| `resolved_by` | ObjectId or null | Always a doctor |
| `resolved_at` | datetime or null | |
| `created_at` | datetime | |

Indexes: `(assigned_doctor_id, status)`; `(status, created_at)`; `task_id`.

### `doctors`
Extra details for users whose role is `doctor`.

| Field | Type | Notes |
|---|---|---|
| `_id` | ObjectId | |
| `user_id` | ObjectId | Unique |
| `specialty` | string | |
| `available` | bool | Management can switch this off |
| `unavailable_until` | datetime or null | |
| `assigned_patient_ids` | array of ObjectId | |
| `fallback_doctor_id` | ObjectId or null | Next reviewer in the chain, controlled by management |

Indexes: unique `user_id`; `available`.

### `providers`  (synthetic)

| Field | Type | Notes |
|---|---|---|
| `_id` | ObjectId | |
| `name` | string | "Dr. Ramesh Kumar" |
| `specialty` | string | "Orthopedics" |
| `facility` | string | |
| `type` | enum | `hospital`, `clinic` (blue and green pins) |
| `state`, `district`, `area` | string | Used by the drill-down |
| `location` | GeoJSON Point | `{type: "Point", coordinates: [lng, lat]}` |
| `contact` | string | Synthetic `+91-XXXXX-XXXXX` |
| `synthetic` | bool | Always true. A guard against real data |

Indexes: `2dsphere` on `location`; `(specialty, state, district, area)`.

### `locations`  (synthetic, for the drill-down)

| Field | Type | Notes |
|---|---|---|
| `state`, `district`, `area` | string | Example: Tamil Nadu, Chennai, Perambur |
| `centre` | GeoJSON Point | Used when the user picks an area instead of GPS |

Index: `(state, district, area)` unique.

### `notifications`
Reminders, missed-task alerts, review waiting notices and callback requests.

| Field | Type | Notes |
|---|---|---|
| `_id` | ObjectId | |
| `recipient_id` | ObjectId | |
| `patient_id` | ObjectId | |
| `task_id` | ObjectId or null | |
| `type` | enum | `reminder`, `missed_task`, `review_waiting`, `callback` |
| `scheduled_at` | datetime | |
| `sent_at` | datetime or null | |
| `read_at` | datetime or null | |
| `template_key` | string | Message comes from a template. No clinical text |
| `callback` | object or null | Only for `type = callback`, see below |

`callback` object:

```json
{ "status": "requested | queued | connecting | completed | cancelled",
  "requested_by": "<user id>", "handled_by": "<management user id>",
  "patient_mask": "+91-9XXXX-MASK1", "provider_mask": "+91-9XXXX-MASK2",
  "started_at": null, "ended_at": null, "duration_sec": null }
```
The masks are synthetic proxy numbers. Real numbers are never stored here.

Indexes: `(sent_at, scheduled_at)` partial where `sent_at = null`; `(recipient_id, read_at)`; `(type, callback.status)`.

### `audit_log`  (append-only)

| Field | Type | Notes |
|---|---|---|
| `_id` | ObjectId | |
| `actor_id` | ObjectId or "system" | Who did it |
| `on_behalf_of` | ObjectId or null | The patient, in elderly mode |
| `action` | string | `login`, `view_plan`, `task_complete`, `flag`, `resolve_review`, `reroute`, `consent_change`, `callback_*` |
| `target_type` | string | `task`, `summary`, `review`, `consent` |
| `target_id` | ObjectId or null | |
| `result` | enum | `ok`, `denied`, `error` |
| `ip` | string | |
| `ts` | datetime | |
| `prev_hash` | string | Hash chain **[P3]** |

Never stored here: clinical text, tokens, passwords or full phone numbers.
The database user for the API has `insert` and `find` only on this collection, with no `update` or `delete`.

Indexes: `(actor_id, ts)`; `(target_id, ts)`; `(on_behalf_of, ts)`.

### `refresh_tokens`  (small helper, for logout and rotation)

| Field | Type | Notes |
|---|---|---|
| `user_id` | ObjectId | |
| `token_hash` | string | Hash only, never the token |
| `expires_at` | datetime | TTL index removes it |
| `revoked` | bool | |

## 1.4 Validation (database level)

Example validator for `tasks` (the other collections follow the same pattern):

```js
db.runCommand({
  collMod: "tasks",
  validator: { $jsonSchema: {
    bsonType: "object",
    required: ["patient_id", "type", "status", "source_line", "created_at"],
    properties: {
      status: { enum: ["Pending", "Completed", "Needs Review"] },
      type: { enum: ["appointment","test","referral","medicine",
                     "care_instruction","date","warning_sign"] },
      confidence: { bsonType: ["double","int"], minimum: 0, maximum: 1 }
    }
  }},
  validationLevel: "strict", validationAction: "error"
})
```

## 1.5 Rules about status changes

```
              ┌───────────── clean ───────────┐
 extracted ──►│ gate                           ├──► Pending ──► Completed
              └──────── flagged ──► Needs Review ──(doctor resolves)──► Pending
```

| From | To | Who can do it |
|---|---|---|
| (new) | Pending | Gate, when every field is clean |
| (new) | Needs Review | Gate, when anything is flagged |
| Pending | Needs Review | Patient or family (manual flag), or the gate on a manual entry |
| Needs Review | Pending | **Doctor only**, through the review resolve endpoint |
| Pending | Completed | Patient, or the delegate in elderly mode |
| Completed | Pending | Patient (undo a tick) |
| Needs Review | Completed | **Never directly** |

Every transition is written to `audit_log`.

---

# Part 2. Backend implementation

## 2.1 Services (Docker Compose)

| Service | Runs | Notes |
|---|---|---|
| `api` | FastAPI app, orchestrator, all endpoints | Port 8000, behind HTTPS in the demo |
| `worker` | Celery worker | Reminders, notifications |
| `beat` | Celery beat | Schedules the recurring jobs |
| `mongo` | MongoDB | Not exposed publicly |
| `redis` | Celery broker | Password protected, internal network only |
| `frontend` | React build served by a web server | Only this and `api` are reachable |

## 2.2 Folder structure

```
backend/
  app/
    main.py                  FastAPI app, routers, middleware
    config.py                Environment settings
    db.py                    Motor client, collection helpers
    security/
      auth.py                Login, JWT, refresh, password hashing
      access.py              current_user, role guard, patient view (consent)
      crypto.py              enc() and dec() field encryption
    models/                  Pydantic models for each collection and each API body
    routers/
      auth.py  patients.py  family.py  summaries.py  tasks.py
      providers.py  review.py  management.py  callbacks.py  audio.py  audit.py
    pipeline/
      orchestrator.py        Runs the steps in order
      reader.py              pdfplumber and text checks
      extraction_agent.py    Claude call (AI agent 1)
      dates.py               Turns "in 2 weeks" into a real date
      safety_gate.py         Fixed rules (no AI)
      planner.py             Builds tasks, reminders, timeline
      simplify_agent.py      Claude call (AI agent 2)
      medicine_template.py   Builds the fixed medicine card
      provider_agent.py      Geo query and ranking
      review_router.py       Assigns doctor, reroutes
    jobs/
      celery_app.py  reminders.py  missed_tasks.py
    services/
      audit.py  notify.py  voice.py  callbacks.py
  tests/
  Dockerfile
```

## 2.3 The pipeline (orchestrator)

The orchestrator is a plain function. It runs as a background task after upload, and writes `discharge_summaries.status` after every step, so the frontend can poll and show progress.

```
POST /summaries
   │
   ▼
[1] reader            status: uploaded → extracting
   │  empty / non-medical / unreadable?  ──► status=needs_manual, error_code set, STOP
   ▼
[2] extraction_agent  (Claude)  returns JSON items
   │  schema invalid / nothing found?    ──► status=needs_manual, a Needs Review record is created, STOP
   ▼
[3] verify evidence   source_line must appear word for word in raw_text
   │  not found?  ──► item gets flag SOURCE_NOT_FOUND
   ▼
[4] dates.resolve     due_date_text → due_date (code, using discharge_date)
   ▼
[5] safety_gate       status: gating   rules run per item and per field
   ▼
[6] planner           status: planning  save tasks, review_queue records, schedule reminders
   ▼
[7] simplify_agent    status: simplifying  plain language + translation (clean tasks only)
   ▼
[8] provider_agent    mark provider_needed and specialty (matching happens on demand with location)
   ▼
[9] review_router     assign a doctor for every new review_queue record
   ▼
status = ready
```

**Why the order matters**
- Evidence is checked **before** the gate, so a made-up line is caught early.
- Dates are resolved by **code**, so the AI never invents a date.
- Simplify runs **only on clean tasks**, so flagged text is never rewritten before a doctor sees it.
- Any failure sets a visible status. It never silently stops.

### Step 1. Reader
- Accept PDF (pdfplumber) or pasted text.
- Reject: empty text, fewer than about 50 characters, no medical-looking content (a simple keyword check for words like "discharge", "mg", "follow", "advice"), or a PDF with no text layer (no OCR in this build).
- Save `raw_text` encrypted, compute `text_hash`, delete the uploaded file.

### Step 2. Extraction agent (AI)
- The prompt holds fixed instructions, then the summary inside a marked data block. The model is told the block is data only.
- The model returns JSON that must match this schema, or it is rejected:

```python
class MedicineFields(BaseModel):
    name: str | None; dose: str | None; timing: str | None
    duration: str | None; special: str | None

class ExtractedItem(BaseModel):
    type: Literal["appointment","test","referral","medicine",
                  "care_instruction","date","warning_sign"]
    title: str
    source_line: str                 # copied exactly from the text
    due_date_text: str | None        # "in 2 weeks", "Day 7", "12 Nov"
    doctor_name: str | None
    specialty: str | None
    medicine: MedicineFields | None
    instruction: str | None
    confidence: float = Field(ge=0, le=1)

class ExtractionResult(BaseModel):
    discharge_date_text: str | None
    items: list[ExtractedItem]
```

- The agent has no tools and no database access. It cannot change status, dates or medicines.

### Step 3. Evidence check

```python
def evidence_ok(item, raw_text) -> bool:
    return normalise(item.source_line) in normalise(raw_text)
```
`normalise` collapses spaces and line breaks. If it fails, the item gets the flag `SOURCE_NOT_FOUND`. The `source_span` offsets are found at this step, for the two-panel highlight.

### Step 4. Date resolution (code)
- Absolute dates ("12 Nov 2026") are parsed directly.
- Relative dates ("in 2 weeks", "Day 7", "after 48 hours") are added to `discharge_date`.
- If `discharge_date` is unknown, or the wording is vague ("soon", "as needed"), `due_date` stays null and the item is flagged `AMBIGUOUS_DATE`.

### Step 5. Safety gate (fixed rules, no AI)

```python
RULES = [
  missing_date_dose_timing_or_doctor,   # per type, which fields are required
  ambiguous_date,
  symptom_question,                     # "what should I do if", "if you feel..."
  medicine_change_or_stop,              # "stop", "discontinue", "increase", "reduce", "switch"
  medicine_conflict,                    # same drug twice with different dose or timing
  low_confidence,                       # confidence < 0.70
  uncategorised,                        # type missing or text fits nothing
  source_not_found,
]

def run_gate(item) -> list[Flag]:
    flags = []
    for rule in RULES:
        flags += rule(item)
    return flags            # empty list means clean
```

Required fields by type:

| Type | Must have |
|---|---|
| appointment | date, doctor name or department |
| test | test name, date |
| referral | specialty |
| medicine | name, dose, timing, duration |
| care_instruction | instruction text |
| date | date text |
| warning_sign | instruction text |

Behaviour:
- **Partial flagging:** each flag names a field. Only that field is marked. Clean fields stay usable and the task still appears on the timeline.
- **Any flag** puts the task in `Needs Review` and creates a `review_queue` record.
- **Warning signs** are not flagged just because they mention a symptom. They are shown as plain alerts. They are flagged only if they contain a "what should I do if" question or fail another rule.
- Manual entries run through the same gate.
- The gate never auto-resolves anything.

Reason codes: `MISSING_DATE`, `MISSING_DOSE`, `MISSING_TIMING`, `MISSING_DURATION`, `MISSING_DOCTOR`, `AMBIGUOUS_DATE`, `SYMPTOM_QUESTION`, `MEDICINE_CHANGE`, `MEDICINE_CONFLICT`, `LOW_CONFIDENCE`, `UNCATEGORISED`, `SOURCE_NOT_FOUND`, `USER_FLAGGED`, `EXTRACTION_FAILED`.

### Step 6. Planner
For each item:
- Insert the `tasks` document with status `Pending` or `Needs Review`.
- For flagged items, insert a `review_queue` record with a short visible `reason_text`.
- For clean items with a `due_date`, create reminder `notifications` (the day before at 09:00 IST, and on the day at 09:00 IST).
- Items with no date go into a "No date yet" group on the timeline.

### Step 7. Simplify and translate agent (AI)
Applies only to **clean** `care_instruction`, `warning_sign`, `appointment`, `test`, `referral` and `date` tasks.

- Writes `simple_text` in English, then translates into the patient's language (`ta`, `hi`, and stretch languages).
- **Medicine tasks never go to the AI.** `medicine_template.py` builds `medicine_card` by copying the extracted values. The labels (Dose, Timing, and so on) come from the language files.
- Checks after each rewrite:
  - Every number in the source line must also appear in the rewrite (so "48 hours" cannot become "24 hours").
  - Banned patterns (diagnosis words, "you should take", "increase", "stop taking") block the output and send the task to Needs Review.
  - If a check fails, the task is flagged `UNCATEGORISED` with a note, instead of showing the rewrite.

### Step 8. Provider flag
Referrals and specialist appointments get `provider_needed = true` and a `specialty`. The actual search runs on demand, when the user opens the map (it needs their location).

### Step 9. Review router

```python
async def assign(review):
    doctor = await pick_doctor(review)          # available, matching specialty, fewest open items
    if not doctor or not doctor.available:
        doctor = await follow_fallback_chain(doctor)   # doctors.fallback_doctor_id, in order
    review.assigned_doctor_id = doctor.id
    review.assignment_history.append(...)
```
- If nobody is available, the record stays `open` with no doctor and appears in management's "needs assignment" list.
- Management can reassign at any time. Every reroute is logged.

## 2.4 Access control (the consent check)

One shared dependency decides what a person may see. Every plan endpoint uses it. No endpoint is allowed to skip it.

```python
async def patient_view(patient_id: ObjectId, user = Depends(current_user)) -> View:
    if user.role == "patient" and user.id == patient_id:
        return View(level="full", operator=False, actor=user.id, on_behalf_of=None)

    if user.role == "family":
        link = await db.family_members.find_one(
            {"patient_id": patient_id, "user_id": user.id, "revoked_at": None})
        if not link:
            await audit("view_plan", user, patient_id, "denied"); raise HTTPException(403)
        consent = await db.consents.find_one(
            {"patient_id": patient_id, "family_member_id": link["_id"], "revoked_at": None})
        level = "full" if link["can_operate"] else consent["access_level"]
        return View(level=level, operator=link["can_operate"],
                    actor=user.id, on_behalf_of=patient_id)

    raise HTTPException(403)       # doctors and management do not use this route
```

What each level returns (filtered **in the API response**, not only in the UI):

| Level | Tasks returned | Fields returned |
|---|---|---|
| `full` | All types | Everything except `fields` hidden for flagged items |
| `appointments` | `appointment`, `test`, `referral` | Title, date, status, provider |
| `reminders` | All types | Title, due date, status only |

For any task with `status = Needs Review`, family always gets: title hidden, text "Waiting for doctor review", `locked: true`.

Doctors reach clinical content only through `/review/*`, and only for items assigned to them. Management endpoints return queue metadata and reason codes, never `source_line` or text.

## 2.5 API endpoints

All endpoints need a valid token, except login. Role guards are listed in the last column.

### Auth
| Method and path | What it does | Who |
|---|---|---|
| `POST /auth/login` | Login, returns cookies | Anyone |
| `POST /auth/refresh` | Rotates the refresh token | Logged in |
| `POST /auth/logout` | Revokes the refresh token | Logged in |
| `GET /me` | Profile, role, language, delegations | Logged in |
| `PUT /me/language` | Change language | Logged in |

### Family and consent
| Method and path | What it does | Who |
|---|---|---|
| `POST /family` | Add a family member with access level and `can_operate` | Patient |
| `PATCH /family/{id}` | Change access level or `notify_on_miss` | Patient |
| `DELETE /family/{id}` | Revoke access immediately | Patient |
| `GET /family` | List members | Patient |
| `GET /me/patients` | Patients this family member can see | Family |

### Summaries
| Method and path | What it does | Who |
|---|---|---|
| `POST /patients/{pid}/summaries` | Upload PDF or paste text. Starts the pipeline | Patient, delegate |
| `GET /summaries/{id}/status` | Progress for polling | Patient, delegate |
| `GET /summaries/{id}` | Original text (decrypted) with highlight spans | Patient, family with `full` |

### Tasks
| Method and path | What it does | Who |
|---|---|---|
| `GET /patients/{pid}/tasks` | List, filtered by consent level | Patient, family |
| `GET /patients/{pid}/timeline` | Tasks grouped and ordered by date | Patient, family |
| `GET /tasks/{id}` | One task, with source line if allowed | Patient, family |
| `POST /tasks/{id}/complete` | Tick done | Patient, delegate |
| `POST /tasks/{id}/undo` | Back to Pending | Patient, delegate |
| `POST /tasks/{id}/flag` | Manual Needs Review flag, with a short note | Patient, family |
| `POST /patients/{pid}/tasks` | Manual entry through the form. Runs the gate | Patient, delegate |
| `GET /tasks/{id}/audio?lang=ta` | Text-to-speech of approved text | Patient, family |

A manual **correction** creates a new task (`entry_mode = manual`, `supersedes = old id`) and flags the old one for review. Extracted text is never edited in place.

### Providers and map
| Method and path | What it does | Who |
|---|---|---|
| `GET /locations/states`, `/districts?state=`, `/areas?district=` | Drill-down lists | Patient, family |
| `GET /providers?specialty=&lat=&lng=` | GPS search | Patient, family |
| `GET /providers?specialty=&state=&district=&area=` | Fallback search | Patient, family |
| `POST /tasks/{id}/provider` | Select a provider as the suggestion | Patient, delegate |

Search returns the 3 to 5 nearest synthetic providers with `distance_km`, and the label text *"Suggestion only, not a guarantee of availability or suitability"*. Coordinates from the browser are used for the query and are not saved.

### Review (doctor)
| Method and path | What it does | Who |
|---|---|---|
| `GET /review/queue` | My assigned items | Doctor |
| `GET /review/{id}` | Item with source line, flagged fields, reasons | Doctor (assigned) |
| `POST /review/{id}/resolve` | `confirmed` or `corrected` (with new values). Moves task to Pending | Doctor (assigned) |

### Management
| Method and path | What it does | Who |
|---|---|---|
| `GET /mgmt/queue` | All reviews: reasons, ages, assignees. No clinical text | Management |
| `POST /mgmt/review/{id}/assign` | Assign or reassign a doctor | Management |
| `PUT /mgmt/doctors/{id}/availability` | Set available or on leave | Management |
| `PUT /mgmt/doctors/{id}/fallback` | Set the next reviewer | Management |
| `GET /mgmt/callbacks` | Callback requests | Management |
| `POST /mgmt/callbacks/{id}/start` | Start the (simulated) masked call | Management |
| `POST /mgmt/callbacks/{id}/complete` | End it and log duration | Management |

### Callbacks and audit
| Method and path | What it does | Who |
|---|---|---|
| `POST /tasks/{id}/callback` | Request a callback. Creates a `callback` notification | Patient, delegate |
| `GET /me/audit` | My own activity and who viewed my plan | Patient |
| `GET /me/notifications` | My notifications | Logged in |

## 2.6 Doctor resolve flow

```
POST /review/{id}/resolve   { outcome: "confirmed" | "corrected", corrected_values?: {...} }
   │
   ├─ caller must be role=doctor AND assigned_doctor_id == caller          else 403
   ├─ review must be open or in_review                                     else 409
   ├─ if corrected: update the task fields, then run the gate on the NEW values
   │       └─ if the gate still flags something → resolve is rejected with the reasons
   ├─ review.status = resolved, resolved_by, resolved_at
   ├─ task.status = Pending (flags cleared)
   ├─ run simplify_agent for this task (now approved), build medicine_card if medicine
   ├─ schedule reminders if a due_date now exists
   ├─ notify patient: "An item was reviewed by your doctor"
   └─ audit: resolve_review
```

## 2.7 Background jobs (Celery)

| Job | Schedule | What it does |
|---|---|---|
| `send_due_notifications` | Every 5 minutes | Finds notifications where `scheduled_at <= now` and `sent_at` is null, sends them, sets `sent_at` |
| `missed_task_check` | Every hour | Finds `Pending` tasks with `due_date < today` and no `missed_notified_at`. Creates `missed_task` notifications for family members with `notify_on_miss` **and** consent that allows reminders. Sets `missed_notified_at` |
| `review_aging_check` | Every 30 minutes | Finds open reviews older than a limit, or assigned to an unavailable doctor, and runs the fallback chain |
| `cleanup` | Daily | Removes expired refresh tokens and uploaded temp files |

Notification text comes from templates such as `reminder_due_today` ("You have a task due today. Open the app to view it."). It never contains medical details.

## 2.8 Callback flow (simulated)

```
Patient taps "Request callback" on a task
  → POST /tasks/{id}/callback  → notification(type=callback, status=requested), audit
Management sees it in /mgmt/callbacks
  → POST .../start    → status=connecting, assigns synthetic masks, UI shows "Connecting..."
  → (simulated) both sides see masked numbers only
  → POST .../complete → status=completed, duration_sec stored, audit(callback_completed)
Task gets a "Callback completed" mark
```
The patient must start it. The system never calls anyone on its own. No call content is stored. In production only the telephony adapter in `services/callbacks.py` changes.

## 2.9 Voice (Listen button)
- `GET /tasks/{id}/audio?lang=ta` refuses if the task is `Needs Review`.
- It reads the stored `simple_text` or translation (or the medicine card read out field by field), sends it to ElevenLabs, and returns audio.
- Audio is cached per task and language so repeat listens cost nothing. Nothing new is ever written for voice.

## 2.10 Security hooks in the backend
These come from SECURITY.md and are built into the flow above.

- Passwords: Argon2id. Tokens: 15 minute access, rotating refresh, in httpOnly cookies.
- Upload checks: type by content, size limit, random filename, delete after reading.
- Rate limits on login, upload, flag and callback.
- Every query that takes an id also checks ownership through `patient_view` or the role guard.
- Parameterised queries only. Pydantic on every request body.
- All views and actions go to `audit_log` through one helper.

## 2.11 Environment variables

```
MONGO_URI=            REDIS_URL=
JWT_SECRET=           FIELD_ENC_KEY=
CLAUDE_API_KEY=       CLAUDE_MODEL=
ELEVENLABS_API_KEY=   ELEVENLABS_VOICE_IDS=en:...,ta:...,hi:...
CORS_ORIGIN=          MAX_UPLOAD_MB=5
CONFIDENCE_THRESHOLD=0.70
```

## 2.12 Build order (backend)

| Phase | Build | Done when |
|---|---|---|
| **0. Setup** | Docker Compose, config, Mongo connection, collections with validators and indexes, seed script (synthetic users, doctors, providers, locations) | `docker compose up` starts all six services and the seed loads |
| **1. Auth and access [P1]** | Login, JWT, roles, `crypto.py`, `patient_view`, audit helper | A family user with `reminders` access gets filtered data. A wrong patient id returns 403 |
| **2. Reader and extraction [P1]** | Upload endpoint, reader, extraction agent, schema validation, evidence check | A sample summary produces validated items, each with a source line found in the text |
| **3. Dates and safety gate [P1]** | `dates.py`, all gate rules, partial flags | A summary with a missing dose produces a flagged field and a `review_queue` record |
| **4. Planner and tasks [P1]** | Task creation, timeline endpoint, complete and undo, manual flag, manual entry | Timeline shows tasks in date order with correct statuses |
| **5. Simplify and medicine card [P1]** | Simplify agent for English, medicine template, number and banned-pattern checks | Medicine cards match the source values exactly |
| **6. Doctor review [P1]** | Review router, doctor queue, resolve endpoint, family locked view | Only the assigned doctor can resolve. Task moves to Pending |
| **7. Translation [P2]** | Tamil and Hindi, number check across languages | Same task readable in three languages with matching numbers |
| **8. Providers [P2]** | Locations and providers APIs, geo query, select provider | GPS and drill-down both return 3 to 5 results with the label |
| **9. Family and notifications [P2]** | Family and consent endpoints, Celery jobs, missed-task alert | A missed task alerts only the consenting family member |
| **10. Voice [P3]** | Audio endpoint with cache | Listen works for approved tasks and refuses flagged ones |
| **11. Callback [P3]** | Callback request and management flow (simulated) | Full request to completed cycle logged in audit |
| **12. Fallback and management [P3]** | Aging job, availability, fallback chain, dashboard data | Marking a doctor unavailable moves their open items to the next reviewer |

Test along the way: the five quick tests in SECURITY.md, a unit test per gate rule, and an end-to-end test of the full pipeline using one sample summary.

---

# Part 3. Application flow (frontend)

## 3.1 Screens by role

| Role | Screens |
|---|---|
| **Everyone** | Login, language and role setup, notifications, footer on every screen |
| **Patient** | Home (timeline and checklist), Upload, Processing, Card view, Two-panel view, Task detail, Provider map, Family access, My activity |
| **Family** | Patient picker, Plan view (filtered to their level), Notifications. In elderly mode: the same screens as the patient, acting for them |
| **Doctor** | Review queue, Review detail |
| **Management** | Dashboard (queue and assignments), Doctor availability, Callback requests |

The footer *"This tool organizes your discharge instructions. It does not give medical advice. Ask your doctor about anything unclear."* is part of the shared layout, so it appears on every screen.

## 3.2 Route map

```
/login
/setup                       language and role confirmation (first login)
/patient
   /home                     timeline + checklist
   /upload
   /processing/:summaryId
   /tasks                    card view (default)
   /tasks/panel/:summaryId   two-panel view
   /tasks/:taskId            detail
   /providers/:taskId        map
   /family                   manage access
   /activity                 who viewed my plan
/family
   /patients                 picker
   /plan/:patientId          filtered plan
/doctor
   /queue
   /review/:reviewId
/mgmt
   /dashboard
   /doctors
   /callbacks
```

Routes are protected by role. Wrong-role access redirects to the user's own home.

## 3.3 Main journeys

### A. Patient: first time, upload to plan

| Step | What the user does | What the system does | API |
|---|---|---|---|
| 1 | Logs in, picks language | Saves language, loads the interface in that language | `POST /auth/login`, `PUT /me/language` |
| 2 | Opens Upload, pastes text or chooses a file | Checks type and size in the browser first | none |
| 3 | Taps Upload | Sends it. Shows a progress screen with steps: Reading, Extracting, Checking, Building plan, Simplifying | `POST /patients/{pid}/summaries`, then poll `GET /summaries/{id}/status` every 2 seconds |
| 4a | (success) | Opens the Home screen with the new timeline and a summary: "12 tasks ready, 2 waiting for doctor review" | `GET /patients/{pid}/timeline` |
| 4b | (empty, unreadable or non-medical input) | Shows a clear message and a button to enter tasks by form | status `needs_manual` |
| 5 | Opens the card view | One task at a time, large text in their language. "Show original" reveals the source line | `GET /patients/{pid}/tasks` |
| 6 | Taps Listen | Plays audio of the approved text | `GET /tasks/{id}/audio` |
| 7 | Taps "Find a provider" on a referral | Opens the map | see journey C |
| 8 | Ticks a task | Status turns green. Timeline updates | `POST /tasks/{id}/complete` |

### B. Needs Review items (what the user sees)

- The card is **orange, grayed out and locked**, with the text "Waiting for doctor review" and the short reason.
- Listen and Complete are disabled on it. Only "Request callback" and "Flag" stay available.
- When the doctor resolves it, the patient gets a notification, and the card turns blue (Pending) with the approved wording.
- A patient or family member can also flag any normal card with a short note.

### C. Provider map

1. The user taps "Find a provider" on a task. The specialty is already filled in from the task.
2. The browser asks for location permission.
   - **Allowed:** the app calls `GET /providers?specialty=&lat=&lng=`.
   - **Denied:** the app shows State, District and Area dropdowns (loaded from `/locations/*`) and calls the fallback search.
3. Leaflet shows pins: blue for hospitals, green for clinics.
4. Tapping a pin shows a provider card with name, facility, distance and contact, and the permanent label *"Suggestion only, not a guarantee of availability or suitability"*.
5. "Select this provider" calls `POST /tasks/{id}/provider`. The card on the task now shows the chosen provider, still labelled as a suggestion.

### D. Family member

1. Logs in and sees the patients they are linked to.
2. Opens a plan. The screen shows only what their access level allows.
   - `full`: all tasks, two-panel view available to verify extraction.
   - `appointments`: appointments, tests and referrals only.
   - `reminders`: titles, dates and statuses only.
3. Needs Review items appear locked as "Waiting for doctor review".
4. Receives reminders and missed-task alerts (if they are the designated member).
5. They can flag a task and, if allowed, request a callback.

**Elderly mode:** when the patient has marked a family member as operator, that person sees the patient's full interface with a small banner "You are helping [patient name]". Every action is recorded with both names.

### E. Patient manages family access

1. Opens Family, taps Add member, and fills in name, relationship and login.
2. Chooses an access level (`full`, `appointments`, `reminders`) and whether this person operates the account and gets missed-task alerts.
3. Can change or remove access at any time. Removal takes effect right away.
4. Opens Activity to see who viewed the plan and when.

### F. Doctor review

1. Opens the queue: items assigned to them, oldest first, each with its reason tag.
2. Opens an item and sees the **source line** from the summary, the flagged fields highlighted, and the reason in plain words.
3. Chooses **Confirm** (the item is fine as extracted) or **Correct** (a form to enter the missing or fixed values).
4. Saves. If the correction still fails a gate rule, the screen shows why. Otherwise the item is closed and returns to the patient as Pending.
5. Cannot assign themselves or see items assigned to others.

### G. Management

1. Dashboard shows open reviews with age, reason code and assignee. No clinical text is shown.
2. Assigns or reassigns a doctor. Marks a doctor unavailable, and the items move along the fallback chain.
3. Sees callback requests, starts the simulated call, and ends it (duration is logged).

### H. Callback

Patient taps "Request callback" on a card, a confirmation says "The hospital will call you. Your number stays private." Management sees it and starts it. The patient sees a "Connecting..." screen with a masked number, then a "Callback completed" mark on the task.

## 3.4 The two task views

| | Card view (default) | Two-panel view |
|---|---|---|
| For | Patients and elderly users | Family verifying extraction |
| Layout | One large card at a time | Left: original summary with colored highlights. Right: generated tasks |
| Highlight colors | n/a | Appointments blue, medicines yellow, warnings red |
| Evidence | "Show original" expands the source line | Click a task to scroll to and flash its highlight, using `source_span` |
| Elderly emphasis | Listen and Callback buttons sit at the **top** of the card, large | n/a |

A toggle switches between them. The medicine card always uses the fixed layout: **Medicine name / Dose / Timing / Duration / Special instructions**.

## 3.5 Card states

| Status | Color | Behaviour |
|---|---|---|
| Pending | Blue | Can complete, listen, flag, request callback |
| Completed | Green | Can undo |
| Needs Review | Orange | Locked and grayed out. "Waiting for doctor review" |

Every card shows: the simple text in the chosen language, date, status badge, reminder, provider suggestion (if any, with its label), and the Listen and Callback buttons.

## 3.6 Frontend structure

```
frontend/src/
  app/            router, layout (header, footer disclaimer), role guards
  api/            one function per endpoint, shared fetch with cookies
  features/
    auth/  upload/  processing/  tasks/  timeline/  providers/
    family/  review/  management/  notifications/
  components/     TaskCard, MedicineCard, StatusBadge, SourceLine, Footer,
                  ProviderMap (react-leaflet), LanguagePicker, ErrorState
  i18n/           en.json, ta.json, hi.json (+ te, kn, ml later)
  styles/         Tailwind, Noto Sans fonts for Tamil and Devanagari
```

Rules for the frontend:
- Server data goes through React Query. Auth and language live in context.
- Large text and high contrast by default. Buttons at least 48 px tall.
- All interface labels come from the language files, including the medicine card labels.
- Extracted text is always rendered as plain text, never as HTML.
- Every error state is visible and offers a next step (retry, manual entry, contact support).

## 3.7 End to end example (synthetic)

Input text:

```
Discharge date: 02 Nov 2026
1. Follow up with cardiologist in 2 weeks.
2. Tab. Metformin 500 mg twice daily for 30 days after food.
3. Fasting blood sugar test on Day 7.
4. Change wound dressing every 48 hours.
5. Seek immediate care if chest pain or breathlessness occurs.
6. Tab. Aspirin once daily. Continue as advised.
```

What the system produces:

| # | Type | Due date | Status | Why |
|---|---|---|---|---|
| 1 | appointment | 16 Nov 2026 | Pending | Date resolved by code. Provider needed: Cardiology |
| 2 | medicine | 02 Nov 2026 start | Pending | Medicine card: Metformin / 500 mg / Twice daily / 30 days / After food |
| 3 | test | 09 Nov 2026 | Pending | "Day 7" resolved from discharge date |
| 4 | care_instruction | recurring | Pending | Rewritten simply, source line kept |
| 5 | warning_sign | none | Pending | Shown as a plain alert, not flagged |
| 6 | medicine | none | **Needs Review** | `MISSING_DOSE`, `MISSING_DURATION`, `AMBIGUOUS_DATE` ("as advised") |

The patient sees 5 clear tasks and 1 locked card. The assigned doctor sees item 6 with its source line and the three reasons. The doctor fills in the details, the gate re-checks them, and the card turns blue for the patient.

---

## Notes on choices

- **Neo4j for access paths only.** Mongo stores consent and assignment records; the graph mirrors them as IDs and is the source for the access check, which lives in one function, `check_access` (this document's `patient_view` sketch). Doctor ids are user ids.
- **One extra collection:** `locations` (needed for the State, District, Area drill-down) and a small `refresh_tokens` helper. Everything else matches the PRD data model.
- **Callbacks** are stored in `notifications`, as the Tech Stack says, with every step in `audit_log`.
- **Contradictions in the PRD** are resolved the same way as Tech_Stack.md section 10: top 3 to 5 providers, State, District and Area drill-down, callbacks started by the patient or the family member operating their account.
