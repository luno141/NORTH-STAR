import logging
import time

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from app.api.routes import router
from app.core.config import settings
from app.core.observability import RequestContextMiddleware, configure_logging
from app.db.migrations import run_schema_migrations
from app.db.session import SessionLocal, engine
from app.models.models import Base
from app.seed.seed_data import seed_all


configure_logging()
logger = logging.getLogger(__name__)

app = FastAPI(title="Federated Threat Intelligence Integrity", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestContextMiddleware)


@app.on_event("startup")
def on_startup() -> None:
    deadline = time.monotonic() + settings.db_startup_timeout_seconds
    last_error: OperationalError | None = None

    while time.monotonic() < deadline:
        try:
            with engine.begin() as conn:
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
            break
        except OperationalError as exc:
            last_error = exc
            logger.warning(
                "Database not ready during startup; retrying in %.1fs",
                settings.db_startup_retry_interval_seconds,
            )
            time.sleep(settings.db_startup_retry_interval_seconds)
    else:
        raise last_error or RuntimeError("Database did not become ready during startup")

    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        run_schema_migrations(db)
        seed_all(db)
    finally:
        db.close()


app.include_router(router)
