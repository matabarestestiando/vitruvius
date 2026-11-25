# Operations

## Secrets and activation

The owner supplied `/root/credentials.txt` on the main server. It must remain mode 0600, outside Git. The environment loader never prints values. The owner confirmed rotation of OpenRouter and database credentials in this session and corrected the ambiguous database-password annotation in the private file. The exact updated value was used successfully; no password candidates were guessed. Maintain the same private-file procedure for future rotation.

Main environment: `/etc/vitruvius/runtime.env`; memory environment: `/etc/vitruvius-memory/runtime.env`. These files also contain generated owner/internal API/Neo4j credentials. Do not expose them through compose output, process arguments, issue reports or traces. The shared memory token must match both sides. Secrets do not exist in container images. Reload configuration by recreating containers.

For Spaces supply AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, SPACES_ENDPOINT, SPACES_REGION and SPACES_BUCKET. Configure private bucket access and CORS for the actual HTTPS portal origin, POST and required upload headers. Presigned requests expire in five minutes and enforce 20 MB. Configure bucket lifecycle as a backstop for abandoned uploads and appropriate deletion of object versions; do not promise erasure while versioned copies persist.

For LangSmith supply the actual API key and optional workspace ID, endpoint and project. Default project is vitruvius-prod; no claim of created remote projects until verified. Inputs/outputs are hidden. Do not turn on global automatic tracing with private context. Observe token/latency metadata and validate redaction with a canary before broader tracing.

## Private access

`ssh -N -L 8000:127.0.0.1:8000 -i ~/.ssh/vitruvius root@142.93.15.239`

Open http://localhost:8000. Obtain the owner token directly from the root-only environment file in your own secure terminal. Do not paste it into a shared transcript. An unauthenticated health check is `/healthz`; authenticated `/api/status` checks PostgreSQL and reports integration configuration, not full integration success.

DNS must point vitruvius.work to 142.93.15.239 before enabling Caddy. Check AAAA too. The provided Caddyfile terminates TLS on the main server and proxies loopback. Configure MCP host/origin protection for actual public hostnames before remote-client testing. No certificates, DNS records, Spaces buckets, LangSmith projects or external MCP connections are assumed to exist.

Memory firewall script installs Docker-aware source restrictions. Persist with a systemd oneshot after Docker and before exposing the API. Neo4j has no public HTTP/Bolt ports. Access via `docker compose exec` or a deliberate tunnel if needed, not public mapping.

## Retention and reliability

Celery worker processes at most one upload concurrently. Beat schedules cleanup each minute. Monitor worker/scheduler failure; expired context is excluded from retrieval even during cleanup outages. REQUEST contexts are deleted after a discussion attempt. A deleted upload leaves an object-only tombstone for ten minutes. Cleanup repeats object deletion during that window to remove any late upload made with an outstanding five-minute signature; no extracted content is retained in tombstones. Bucket lifecycle is an additional safety net. Temporary attachment deletion does not by itself erase generated conversation answers, external provider retention or backups. Delete the session when its derived history should also be purged.

The PostgreSQL advisory lock serializes concurrent clients for the same session. Checkpoints are private and keyed by session/run. Partial completed expert messages survive provider failures. Initial implementation does not automatically resume a failed in-flight graph; owner retries are visible new turns. Tool-write approval is consumed before dispatch, so a failed external request requires a new approval and must be checked for remote completion before retrying.

## Verification, backup and rollback

Run `uv run pytest -q` in each repository and `npm ci && npm run build` in frontend. Test real pgvector/checkpoint/Neo4j integrations on isolated test data, and distinguish those checks from credential-dependent live operations. Never ingest literature as a test unless owner supplied it. Provider smoke tests use explicitly labeled synthetic technical facts only and must be removed afterward.

Enable and verify DigitalOcean managed DB backups and droplet backups; not assumed active. Back up Neo4j with a consistent dump while stopped (or supported online backup for the chosen edition). Redis is a queue, not the authoritative data store. Document restore and test before relying on backups. No backup job has been claimed installed by the application.

Rollback by restoring the previous source/image and recreating services without `down -v`; never remove volumes. Future schema migrations need a tested rollback/forward strategy. Record service/image IDs, health observations and unresolved issues in STATUS.md. Avoid dumping logs that might contain third-party errors with request bodies.
