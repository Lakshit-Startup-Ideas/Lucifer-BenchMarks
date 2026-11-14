# V1 memory hash: findings and the v2 fix

Found 14 Nov 2026 by experiment on Lucifer-BenchMarks at commit `fe08665` (`src/lucifer/memory.py`). The published V1 result is not affected (nobody tampered with the chain); these are weaknesses in what the chain can promise.

| # | Finding | How verified | v2 (`src/lucv11/ledger.py`) |
|---|---|---|---|
| 1 | `run_id` and `seed` are outside the hash. Changing them leaves `verify_chain()` and `audit()` True. | scratch DB: edit both, both checks still True | all seven fields are hashed; test `test_editing_any_field_including_provenance_breaks_the_chain` |
| 2 | Fields are joined with `"|"`, no length. `("a|b","c")` and `("a","b|c")` give the same hash. | direct comparison returned True | every field is length-prefixed (8-byte big-endian) plus a domain tag; test `test_v1_separator_collision_exists_and_v2_removes_it` |
| 3 | Anyone who rewrites every row and recomputes the hashes produces a valid chain. V1 stores no outside copy of the head. | reasoning, plus test on the v2 ledger | `verify(expected_head, expected_length)` checks against an externally stored anchor; tests for rewrite and truncation |
| 4 | `audit().provenance_ok` only checks fields are non-empty. | read the code | `add()` refuses empty `run_id`/negative seed; provenance is hashed |

Compatibility: `hash_v1` reproduces the V1 formula (two test vectors taken from the V1 code), so V1 chains remain verifiable. Mixing v1 and v2 entries in one chain is not supported; migrate by starting a new v2 chain whose first entry records the final v1 head.

Limits: a hash chain detects edits only when checked, says nothing about who edited, and does not make deletion of the whole store impossible. The anchor must live somewhere the ledger's owner cannot silently change (for example an OpenTimestamps-stamped head, or a signed tag).
