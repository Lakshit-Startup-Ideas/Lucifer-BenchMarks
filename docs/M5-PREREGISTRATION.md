# M5 pre-registration: parent coordinator and independent children

Written BEFORE any M5 code or run (14 Nov 2026). Amendments go at the bottom with the reason.

## Scope
An **in-process prototype** (no network, no real key management) of a parent coordinator and independent child systems, built on Ledger v2 (`ledger.py`) and the event-sourced learner (`events.py`). Each child is its own trust boundary. The parent sees **metadata only**: ledger head and length, parameter hashes, checkpoint names, evaluation numbers. Raw experiences and parameters never leave a child.
It says nothing about LLMs. The threat model and its limits are in `M5-THREAT-MODEL.md`.

## Property hypotheses (tests, no statistics; each must hold or M5 fails)
- **H5-P1 registration:** a child can only talk to the parent after the parent issues it an id and a secret; unregistered, revoked or unknown ids are rejected and the rejection is logged without the payload.
- **H5-P2 authentication:** a message whose HMAC does not verify is rejected; a child cannot speak as another child, even in the same tenant.
- **H5-P3 replay protection:** an envelope with a sequence number not greater than the last accepted one is rejected.
- **H5-P4 schema allowlist:** every message type has an exact set of allowed fields with strict value patterns (hashes are 64 hex characters, names are short identifiers, numbers are finite). Unknown fields, nested values, free text, oversize payloads and raw-looking values are rejected.
- **H5-P5 no raw leakage:** after children observe and learn from a canary vector, a full export of the parent's state contains no trace of the canary (value strings, content hash, parameters).
- **H5-P6 independence:** training child A leaves child B's parameter hash unchanged; stores are separate objects; the parent holds no references to child objects.
- **H5-P7 anchored audit:** the parent stores each child's last reported ledger head and length; `verify_child` accepts the honest child, and rejects a child whose history was rewritten (even with recomputed hashes) or truncated below the anchor, while accepting a child that has appended since the anchor.
- **H5-P8 checkpoint integrity:** a child restoring a checkpoint is checked against the parameter hash the parent recorded; a tampered local checkpoint is rejected.
- **H5-P9 audit trail:** registration, heartbeats, checkpoint and evaluation reports, rejections and revocation each add one entry to the parent's own Ledger v2 chain, which verifies.

## Statistical hypotheses: when does sharing help? (brief items 4 and 5, simulated)
Setup: 2 tenants, 6 contexts, items `x ~ N(0, I_20)`, label from a hidden linear rule per (tenant, context); 60 training examples per (tenant, context), shuffled; 5 epochs of per-example SGD (lr 0.1) with the M4 learner (rank 4); 300 test items per (tenant, context). Rules are built as in M4 (half a shared direction, half a sparse part). 30 seeds, paired.
- `personal`: one model per tenant trained only on that tenant's data.
- `pooled`: one model trained on both tenants' data together, heads keyed by context id only (what a shared-only system would do).
- World `same`: both tenants have identical rules. World `conflict`: tenant B's rules are independent of tenant A's for the same context ids.
Metric: mean test accuracy over tenants and contexts. Paired difference, 95% bootstrap interval.
- **H5a (sharing hurts when rules conflict):** `personal` minus `pooled` >= +0.10 in world `conflict` with the lower end > +0.05. FAILS otherwise.
- **H5b (sharing helps when rules agree):** `pooled` minus `personal` >= +0.02 in world `same` with the lower end > 0. FAILS otherwise (then sharing has no demonstrated benefit even when allowed, and the review mechanism of M6 has less to protect).

## What a pass would and would not mean
A pass of H5a+H5b shows that whether to share depends on whether tenants' rules agree, so a review step must test agreement before promoting knowledge (M6). It does not show that real users' knowledge behaves like this. The properties show the prototype enforces its own rules in-process; they do not show a deployed system is secure.

## Amendments

**A1 (14 Nov 2026, after run 1; thresholds NOT changed).** Property hypotheses P1-P9 all pass. H5a PASS (personal minus pooled +0.147 in the conflict world). H5b FAIL as registered: pooled minus personal +0.0085 [+0.0006, +0.0162], below the 0.02 threshold. Mutation check of the security tests: first run was invalid (pytest imported unmutated code through `pythonpath`), redone correctly; see `M5-RESULTS.md`.
