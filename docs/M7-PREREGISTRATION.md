# M7 pre-registration: native agent runtime, tool engine, MCP and A2A interfaces, browser policy layer

Written BEFORE any M7 code or run (14 Nov 2026). Amendments go at the bottom. This milestone is engineering: every hypothesis is a **property that must hold** (test, no statistics), plus one interoperability check against an external reference implementation.

## What was checked online before designing (14 Nov 2026) and what is claimed
- MCP: the current revision is **2026-07-28**; it removed the `initialize`/`initialized` handshake (version and capabilities travel per request in `_meta`; `server/discover` replaces it). The official Python SDK (`mcp` 2.3.0, installed in an isolated venv) reports `LATEST_PROTOCOL_VERSION = 2026-07-28`, and its client in `mode="auto"` probes `server/discover` and falls back to the `initialize` handshake for older servers; `mode="legacy"` forces the handshake. Handshake-era versions known to that SDK: 2024-11-05, 2025-03-26, 2025-06-18, 2025-11-25.
  **Claim made by this milestone:** a **handshake-era** MCP server (tools only: `initialize`, `ping`, `tools/list`, `tools/call`) that the official client can use. **Not claimed:** the 2026-07-28 revision, Streamable HTTP, resources, prompts, sampling, OAuth.
- A2A: spec versions differ. v0.3.0 task states are lowercase (`submitted`, `working`, `input-required`, `completed`, `canceled`, `failed`, `rejected`, `auth-required`, `unknown`); v1.0 renames them `TASK_STATE_*`. I could not confirm the official Agent Card path from an official page (a third-party issue says `/.well-known/agent-card.json`). **Claim made:** an in-process **model** of the v0.3.0 lifecycle and of card-based discovery, with the card path configurable and unverified. **Not claimed:** wire compatibility with any A2A version.
- Sources: https://modelcontextprotocol.io/docs/2026-07-28/learn/versioning ; https://github.com/modelcontextprotocol/modelcontextprotocol (tools.mdx for 2025-06-18 and 2026-07-28); https://a2a-protocol.org/v0.3.0/specification/ ; https://a2a-protocol.org/v1.0.0/specification/ ; the `mcp` 2.3.0 package source.

## Properties (each must hold or M7 fails)
**Tool engine**
- T1 default deny: an agent can call only tools whose capability it was explicitly granted; unknown agents, unknown tools and revoked agents are refused.
- T2 discovery is filtered: an agent lists only the tools it may call.
- T3 input validation: calls that violate the schema (wrong type, missing required, extra field, out-of-range, too long, enum, pattern, boolean-as-integer, nested violations) are refused before the handler runs.
- T4 output validation: oversize or non-serialisable handler output becomes an error result, never a crash.
- T5 audit: every attempt (allowed or denied) appends a Ledger v2 entry; entries hold a hash of the arguments and the argument names, never raw arguments or raw outputs; the chain verifies and detects edits.
- T6 timeout, T7 rate limit, T9 handler exceptions become error results and the engine keeps serving.
- T8 approval: tools with external side effects need a one-time approval token bound to the exact arguments, single use, with an expiry; a token for other arguments, a reused token and an expired token are refused.
**MCP adapter**
- M1 JSON-RPC 2.0: ids echoed; parse error -32700; invalid request -32600; unknown method -32601; invalid params -32602; notifications get no reply; `server/discover` answers -32601 (so the official client falls back).
- M2 `initialize` negotiation returns a supported `protocolVersion`, `capabilities.tools`, `serverInfo`.
- M3 `tools/list` returns `name`, `description`, `inputSchema`; `tools/call` returns `content[]` and `isError`; permission and validation failures are tool errors (`isError: true`), malformed protocol use is a protocol error.
- **M5 interoperability:** the official `mcp` 2.3.0 client, in `auto` and in `legacy` mode, over stdio, connects, lists exactly the tools the configured agent may call, calls one successfully, and receives `isError` for a denied and for an invalid call, without raising. FAILS on any exception. A pinned 2026-07-28 connection is also attempted and the outcome recorded as it is (not expected to work, not claimed).
**Agent runtime**
- A1 lifecycle transitions follow an allowed table; illegal ones are refused. A2 retries use backoff and stop at max attempts. A3 crash recovery: after discarding the runtime and rebuilding from its ledger and result store, unfinished tasks run and finished tasks do not run again (idempotency key). A4 the runtime audit chain verifies.
**A2A model**
- B1 task state machine: terminal states are final; illegal transitions are refused. B2 discovery and negotiation: a caller sees a card, and a task is accepted only if the skill exists and the caller holds permission for it. B3 boundary: the callee receives only the message, callers are authenticated (HMAC as in M5), unauthenticated or replayed requests are refused, and no credential is passed along. B4 absence is explicit: with no card, discovery returns nothing and the browser path is labelled `browser-automation`, never `agent-to-agent`.
**Browser policy layer** (a policy and audit layer over an abstract driver; a real browser driver is **not built**: no dependency was justified yet)
- W1 only allow-listed origins (exact scheme, host and port); lookalike hosts, `user@host` tricks, other ports, `http` downgrades, `file:`, `data:`, `javascript:` refused. W2 redirects are re-checked against the allow-list. W3 sensitive fields (password, card number, government id patterns, hidden fields) are never filled by the agent. W4 submitting a form needs a single-use approval bound to the form and values. W5 page text is returned wrapped as untrusted data and never triggers a tool call. W6 every action is audited without raw field values.

## Explicitly not covered
Real network, TLS, OAuth/OIDC, a real browser, CAPTCHA, resource isolation of handler code (a timed-out handler thread keeps running), side channels, the 2026-07-28 MCP revision, A2A wire protocol.

## Amendments
(none)
