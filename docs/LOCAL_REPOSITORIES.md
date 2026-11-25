# Local code from an external conversation

The portal has no conversation menu, chat composer, or chat testing entry point. Conversations happen in an authenticated MCP client. The portal manages experts, sources and approvals and provides a narrowly focused folder-sharing page.

## Workflow

1. Client calls `list_projects` / `list_boards`, then `create_session`, or reuses `list_sessions` and the existing session.
2. At the owner's request, call `prepare_local_repository(session_id)` and present its URL. This does not read the computer or upload files. The URL contains only the session ID and grants no access.
3. Owner opens the link on the computer with the code, signs in with their owner token if required, and selects a folder in the browser. `webkitdirectory` offers broad browser compatibility and grants no write capability. Never ask for the owner token in a conversation.
4. Owner reviews the eligible relative paths, optionally deselects files, grants explicit consent, and clicks Share temporary copy. Selection alone performs no upload. No Git account, mount, local daemon or filesystem permission in the external client is needed.
5. Same client/session calls `list_local_repositories`, `search_local_repository` and `read_local_repository`. `discuss` automatically includes relevant real code excerpts as `provided_context` for grounded expert reasoning. A different session cannot read the copy even if it knows the repository ID.
6. Disconnect on the sharing page or wait for expiry. Share a new copy to reflect local changes. Sharing the same folder name in the same session atomically replaces its previous snapshot only after validation succeeds. Nothing is automatically synchronized.

## Privacy and limits

- Read-only snapshot. No clone, build, shell, Git command, filesystem path on the server, or code execution. Never infer commit identity: this is the selected local working copy, possibly with uncommitted changes.
- Relative paths only, no absolute paths, traversal or hidden components. Browser selection returns file objects; Vitruvius does not request OS-wide filesystem access.
- Client and server both exclude hidden directories, dependencies, build artifacts, unsupported extensions, common credential filenames and private-key/credential patterns. Matching contents are skipped before upload; server repeats checks and rejects the whole payload atomically if a suspect file remains. Validation responses omit submitted code.
- Filters are best effort, not a secret-detection guarantee. `.gitignore` is **not interpreted**. Review the selection and share only code the owner is authorized to send. Symlink handling is the browser's file-picker behavior; there is no server symlink traversal or arbitrary filesystem read.
- Up to 500 selected text files, 200 KB per file in the browser, 200,000 characters per file server-side, two million characters in total, three active snapshots per session. Skipped files make the copy explicitly partial. These are code-context budgets separate from document uploads (the old 20 MB document cap remains removed).
- Names/paths and selected text reach private PostgreSQL only after consent. Relevant excerpts reach OpenRouter when consulted. No snapshot text is returned in the general catalog or stored as bibliographic foundation. Tracing inputs/outputs remain redacted.
- Fixed 24-hour expiry in the UI; API permits 1–24 hours. Expired copies become immediately unreadable. The existing cleanup worker removes expired rows on its retention schedule; deleting a session removes all its snapshots. Worker queue delays can postpone physical cleanup, not expiry enforcement.
- Disconnect deletes the queryable snapshot. Quotes in saved answers/citations and the external client's chat can persist under their own retention. Backups follow provider policies; this is not a promise of erasure from backups or from clients.
- Search returns ranked real excerpts. Read allows 1–150 lines, at most 6000 characters per call, with line ranges, truncation flag and SHA256 of the full shared file text. Longer files need additional ranges; very long individual lines remain bounded. These tools do not claim to audit the entire repository.
- All REST and MCP operations use existing owner authentication. The sharing link adds no credential, public read endpoint, broader permissions, or access to memory/Neo4j.

## Client compatibility

This is standard inbound MCP functionality at `https://vitruvius.work/mcp/` with the existing owner Bearer authentication. It works independently of a client's local file access **once that client is successfully connected to this MCP server**. Client-specific account/plan, remote-connector authentication and transport support still need verification in each actual client. Do not claim that Claude, ChatGPT and Gemini have been individually connected or validated merely because the MCP protocol test passed. No client credentials or OAuth configuration are assumed.

Browser references: https://developer.mozilla.org/en-US/docs/Web/API/HTMLInputElement/webkitdirectory and https://developer.mozilla.org/en-US/docs/Web/API/File/webkitRelativePath .

## Validation

- 60 backend tests, including auth, consent, excluded paths, secret filtering, redacted errors, session isolation, real search/ranges/digests, expiry/retention, disconnect/session deletion, shared MCP/API state, and code delivered to the grounded council.
- Three browser-module tests: selecting a folder reads no contents, excluded/unselected files never reach preparation, suspected credentials are skipped before upload.
- Production frontend build and isolated browser walkthrough using a synthetic private-demo folder with a deliberately excluded `.env` fixture.
- Production smoke passed: authenticated real MCP prepare/list/search/read, cross-session isolation, actual council response citing local code plus a reviewed primary premise, immediate disconnect, and synthetic-data cleanup.
- Public built assets verified to contain folder sharing and no portal chat/testing entry point.
- Actual-client connections in the owner's Claude, ChatGPT and Gemini accounts remain unverified; no universal client authentication claim is made.
