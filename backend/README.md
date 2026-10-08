# Backend: Discharge & Follow-up Coordinator

FastAPI + MongoDB only. Synthetic data only. Model calls use Groq (`groq_api_key`, `GROQ_MODEL`); `CLAUDE_API_KEY` is an optional fallback.

## Run

```bash
cd backend
python -m pip install -r requirements.txt
cp .env.example .env                       # fill it in; the real .env is git-ignored
python -m scripts.seed_demo --reset        # wipes the database, loads people, hubs, providers, uploads the 5 samples
uvicorn app.main:app --port 8000
python -m scripts.dev_server               # no Atlas, no model: in-memory demo on :8000
python -m pytest                           # 113 tests, in-memory database, no network
python -m scripts.db_check                 # connection, collections, encrypted round trip
python -m scripts.verify_samples [--live]  # pipeline vs sample_data/discharge_template/expected.json
```

`GET /health` returns `{"db":"ok"}` or 503. Background jobs (reminders, missed-task alerts, review aging) run in the API
process every 60 seconds and take a lease in `job_locks` first, so several API processes are safe.

Required secrets: `MONGO_URI`, `MONGO_DB`, `JWT_SECRET` (32+ chars), `FIELD_ENC_KEY` (base64 of 32 bytes). Optional: `ELEVENLABS_*` (Listen is hidden behind a clear message when voice ids are unset).

## Layout

`app/core` config, db, security, audit, jobs. `app/pipeline` reader, extraction, dates, safety gate, planner, simplify, review routing. `app/modules/*` one router (+ service) per area. See `docs/DATA_MODEL.md`.

## Safety core (unchanged rules)

Fixed-rule safety gate, exact source-line evidence, code-only dates, fixed medicine card, rewrite checks, and a coverage check:
every numbered line in the actionable template sections must be accounted for, or it becomes a visible Needs Review item.
Family never sees a Needs Review item, only "Waiting for doctor review".
