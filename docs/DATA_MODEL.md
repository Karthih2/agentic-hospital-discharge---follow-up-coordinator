# Data model (MongoDB only)

Validators and indexes live in `backend/app/core/db.py`. Every document carries `schema_version` (now 2);
`python -m scripts.migrate` upgrades older ones. Clinical and personal fields are AES-GCM encrypted (`v1:...`).

| Collection | Pattern | Why |
|---|---|---|
| `tasks` | Polymorphic | One collection, `type` discriminator (appointment, test, referral, medicine, care_instruction, date, warning_sign); type-specific values sit in `fields` (medicine incl. route, appointment time, location, phone). One query lists a patient's whole plan. |
| `review_queue` | Extended Reference | `snapshot` holds task type, reason codes, patient code and created date, so the doctor queue and admin routing list need no joins. Clinical text is never copied. |
| `patient_stats` | Computed | Pending, Completed, Needs Review counts and next due date per patient, recomputed on every task status change. Hub cards and the admin overview read this one document. |
| `discharge_summaries` | Subset | List screens project away `raw_text`, `header`, `diagnoses`, `notices`; raw text loads only on the summary view. |
| `audit_log` | Bucket | One document per actor per day, `events` capped at 200, then a new bucket (`seq`). Events are hash-chained inside a bucket. |
| `task_revisions` | Document Versioning | A doctor correction stores the previous values here (task keeps its `supersedes` link for manual replacements). |
| `locations` | Tree | State > District > Area with an `ancestors` array for the drill-down. |
| `providers` | Attribute | `attributes: [{k, v}]` (language, facility_type), compound index on `attributes.k, attributes.v`. |
| all | Schema Versioning | `schema_version` on every document; `scripts/migrate.py`. |

Hub model: `family_hubs` (name, manager), `hub_members` (hub, user, role manager|patient|viewer), `consents`
(patient, grantee, hub, level, granted_by, guardian_consent, revoked_at; closed records are kept as history),
`hub_invites` (manager asks a patient by code; the patient or guardian answers), `notifications` (template keys only).
Every task and summary has one `patient_id`, so plans never mix. `job_locks` holds one lease per background job.

Rate limits: kept in process memory (`core/security/ratelimit.py`). Use a Mongo TTL collection if you run several API workers.
