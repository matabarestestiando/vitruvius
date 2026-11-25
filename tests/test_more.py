from io import BytesIO
from zipfile import ZipFile
import pytest
from fastapi import HTTPException
from app.skills import import_skill
from app.db import Record, now
from app.knowledge import visible


def test_skill_import_no_archive_extraction():
    buf = BytesIO()
    with ZipFile(buf, "w") as z:
        z.writestr("../../SKILL.md", "Safe methodology")
    assert import_skill("skill.zip", buf.getvalue()) == "Safe methodology"
    with pytest.raises(HTTPException):
        import_skill("script.py", b"print(1)")


def test_expert_and_project_isolation():
    session = Record(
        id="session", kind="session", data={"project_id": "p1", "board_id": "b1"}
    )
    doc = Record(
        kind="context",
        data={
            "scope": "PROJECT",
            "project_id": "p2",
            "status": "ready",
            "expert_ids": [],
            "expires_at": None,
        },
    )
    assert not visible(doc, session, "e1")
    doc.data = {**doc.data, "project_id": "p1", "expert_ids": ["e2"]}
    assert not visible(doc, session, "e1")
    assert visible(doc, session, "e2")


def test_permanent_context_promotion_requires_owner(client, headers, workspace):
    _, s, _ = workspace
    c = client.post(
        "/api/contexts",
        headers=headers,
        json={"session_id": s["id"], "title": "context", "text": "text"},
    ).json()
    assert (
        client.post("/api/contexts/" + c["id"] + "/promote?scope=PROJECT").status_code
        == 401
    )
    promoted = client.post(
        "/api/contexts/" + c["id"] + "/promote?scope=PROJECT", headers=headers
    ).json()
    assert promoted["expires_at"] is None
    assert promoted["permanent_consent"] is True


def test_reject_arbitrary_mcp_origin(client, headers):
    r = client.post(
        "/api/connections",
        headers=headers,
        json={"name": "bad", "url": "http://169.254.169.254/"},
    )
    assert r.status_code == 422


def test_skill_versions_are_immutable(client, headers):
    a = client.post(
        "/api/skills", headers=headers, json={"name": "Design", "content": "first"}
    ).json()
    b = client.post(
        "/api/skills",
        headers=headers,
        json={"name": "Design", "content": "second", "previous_id": a["id"]},
    ).json()
    assert b["version"] == 2 and a["id"] != b["id"]
    skills = client.get("/api/catalog", headers=headers).json()["skill"]
    assert next(s for s in skills if s["id"] == a["id"])["content"] == "first"


def test_mcp_protocol_and_shared_board_data(db, headers, monkeypatch):
    from contextlib import contextmanager
    from fastapi.testclient import TestClient
    from app.main import app
    from app import db as database

    @contextmanager
    def factory():
        yield db

    monkeypatch.setattr(database, "Session", factory)
    h = {**headers, "Accept": "application/json, text/event-stream"}
    with TestClient(app, base_url="http://localhost") as c:
        r = c.post(
            "/mcp/",
            headers=h,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "1"},
                },
            },
        )
        assert r.status_code == 200
        assert r.json()["result"]["serverInfo"]["name"] == "Vitruvius"
        r = c.post(
            "/mcp/",
            headers=h,
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {"name": "list_boards", "arguments": {}},
            },
        )
        assert r.status_code == 200 and not r.json()["result"].get("isError")
        assert "Conversational AI" in str(r.json())


def test_presigned_reupload_cannot_leave_an_orphan(db, monkeypatch):
    from app import knowledge
    from app.db import Chunk
    from datetime import timedelta

    deleted = []

    class Store:
        def delete_object(self, **kwargs):
            deleted.append(kwargs["Key"])

    monkeypatch.setattr(knowledge, "spaces", lambda: Store())
    d = Record(
        kind="context",
        data={
            "status": "ready",
            "scope": "SESSION",
            "object_key": "temporary/test",
            "expires_at": None,
        },
    )
    db.add(d)
    db.flush()
    db.add(Chunk(document_id=d.id, text="private", page=None, embedding=None))
    db.commit()
    knowledge.remove_document(db, d)
    assert d.kind == "context_tombstone" and db.query(Chunk).count() == 0
    assert "private" not in str(d.data)
    d.data = {**d.data, "purge_until": (now() - timedelta(seconds=1)).isoformat()}
    db.commit()
    knowledge.cleanup(db)
    assert db.get(Record, d.id) is None and deleted == [
        "temporary/test",
        "temporary/test",
    ]


def test_context_window_is_bounded():
    from app.board import bounded_transcript

    history = [{"speaker": "test", "content": "x" * 12000} for _ in range(20)]
    bounded = bounded_transcript(history)
    assert len(bounded) == 4 and sum(len(m["content"]) for m in bounded) <= 48000


def test_curated_memory_tracks_and_deletes_episode(
    client, headers, workspace, monkeypatch
):
    import app.main as main
    from types import SimpleNamespace

    calls = []

    class FakeHTTP:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def post(self, url, **kwargs):
            calls.append((url, kwargs["json"]))
            return SimpleNamespace(
                status_code=200,
                json=lambda: {"episode_id": "episode-test", "deleted": True},
            )

    monkeypatch.setattr(
        main,
        "settings",
        SimpleNamespace(
            memory_token="private-test-token", memory_url="http://private-memory"
        ),
    )
    monkeypatch.setattr(main.httpx, "AsyncClient", lambda **kwargs: FakeHTTP())
    p, _, _ = workspace
    r = client.post(
        "/api/memories",
        headers=headers,
        json={
            "scope": "project",
            "target_id": p["id"],
            "text": "approved synthetic decision",
            "approved": True,
        },
    )
    assert r.status_code == 200
    rid = r.json()["record_id"]
    events = client.get("/api/catalog", headers=headers).json()["memory_event"]
    assert len(events) == 1 and "approved synthetic decision" not in str(events)
    assert client.delete("/api/memories/" + rid, headers=headers).status_code == 200
    assert len(calls) == 2
