# M5 threat model (prototype scope)

## Assets
1. Each tenant's raw experiences and learned parameters (confidential to the tenant).
2. Integrity of each child's event history and checkpoints.
3. Integrity of the parent's registry and audit chain.
4. Availability of the parent (not addressed in the prototype).

## Actors
Honest child; **curious child** (tries to read another tenant's data); **malicious child** (forges, replays, floods, smuggles data out in messages); **compromised parent** (out of scope: a compromised parent sees all metadata, but by design holds no raw data or parameters); **network attacker** (out of scope in-process; a real deployment needs TLS and per-child asymmetric keys).

## Threats, mitigations and the test that checks them
| # | Threat | Mitigation in the prototype | Test (H5-P) |
|---|---|---|---|
| T1 | Unregistered or revoked client talks to the parent | parent issues id+secret; revoke removes access | P1 |
| T2 | Child speaks as another child | HMAC-SHA256 per child secret, constant-time compare | P2 |
| T3 | Replay of a captured message | strictly increasing sequence number per child | P3 |
| T4 | Raw data smuggled in a message | exact per-type field allowlist, strict value patterns, size cap, no nesting | P4, P5 |
| T5 | Tenant A learns from tenant B's data | the parent offers no read API for child data; separate stores; no shared references | P5, P6 |
| T6 | A child rewrites its own history after reporting | parent keeps the last reported head and length; prefix check | P7 |
| T7 | Tampered local checkpoint restored | restore checks the parent's recorded parameter hash | P8 |
| T8 | Silent parent-side tampering or loss of the audit trail | parent audit chain is Ledger v2 (detects edits when checked) | P9 |
| T9 | Rejection log becomes a leak | rejections log only the reason and a truncated claimed id, never the payload | P1 |

## Explicitly NOT covered
- Real cryptographic key management: secrets are random bytes generated in memory and handed to the child directly; a deployment needs asymmetric keys, rotation and an HSM or KMS.
- Covert channels through allowed fields (a child can still leak a few bits through numbers and identifiers it is allowed to send).
- Model inversion or membership inference from parameters (the parent never receives parameters, but a later knowledge-sharing step in M6 will, and needs its own analysis).
- Denial of service, rate limiting, timing side channels, transport security, and anything outside one process.
- A hash chain detects edits when it is checked; it does not prevent them, and it cannot show who edited.
