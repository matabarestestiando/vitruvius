# Vitruvius

Single-owner expert council. Vue 3/Vuetify portal, FastAPI, dynamic LangGraph discussion, OpenRouter, redacted LangSmith tracing, managed PostgreSQL/pgvector, Spaces, MCP server/client, private Graphiti memory in the independent `vitruvius-memory` repository.

No authors are impersonated. The initial seven named panelists are virtual specialists with **empty libraries**. No books, papers, remote tools, or repository contents are claimed to have been ingested.

## Develop

Python 3.12, uv, Node 22. `uv sync --frozen`; `uv run pytest -q`; in `frontend`, `npm ci` and `npm run build`. Set private environment variables from `.env.example` before running `uv run uvicorn app.main:app --port 8000`. The portal development server is `npm run dev` in `frontend`.

## Deploy

Runtime secrets: `/etc/vitruvius/runtime.env`, root-owned mode 0600. Source in `/opt/vitruvius`. `docker compose --env-file /etc/vitruvius/runtime.env up -d --build`. Never run `docker compose config` in shared logs because it expands secrets. API binds only `127.0.0.1:8000`. Use an SSH tunnel until DNS and HTTPS are configured. Compose runs Redis, an ingestion worker, and a retention scheduler without public ports.

Copy the managed PostgreSQL connection using an exact confirmed password (URL encode it). Production never falls back to SQLite or a local PostgreSQL instance. Database initialization creates the initial schema, vector extension, and HNSW index. Use a non-administrator application role after initial provisioning. Prefer `sslmode=verify-full` with the provider CA mounted read-only; `require` is the supplied initial mode and does not verify server identity.

The owner token is generated on the server and never committed. Browser authentication is Bearer and held in memory only. All REST operations except `/healthz` and the portal assets require it. MCP at `/mcp/` has the same authorization. Never use the owner token over public plain HTTP.

See [scope and architecture](docs/ARCHITECTURE.md), [operations](docs/OPERATIONS.md), [implementation status](docs/STATUS.md), and [API workflow](docs/API.md).

## Grounding required

Expert names do not constitute evidence. The Board now requires reviewed primary libraries and retrieved, quoted evidence before allowing technical claims; unsupported responses abstain. Existing experts without primary sources will not issue technical opinions. Expert references, content ingestion and owner-approved professional profiles are documented in [GROUNDING.md](docs/GROUNDING.md). X/YouTube links alone are not ingested evidence; provide their text/transcript/PDF in this version.
