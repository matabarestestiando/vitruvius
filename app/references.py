"""References are registered separately from processed, reviewed evidence."""

from urllib.parse import urlsplit
from fastapi import HTTPException
from .db import Record
from .schemas import ContextIn, SourceMetadata
from .knowledge import create_context
from .source_fetch import url_parts


def validate_reference_url(kind, url):
    if not url:
        if kind != "pdf":
            raise HTTPException(422, "Indique el enlace de la fuente")
        return
    try:
        p = url_parts(url)
    except ValueError as e:
        raise HTTPException(422, str(e)) from None
    host = p.hostname.lower()
    if kind == "x_post" and host not in (
        "x.com",
        "www.x.com",
        "twitter.com",
        "www.twitter.com",
    ):
        raise HTTPException(422, "Use el enlace directo a una publicación de X")
    if kind == "youtube" and host not in (
        "youtube.com",
        "www.youtube.com",
        "m.youtube.com",
        "youtu.be",
    ):
        raise HTTPException(422, "Use el enlace directo al video de YouTube")


def linked_context(db, reference, session, text="", source_url=None):
    d = reference.data
    medium = {"youtube": "video", "x_post": "social", "pdf": "pdf"}.get(
        d["kind"], "text"
    )
    context = ContextIn(
        session_id=session.id,
        title=d["title"],
        text=text,
        scope="EXPERT",
        expert_ids=[d["expert_id"]],
        permanent_consent=True,
        source=SourceMetadata(
            author=d["author"],
            source_url=source_url or d.get("url"),
            kind="author_work",
            medium=medium,
        ),
    )
    doc = create_context(db, context, session)
    reference.data = {
        **reference.data,
        "document_id": doc.id,
        "status": "processed" if text else "awaiting_upload",
    }
    db.commit()
    return doc
