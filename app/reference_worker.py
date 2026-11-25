import asyncio
from .worker import celery
from .db import Session, Record
from .references import linked_context
from .source_fetch import fetch_public, SourceAccessError
from .knowledge import spaces, index_document
from .config import settings


@celery.task(name="references.index")
def index_reference(reference_id):
    if not Session:
        return
    with Session() as db:
        ref = db.get(Record, reference_id)
        if not ref or not ref.data.get("document_id"):
            return
        doc = db.get(Record, ref.data["document_id"])
        if not doc or doc.kind != "context":
            return
        try:
            asyncio.run(index_document(db, doc))
            ref.data = {**ref.data, "index_status": "ready"}
            db.commit()
        except Exception:
            db.rollback()
            ref = db.get(Record, reference_id)
            if ref:
                ref.data = {
                    **ref.data,
                    "index_status": "failed",
                    "message": "El texto está incorporado; no se pudo completar el índice vectorial.",
                }
                db.commit()


@celery.task(name="references.import", soft_time_limit=240, time_limit=270)
def import_public_reference(reference_id):
    if not Session:
        return
    with Session() as db:
        ref = db.get(Record, reference_id)
        if not ref or ref.kind != "reference" or ref.data.get("document_id"):
            return
        try:
            if ref.data["kind"] not in ("article", "pdf"):
                raise SourceAccessError(
                    "Esta fuente requiere texto o transcripción aportada por el propietario"
                )
            session = db.get(Record, ref.data["session_id"])
            if not session or session.kind != "session":
                raise SourceAccessError(
                    "La conversación de biblioteca ya no está disponible"
                )
            final_url, content_type, content = fetch_public(ref.data["url"])
            if content_type == "application/pdf":
                doc = linked_context(db, ref, session, source_url=final_url)
                key = "context/" + doc.id + "/source.pdf"
                spaces().put_object(
                    Bucket=settings.spaces_bucket,
                    Key=key,
                    Body=content,
                    ContentType="application/pdf",
                )
                doc.data = {
                    **doc.data,
                    "object_key": key,
                    "content_type": "application/pdf",
                    "status": "queued",
                }
                ref.data = {**ref.data, "status": "queued", "fetched_url": final_url}
                db.commit()
                from .worker import ingest

                ingest.delay(doc.id)
            else:
                doc = linked_context(
                    db, ref, session, content.decode("utf-8"), source_url=final_url
                )
                ref.data = {
                    **ref.data,
                    "fetched_url": final_url,
                    "message": "Se incorporó el texto público accesible. Revise autoría, procedencia e integridad antes de usarlo como fundamento.",
                }
                db.commit()
                index_reference.delay(ref.id)
        except Exception as exc:
            db.rollback()
            ref = db.get(Record, reference_id)
            if ref:
                ref.data = {
                    **ref.data,
                    "status": "requires_content",
                    "message": str(exc)
                    if isinstance(exc, SourceAccessError)
                    else "No se pudo recuperar la fuente. Aporte su texto autorizado o un PDF; el enlace solo no cuenta como evidencia.",
                }
                db.commit()
