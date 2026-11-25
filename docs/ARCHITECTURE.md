# Product scope and architecture

Recovered from all three pages of the referenced conversation on 2026-11-25. Later decisions supersede earlier Qdrant/Zep proposals: managed PostgreSQL + pgvector and independent Graphiti/Neo4j are selected.

## Product

A private, single-owner workspace to create skills and experts, constitute named expert boards, discuss software problems through a real dynamically routed LangGraph, inspect project repositories without running or changing their code, and turn provisional conclusions into owner-approved requirements, ADRs, specifications and development prompts for Codex/Claude Code. Compatible MCP clients can continue the same server-side session; interoperability must be verified per client and is not promised universally.

Initial board: Antonio Gulli (agent architecture), Harrison Chase (LangGraph), Chip Huyen (AI engineering), Daniel Chalef (memory), Martin Kleppmann (distributed systems), Cathy Pearl (conversation design), Micheal Lanham (implementation). These are virtual panelist names inspired by specialties, not the authors, their endorsements, or actual statements. Their libraries start empty. Sources require explicit upload and actual retrieval before they can support citations. No fake book/paper counts or fabricated source ingestion.

Skills are immutable versioned Markdown records; experts reference versions. Boards reference persistent experts. Projects own sessions, repository associations, requirements and ADRs. Discussion history is in PostgreSQL. A moderator chooses speakers dynamically, can revisit a specialist and stop early; turn/recursion/tool-call budgets bound execution. Specialists address colleagues by name, retrieve permitted context and approved scoped memories, and can call registered MCP tools under explicit per-expert permissions. Model output is never an approval. Failed sessions preserve completed messages.

## Deployment topology

- `vitruvius` 142.93.15.239 / VPC 10.116.0.4: Vue 3 + Vuetify, FastAPI, MCP, LangGraph, Redis + Celery ingestion and retention.
- `vitruvius-memory` 157.245.85.152 / VPC 10.116.0.5: authenticated API on private port 8001; Graphiti and Neo4j on a Docker network. Neo4j publishes no ports. Main droplet is the only allowed network caller.
- Managed PostgreSQL private address resolves to 10.116.0.6: structured data, history, approvals, vector chunks, LangGraph checkpoints. Private/TLS connection. No local database in production.
- DigitalOcean Spaces: private originals and temporary attachments; bounded short-lived presigned POST upload. No bucket name, region or endpoint is assumed.
- OpenRouter: all generation, embeddings and Graphiti reranking use its OpenAI-compatible endpoint, with configurable models. No silent provider fallback or placeholder responses.
- LangSmith: explicit sanitized model spans with model/token/session metadata; request, document, prompt, response and credentials omitted. Content-free context, repository, tool, artifact and memory events provide identifiers and counts; memory events accept validated UUID correlation IDs. Broader quality evaluation remains tracked in STATUS.

## Context Management Engine

Default scope SESSION and 24-hour retention; REQUEST retires at the end of a discussion call. PROJECT, BOARD, EXPERT and GLOBAL require explicit permanent consent. Expert allowlists further restrict any scope. Retrieval applies scope, target and expiry before scoring, with page and chunk provenance. Original files, extracted text and embeddings are removed on expiry/deletion. Object-only tombstones repeat deletion until outstanding five-minute upload signatures have expired, preventing reupload orphans. Cleanup runs every minute while services are healthy. Failed object deletion does not erase the record, allowing a later retry. Permanent promotion is an explicit owner action. Long-term Graphiti writes require a separate explicit approval; temporary material is never automatically sent as a memory episode.

Original-document retention is distinct from the conversation: expert answers and private checkpoints may contain derived excerpts. Those remain part of session history until the session is deleted. The UI and operations documentation must disclose this; no claim of erasure from provider systems or backups. Spaces bucket lifecycle, versioning and provider retention need operator configuration.

Text, Markdown and text-based PDFs supported initially, with page citations and limits. The production worker uses Docling with CPU-only PyTorch, table extraction, two CPU threads and a five-minute task limit; OCR is disabled in this initial configuration. Model weights are cached in a private persistent volume. Future source types include EPUB/HTML, OCR for scanned PDFs, audio/video/podcasts, RSS, scene analysis, transcript speakers and timestamps. Unsupported source types fail explicitly. Never pretend these pipelines are already active.

## Decisions and execution

Artifacts are immutable revisions. Approval binds to the content SHA256 and revision. A newer unapproved revision blocks handoff export. Export includes only current approved artifacts and their acceptance criteria. MCP write approvals bind to connection, expert, tool and exact arguments and are consumed before dispatch. Read-only repository intelligence uses only owner-mounted repositories, tracks commit SHA, excludes dot-env files, dependencies, Git internals, traversal, large and unsupported files, and never fetches, builds or executes repository code. MCP origins must be preauthorized in server configuration.

## Data model and extensibility

PostgreSQL `records` stores typed entity payloads; `messages`, `chunks`, `approvals` have relational foreign keys. pgvector column is 1536-dimensional (explicit model contract); JSON vectors support tests, cosine HNSW supports production. Initial schema setup is idempotent; future changes need versioned migrations. MCP, memory and object-storage adapters separate services. Group IDs are validated by the memory API and deterministically hashed for Graphiti's restricted namespace alphabet.
