from datetime import timedelta
from io import BytesIO
import os
import boto3
from botocore.config import Config
from openai import AsyncOpenAI
from sqlalchemy import select, delete, text
from fastapi import HTTPException
from .db import Record, Chunk, now
from .config import settings


def spaces():
    if not settings.spaces_ready:
        raise HTTPException(503, "Spaces no está configurado")
    return boto3.client(
        "s3",
        endpoint_url=settings.spaces_endpoint,
        region_name=settings.spaces_region,
        config=Config(signature_version="s3v4"),
    )


def visible(doc, session, expert_id, at=None):
    d = doc.data
    s = session.data
    at = at or now()
    if d.get("status") != "ready":
        return False
    if d.get("expires_at") and d["expires_at"] <= at.isoformat():
        return False
    if d.get("expert_ids") and expert_id not in d["expert_ids"]:
        return False
    scope = d["scope"]
    return (
        scope == "GLOBAL"
        or scope in ("SESSION", "REQUEST")
        and d["session_id"] == session.id
        or scope == "PROJECT"
        and d["project_id"] == s["project_id"]
        or scope == "BOARD"
        and d["board_id"] == s["board_id"]
        or scope == "EXPERT"
        and expert_id in d["expert_ids"]
    )


def create_context(db, data, session):
    if (
        data.scope in ("GLOBAL", "PROJECT", "BOARD", "EXPERT")
        and not data.permanent_consent
    ):
        raise HTTPException(
            422, "El contexto permanente requiere autorización explícita"
        )
    if data.scope == "EXPERT" and not data.expert_ids:
        raise HTTPException(422, "Indique expertos")
    d = data.model_dump(exclude={"text"})
    d.update(
        project_id=session.data["project_id"],
        board_id=session.data["board_id"],
        status="ready",
        object_key=None,
        expires_at=(now() + timedelta(hours=data.retention_hours)).isoformat()
        if data.scope in ("REQUEST", "SESSION")
        else None,
        source_type="text",
        bibliography=None,
    )
    rec = Record(kind="context", data=d)
    db.add(rec)
    db.flush()
    for i in range(0, len(data.text), 2400):
        db.add(
            Chunk(
                document_id=rec.id,
                text=data.text[i : i + 2800],
                page=None,
                embedding=None,
            )
        )
    db.commit()
    return rec


async def embed(value):
    if not settings.openrouter_key:
        raise HTTPException(503, "OpenRouter no está configurado")
    async with AsyncOpenAI(
        api_key=settings.openrouter_key, base_url="https://openrouter.ai/api/v1"
    ) as client:
        result = await client.embeddings.create(
            model=settings.embedding_model, input=value, dimensions=1536
        )
    return result.data[0].embedding


async def index_document(db, doc):
    chunks = list(db.scalars(select(Chunk).where(Chunk.document_id == doc.id)))
    for c in chunks:
        vector = await embed(c.text)
        c.embedding = vector
        if db.bind.dialect.name == "postgresql":
            db.execute(
                text(
                    "UPDATE chunks SET vector_embedding=CAST(:v AS vector) WHERE id=:id"
                ),
                {"v": str(vector), "id": c.id},
            )
    db.commit()


async def retrieve(db, session, expert_id, query, limit=6):
    ids = [
        d.id
        for d in db.scalars(select(Record).where(Record.kind == "context"))
        if visible(d, session, expert_id)
    ]
    if not ids:
        return []
    if db.bind.dialect.name == "postgresql" and settings.openrouter_key:
        v = await embed(query)
        # Access filters are applied before scoring; no caller-provided SQL identifiers.
        rows = (
            db.execute(
                text(
                    "SELECT id FROM chunks WHERE document_id = ANY(:ids) AND vector_embedding IS NOT NULL ORDER BY vector_embedding <=> CAST(:v AS vector) LIMIT :n"
                ),
                {"ids": ids, "v": str(v), "n": limit},
            )
            .scalars()
            .all()
        )
        chunks = [db.get(Chunk, i) for i in rows]
    else:
        chunks = []
    if not chunks:
        words = set(query.lower().split())
        candidates = list(db.scalars(select(Chunk).where(Chunk.document_id.in_(ids))))
        chunks = sorted(
            candidates,
            key=lambda c: len(words & set(c.text.lower().split())),
            reverse=True,
        )[:limit]
    from .observability import event

    event(
        "context_retrieval",
        session_id=session.id,
        expert_id=expert_id,
        chunk_ids=[c.id for c in chunks],
    )
    return [
        {
            "chunk_id": c.id,
            "document_id": c.document_id,
            "page": c.page,
            "text": c.text,
            "title": db.get(Record, c.document_id).data["title"],
            "source": db.get(Record, c.document_id).data.get("source"),
        }
        for c in chunks
    ]


def remove_document(db, doc):
    db.refresh(doc, with_for_update=True)
    key = doc.data.get("object_key")
    if key:
        spaces().delete_object(
            Bucket=settings.spaces_bucket, Key=doc.data["object_key"]
        )
    db.execute(delete(Chunk).where(Chunk.document_id == doc.id))
    if key:
        # Repeat object deletion after any outstanding presigned URL has expired.
        doc.kind = "context_tombstone"
        doc.data = {
            "object_key": key,
            "purge_until": (now() + timedelta(minutes=10)).isoformat(),
        }
    else:
        db.delete(doc)
    db.commit()


def cleanup(db):
    count = 0
    for tombstone in list(
        db.scalars(select(Record).where(Record.kind == "context_tombstone"))
    ):
        spaces().delete_object(
            Bucket=settings.spaces_bucket, Key=tombstone.data["object_key"]
        )
        if tombstone.data["purge_until"] <= now().isoformat():
            db.delete(tombstone)
        db.commit()
    for doc in list(db.scalars(select(Record).where(Record.kind == "context"))):
        if doc.data.get("expires_at") and doc.data["expires_at"] <= now().isoformat():
            remove_document(db, doc)
            count += 1
    return count


def extract(content, content_type):
    if len(content) > 20 * 1024 * 1024:
        raise ValueError("Archivo mayor de 20 MB")
    if content_type == "application/pdf":
        if os.getenv("DOCUMENT_PROCESSOR") == "docling":
            from docling.datamodel.base_models import DocumentStream, InputFormat
            from docling.datamodel.pipeline_options import PdfPipelineOptions
            from docling.datamodel.accelerator_options import (
                AcceleratorOptions,
                AcceleratorDevice,
            )
            from docling.document_converter import DocumentConverter, PdfFormatOption

            options = PdfPipelineOptions(do_ocr=False, do_table_structure=True)
            options.accelerator_options = AcceleratorOptions(
                num_threads=2, device=AcceleratorDevice.CPU
            )
            converter = DocumentConverter(
                allowed_formats=[InputFormat.PDF],
                format_options={
                    InputFormat.PDF: PdfFormatOption(pipeline_options=options)
                },
            )
            result = converter.convert(
                DocumentStream(name="attachment.pdf", stream=BytesIO(content)),
                max_num_pages=500,
                max_file_size=20 * 1024 * 1024,
            )
            pages = {}
            for item, _ in result.document.iterate_items():
                value = getattr(item, "text", "")
                if item.__class__.__name__ == "TableItem":
                    value = item.export_to_markdown(doc=result.document)
                if not value:
                    continue
                provenance = getattr(item, "prov", [])
                page = provenance[0].page_no if provenance else None
                pages.setdefault(page, []).append(value)
            return [(page, "\n".join(parts)) for page, parts in pages.items()]
        from pypdf import PdfReader

        reader = PdfReader(BytesIO(content))
        if len(reader.pages) > 500:
            raise ValueError("PDF mayor de 500 páginas")
        return [(i + 1, p.extract_text() or "") for i, p in enumerate(reader.pages)]
    if content_type in ("text/plain", "text/markdown"):
        return [(None, content.decode("utf-8"))]
    raise ValueError("Formato no soportado: solo PDF, texto y Markdown en esta versión")
