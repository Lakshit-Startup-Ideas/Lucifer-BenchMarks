# Lucifer V1.1 (research log, simulation only)

Version 1 (everything outside this folder) asks one question: does a frozen model that remembers its own mistakes solve later tasks better? V1.1 asks the harder questions behind it, in eight milestones, using **small simulated learners we wrote ourselves**. **No language model is involved in any V1.1 result.**

Read first: [`docs/TECHNICAL-REPORT.md`](docs/TECHNICAL-REPORT.md) (scoreboard, claims ledger, measured overhead, limits). The public, append-only milestone page is at <https://lucifer-update.vercel.app/milestones>.

Goals and how to help: the open issues in the milestone [V1.2: validate with a language model](https://github.com/Lakshit-Startup-Ideas/Lucifer-BenchMarks/milestone/2); the closed [V1.1 milestone](https://github.com/Lakshit-Startup-Ideas/Lucifer-BenchMarks/milestone/1) holds the merged pull request. See [`../CONTRIBUTING.md`](../CONTRIBUTING.md) and the [literature review](docs/LITERATURE.md) (partial, abstract level).

## Scoreboard
21 registered threshold hypotheses: **10 passed, 11 failed**, with no threshold ever moved. Every property check (event pipeline, parent/child protocol, review properties, tool engine, MCP handshake era, runtime, A2A model, browser policy) passed. Each milestone has a pre-registration written and committed **before** its code or run (`docs/M*-PREREGISTRATION.md`), results (`docs/M*-RESULTS.md`) and a decision record (`docs/decisions/`).

## What is here
| Path | What |
|---|---|
| `src/lucv11/` | the code: `ledger.py` (hash chain v2), `dynnet.py` + `m2.py` (growable networks), `m3.py` (executive), `learner.py` + `events.py` + `m4.py` (learning, event-sourced), `distributed.py` + `m5.py` (parent and children), `knowledge.py` + `m6.py` (review), `tools.py` + `mcp_server.py` + `agents.py` + `a2a.py` + `browser.py` (M7), `m8.py`, `reproduce.py`, `overhead.py` |
| `tests/` | 202 tests (4 interop tests need an isolated venv with the official `mcp` SDK and skip otherwise) |
| `results/` | raw outputs of every run, including the uninformative first runs |
| `docs/` | pre-registrations, results, ADRs, the M5 threat model, the V1 hash findings, the technical report |
| `proof/`, `tools/prove.py` | proof-of-existence manifests and the tool that creates and verifies them |

## Run it
```bash
cd v1.1
python -m venv .venv && .venv/bin/pip install -e ".[dev]"   # numpy is pinned
.venv/bin/python -m pytest -q                                # 202 tests
.venv/bin/python -m lucv11.reproduce                         # reruns M2-M6 and M8 from scratch and compares every verdict flag (about 70 s)
```
The reproduction compares 23 verdict flags and every number with the committed results. On the author's Mac all matched with a maximum numeric difference of 0; other platforms may differ in the last digits, verdicts must not.

## Proof of existence
`proof/` holds two manifests (SHA-256 of every file at a fixed commit) and their OpenTimestamps stamps: V1 at `fe08665` and V1.1 at `ce5ed13`. Both commits are in this repository's history. To check:
```bash
python3 v1.1/tools/prove.py --verify v1.1/proof/manifest-v11-ce5ed13.json --repo .   # needs a full clone, not a shallow one
ots verify v1.1/proof/manifest-v11-ce5ed13.json.ots                                    # needs a Bitcoin node or block explorer access
```
**Status (14 Nov 2026): both stamps are confirmed in Bitcoin.** The V1 manifest is anchored in block 975752 (06:32 UTC) and the V1.1 manifest in blocks 975759 and 975761 (07:17 and 07:18 UTC). Checked independently: each stamp commits to its manifest's SHA-256 (V1 `ac3c4ffc...`, V1.1 `f85c2af4...`) and the Merkle root it attests equals the block header's Merkle root on a public block explorer.

A timestamp shows a file existed by a date. It does not show who wrote it, and it is not a patent or a copyright registration.

## What this does not show
Nothing here is evidence about language models. Effect sizes in designed worlds follow from our parameters. The review step was tested only against non-adaptive attackers. The MCP server speaks the handshake era and was tested against the official Python client; the 2026-07-28 revision is not supported. The A2A part is a model, the browser part a policy layer over a fake driver. See the technical report, section 6.

Original architecture and USP documents were not available while this was built, so the map from the original Lucifer ideas to V1.1 is **not done**.
