import asyncio
import shutil, tempfile
from pathlib import Path
from celery import Celery
from .config import settings
from .db import Session, Record, Chunk
from .knowledge import spaces, extract, index_document, cleanup

celery = Celery("vitruvius", broker=settings.redis_url, backend=settings.redis_url)
celery.conf.imports = ("app.reference_worker",)
celery.conf.update(
    worker_concurrency=1,
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    task_ignore_result=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    beat_schedule={"expire-context": {"task": "context.expire", "schedule": 60.0}},
)


@celery.task(name="context.expire")
def expire_context():
    # This worker is single-concurrency: cleanup cannot race an active import.
    for directory in Path(tempfile.gettempdir()).glob("vitruvius-ingest-*"):
        if directory.is_dir() and not directory.is_symlink():
            shutil.rmtree(directory, ignore_errors=True)
    if Session:
        with Session() as db:
            return cleanup(db)


@celery.task(name="context.ingest", soft_time_limit=3300, time_limit=3600)
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
        from .processing import Progress,extract_for_ingestion
        progress=Progress(document_id)
        try:
            progress("downloading")
            # A retry never accumulates duplicate excerpts from an interrupted extraction.
            from sqlalchemy import delete
            db.execute(delete(Chunk).where(Chunk.document_id==document_id))
            s3 = spaces()
            obj = s3.get_object(
                Bucket=settings.spaces_bucket, Key=doc.data["object_key"]
            )
            try:
                if (
                    obj["ContentLength"]
                    > shutil.disk_usage(tempfile.gettempdir()).free - 1024 * 1024 * 1024
                ):
                    raise ValueError(
                        "No hay espacio temporal suficiente para procesar este archivo"
                    )
                with tempfile.TemporaryDirectory(
                    prefix="vitruvius-ingest-"
                ) as directory:
                    path = Path(directory) / (
                        "source.pdf"
                        if doc.data["content_type"] == "application/pdf"
                        else "source.txt"
                    )
                    with path.open("wb") as stream:
                        for block in obj["Body"].iter_chunks(chunk_size=1024 * 1024):
                            stream.write(block)
                    any_text = False
                    for page, value in extract_for_ingestion(path, doc.data["content_type"],progress,fallback=extract):
                        if value.strip():
                            any_text = True
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
                    if not any_text:
                        raise ValueError(
                            "El documento no tiene texto extraíble; OCR sigue desactivado"
                        )
                    asyncio.run(index_document(db, doc, commit=False,progress=lambda done,total:progress("indexing",chunks_done=done,chunks_total=total)))
            finally:
                obj["Body"].close()
            doc.data = {**doc.data, "status": "ready", "processing_summary":dict(progress.state)}
            db.commit()
            progress("ready")
        except Exception:
            db.rollback()
            doc = db.get(Record, document_id)
            if doc:
                doc.data = {
                    **doc.data,
                    "status": "failed",
                    "error": "No se pudo procesar el documento. Revise el formato, texto extraíble, recursos disponibles y configuración.",
                }
                db.commit()
                progress("failed")
