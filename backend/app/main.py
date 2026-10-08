import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core import jobs
from app.core.db import get_db, init_db
from app.modules.admin import router as admin
from app.modules.auth import router as auth
from app.modules.hubs import router as hubs
from app.modules.notifications import router as notifications
from app.modules.providers import router as providers
from app.modules.review import router as review
from app.modules.summaries import router as summaries
from app.modules.tasks import router as tasks

log = logging.getLogger("app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.validate_secrets()
    loop = None
    if not settings.skip_init:
        try:
            await init_db()
        except Exception:
            log.warning("Database initialization failed; starting API in degraded mode until MongoDB is reachable.",
                        exc_info=True)
        else:
            loop = asyncio.create_task(jobs.run_loop())  # reminders, missed-task alerts, review aging (leased, idempotent)
    yield
    if loop:
        loop.cancel()


app = FastAPI(title="Discharge & Follow-up Coordinator API", lifespan=lifespan,
              docs_url=None, redoc_url=None, openapi_url=None)  # no public schema in the demo build

app.add_middleware(CORSMiddleware, allow_origins=[settings.cors_origin], allow_credentials=True,
                   allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
                   allow_headers=["Content-Type", "X-CSRF-Token"])


@app.middleware("http")
async def security_headers(request: Request, call_next):
    resp = await call_next(request)
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "no-referrer"
    resp.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
    resp.headers["Cache-Control"] = "no-store"
    return resp


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    # field names only; never echo the submitted values back
    fields = [".".join(str(p) for p in e["loc"][1:]) or e["loc"][0] for e in exc.errors()]
    return JSONResponse({"detail": "Invalid request", "fields": fields}, status_code=422)


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    log.error("unhandled %s on %s", type(exc).__name__, request.url.path)  # type only, no stack to the user
    return JSONResponse({"detail": "Something went wrong"}, status_code=500)


for r in (auth, hubs, summaries, tasks, providers, review, admin, notifications):
    app.include_router(r.router)


@app.get("/health")
async def health():
    """No auth, no data: only whether the database answers."""
    try:
        await asyncio.wait_for(get_db().command("ping"), timeout=5)
    except Exception:
        return JSONResponse({"db": "down"}, status_code=503)
    return {"db": "ok"}
