from pathlib import Path
from types import SimpleNamespace
import pytest
from app.db import Record, Chunk


def test_upload_policy_and_finalize_accept_more_than_20mb(
    client, headers, workspace, monkeypatch
):
    import app.main as main
    from app.worker import ingest

    seen = {}

    class Store:
        def generate_presigned_post(self, **kwargs):
            seen.update(kwargs)
            return {"url": "https://bucket.example.invalid", "fields": {}}

        def head_object(self, **kwargs):
            return {"ContentLength": 25 * 1024 * 1024}

    monkeypatch.setattr(main, "spaces", lambda: Store())
    queued = []
    monkeypatch.setattr(ingest, "delay", lambda id: queued.append(id))
    _, session, _ = workspace
    doc = client.post(
        "/api/contexts",
        headers=headers,
        json={
            "session_id": session["id"],
            "title": "Synthetic large upload",
            "text": "",
        },
    ).json()
    assert (
        client.post(
            "/api/contexts/" + doc["id"] + "/upload?content_type=application%2Fpdf",
            headers=headers,
            json={},
        ).status_code
        == 200
    )
    assert all(
        not isinstance(c, list) or c[0] != "content-length-range"
        for c in seen["Conditions"]
    )
    assert seen["Conditions"] == [{"Content-Type": "application/pdf"}]
    assert (
        client.post(
            "/api/contexts/" + doc["id"] + "/finalize", headers=headers, json={}
        ).status_code
        == 200
    )
    assert queued == [doc["id"]]
    contexts = client.get("/api/catalog", headers=headers).json()["context"]
    assert contexts[0]["size_bytes"] == 25 * 1024 * 1024


def test_large_pdf_and_text_have_no_20mb_rejection(tmp_path, monkeypatch):
    from pypdf import PdfWriter
    from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject
    from app.knowledge import extract

    monkeypatch.delenv("DOCUMENT_PROCESSOR", raising=False)
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    page[NameObject("/Resources")] = DictionaryObject(
        {
            NameObject("/Font"): DictionaryObject(
                {NameObject("/F1"): writer._add_object(font)}
            )
        }
    )
    text = DecodedStreamObject()
    text.set_data(b"BT /F1 16 Tf 72 720 Td (SYNTHETIC LARGE PDF VERIFICATION) Tj ET")
    page[NameObject("/Contents")] = writer._add_object(text)
    padding = DecodedStreamObject()
    padding.set_data(b"x" * (21 * 1024 * 1024))
    writer._add_object(padding)
    path = tmp_path / "large.pdf"
    with path.open("wb") as stream:
        writer.write(stream)
    assert path.stat().st_size > 20 * 1024 * 1024
    assert "SYNTHETIC LARGE PDF" in extract(path, "application/pdf")[0][1]
    textpath = tmp_path / "large.txt"
    textpath.write_text("x" * (21 * 1024 * 1024))
    blocks = extract(textpath, "text/plain")
    total = 0
    for _, block in blocks:
        assert len(block) <= 65536
        total += len(block)
    assert total > 20 * 1024 * 1024


@pytest.mark.asyncio
async def test_embeddings_are_batched_without_committing_worker_transaction(
    db, monkeypatch
):
    import app.knowledge as knowledge

    doc = Record(kind="context", data={})
    db.add(doc)
    db.flush()
    for i in range(65):
        db.add(
            Chunk(
                document_id=doc.id,
                text="Synthetic chunk " + str(i),
                page=1,
                embedding=None,
            )
        )
    db.commit()
    sizes = []

    async def fake(values):
        sizes.append(len(values))
        return [[0.1, 0.2] for _ in values]

    monkeypatch.setattr(knowledge, "embed", fake)
    await knowledge.index_document(db, doc, commit=False)
    assert sizes == [32, 32, 1]
    assert all(c.embedding is not None for c in db.query(Chunk))
    db.rollback()
    assert all(c.embedding is None for c in db.query(Chunk))


def test_worker_streams_to_disk_and_removes_temporary_input(db, monkeypatch):
    import app.worker as worker
    from contextlib import contextmanager

    payload = b"Synthetic streamed input for worker verification."
    closed = []
    captured = []

    class Body:
        def read(self, *args):
            raise AssertionError("Whole-object reads are not allowed")

        def iter_chunks(self, chunk_size):
            yield payload

        def close(self):
            closed.append(True)

    class Store:
        def get_object(self, **kwargs):
            return {"ContentLength": len(payload), "Body": Body()}

    @contextmanager
    def factory():
        yield db

    monkeypatch.setattr(worker, "Session", factory)
    monkeypatch.setattr(worker, "spaces", lambda: Store())

    def extract(path, mime):
        assert isinstance(path, Path) and path.read_bytes() == payload
        captured.append(path)
        return [(1, "Synthetic text from disk")]

    monkeypatch.setattr(worker, "extract", extract)

    async def index(*args, **kwargs):
        assert kwargs["commit"] is False

    monkeypatch.setattr(worker, "index_document", index)
    doc = Record(
        kind="context",
        data={
            "status": "queued",
            "content_type": "text/plain",
            "object_key": "synthetic",
        },
    )
    db.add(doc)
    db.commit()
    worker.ingest.run(doc.id)
    assert (
        doc.data["status"] == "ready"
        and closed
        and captured
        and not captured[0].exists()
    )
