# Backend: Discharge & Follow-up Coordinator

FastAPI + SQLite (Python's built-in `sqlite3`, no database server). Synthetic data only. Model calls use Groq
(`groq_api_key`, `GROQ_MODEL`); `CLAUDE_API_KEY` is an optional fallback. With no model at all, a rule-based reader
still builds every plan.

## Run

```bash
cd backend
python -m pip install -r requirements.txt
cp .env.example .env                       # fill in JWT_SECRET and FIELD_ENC_KEY; the real .env is git-ignored
python -m scripts.seed_demo --reset        # wipes data/discharge.db, loads people, hubs, providers, uploads the 5 samples
python -m scripts.seed_demo --reset --publish   # same, and each matched doctor publishes their plan (demo shortcut)
uvicorn app.main:app --port 8000
python -m scripts.dev_server               # in-memory demo on :8000, no model calls (add --publish to skip review)
python -m pytest                           # 154 tests, in-memory SQLite, no network
python -m scripts.db_check                 # opens the file, lists tables, encrypted round trip, unique-key check
python -m scripts.verify_samples [--live | --rules]   # pipeline vs sample_data/discharge_template/expected.json
```

The database is one file, `backend/data/discharge.db` (set `SQLITE_PATH` to move it; `:memory:` for a throwaway one).
It is created on first start. Back it up by copying the file while the API is stopped.

`GET /health` returns `{"db":"ok"}` or 503. Background jobs (reminders, missed-task alerts, review and plan aging) run
in the API process every 60 seconds and take a lease in `job_locks` first.

Required secrets: `JWT_SECRET` (32+ chars), `FIELD_ENC_KEY` (base64 of 32 bytes). Optional: `ELEVENLABS_*` (Listen is
hidden behind a clear message when voice ids are unset). Old `MONGO_*`, `NEO4J_*` and `REDIS_URL` values are ignored.

## Plan workflow

1. Patient (or a family manager with full consent) uploads or pastes a summary.
2. **Doctor matching** (code, `app/pipeline/doctor_match.py`): the Attending Physician named on the summary, else the
   patient's existing doctor, else the attending's specialty, else the least busy doctor. An unavailable doctor hands
   over along the admin-controlled fallback chain.
3. **Draft plan**: extraction (AI, or `rule_extractor.py` when the model is missing or fails), evidence check, dates,
   fixed-rule safety gate, planner, plain language and translation. Every task is `published: false`.
4. The matched doctor opens **Plans to review** (`/plans`): edits any item, confirms or corrects flagged items, removes
   or adds items. Every change re-runs the safety gate and is kept in `task_revisions`.
5. **Publish** (`POST /plans/{id}/publish`): blocked while items are flagged, unless the doctor chooses to keep them in
   review. Only now do the patient and family see the plan and do reminders start.
6. After publishing, a patient or family flag goes to the same doctor's review queue, as before.

The patient, family, jobs and statistics never read an unpublished task. The admin desk sees plan routing
(`/admin-api/plans`) by patient code only and can hand a draft, with its flagged items, to another doctor.

## Layout

`app/core` config, SQLite store (`store.py`), db rules, security, audit, jobs. `app/pipeline` reader, extraction,
rule extractor, doctor matching, dates, safety gate, planner, simplify, review routing. `app/modules/*` one router
(+ service) per area, `plans` is the doctor's plan editor. See `docs/DATA_MODEL.md`.

## Safety core (unchanged rules)

Fixed-rule safety gate, exact source-line evidence, code-only dates, fixed medicine card, rewrite checks, and a coverage
check: every numbered line in the actionable template sections must be accounted for, or it becomes a visible Needs
Review item. A medicine is flagged whenever any other line talks about changing it (an injected or second order).
Family never sees a Needs Review item, only "Waiting for doctor review".
