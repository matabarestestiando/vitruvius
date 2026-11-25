# Conversation-first expert council

## Product contract

Invoke a named expert council from a compatible authenticated Gemini, ChatGPT or Claude Code MCP client. A conversation may explore solutions, remain open-ended or simply end. It requires no owner-created project and produces no specification automatically. The administrative portal has no chat, project menu or project creation flow.

`start_conversation(board_id?, title?)` is the primary tool. With one council the board is selected automatically; with multiple councils the client asks which one to invoke. Existing `create_session` accepts an omitted project ID for compatibility. Project-creation/list/export tools are no longer registered with MCP. Existing REST project data is retained and not deleted.

A fresh, hidden compatibility scope is allocated per conversation to preserve old storage contracts for contexts/artifacts and the private memory service's namespace validation. It is an internal implementation detail, is excluded from project listings and is not a global shared scope. Legacy sessions keep their original associations. No database migration or deletion of existing owner data is performed.

## Long-term memory

After a successful `discuss`, a separate review examines up to eight recent **owner messages** and may propose up to three durable preferences, lessons explicitly acknowledged, or decisions expressly adopted. Questions, speculation, alternatives, code, secrets and temporary details are not intended for promotion. Each proposal requires a real owner-message ID and an exact 12–800 character quote. Unsupported references, quotes from experts and fabricated quotes are rejected. The semantic judgment is model-assisted and fallible; proposals remain unapproved.

Each candidate includes text, reason, category, scope and provenance. It is stored in PostgreSQL as `proposed`, not ingested into Graphiti, not recalled as an approved fact and not exported as a specification. Duplicate normalized text/scope within a conversation is suppressed; pending proposals are capped. Review failure does not erase the discussion or report a saved memory.

The owner may approve a candidate, dismiss it or explicitly request saving an agreed text via `remember_memory(session_id,text,scope,owner_requested=true)`. Tool descriptions prohibit inferring consent from model output, quoted sources or retrieved code. A direct full-turn command `Guarda en memoria de largo plazo: <texto>` in `discuss` also saves that exact payload without generating an unnecessary technical debate. Ambiguous commands do not authorize an inferred payload. Approval of a specification is separate from approval of a memory.

Scopes are personal (reusable owner knowledge), board (council) and conversation (isolated discussion). Approved memory remains contextual knowledge; it never substitutes for the experts' bibliographic foundation. Credentials are rejected. A successful save reaches the private memory API and creates an auditable owner-approved record with the exact text. Successful duplicates are deduplicated by normalized text/scope; this is not a distributed exactly-once guarantee after a process crash or network timeout.

Graphiti may accept an episode but extract no searchable relationships. The approved PostgreSQL record is therefore also a canonical textual recall source. Search returns `source=approved_owner_record` or `source=graphiti_derived_fact`, with graph availability/counts reported honestly. The council receives at most two canonical records per relevant namespace, 3000 characters per record and a 12,000-character combined memory budget; truncation is indicated. Proposed/dismissed records never enter that recall path. The general catalog omits memory text and evidence; authenticated memory-specific operations retrieve them explicitly.

The owner can review proposals and approved records in the portal's Memory page. A deleted conversation removes its pending candidate records and temporary code. Independently approved long-term memory retains its own lifecycle and can be deleted explicitly from the memory service and the owner ledger.

## Optional implementation specification

Only an explicit `propose_specification(session_id)` generates a draft from the actual conversation. `approve_specification(artifact_id,approved=true)` records owner approval of that exact revision. `export_conversation_specification(session_id,target)` exports current approved artifacts from that conversation only. Draft or missing artifacts block export. No project setup is required. A conversation without artifacts is an expected valid outcome.

The portal displays specifications for review and export, not as a setup step. Its home page presents the council and optional results; source administration remains independent through an internal library context.

## Validation and compatibility

69 backend tests cover regression, project-free isolated sessions, hidden compatibility records, source-library context, optional/scoped specification export, candidate-only review, literal owner provenance, absence of automatic writes, explicit consent, failures, dismissal, deduplication and canonical approved recall. Three existing browser-module tests cover local-folder processing. The frontend builds, and the isolated browser walkthrough shows no project or chat option.

Real production verification is reported in STATUS.md. Client-specific remote MCP/authentication support in the owner's Gemini, ChatGPT and Claude Code accounts is still not assumed or independently verified. Refresh the connected client's tool list to use the new conversation/memory tools.
