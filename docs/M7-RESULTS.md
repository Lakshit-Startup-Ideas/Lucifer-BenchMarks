# M7 results: native agent runtime, tool engine, MCP and A2A interfaces, browser policy layer

Property run (14 Nov 2026), Python 3.15.2 only, 193 tests pass (4 interop tests need the isolated venv and ran there; they are skipped in the mutation copies). Registered properties: `M7-PREREGISTRATION.md`.
Engineering milestone: the hypotheses are properties, not statistics.

## Verdicts
| Group | Verdict | Evidence |
|---|---|---|
| Tool engine T1-T9 | **PASS** | `tests/test_tools.py` (default deny, indistinguishable refusals, filtered discovery, 15 invalid-input cases, output limits, handler errors without leaking, timeout, rate limit, one-time approvals bound to agent, tool and exact arguments, audit without raw arguments) |
| MCP adapter M1-M4 | **PASS** | `tests/test_mcp.py` (JSON-RPC errors and ids, notifications, batch refused, initialisation gate, tool errors as results, approval via `_meta`, stdio loop, real subprocess) |
| **M5 interoperability with the official SDK** | **PASS for the handshake era, FAIL (as expected) for 2026-07-28** | see below |
| Agent runtime A1-A4 | **PASS** | lifecycle table, exponential backoff and max attempts, crash recovery without repeating finished tasks (idempotency key), verifiable log |
| A2A model B1-B4 | **PASS** (as a model) | state machine, authenticated and replay-protected submission, peers see only their own tasks, unknown and unpermitted skills rejected identically, routes labelled `agent-to-agent` or `browser-automation` |
| Browser policy W1-W6 | **PASS** (over a fake driver) | 14 hostile URLs refused without reaching the driver, redirect re-check, sensitive fields never filled, one-time submit approval bound to the form, page text wrapped as untrusted, audit without raw values |

## Interoperability, observed (official `mcp` 2.3.0 client, stdio, our server as agent `reader`)
| Client mode | Result |
|---|---|
| `auto` | probed `server/discover` (our server answers "method not found"), fell back to `initialize`, negotiated **2025-11-25**, listed exactly `add` and `echo`, `add(2,3)` returned `5`, an invalid call and a call to the hidden `draft_email` and to a missing tool all returned `isError: true`; no exception |
| `legacy` | same result |
| `writer` agent, `legacy` | lists `add`, `draft_email`, `echo`; `draft_email` without approval returns `isError` with `approval_required` |
| pinned `2026-07-28` | **fails** (exception group); this revision is not supported and is not claimed. A test records it so a future change must update the claim |
The official client parses our `tools/list` and `tools/call` results with its own strict types, so the shapes match what that SDK expects in the handshake era.

## Do the tests bite? Mutation check
22 mutants, one safeguard disabled each, tests run from the mutated copy: 21 killed. The survivor (`a2a terminal states not final`) is an **equivalent mutant**: the transition table already has no exits from terminal states, so the explicit guard is redundant defence in depth and removing it changes nothing. Mutants: capability check, input validation, rate limit, approval single-use, approval binding, approval expiry, raw arguments in audit, handler message echoed, output size cap, tool errors as protocol errors, initialisation gate, `server/discover` answered, retries without limit, idempotency, A2A replay, A2A skill permission, A2A task ownership, browser redirect re-check, userinfo in URL, sensitive-field check, browser approval binding.

## Limits, stated plainly
- **MCP:** handshake era only, tools only, stdio only. Not the 2026-07-28 revision, not Streamable HTTP, no resources, prompts, sampling, OAuth. stdio has no in-band authentication, so the connection runs as one configured agent identity.
- **A2A:** an in-process **model** of the v0.3.0 lifecycle and card discovery. Not wire compatible with any version; the card path is unverified (taken from a third-party issue).
- **Browser:** a policy and audit layer over a fake driver. No real browser, no JavaScript, no cookies or sessions, no CAPTCHA handling, no real prompt-injection corpus: W5 shows page text never triggers an action in this layer, not that a model reading it is immune.
- **Tool engine:** a handler that times out keeps running in its thread; there is no resource isolation or sandbox for handler code. The rate limit counts only calls that reached a handler. Approvals are in-memory and not persisted.
- **Runtime:** the task log stores task arguments (needed for recovery), so it is private state; the result store is in memory and must be persisted with the log for real recovery.
- Only Python 3.15 was run locally; the CI matrix (3.11 and 3.13) has never run.

## Decision: ADR `decisions/0006-own-runtime-open-protocol-adapters.md`
