# Deployment status — 2026-11-25

## Operational prototype

- Main: 142.93.15.239 / 10.116.0.4. HTTPS portal https://vitruvius.work, REST /api, authenticated MCP /mcp/. Caddy TLS certificate verified. API on loopback behind proxy; Redis, worker and scheduler have no public ports.
- Memory: 157.245.85.152 / 10.116.0.5. Graphiti API bound to private 8001, Bearer authentication, Docker-aware source restrictions allowing main VPC host only. Neo4j 5.26.27 has no published ports. Public 7474, 7687 and 8001 were tested closed.
- Managed PostgreSQL authenticated with the exact corrected private-file password; pgvector 0.8.7 active, embeddings and checkpoint persistence tested. No local production database substitute.
- OpenRouter authentication and real model/embedding calls passed. The owner confirmed rotation. Keys injected through root-only environment files; never committed.
- Spaces private ACL verified, real bounded presigned upload, extraction, embedding and deletion passed. Browser CORS installed for the public portal and local SSH-tunnel origins.
- LangSmith API authentication, synthetic trace write/read and actual Board trace redaction verified. Inputs and outputs were empty in eight inspected actual spans. Memory, context, tool, repository and artifact events record identifiers/counts rather than contents. US default endpoint accepted this account's key.
- Owner login details: `/root/vitruvius-access.txt` on the main server, mode 0600. Runtime secrets under `/etc/vitruvius/runtime.env` and `/etc/vitruvius-memory/runtime.env`. No secrets in this repository or deployment report.

## Implemented scope

| Module | Implementation |
|---|---|
| Skill Registry | Immutable Markdown versions, safe Markdown/ZIP import, explicit version references. |
| Knowledge Engine | Real text/Markdown/PDF ingestion, pgvector semantic retrieval, page/chunk provenance and owner-supplied source metadata. Empty founding libraries. |
| Expert Builder and Boards | Persistent named literature-inspired virtual specialists, skills and configurable models; seven-member founding Board. |
| Board Orchestrator | Dynamic LangGraph moderator, objections/replies/questions, bounded context/turn/tool budgets, durable checkpoints and session history. |
| Long-term memory | Independent Graphiti/Neo4j, OpenRouter inference/embeddings/reranking, explicit curation, scoped search and episode deletion. |
| Projects and code intelligence | Project/session association; owner-mounted Git sources read-only, safe tracked-file listing/search/read and commit provenance. No code execution. |
| Requirements, ADRs and artifacts | Discussion-derived drafts or manual revisions, acceptance criteria, hash-bound owner approvals, current-revision gate. |
| Development handoff | Approved specification prompt export for Codex and Claude Code. |
| Implementation Reviewer | Read-only repository evidence compared to approved artifacts, bounded findings, no invented test execution. |
| MCP inbound | Standard Streamable HTTP; shared session tools, project/session creation, contextual text, presigned temporary upload and draft/export. |
| MCP outbound and tool permissions | Origin allowlist, discovery, per-expert read/write permissions. Writes become owner-reviewable exact-argument requests and one-use approvals. |
| Observability and evaluation | Sanitized LangSmith model/token/session metadata and operation events; 18 deterministic automated tests plus live integration checks. |
| Context Management Engine | SESSION default/24h, REQUEST expiry, all six scopes, expert restrictions, configurable retention, explicit promotion, deletion of originals/chunks/vectors, repeat-deletion tombstones and cross-client continuity. |
| Multimodal extension | Future scope preserved; no claim of audio/video/podcast processing. |

Docling runs in the production worker with CPU-only PyTorch, two threads, one concurrent ingestion, persistent model cache and a 55-minute soft task limit and 60-minute hard task limit. A real synthetic PDF was uploaded through Spaces, extracted with page 1 provenance, embedded and removed successfully. OCR remains disabled. Plain-text/PDF ingestion does not claim EPUB, HTML synchronization or multimedia support.

## Verification evidence

- 16 main-service automated tests, 2 memory-service automated tests passed. These include authentication, context isolation/expiry/promotion/deletion, approval-gated export, repository traversal and sensitive-file exclusion, skill versions/import, exact write-tool approvals, dynamic graph routing, MCP protocol, bounded context and curated-memory episode tracking/deletion.
- Vue/Vuetify production build passed. Visual portal review checked the council, decision and context controls at mobile and desktop layout breakpoints.
- Full live synthetic run passed: pgvector embedding → dynamic Board → shared MCP history → generated draft → approval → handoff → Spaces upload → worker → deletion → Graphiti ingestion/search/isolation → session/history/checkpoint deletion.
- Graphiti relation check extracted 4 nodes and 3 edges, returned 3 facts and returned no facts in another namespace. Synthetic episodes were deleted.
- LangSmith trace write/read and actual content redaction passed; public API and MCP without credentials returned 401, portal returned 200 with valid TLS.
- No books or papers were ingested. All verification data was explicitly synthetic. Interrupted verification sessions are cleaned separately before final handoff.

## Limits and follow-up validation

- This is an operational single-owner prototype. There is no claim of high availability, load testing, backup restoration validation or production security certification.
- Actual books/papers, licensing/provenance review, bibliographic quality evaluation, dataset-based expert evaluations and automated source synchronization await owner-supplied sources. No author opinions are asserted.
- Individual ChatGPT/Claude/Gemini connector setup and OAuth support are not verified; standard Bearer MCP protocol continuity was tested. External VueForge/Alexandria MCP URLs, credentials and allowed tools were not supplied, so no remote integration is represented as connected.
- OCR, EPUB, richer office-file conversion, audio/video/podcasts and automatic failed-graph resumption are not enabled. Completed messages survive failures; retries create visible new turns.
- Original attachment expiry does not erase quotations already generated in private conversation history/checkpoints, provider retention or backups. Session deletion removes local temporary context, messages and checkpoints; permanent knowledge/approved artifacts/curated memories retain independent policies.
- Managed database and droplet backups/restore have not been verified through the DigitalOcean control plane. The supplied doadmin database role is used initially; create a restricted application role and mount the provider CA for verify-full TLS as follow-up hardening. Supplied sslmode=require is active.
- DNS was updated by the owner and public resolver A now returns 142.93.15.239 with no AAAA. Some recursive resolvers may retain the old parking answers until their cache expires. TLS was verified directly against the target address with the real hostname.

## Grounding and expert content correction

The previous ungrounded opinion behavior is disabled. Experts need reviewed primary libraries, retrieved exact quotations and claim review. References, extracted content and reviewed foundations are separate states. Professional profiles remain drafts until owner approval. X/YouTube URLs alone are not ingested evidence. The 20 MiB upload limit has been removed across the pipeline. See GROUNDING.md for behavior, retained operational limits and validation.


## Conversación como recorrido principal
- Navegación principal reducida a proyectos, conversación y biblioteca de expertos. Memoria, documentos, skills y conexiones opcionales bajo herramientas avanzadas.
- Crear/seleccionar un proyecto abre conversación; el primer mensaje crea la sesión. Selectores secundarios plegados.
- Acuerdos y entrega se abren desde una charla con historial; explicación de requisitos y decisiones, revisión y aprobación conservadas.
- Repositorios salen del panel. Un enlace raíz HTTPS de GitHub en un turno dispara lectura pública sin credenciales, limitada a índice y cuatro fragmentos del commit fijado. Solo contexto del caso, no evidencia de autor. No clona, escribe ni ejecuta código.
- Repositorios privados y otros proveedores: integración de acceso pendiente; mensaje explícito de acceso no disponible, nunca se presenta como analizado. No se amplió acceso a credenciales ni conexiones del propietario.
- Límite de lectura inicial: hasta cuatro archivos de 80 KB (primeros 1600 caracteres), muestra de 35 rutas, índice truncado indicado; cada enlace nuevo solicita otra lectura. No promete una revisión completa ni navegación autónoma por todo el código.
- Validación: 41 pruebas backend, compilación frontend y recorrido visual local aislado.
- API pública de GitHub documentada en https://docs.github.com/en/rest/git/trees y https://docs.github.com/en/rest/git/blobs
