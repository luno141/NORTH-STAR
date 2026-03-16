from app.db.session import SessionLocal
from app.models.models import IngestionSource
from app.services.federation import run_federation
from app.services.ingestion import ingest_rss
from app.services.live_feeds import get_due_ingestion_sources, run_ingestion_source
from app.tasks.worker_app import celery_app


@celery_app.task(bind=True)
def run_federation_job(self):
    db = SessionLocal()
    try:
        shared, details = run_federation(db)
        return {"shared": shared, "details": details, "task_id": self.request.id}
    finally:
        db.close()


@celery_app.task(bind=True)
def run_rss_job(self, org_id: int, contributor_id: int | None = None):
    db = SessionLocal()
    try:
        count = ingest_rss(db=db, org_id=org_id, contributor_id=contributor_id)
        return {"created": count, "task_id": self.request.id}
    finally:
        db.close()


@celery_app.task(bind=True)
def run_ingestion_source_job(self, source_id: int, trigger: str = "scheduler"):
    db = SessionLocal()
    try:
        source = db.query(IngestionSource).filter(IngestionSource.id == source_id).first()
        if not source:
            return {"source_id": source_id, "status": "missing", "created": 0, "task_id": self.request.id}
        return run_ingestion_source(db, source, trigger=trigger, task_id=self.request.id)
    finally:
        db.close()


@celery_app.task(bind=True)
def run_due_ingestion_sources_job(self, org_id: int | None = None):
    db = SessionLocal()
    try:
        queued: list[dict[str, object]] = []
        for source in get_due_ingestion_sources(db, org_id=org_id):
            result = run_ingestion_source_job.delay(source.id, "scheduler")
            queued.append(
                {
                    "source_id": source.id,
                    "name": source.name,
                    "task_id": result.id,
                }
            )
        return {"queued": len(queued), "sources": queued, "task_id": self.request.id}
    finally:
        db.close()
