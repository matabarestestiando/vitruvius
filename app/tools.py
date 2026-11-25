import os
from urllib.parse import urlparse
import httpx
from fastapi import HTTPException
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from sqlalchemy import select
from .db import Record
from .config import settings


def validate_url(url):
    u = urlparse(url)
    origin = f"{u.scheme}://{u.netloc}"
    if (
        u.scheme != "https"
        or u.username
        or u.password
        or origin not in settings.mcp_origins.split(",")
    ):
        raise HTTPException(
            422, "El origen HTTPS debe estar autorizado en MCP_ALLOWED_ORIGINS"
        )
    return url


async def remote(connection, tool=None, arguments=None):
    d = connection.data
    validate_url(d["url"])
    token = os.getenv(d.get("token_env") or "")
    headers = {"Authorization": "Bearer " + token} if token else {}
    async with httpx.AsyncClient(
        headers=headers, follow_redirects=False, timeout=30
    ) as http:
        async with streamablehttp_client(d["url"], http_client=http) as (
            read,
            write,
            _,
        ):
            async with ClientSession(read, write) as session:
                await session.initialize()
                if tool:
                    return (await session.call_tool(tool, arguments or {})).model_dump(
                        mode="json"
                    )
                return (await session.list_tools()).model_dump(mode="json")


async def execute(db, connection, expert_id, tool, arguments, approval_id=None):
    d = connection.data
    if expert_id not in d["expert_ids"]:
        raise HTTPException(403, "Experto sin acceso")
    if tool not in d["read_tools"] + d["write_tools"]:
        raise HTTPException(403, "Herramienta sin permiso")
    if tool in d["write_tools"]:
        approval = (
            db.scalar(select(Record).where(Record.id == approval_id).with_for_update())
            if approval_id
            else None
        )
        expected = {
            "connection_id": connection.id,
            "expert_id": expert_id,
            "tool": tool,
            "arguments": arguments,
        }
        if (
            not approval
            or approval.kind != "tool_approval"
            or approval.data != expected
        ):
            pending = next(
                (
                    r
                    for r in db.scalars(
                        select(Record).where(Record.kind == "tool_request")
                    )
                    if r.data == expected
                ),
                None,
            )
            if pending is None:
                pending = Record(kind="tool_request", data=expected)
                db.add(pending)
                db.commit()
            raise HTTPException(
                409,
                {
                    "message": "La acción requiere aprobación del propietario para estos argumentos exactos",
                    "request_id": pending.id,
                },
            )
        # Consume before external invocation; failed writes require a new approval (at-most-once dispatch).
        approval.kind = "tool_approval_consumed"
        db.commit()
    result = await remote(connection, tool, arguments)
    from .observability import event

    event("mcp_tool", connection_id=connection.id, expert_id=expert_id, tool_name=tool)
    db.add(
        Record(
            kind="tool_audit",
            data={
                "connection_id": connection.id,
                "expert_id": expert_id,
                "tool": tool,
                "success": not result.get("isError", False),
            },
        )
    )
    db.commit()
    return result
