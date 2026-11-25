import asyncio
from contextlib import asynccontextmanager
from datetime import timedelta
import hashlib
import json
import os
from pathlib import Path
from uuid import uuid4
import httpx
from fastapi import (
    FastAPI,
    Depends,
    HTTPException,
    Query,
    Request,
    UploadFile,
    File,
    Form,
)
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select, text
from sqlalchemy.orm import Session as DB
from . import db as database
from .db import Record, Message, Approval, Chunk, db_session, now
from .config import settings
from .auth import owner
from .schemas import *
from .knowledge import (
    create_context,
    retrieve,
    cleanup,
    remove_document,
    spaces,
    index_document,
)
from .seed import seed
from .repositories import inspect, repository
from .tools import validate_url, remote, execute

os.environ["LANGSMITH_HIDE_INPUTS"] = "true"
os.environ["LANGSMITH_HIDE_OUTPUTS"] = "true"
os.environ["LANGSMITH_TRACING"] = (
    "false"  # only explicit redacted OpenRouter spans are enabled
)


@asynccontextmanager
async def lifespan(app):
    if database.engine:
        database.initialize()
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

        async with AsyncPostgresSaver.from_conn_string(
            settings.database_url.replace("postgresql+psycopg://", "postgresql://")
        ) as saver:
            await saver.setup()
        with database.Session() as db:
            seed(db)
    async with mcp.session_manager.run():
        yield


app = FastAPI(
    title="Vitruvius",
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)
D = Depends(db_session)
O = Depends(owner)


def record(db, id, kind=None):
    r = db.get(Record, id)
    if not r or kind and r.kind != kind:
        raise HTTPException(404, "No encontrado")
    return r


def output(r):
    return {"id": r.id, "kind": r.kind, **r.data}


def add(db, kind, data):
    r = Record(kind=kind, data=data)
    db.add(r)
    db.commit()
    return output(r)


@app.get("/healthz")
def health():
    return {"status": "alive", "version": "0.1.0"}


@app.get("/api/status", dependencies=[O])
def status(db: DB = D):
    db.execute(text("SELECT 1"))
    return {
        "postgresql": "ready",
        "openrouter": bool(settings.openrouter_key),
        "spaces": settings.spaces_ready,
        "langsmith": bool(os.getenv("LANGSMITH_API_KEY")),
        "memory_configured": bool(settings.memory_token),
    }


@app.get("/api/catalog", dependencies=[O])
def catalog(db: DB = D):
    kinds = [
        "expert",
        "board",
        "project",
        "skill",
        "session",
        "context",
        "artifact",
        "repository",
        "connection",
        "memory_event",
        "tool_request",
    ]
    return {
        k: [
            output(r)
            for r in db.scalars(
                select(Record).where(Record.kind == k).order_by(Record.created_at)
            )
        ]
        for k in kinds
    }


@app.post("/api/experts", dependencies=[O])
def experts(data: ExpertIn, db: DB = D):
    for i in data.skill_ids:
        record(db, i, "skill")
    return add(db, "expert", data.model_dump())


@app.post("/api/boards", dependencies=[O])
def boards(data: BoardIn, db: DB = D):
    for i in data.expert_ids:
        record(db, i, "expert")
    if len(set(data.expert_ids)) != len(data.expert_ids):
        raise HTTPException(422, "Expertos duplicados")
    return add(db, "board", data.model_dump())


@app.post("/api/projects", dependencies=[O])
def projects(data: ProjectIn, db: DB = D):
    return add(db, "project", data.model_dump())


@app.post("/api/skills", dependencies=[O])
def skills(data: SkillIn, db: DB = D):
    previous = record(db, data.previous_id, "skill") if data.previous_id else None
    return add(
        db,
        "skill",
        {
            **data.model_dump(),
            "version": previous.data["version"] + 1 if previous else 1,
        },
    )


@app.post("/api/sessions", dependencies=[O])
def sessions(data: SessionIn, db: DB = D):
    record(db, data.board_id, "board")
    record(db, data.project_id, "project")
    return add(db, "session", data.model_dump())


@app.get("/api/sessions/{id}/messages", dependencies=[O])
def messages(id: str, db: DB = D):
    record(db, id, "session")
    return [
        {
            "id": m.id,
            "speaker": m.speaker,
            "content": m.content,
            "citations": m.citations,
        }
        for m in db.scalars(
            select(Message)
            .where(Message.session_id == id)
            .order_by(Message.created_at, Message.id)
        )
    ]


async def run_turn(db, id, data):
    if not settings.openrouter_key:
        raise HTTPException(503, "Configure la credencial rotada de OpenRouter")
    session = record(db, id, "session")
    board = record(db, session.data["board_id"], "board")
    # Advisory lock prevents concurrent clients from interleaving a session.
    lock_id = int.from_bytes(
        hashlib.sha256(id.encode()).digest()[:8], "big", signed=True
    )
    conn = database.engine.connect() if db.bind.dialect.name == "postgresql" else None
    acquired = conn is None
    try:
        if (
            conn
            and not conn.execute(
                text("SELECT pg_try_advisory_lock(:id)"), {"id": lock_id}
            ).scalar()
        ):
            raise HTTPException(409, "La sesión ya está en ejecución")
        acquired = True
        if conn:
            conn.commit()
        cleanup(db)
        transcript = [
            {"speaker": m.speaker, "content": m.content}
            for m in db.scalars(
                select(Message)
                .where(Message.session_id == id)
                .order_by(Message.created_at)
            )
        ][-60:]
        transcript.append({"speaker": "Propietario", "content": data.text})
        db.add(
            Message(
                session_id=id, speaker="Propietario", content=data.text, citations=[]
            )
        )
        db.commit()
        from .board import BoardRunner
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

        url = settings.database_url.replace("postgresql+psycopg://", "postgresql://")
        experts = [record(db, e, "expert") for e in board.data["expert_ids"]]
        db.commit()  # Release read snapshots before the asynchronous graph executes.
        async with AsyncPostgresSaver.from_conn_string(url) as saver:
            await BoardRunner(db, session, experts, saver).run(
                transcript, data.max_turns, str(uuid4())
            )
        # REQUEST attachments are retired after this call, including when the model fails.
        return messages(id, db)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            502,
            "Falló la ejecución del Board; el historial ya guardado puede consultarse",
        ) from None
    finally:
        for d in list(db.scalars(select(Record).where(Record.kind == "context"))):
            if (
                acquired
                and d.data.get("session_id") == id
                and d.data.get("scope") == "REQUEST"
            ):
                remove_document(db, d)
        if conn:
            conn.execute(text("SELECT pg_advisory_unlock(:id)"), {"id": lock_id})
            conn.close()


@app.post("/api/sessions/{id}/turns", dependencies=[O])
async def turns(id: str, data: TurnIn, db: DB = D):
    return await run_turn(db, id, data)


@app.post("/api/contexts", dependencies=[O])
def contexts(data: ContextIn, db: DB = D):
    session = record(db, data.session_id, "session")
    for eid in data.expert_ids:
        record(db, eid, "expert")
    return output(create_context(db, data, session))


@app.post("/api/contexts/{id}/index", dependencies=[O])
async def index(id: str, db: DB = D):
    await index_document(db, record(db, id, "context"))
    return {"status": "indexed"}


@app.post("/api/contexts/{id}/upload", dependencies=[O])
def upload(
    id: str,
    content_type: str = Query(pattern="^(application/pdf|text/plain|text/markdown)$"),
    db: DB = D,
):
    doc = record(db, id, "context")
    if doc.data.get("object_key"):
        raise HTTPException(409, "Ya existe una carga")
    key = "context/" + doc.id + "/" + str(uuid4())
    result = spaces().generate_presigned_post(
        Bucket=settings.spaces_bucket,
        Key=key,
        Fields={"Content-Type": content_type},
        Conditions=[
            ["content-length-range", 1, 20 * 1024 * 1024],
            {"Content-Type": content_type},
        ],
        ExpiresIn=300,
    )
    doc.data = {
        **doc.data,
        "object_key": key,
        "content_type": content_type,
        "status": "awaiting_upload",
    }
    db.commit()
    return result


@app.post("/api/contexts/{id}/finalize", dependencies=[O])
def finalize(id: str, db: DB = D):
    doc = record(db, id, "context")
    if doc.data["status"] != "awaiting_upload":
        raise HTTPException(409, "Carga no disponible")
    head = spaces().head_object(
        Bucket=settings.spaces_bucket, Key=doc.data["object_key"]
    )
    if head["ContentLength"] > 20 * 1024 * 1024:
        raise HTTPException(422, "Archivo demasiado grande")
    doc.data = {**doc.data, "status": "queued"}
    db.commit()
    from .worker import ingest

    ingest.delay(id)
    return {"status": "queued"}


@app.delete("/api/contexts/{id}", dependencies=[O])
def delete_context(id: str, db: DB = D):
    remove_document(db, record(db, id, "context"))
    return {"deleted": True}


@app.post("/api/contexts/{id}/promote", dependencies=[O])
def promote(
    id: str, scope: str = Query(pattern="^(PROJECT|BOARD|EXPERT|GLOBAL)$"), db: DB = D
):
    doc = record(db, id, "context")
    if scope == "EXPERT" and not doc.data["expert_ids"]:
        raise HTTPException(422, "Debe asignar expertos")
    doc.data = {
        **doc.data,
        "scope": scope,
        "expires_at": None,
        "permanent_consent": True,
    }
    db.commit()
    return output(doc)


@app.post("/api/contexts/cleanup", dependencies=[O])
def expire(db: DB = D):
    return {"deleted": cleanup(db)}


@app.post("/api/artifacts", dependencies=[O])
def artifacts(data: ArtifactIn, db: DB = D):
    session = record(db, data.session_id, "session")
    if session.data["project_id"] != data.project_id:
        raise HTTPException(422, "Proyecto incorrecto")
    previous = record(db, data.previous_id, "artifact") if data.previous_id else None
    if previous and previous.data["project_id"] != data.project_id:
        raise HTTPException(422, "Versión de otro proyecto")
    value = {
        **data.model_dump(),
        "version": previous.data["version"] + 1 if previous else 1,
        "status": "draft",
    }
    value["digest"] = hashlib.sha256(
        json.dumps(value, sort_keys=True).encode()
    ).hexdigest()
    from .observability import event

    event(
        "artifact_draft",
        project_id=data.project_id,
        kind=data.kind,
        digest=value["digest"],
    )
    return add(db, "artifact", value)


@app.post("/api/artifacts/{id}/approve", dependencies=[O])
def approve(id: str, db: DB = D):
    r = record(db, id, "artifact")
    if r.data["status"] != "approved":
        db.add(Approval(artifact_id=id, digest=r.data["digest"]))
        r.data = {**r.data, "status": "approved"}
        db.commit()
    return output(r)


@app.get("/api/projects/{id}/export", dependencies=[O])
def export(
    id: str,
    target: str = Query(default="codex", pattern="^(codex|claude-code)$"),
    db: DB = D,
):
    project = record(db, id, "project")
    all_artifacts = [
        r
        for r in db.scalars(select(Record).where(Record.kind == "artifact"))
        if r.data["project_id"] == id
    ]
    superseded = {r.data.get("previous_id") for r in all_artifacts}
    current = [r for r in all_artifacts if r.id not in superseded]
    if not current or any(r.data["status"] != "approved" for r in current):
        raise HTTPException(
            409, "Apruebe todas las versiones actuales antes de exportar"
        )
    return {
        "target": target,
        "prompt": "# Implementar "
        + project.data["name"]
        + "\n\nInspecciona el repositorio antes de modificarlo. Implementa incrementalmente y verifica los criterios de aceptación. No inventes fuentes ni alteres decisiones aprobadas sin consultarlo.\n\n"
        + "\n\n".join(
            f"## {r.data['kind']}: {r.data['title']} (v{r.data['version']}, SHA256 {r.data['digest']})\n{r.data['content']}\nCriterios de aceptación:\n"
            + "\n".join("- " + c for c in r.data["acceptance_criteria"])
            for r in current
        ),
    }


@app.post("/api/repositories", dependencies=[O])
def repositories(data: RepositoryIn, db: DB = D):
    record(db, data.project_id, "project")
    repository(data.path)
    return add(db, "repository", data.model_dump())


@app.get("/api/repositories/{id}/inspect", dependencies=[O])
def repo_inspect(
    id: str,
    query: str = Query(default="", max_length=200),
    file: str | None = None,
    db: DB = D,
):
    return inspect(record(db, id, "repository").data["path"], query, file)


@app.post("/api/connections", dependencies=[O])
def connections(data: ConnectionIn, db: DB = D):
    validate_url(data.url)
    for eid in data.expert_ids:
        record(db, eid, "expert")
    if data.token_env and not data.token_env.startswith("MCP_SECRET_"):
        raise HTTPException(422, "Use una variable MCP_SECRET_...")
    return add(db, "connection", data.model_dump())


@app.get("/api/connections/{id}/tools", dependencies=[O])
async def discover(id: str, db: DB = D):
    return await remote(record(db, id, "connection"))


@app.post("/api/connections/{id}/approve", dependencies=[O])
def approve_tool(id: str, data: ToolCallIn, db: DB = D):
    r = record(db, id, "connection")
    if (
        data.tool not in r.data["write_tools"]
        or data.expert_id not in r.data["expert_ids"]
    ):
        raise HTTPException(403, "Sin permiso")
    return add(db, "tool_approval", {"connection_id": id, **data.model_dump()})


@app.post("/api/connections/{id}/call", dependencies=[O])
async def call_tool(
    id: str, data: ToolCallIn, approval_id: str | None = None, db: DB = D
):
    return await execute(
        db,
        record(db, id, "connection"),
        data.expert_id,
        data.tool,
        data.arguments,
        approval_id,
    )


@app.post("/api/tool-requests/{id}/execute", dependencies=[O])
async def execute_requested_tool(id: str, db: DB = D):
    request = db.scalar(select(Record).where(Record.id == id).with_for_update())
    if not request or request.kind != "tool_request":
        raise HTTPException(409, "Solicitud ya atendida o inexistente")
    d = request.data
    request.kind = "tool_request_consumed"
    db.commit()
    approval = add(db, "tool_approval", d)
    return await execute(
        db,
        record(db, d["connection_id"], "connection"),
        d["expert_id"],
        d["tool"],
        d["arguments"],
        approval["id"],
    )


@app.post("/api/memories", dependencies=[O])
async def memories(data: MemoryIn, db: DB = D):
    if not data.approved:
        raise HTTPException(422, "La memoria requiere aprobación explícita")
    if not settings.memory_token:
        raise HTTPException(503, "Memoria no configurada")
    if data.scope != "personal":
        record(db, data.target_id, data.scope)
    group = "vitruvius:" + data.scope + ":" + (data.target_id or "owner")
    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(
            settings.memory_url + "/episodes",
            headers={"Authorization": "Bearer " + settings.memory_token},
            json={
                "group_id": group,
                "text": data.text,
                "approved": True,
                "name": str(uuid4()),
            },
        )
    if r.status_code >= 400:
        raise HTTPException(502, "Servicio de memoria no disponible")
    result = r.json()
    event = add(
        db,
        "memory_event",
        {
            "scope": data.scope,
            "target_id": data.target_id,
            "group_id": group,
            "episode_id": result["episode_id"],
            "status": "approved",
        },
    )
    return {**result, "record_id": event["id"]}


@app.delete("/api/memories/{id}", dependencies=[O])
async def delete_memory(id: str, db: DB = D):
    event = record(db, id, "memory_event")
    async with httpx.AsyncClient(timeout=90) as client:
        r = await client.post(
            settings.memory_url + "/episodes/" + event.data["episode_id"] + "/delete",
            headers={"Authorization": "Bearer " + settings.memory_token},
            json={"group_id": event.data["group_id"]},
        )
    if r.status_code >= 400:
        raise HTTPException(502, "No se pudo borrar el episodio")
    db.delete(event)
    db.commit()
    return {"deleted": True}


@app.post("/api/skills/import", dependencies=[O])
async def import_skill_route(
    name: str = Form(...), file: UploadFile = File(...), db: DB = D
):
    from .skills import import_skill

    value = import_skill(file.filename or "", await file.read(1024 * 1024 + 1))
    return skills(SkillIn(name=name, content=value), db)


@app.post("/api/sessions/{id}/draft", dependencies=[O])
async def draft(id: str, data: DraftIn, db: DB = D):
    if not settings.openrouter_key:
        raise HTTPException(503, "OpenRouter no configurado")
    session = record(db, id, "session")
    board = record(db, session.data["board_id"], "board")
    from .board import BoardRunner

    runner = BoardRunner(
        db, session, [record(db, e, "expert") for e in board.data["expert_ids"]]
    )
    history = messages(id, db)[-60:]
    if not history:
        raise HTTPException(422, "Primero discuta el problema con el Board")
    try:
        generated = json.loads(
            await runner.complete(
                "Redacta un BORRADOR de "
                + data.kind
                + " basado solo en la discusión. Distingue pendientes, alternativas, restricciones, riesgos y decisiones propuestas. No inventes fuentes ni aprobaciones. JSON con title, content y acceptance_criteria (lista de strings verificables).",
                history,
                structured=True,
            )
        )
        value = ArtifactIn(
            project_id=session.data["project_id"],
            session_id=id,
            kind=data.kind,
            **generated,
        )
    except Exception:
        raise HTTPException(502, "No se pudo generar un borrador válido") from None
    return artifacts(value, db)


@app.post("/api/projects/{id}/review", dependencies=[O])
async def implementation_review(id: str, data: ReviewIn, db: DB = D):
    if not settings.openrouter_key:
        raise HTTPException(503, "OpenRouter no configurado")
    repo = record(db, data.repository_id, "repository")
    if repo.data["project_id"] != id:
        raise HTTPException(422, "Repositorio de otro proyecto")
    approved = export(id, "codex", db)
    evidence = inspect(repo.data["path"], data.query)
    from .board import BoardRunner

    session = db.scalar(select(Record).where(Record.kind == "session"))
    if not session:
        raise HTTPException(422, "Cree una sesión")
    runner = BoardRunner(db, session, [])
    report = await runner.complete(
        "Revisa los fragmentos contra los requisitos aprobados. Cita ruta, línea y commit. No afirmes ejecución de pruebas ni revisión de archivos no suministrados. Expón límites y riesgos.",
        [{"specification": approved["prompt"], "evidence": evidence}],
    )
    return add(
        db,
        "review",
        {
            "project_id": id,
            "commit": evidence["commit"],
            "query": data.query,
            "report": report,
        },
    )


@app.post("/api/memories/search", dependencies=[O])
async def memory_search(data: MemorySearchIn, db: DB = D):
    if not settings.memory_token:
        raise HTTPException(503, "Memoria no configurada")
    if data.scope != "personal":
        record(db, data.target_id, data.scope)
    group = "vitruvius:" + data.scope + ":" + (data.target_id or "owner")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            settings.memory_url + "/search",
            headers={"Authorization": "Bearer " + settings.memory_token},
            json={"group_id": group, "query": data.query, "limit": 6},
        )
    if r.status_code >= 400:
        raise HTTPException(502, "Búsqueda de memoria no disponible")
    return r.json()


@app.delete("/api/sessions/{id}", dependencies=[O])
async def delete_session(id: str, db: DB = D):
    from sqlalchemy import delete

    session = record(db, id, "session")
    if db.bind.dialect.name == "postgresql":
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

        # UUID IDs generated by the server; exact prefix matches only this session.
        runs = (
            db.execute(
                text(
                    "SELECT DISTINCT thread_id FROM checkpoints WHERE thread_id LIKE :prefix"
                ),
                {"prefix": id + ":%"},
            )
            .scalars()
            .all()
            if db.execute(text("SELECT to_regclass('checkpoints')")).scalar()
            else []
        )
        async with AsyncPostgresSaver.from_conn_string(
            settings.database_url.replace("postgresql+psycopg://", "postgresql://")
        ) as saver:
            for run in runs:
                await saver.adelete_thread(run)
    for doc in list(db.scalars(select(Record).where(Record.kind == "context"))):
        if doc.data["session_id"] == id and doc.data["scope"] in ("REQUEST", "SESSION"):
            remove_document(db, doc)
    db.execute(delete(Message).where(Message.session_id == id))
    db.delete(session)
    db.commit()
    return {
        "deleted": True,
        "note": "Los documentos permanentes, artefactos y memorias aprobadas conservan su retención independiente",
    }


# The standard Python MCP SDK implements Streamable HTTP and protocol negotiation.
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

mcp = FastMCP(
    "Vitruvius",
    stateless_http=True,
    json_response=True,
    streamable_http_path="/",
    transport_security=TransportSecuritySettings(
        allowed_hosts=["127.0.0.1:*", "localhost:*", "localhost", "vitruvius.work"],
        allowed_origins=["http://localhost:*", "https://vitruvius.work"],
    ),
)


@mcp.tool()
def list_boards() -> list[dict]:
    if not database.Session:
        raise ValueError("PostgreSQL no configurado")
    with database.Session() as db:
        return [
            output(r) for r in db.scalars(select(Record).where(Record.kind == "board"))
        ]


@mcp.tool()
def list_sessions() -> list[dict]:
    with database.Session() as db:
        return [
            output(r)
            for r in db.scalars(select(Record).where(Record.kind == "session"))
        ]


@mcp.tool()
def create_session(
    board_id: str, project_id: str, title: str = "Nueva discusión"
) -> dict:
    with database.Session() as db:
        return sessions(
            SessionIn(board_id=board_id, project_id=project_id, title=title), db
        )


@mcp.tool()
def get_session(session_id: str) -> list[dict]:
    with database.Session() as db:
        return messages(session_id, db)


@mcp.tool()
async def discuss(session_id: str, text: str, max_turns: int = 5) -> list[dict]:
    with database.Session() as db:
        return await run_turn(db, session_id, TurnIn(text=text, max_turns=max_turns))


@mcp.tool()
def attach_context(
    session_id: str, title: str, text: str, retention_hours: int = 24
) -> dict:
    with database.Session() as db:
        return contexts(
            ContextIn(
                session_id=session_id,
                title=title,
                text=text,
                retention_hours=retention_hours,
            ),
            db,
        )


@mcp.tool()
def get_skill(skill_id: str) -> dict:
    with database.Session() as db:
        return output(record(db, skill_id, "skill"))


@mcp.tool()
def export_development_prompt(project_id: str, target: str = "codex") -> dict:
    with database.Session() as db:
        return export(project_id, target, db)


@mcp.tool()
def create_project(name: str, description: str = "") -> dict:
    with database.Session() as db:
        return projects(ProjectIn(name=name, description=description), db)


@mcp.tool()
def list_contexts(session_id: str) -> list[dict]:
    with database.Session() as db:
        record(db, session_id, "session")
        return [
            output(r)
            for r in db.scalars(select(Record).where(Record.kind == "context"))
            if r.data["session_id"] == session_id
        ]


@mcp.tool()
def create_context_upload(
    session_id: str,
    title: str,
    content_type: str = "application/pdf",
    retention_hours: int = 24,
) -> dict:
    if content_type not in ("application/pdf", "text/plain", "text/markdown"):
        raise ValueError("Unsupported format")
    with database.Session() as db:
        doc = contexts(
            ContextIn(
                session_id=session_id, title=title, retention_hours=retention_hours
            ),
            db,
        )
        return {"context_id": doc["id"], "upload": upload(doc["id"], content_type, db)}


@mcp.tool()
def finalize_context_upload(context_id: str) -> dict:
    with database.Session() as db:
        return finalize(context_id, db)


@mcp.tool()
async def propose_specification(session_id: str, kind: str = "specification") -> dict:
    with database.Session() as db:
        return await draft(session_id, DraftIn(kind=kind), db)


class MCPAuth:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            from .auth import check_token

            try:
                check_token(dict(scope["headers"]).get(b"authorization", b"").decode())
            except HTTPException:
                from starlette.responses import JSONResponse

                return await JSONResponse({"error": "Unauthorized"}, status_code=401)(
                    scope, receive, send
                )
        return await self.app(scope, receive, send)


app.mount("/mcp", MCPAuth(mcp.streamable_http_app()))
static = Path(__file__).parent / "static"
if static.exists():
    app.mount("/assets", StaticFiles(directory=static / "assets"), name="assets")

    @app.get("/")
    def portal():
        return FileResponse(static / "index.html")
