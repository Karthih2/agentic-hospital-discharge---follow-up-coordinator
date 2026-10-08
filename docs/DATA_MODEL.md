# Data model (SQLite)

One SQLite file (`backend/data/discharge.db`, `SQLITE_PATH`). Every collection is a table
`c_<name>(id TEXT PRIMARY KEY, doc TEXT)` holding the record as JSON; `app/core/store.py` gives the code a small
document API (find, update with `$set`/`$push`/`$inc`, conditional updates). Field rules and unique keys live in
`backend/app/core/db.py` (`RULES`) and are checked on every write. Writes run in `BEGIN IMMEDIATE` transactions, so a
conditional update ("only if still Pending", "only if still a draft") is atomic, also across processes.
Every record carries `schema_version` (now 2). Clinical and personal fields are AES-GCM encrypted (`v1:...`).
Ids are 24-character, time-ordered hex strings (`app/core/ids.py`).

| Table | Pattern | Why |
|---|---|---|
| `tasks` | Polymorphic | One table, `type` discriminator (appointment, test, referral, medicine, care_instruction, date, warning_sign); type-specific values sit in `fields`. `published` is false while the plan is a doctor's draft; `doctor_edited` marks a doctor's change. |
| `discharge_summaries` | Subset | Also the plan record: `plan_status` (generating, draft, published), `plan_doctor_id`, `plan_match` (reason, attending, history), `published_at`, `extraction_method` (model or rules). List screens skip `raw_text`. |
| `review_queue` | Extended Reference | `snapshot` holds task type, reason codes, patient code and date, so queues need no joins. `plan_draft` marks items of an unpublished plan (handled in the plan editor). |
| `patient_stats` | Computed | Pending, Completed, Needs Review counts and next due date per patient, published tasks only. |
| `audit_log` | Bucket | One record per actor per day, `events` capped at 200, then a new bucket (`seq`). Events are hash-chained. |
| `task_revisions` | Document Versioning | Previous values of every doctor correction, plan edit (`kind: plan_edit`) and removal (`kind: plan_remove`). |
| `locations` | Tree | State > District > Area with an `ancestors` array for the drill-down. |
| `providers` | Attribute | `attributes: [{k, v}]` (language, facility_type). All `synthetic: true`. |
| all | Schema Versioning | `schema_version` on every record; `scripts/migrate.py`. |

Hub model: `family_hubs`, `hub_members` (manager, patient, viewer), `consents` (patient, grantee, hub, level),
`hub_invites`, `notifications` (template keys only; `plan_ready` for the doctor, `plan_published` for patient and
family). Every task and summary has one `patient_id`, so plans never mix. `job_locks` holds one lease per job.
`doctors` holds specialty, availability, `assigned_patient_ids` and the `fallback_doctor_id` chain.

Rate limits are kept in process memory (`core/security/ratelimit.py`).
