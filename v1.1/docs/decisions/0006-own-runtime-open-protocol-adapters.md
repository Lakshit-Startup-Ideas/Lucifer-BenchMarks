# ADR 0006: Own tool engine and runtime; MCP and A2A as thin adapters, pinned to a named protocol era

- **Date:** 14 Nov 2026
- **Status:** accepted; 2026-07-28 MCP, A2A wire protocol and a real browser driver are **future work**
- **Problem:** the brief asks for an independently designed agent platform (no dependency on LangChain, LangGraph or CrewAI), an MCP-compatible tool infrastructure, agent-to-agent communication, and browser interaction, without rebuilding standards for no reason.
- **Decision:**
  1. The tool engine (`tools.py`) is protocol-independent and holds the policy: deny by default, filtered discovery, validation, rate limit, timeout, one-time bound approvals, audit without raw data.
  2. MCP is an **adapter** (`mcp_server.py`) pinned to the handshake era (2025-06-18 / 2025-11-25), proven against the official SDK client. Claims name the protocol era; the 2026-07-28 revision is not claimed.
  3. A2A is a **model** of the lifecycle and discovery with explicit "agent-to-agent vs browser-automation" routing; no wire claim.
  4. The browser layer is a **policy layer** over an abstract driver; credentials, card numbers and similar fields are never filled by the agent, and submitting needs a one-time human approval.
  5. Standards are checked online before each compatibility claim (done 14 Nov 2026); the SDK is used only in an isolated test venv, not as a dependency of the product.
- **Evidence:** `docs/M7-RESULTS.md`: 193 tests, 21 of 22 mutants killed (1 equivalent), official client interop in two modes.
- **Rejected:**
  - Building on an agent framework: against the brief; the policy layer is the part that matters and is small.
  - Claiming "MCP compatible" without naming the era: the current revision removed the handshake, so the claim would have been wrong for new clients.
  - Adding a browser automation dependency now: no real-driver requirement was tested yet; a policy layer with a fake driver is the smallest honest step.
- **Trade-offs:** adapters must be revised as protocols move; this one will need a 2026-07-28 variant to talk to modern-only clients.
- **Implementation status:** `tools.py`, `mcp_server.py`, `agents.py`, `a2a.py`, `browser.py`. **Validation status:** unit and interop tests only; nothing run against a real third-party agent, site or browser.
