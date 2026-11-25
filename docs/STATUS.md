# Estado actual: consejo y conversaciones libres

- El propietario invoca al consejo desde un cliente MCP conectado. `start_conversation` no requiere proyecto. Se retiraron el menú y la creación de proyectos del portal, además de los antiguos tools MCP de configuración de proyectos. El chat del portal sigue eliminado.
- Una conversación puede terminar sin artefactos. La especificación solo se genera a petición y su exportación exige aprobar la revisión actual de esa conversación.
- Vitruvius evalúa declaraciones del propietario y propone recuerdos duraderos con razón y cita literal. No guarda automáticamente las propuestas. El propietario puede aprobarlas, descartarlas o pedir expresamente que se guarde un texto.
- Las peticiones explícitas escriben en la memoria privada y conservan el texto aprobado como registro canónico recuperable. La búsqueda no depende de que Graphiti haya extraído relaciones de ese texto. El catálogo general no expone los textos de memoria.
- Producción verificada: inicio sin proyecto; revisión real por modelo con propuesta sin escritura; consentimiento obligatorio; guardado real en Graphiti privado y recuperación del texto aprobado; especificación solicitada, aprobada y exportada; limpieza completa de datos sintéticos.
- 69 pruebas backend y compilación frontend correctas. El procesamiento de carpetas conserva sus tres pruebas de navegador. Vista aislada del portal validada sin proyectos ni chat.
- No se probó la conexión desde las cuentas particulares del propietario en Gemini, ChatGPT y Claude Code; cada cliente debe admitir MCP remoto y la autenticación existente. Actualice las herramientas del cliente para usar el nuevo recorrido.
- Datos y asociaciones anteriores conservados. Los ámbitos internos de compatibilidad son privados por conversación y no son una configuración del producto. Véase CONVERSATION_MODEL.md.

## Historial de despliegue anterior

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


## Conversaciones desde clientes; repositorios locales

El portal ya no tiene chat ni menú Conversación. Claude, ChatGPT o Gemini conectado a MCP mantiene la conversación; el portal administra fuentes, expertos y acuerdos y abre la selección de carpeta a petición del cliente.

`prepare_local_repository` devuelve un enlace autenticado al propietario para la sesión. La carpeta se selecciona en el navegador y se comparte explícitamente como copia temporal de 24 horas. El mismo cliente puede listar, buscar y leer el código real; `discuss` lo incorpora como contexto del caso, sin sustituir las fuentes del experto. Las copias se pueden desconectar y vencen incluso si el worker tarda en limpiarlas.

No es acceso en vivo al disco, no requiere publicar el repo privado y no necesita configurar repositorios en un panel. No se verificó la conexión individual de los tres clientes: cada uno debe admitir MCP remoto y la autenticación existente. Véase LOCAL_REPOSITORIES.md para límites y verificación.
