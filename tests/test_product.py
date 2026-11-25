from datetime import timedelta
from fastapi import HTTPException
import pytest
from app.db import Record, Chunk, now
from app.knowledge import visible, cleanup
from app.repositories import safe_file


def test_auth_and_no_secret_configuration(client, headers):
    assert client.get("/api/catalog").status_code == 401
    assert client.get("/mcp/").status_code == 401
    assert client.get("/healthz").status_code == 200
    assert client.get("/api/status", headers=headers).status_code == 200


def test_context_consent_scope_expiry_and_purge(client, headers, workspace, db):
    project, session, catalog = workspace
    payload = {
        "session_id": session["id"],
        "title": "Private context",
        "text": "sensitive data",
    }
    permanent = client.post(
        "/api/contexts", headers=headers, json={**payload, "scope": "GLOBAL"}
    )
    assert permanent.status_code == 422
    doc = client.post("/api/contexts", headers=headers, json=payload).json()
    obj = db.get(Record, doc["id"])
    sess = db.get(Record, session["id"])
    assert visible(obj, sess, catalog["expert"][0]["id"])
    other = Record(
        id="other",
        kind="session",
        data={"project_id": project["id"], "board_id": session["board_id"]},
    )
    assert not visible(obj, other, catalog["expert"][0]["id"])
    obj.data = {**obj.data, "expires_at": (now() - timedelta(seconds=1)).isoformat()}
    db.commit()
    assert not visible(obj, sess, catalog["expert"][0]["id"])
    assert cleanup(db) == 1
    assert db.get(Record, doc["id"]) is None
    assert db.query(Chunk).count() == 0


def test_approved_versions_only_export(client, headers, workspace):
    p, s, _ = workspace
    payload = {
        "project_id": p["id"],
        "session_id": s["id"],
        "title": "A decision",
        "kind": "adr",
        "content": "Use PostgreSQL",
        "acceptance_criteria": ["Survives restart"],
    }
    a = client.post("/api/artifacts", headers=headers, json=payload).json()
    assert (
        client.get("/api/projects/" + p["id"] + "/export", headers=headers).status_code
        == 409
    )
    assert (
        client.post(
            "/api/artifacts/" + a["id"] + "/approve", headers=headers
        ).status_code
        == 200
    )
    out = client.get("/api/projects/" + p["id"] + "/export", headers=headers).json()
    assert "Use PostgreSQL" in out["prompt"]
    assert a["digest"] in out["prompt"]
    b = client.post(
        "/api/artifacts",
        headers=headers,
        json={**payload, "content": "Use a different solution", "previous_id": a["id"]},
    ).json()
    assert b["version"] == 2
    assert (
        client.get("/api/projects/" + p["id"] + "/export", headers=headers).status_code
        == 409
    )


def test_repository_traversal_and_sensitive_files(tmp_path):
    (tmp_path / "safe.py").write_text("hello")
    (tmp_path / ".env").write_text("secret")
    (tmp_path / "link.py").symlink_to("/etc/passwd")
    assert safe_file(tmp_path, "safe.py").name == "safe.py"
    for name in ["../outside.py", ".env", "link.py"]:
        with pytest.raises(HTTPException):
            safe_file(tmp_path, name)


@pytest.mark.asyncio
async def test_write_tool_exact_approval_consumed(db, monkeypatch):
    from app import tools

    e = Record(id="expert", kind="expert", data={})
    db.add(e)
    c = Record(
        id="connection",
        kind="connection",
        data={"expert_ids": ["expert"], "read_tools": [], "write_tools": ["create"]},
    )
    db.add(c)
    db.commit()
    calls = []

    async def fake(*args):
        calls.append(args)
        return {"isError": False}

    monkeypatch.setattr(tools, "remote", fake)
    with pytest.raises(HTTPException):
        await tools.execute(db, c, "expert", "create", {"x": 1})
    approval = Record(
        kind="tool_approval",
        data={
            "connection_id": c.id,
            "expert_id": "expert",
            "tool": "create",
            "arguments": {"x": 1},
        },
    )
    db.add(approval)
    db.commit()
    with pytest.raises(HTTPException):
        await tools.execute(db, c, "expert", "create", {"x": 2}, approval.id)
    await tools.execute(db, c, "expert", "create", {"x": 1}, approval.id)
    with pytest.raises(HTTPException):
        await tools.execute(db, c, "expert", "create", {"x": 1}, approval.id)
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_board_dynamic_router_and_limit(db, workspace):
    from app.board import BoardRunner

    _, s, catalog = workspace
    experts = [db.get(Record, e["id"]) for e in catalog["expert"][:2]]
    runner = BoardRunner(db, db.get(Record, s["id"]), experts, client=object())

    async def fake(system, transcript, model=None, structured=False):
        if structured:
            return '{"done":false,"next_speaker":"' + experts[1].id + '"}'
        if system.startswith("Resume"):
            return "Provisional summary"
        return "Antonio, necesito aclarar el requisito."

    runner.complete = fake
    result = await runner.graph(2).ainvoke(
        {
            "transcript": [{"speaker": "Owner", "content": "Design agent"}],
            "turns": 0,
            "next_speaker": "",
            "done": False,
            "summary": "",
        }
    )
    assert result["turns"] == 2
    assert result["transcript"][1]["speaker"] == experts[1].data["name"]
    assert result["summary"] == "Provisional summary"
