"""Run inside API container. Synthetic integration verification; prints no secrets or model content."""

import asyncio, json, os, time, uuid
import httpx
from sqlalchemy import select, delete, text
from app.db import Session, Record, Message, Chunk, Approval
from app.config import settings


async def main():
    headers = {"Authorization": "Bearer " + settings.owner_token}
    project_id = session_id = episode_id = None
    async with httpx.AsyncClient(
        base_url="http://127.0.0.1:8000", headers=headers, timeout=240
    ) as api:

        async def request(method, path, data=None):
            r = await api.request(method, path, json=data)
            if r.status_code >= 400:
                raise RuntimeError(path + " returned " + str(r.status_code))
            return r.json()

        try:
            catalog = await request("GET", "/api/catalog")
            p = await request(
                "POST",
                "/api/projects",
                {"name": "SYNTHETIC DEPLOYMENT VERIFICATION " + str(uuid.uuid4())[:8]},
            )
            project_id = p["id"]
            s = await request(
                "POST",
                "/api/sessions",
                {
                    "project_id": project_id,
                    "board_id": catalog["board"][0]["id"],
                    "title": "Temporary integration verification",
                },
            )
            session_id = s["id"]
            c = await request(
                "POST",
                "/api/contexts",
                {
                    "session_id": session_id,
                    "title": "Synthetic deployment check",
                    "text": "SYNTHETIC TEST DATA: the sample application has one owner and needs an explicit approval before exporting development specifications.",
                },
            )
            await request("POST", "/api/contexts/" + c["id"] + "/index", {})
            with Session() as db:
                count = db.execute(
                    text(
                        "SELECT count(*) FROM chunks WHERE document_id=:id AND vector_embedding IS NOT NULL"
                    ),
                    {"id": c["id"]},
                ).scalar()
                assert count > 0
            print("Managed pgvector embedding/index: PASS")
            result = await request(
                "POST",
                "/api/sessions/" + session_id + "/turns",
                {
                    "text": "Prueba sintética de despliegue. Antonio, pide a Harrison revisar un agente de un solo usuario que exporta especificaciones solo tras aprobación. Consulta el contexto adjunto. No atribuyas afirmaciones a autores ni libros. Limita la discusión a una intervención.",
                    "max_turns": 1,
                },
            )
            assert len(result) >= 3
            print(
                "Dynamic LangGraph/OpenRouter/PostgreSQL checkpoint: PASS; messages:",
                len(result),
            )
            # Standard protocol, same session, no fabricated client interoperability claim.
            r = await api.post(
                "/mcp/",
                headers={"Accept": "application/json, text/event-stream"},
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/call",
                    "params": {
                        "name": "get_session",
                        "arguments": {"session_id": session_id},
                    },
                },
            )
            assert r.status_code == 200 and not r.json()["result"].get("isError")
            print("MCP same-session history: PASS")
            draft = await request(
                "POST",
                "/api/sessions/" + session_id + "/draft",
                {"kind": "specification"},
            )
            r = await api.get("/api/projects/" + project_id + "/export")
            assert r.status_code == 409
            await request("POST", "/api/artifacts/" + draft["id"] + "/approve", {})
            handoff = await request(
                "GET", "/api/projects/" + project_id + "/export?target=codex"
            )
            assert draft["digest"] in handoff["prompt"]
            print("Generated draft/approval/handoff: PASS")
            upload = await request(
                "POST",
                "/api/contexts",
                {
                    "session_id": session_id,
                    "title": "Temporary upload verification",
                    "text": "",
                },
            )
            signed = await request(
                "POST",
                "/api/contexts/" + upload["id"] + "/upload?content_type=text%2Fplain",
                {},
            )
            async with httpx.AsyncClient(timeout=30) as external:
                r = await external.post(
                    signed["url"],
                    data=signed["fields"],
                    files={
                        "file": (
                            "synthetic.txt",
                            b"SYNTHETIC UPLOAD: temporary deployment verification, not a literature source.",
                            "text/plain",
                        )
                    },
                )
                assert r.status_code in (200, 201, 204), r.status_code
            await request("POST", "/api/contexts/" + upload["id"] + "/finalize", {})
            for _ in range(35):
                await asyncio.sleep(2)
                cat = await request("GET", "/api/catalog")
                item = next(x for x in cat["context"] if x["id"] == upload["id"])
                if item["status"] in ("ready", "failed"):
                    break
            assert item["status"] == "ready", item["status"]
            await request("DELETE", "/api/contexts/" + upload["id"])
            print("Spaces presigned upload/worker extraction/embedding/deletion: PASS")
            async with httpx.AsyncClient(
                base_url=settings.memory_url,
                headers={"Authorization": "Bearer " + settings.memory_token},
                timeout=240,
            ) as memory:
                group = "vitruvius:project:" + project_id
                r = await memory.post(
                    "/episodes",
                    json={
                        "group_id": group,
                        "name": "synthetic-verification",
                        "text": "SYNTHETIC TEST DATA. Project Meridian uses PostgreSQL as its database. Project Meridian is deployed on host Atlas. Test Owner operates Project Meridian. These are disposable deployment verification facts, not literature.",
                        "approved": True,
                    },
                )
                assert r.status_code == 200, "memory ingestion " + str(r.status_code)
                episode_id = r.json()["episode_id"]
                r = await memory.post(
                    "/search",
                    json={
                        "group_id": group,
                        "query": "Which database does Project Meridian use?",
                        "limit": 3,
                    },
                )
                assert r.status_code == 200 and r.json()["facts"], (
                    "memory search " + str(r.status_code)
                )
                other = await memory.post(
                    "/search",
                    json={
                        "group_id": "vitruvius:project:isolated-verification",
                        "query": "verification-council",
                        "limit": 3,
                    },
                )
                assert other.status_code == 200 and not other.json()["facts"]
                print("Graphiti ingestion/search/namespace isolation: PASS")
                r = await memory.post(
                    "/episodes/" + episode_id + "/delete", json={"group_id": group}
                )
                assert r.status_code == 200
                episode_id = None
            await request("DELETE", "/api/sessions/" + session_id)
            session_id = None
            print("Session context/history/checkpoint deletion: PASS")
        finally:
            if session_id:
                try:
                    await api.delete("/api/sessions/" + session_id)
                except Exception:
                    pass
            if episode_id:
                async with httpx.AsyncClient(timeout=90) as mem:
                    await mem.post(
                        settings.memory_url + "/episodes/" + episode_id + "/delete",
                        headers={"Authorization": "Bearer " + settings.memory_token},
                        json={"group_id": "vitruvius:project:" + project_id},
                    )
            if project_id:
                with Session() as db:
                    for a in list(
                        db.scalars(
                            select(Record).where(
                                Record.kind.in_(["artifact", "review"])
                            )
                        )
                    ):
                        if a.data.get("project_id") == project_id:
                            db.execute(
                                delete(Approval).where(Approval.artifact_id == a.id)
                            )
                            db.delete(a)
                    db.delete(db.get(Record, project_id))
                    db.commit()
            print("Synthetic verification data cleanup: completed")


if __name__ == "__main__":
    asyncio.run(main())
