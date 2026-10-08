> **Update (Oct 2026):** the backend now runs on **SQLite** (one file, `backend/data/discharge.db`). MongoDB, Neo4j, Redis and Celery are no longer used; read their mentions below as history. Plans are drafts for the matched doctor until published. Current details: `backend/README.md` and `docs/DATA_MODEL.md`.

# Tech Stack PRD: Agentic Hospital Discharge & Follow-up Coordinator

Aligned to the Updated PRD (Acentra Hackathon). One choice per layer. Synthetic data only.

## 1. What changed from the earlier stack

| Area | Earlier stack | Corrected to match the PRD | PRD ref |
| --- | --- | --- | --- |
| Roles | Patient, **Manager**, Family, Doctor, Management | Four roles only: Patient, Family Member, Doctor Reviewer, Management. Elderly mode is a family member operating the patient's account with patient-granted access, not a separate role | §2 |
| Languages | Six languages, all equal | English, Tamil, Hindi are demo-polished. Telugu, Kannada, Malayalam are stretch goals | §1 |
| Provider matching | Missing | Added: code agent (DB query + proximity sort), Leaflet.js map, browser GPS with State, District, Area fallback | §7 |
| Map | Missing | Leaflet.js with OpenStreetMap tiles, no API key | §7 |
| Safety gate | Missing dates or doses, symptoms, medicine changes | Full rule set: missing or ambiguous date, dose, timing or doctor name; symptom or what-should-I-do-if text; medicine change, stop order or clash; confidence below 70%; uncategorised text. Also partial (field-level) flagging and user-triggered flags | §5 |
| Seven item types | Mentioned, not named | Named: appointments, tests, referrals, medicines, care instructions, dates, warning signs | §4 |
| Orchestration | Missing | FastAPI orchestrator calling nine agents as plain functions. Only two agents use an AI model | Agent Architecture |
| Neo4j | Family hub, consent, doctor primary and fallback | **Kept, IDs and relationships only** (decision made at build time, following SECURITY.md). It answers one question: is there an allowed path from this user to this patient, and at what level. MongoDB holds all content. See backend/README.md | SECURITY §5.3, §6.2 |
| Encryption at rest | Missing | Added: application-level field encryption for patient and family data | §8 |
| Audit log | Listed as a collection | Append-only, logs every view and action, plus callback logs (who, when, duration, no content) | §2, §8, §11 |
| Scheduling | Celery + Redis | Celery worker plus **Celery beat** for missed-task alerts | Agent Architecture |
| Callback | Simulated with synthetic numbers | Same, now with the full flow: request, queue, route, connect, log. Twilio is production only | §11 |
| Deployment | FastAPI, MongoDB, Neo4j, Redis, React | Backend services: api, worker, beat, redis. MongoDB Atlas and Neo4j Aura are hosted. Frontend comes later | n/a |

## 2. Final tech stack

| Layer | Choice | Used for |
| --- | --- | --- |
| **Frontend** | React + Vite + Tailwind CSS, react-leaflet, react-i18next | Sign-in, upload or paste screen, card view and two-panel view, checklist, timeline, doctor review queue, management dashboard, provider map, permanent safety footer on every screen |
| **Map** | Leaflet.js with OpenStreetMap tiles | Provider pins (hospitals blue, local clinics green), provider card with Select this provider |
| **Backend** | Python + FastAPI (Pydantic models) | All APIs and the orchestrator that runs the pipeline step by step |
| **File input** | FastAPI upload + pdfplumber, plus pasted text | Accepts PDF or text and extracts the text. Blank, unstructured or non-medical input returns a clear error and opens manual entry |
| **AI extraction** | Claude API, JSON-schema output validated by Pydantic | Finds the seven item types. Each item carries its exact source line and a confidence score |
| **Safety gate** | Python rule engine, no AI | Marks each item or field Pending or Needs Review using the fixed rules in section 5 |
| **Plain language and translation** | Claude API for care instructions and warning signs; **fixed template** for medicines | Simple wording in English, Tamil and Hindi (Telugu, Kannada, Malayalam as stretch). Medicine lines are never reworded |
| **Voice** | ElevenLabs API (text-to-speech only) | Listen button. Reads stored, approved text only and never generates new wording |
| **Provider matching** | Python code agent + MongoDB geo query | Specialty plus location filter, ranked by proximity |
| **Database** | MongoDB (Motor async driver) | Users, family members, consent, summaries, tasks, evidence, review queue, doctors, providers, notifications, audit log |
| **Authentication** | JWT + role-based access control | Four roles, enforced on every endpoint |
| **Consent check** | FastAPI dependency reading the Consent collection | Runs on every request to view a plan and returns only what the patient allowed |
| **Reminders and alerts** | Celery + Celery beat + Redis | Scheduled reminders, missed-task alerts to the designated family member, hub notifications |
| **Callback** | Simulated in the app, synthetic masked numbers | Masked-number screen and Connecting state. Twilio is a production layer only |
| **Deployment** | Docker Compose | One command runs frontend, api, worker, beat, mongo and redis |

## 3. Agents and how each maps to the stack

One orchestrator, called as plain FastAPI functions. LangGraph is the PRD's alternative, but a Needs Review item already pauses the flow as saved task state in MongoDB, so no long-running process has to wait for the doctor.

| Agent | Job | Type | Built with |
| --- | --- | --- | --- |
| Orchestrator | Runs steps in order, routes unclear items, waits for human review | Light logic | FastAPI |
| Extraction | Pulls seven item types with source lines | **AI** | Claude API |
| Safety gate | Pending or Needs Review | Fixed rules, not AI | Python rule engine |
| Planner | Items to tasks, dates, reminders, timeline | Code | Python |
| Simplify and translate | Plain language and chosen language, template for medicines | **AI** | Claude API + template |
| Provider matching | Specialty and location match, renders map | Code | MongoDB query + Leaflet.js |
| Review routing | Assigns doctor, reroutes if unavailable | Code | Python + MongoDB |
| Notification | Reminders to patient and family, callback request trigger | Code | Celery + Redis |
| Task scheduler | Fires missed-task alerts | Code | Celery beat |

## 4. How it connects

1. **Sign in.** The user picks a language and role. JWT carries the role. Family members are added by the patient with an access level: full, appointments only, or reminders only.
2. **Upload.** React sends the file or pasted text to FastAPI. pdfplumber extracts text. Blank, non-medical or unreadable input stops here with a visible error and a manual entry form. Scanned PDFs without a text layer are treated as unreadable because there is no OCR.
3. **Extract.** Claude returns the seven item types as JSON. Pydantic validates it. Each item stores its exact source line and confidence.
4. **Safety gate.** The rule engine checks every item, including manual entries. Unclear fields are flagged individually so clean fields keep moving.
5. **Build plan.** The planner saves tasks in MongoDB with date, status, reminder and timeline position. Flagged items create Review Queue records with a visible reason.
6. **Explain simply.** Claude rewrites care instructions and warnings, then translates. Medicine lines use the fixed template. The source line stays beside every rewrite.
7. **Suggest providers.** Referrals are matched to synthetic providers by specialty and location, then shown on the map with the label Suggestion only, not a guarantee of availability or suitability.
8. **Doctor review.** The review routing agent assigns a doctor. If that doctor is unavailable, the item moves to the next assigned reviewer, controlled by management. Only a doctor can close a Needs Review item.
9. **Follow through.** Celery sends reminders to the patient and, with consent, to family. Celery beat alerts the designated family member when a Pending task passes its due date.
10. **Output.** The patient sees timeline, checklist, reminders and the evidence behind each item. Listen reads approved text through ElevenLabs on request.

## 5. Safety gate rules (Python rule engine)

An item or field becomes **Needs Review** if any of these is true:

- Date, dose, timing or doctor name is missing or ambiguous
- It describes a symptom or contains a what-should-I-do-if question
- It involves a medicine change, a stop order, or a clash between two instructions
- Extraction confidence is below 70%
- The text fits no known extraction category

Additional rule for grounding: the stored source line must appear verbatim in the uploaded summary. If it does not, the item is flagged, because model-reported confidence alone is not a reliable signal.

Hard rules enforced in code:

- The gate never auto-resolves a Needs Review item
- Only the Doctor Reviewer role can close one, and the endpoint rejects every other role
- Patients and family members can flag any item manually at any time
- Family sees flagged items as Waiting for doctor review, locked and grayed out
- Complete extraction failure routes the item to Needs Review and prompts re-upload or manual entry
- The system fails visibly and never silently

## 6. Data layer (MongoDB only)

**Collections:** users, family\_members, consents, discharge\_summaries, tasks, review\_queue, doctors, providers, notifications, audit\_log. These match the PRD data model.

- **Neo4j holds IDs and relationships only** (consent path, doctor assignment, `NEXT_FALLBACK` chain). Mongo documents still record the same facts as the source of content; the graph is checked on every access.
- **Callbacks** are stored as notification records of type callback, with each step written to the audit log. The PRD defines no separate callback table.
- **Providers** use a 2dsphere index on synthetic coordinates for proximity ranking. Fields: name, specialty, facility, city or area, coordinates, distance, contact, type (hospital or local clinic).
- **Encryption at rest:** AES-GCM field encryption (Python cryptography library) on raw\_text, source\_line, simple\_text, translated\_text and family contact details. The key lives in the backend environment only. Use an encrypted volume for the MongoDB data directory as a second layer.
- **Audit log is append-only:** the API exposes no update or delete route, and the database user for this service has insert and read permissions only. Every view and action is logged, including who called, when, and duration for callbacks, with no call content.

## 7. Security, privacy and constraints

- Claude and ElevenLabs API keys live on the backend only, never in the React bundle
- RBAC is enforced on every endpoint, and the consent check runs on every request to view a plan
- Elderly mode: the patient owns the account and a family member operates it through patient-granted full access. Audit entries record the family member as actor and the patient as target
- Family members cannot edit instructions or resolve Needs Review. Management cannot change clinical content
- Location: browser GPS coordinates are used for the query and are not persisted. If permission is denied, the user picks State, District and Area manually
- Every record, provider and phone number is synthetic. Contact numbers use the +91-XXXXX-XXXXX format
- The footer *This tool organizes your discharge instructions. It does not give medical advice. Ask your doctor about anything unclear.* is rendered by the shared layout component, so it appears on every screen
- Provider suggestions always carry the label *Suggestion only, not a guarantee of availability or suitability*
- Medicine content is never freely rewritten: Medicine name, Dose, Timing, Duration, Special instructions
- Fonts: Noto Sans variants for Tamil and Devanagari, with Telugu, Kannada and Malayalam added for the stretch languages

## 8. Deployment (Docker Compose)

| Service | Role |
| --- | --- |
| frontend | React + Vite build |
| api | FastAPI orchestrator and all endpoints |
| worker | Celery worker for reminders and notifications |
| beat | Celery beat for scheduled and missed-task checks |
| mongo | MongoDB |
| redis | Celery broker |

Secrets (Claude key, ElevenLabs key, JWT secret, field-encryption key) come from a backend-only `.env` file.

## 9. Build order mapped to the stack

| Priority | Feature | Stack pieces |
| --- | --- | --- |
| **P1** | Upload, extract seven types with evidence, safety gate, tasks and timeline, plain-language rewrite | FastAPI, pdfplumber, Claude, rule engine, MongoDB, React |
| **P1** | Doctor reviewer queue | MongoDB review\_queue, RBAC, audit log |
| **P2** | Language selection and translation (English, Tamil, Hindi) | Claude, react-i18next, medicine template |
| **P2** | Provider suggestions with GPS | MongoDB geo query, Leaflet.js |
| **P2** | Card and two-panel views, family access and notifications | React, consent check, Celery + Redis |
| **P3** | Listen button | ElevenLabs |
| **P3** | Request callback | Notification agent, simulated masked-number UI |
| **P3** | Fallback routing, management dashboard | Review routing agent, management role |

Get P1 fully working first. A clean end-to-end P1 demo beats a broken P3 feature.

## 10. Points in the PRD to confirm

The updated PRD contradicts itself in a few places. This document uses the choice shown, so change it if you decide otherwise.

1. **Provider results:** Section 7 says both top 3 and top 3 to 5. Used: 3 to 5, ranked by proximity.
2. **Location fallback:** Section 7 describes both a State, District, Area drill-down and a single city dropdown. Used: the drill-down.
3. **Who can request a callback:** Section 2 lets family trigger it on missed tasks, while Section 11 says the patient must initiate. Used: the patient or a family member operating their account, and never the system on its own.
4. **Warning signs versus the symptom rule:** warning signs naturally describe symptoms, so a literal reading would flag every one. Used: flag only when the text is a symptom description with a what-should-I-do-if question, or when other gate rules fail. Warning signs with clear wording are displayed as plain-language alerts.
5. **Section numbering:** Section 11 appears before Section 10. This is cosmetic.
