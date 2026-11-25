from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import (
    JSON,
    DateTime,
    String,
    Text,
    create_engine,
    ForeignKey,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from .config import settings


def now():
    return datetime.now(timezone.utc)


def uid():
    return str(uuid4())


class Base(DeclarativeBase):
    pass


class Record(Base):
    __tablename__ = "records"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    kind: Mapped[str] = mapped_column(String, index=True)
    data: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Message(Base):
    __tablename__ = "messages"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    session_id: Mapped[str] = mapped_column(ForeignKey("records.id"), index=True)
    speaker: Mapped[str] = mapped_column(String)
    content: Mapped[str] = mapped_column(Text)
    citations: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Chunk(Base):
    __tablename__ = "chunks"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    document_id: Mapped[str] = mapped_column(ForeignKey("records.id"), index=True)
    text: Mapped[str] = mapped_column(Text)
    page: Mapped[int | None]
    embedding: Mapped[list | None] = mapped_column(JSON)


class Approval(Base):
    __tablename__ = "approvals"
    __table_args__ = (UniqueConstraint("artifact_id", "digest"),)
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    artifact_id: Mapped[str] = mapped_column(ForeignKey("records.id"))
    digest: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


engine = (
    create_engine(settings.database_url, pool_pre_ping=True)
    if settings.database_url
    else None
)
Session = sessionmaker(engine, expire_on_commit=False) if engine else None


def db_session():
    if Session is None:
        from fastapi import HTTPException

        raise HTTPException(503, "PostgreSQL no está configurado")
    with Session() as db:
        yield db


def initialize():
    if engine is None:
        return
    Base.metadata.create_all(engine)
    if engine.dialect.name == "postgresql":
        from sqlalchemy import text

        with engine.begin() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            conn.execute(
                text(
                    "ALTER TABLE chunks ADD COLUMN IF NOT EXISTS vector_embedding vector(1536)"
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS chunk_vector_idx ON chunks USING hnsw (vector_embedding vector_cosine_ops)"
                )
            )
