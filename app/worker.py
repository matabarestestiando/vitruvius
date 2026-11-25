import asyncio
from celery import Celery
from .config import settings
from .db import Session, Record, Chunk
from .knowledge import spaces, extract, index_document, cleanup

celery = Celery("vitruvius", broker=settings.redis_url, backend=settings.redis_url)
celery.conf.update(
    worker_concurrency=1,
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    task_ignore_result=True,
    beat_schedule={"expire-context": {"task": "context.expire", "schedule": 60.0}},
)


@celery.task(name="context.expire")
def expire_context():
    if Session:
        with Session() as db:
            return cleanup(db)


@celery.task(name="context.ingest", soft_time_limit=270, time_limit=300)
def ingest(document_id):
    if not Session:
        return
    with Session() as db:
        from sqlalchemy import select

        doc = db.scalar(
            select(Record).where(Record.id == document_id).with_for_update()
        )
        if not doc or doc.kind != "context" or doc.data["status"] != "queued":
            return
        try:
            s3 = spaces()
            obj = s3.get_object(
                Bucket=settings.spaces_bucket, Key=doc.data["object_key"]
            )
            if obj["ContentLength"] > 20 * 1024 * 1024:
                raise ValueError("size")
            content = obj["Body"].read(20 * 1024 * 1024 + 1)
            pages = extract(content, doc.data["content_type"])
            total = sum(len(t) for _, t in pages)
            if not total or total > 2000000:
                raise ValueError("Texto vacío o demasiado extenso")
            for page, value in pages:
                for i in range(0, len(value), 2400):
                    db.add(
                        Chunk(
                            document_id=doc.id,
                            text=value[i : i + 2800],
                            page=page,
                            embedding=None,
                        )
                    )
            db.flush()
            asyncio.run(index_document(db, doc))
            doc.data = {**doc.data, "status": "ready"}
            db.commit()
        except Exception:
            db.rollback()
            doc = db.get(Record, document_id)
            if doc:
                doc.data = {
                    **doc.data,
                    "status": "failed",
                    "error": "No se pudo procesar: revise formato, tamaño y configuración",
                }
                db.commit()
