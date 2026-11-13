# Lucifer V1: experiment plan

Status: v0.1, the plan as written **before** any real run (kept unchanged below). The first real run is now done: convention task set, `qwen2.5-coder:14b`, 5 seeds, 12 Nov 2026. See section 7 of `docs/IMPLEMENTATION-GUIDE.md` and `results/published/qwen14b-convention/`. That run used 18 similar + transfer tasks, fewer than the roughly 48 this plan recommends (see "Power" below), so it is a first look, not a final verdict.

## The one claim
> **H1.** An ordinary open-weight language model, given persistent memory of its own earlier attempts and a feedback signal, solves *later, related* tasks at a higher rate than the same model without them.

Everything else (dashboard, other mechanisms, training, wearables, factories) waits until H1 has a measured answer. A "no" is a valid result and gets reported.

## Conditions (same model, same prompts, same retries)
| | Memory written | Memory read at eval |
|---|---|---|
| **A. baseline** | no | no |
| **B. lucifer** | yes | the most *relevant* lessons (lexical retrieval, top 3) |
| **C. irrelevant** | yes | the *least* relevant lessons, same count (the code's control; random picks were often relevant by luck) |

C is the control that matters most. If B beats A but not C, the gain came from a longer prompt, not from learning.

## Phases (per seed, per condition, fresh memory each time)
1. **Experience.** Run the *experience* tasks in a seeded random order. B and C write a lesson after every attempt (failure: what failed and what the spec said; success after a retry: the fix).
2. **Frozen evaluation.** Memory is read-only. Run: *similar* tasks (same pitfall, new problem), *transfer* tasks (pitfalls mixed in a new way), and *replay* tasks (the experience tasks again, to detect forgetting and plain memorisation).

Within a task every condition gets one retry after seeing the failing test's output, so the baseline is not handicapped.

## Metrics
- **Primary:** pass@1 (first attempt passes the hidden tests) on similar + transfer tasks.
- Secondary: pass@2, attempts per task, latency, prompt and completion tokens, retrieval hit rate.
- Every number comes from `results/*/attempts.jsonl`; nothing is typed in by hand.

## Gates (they mirror the promises already made in outreach, so they must be real)
1. **Improvement.** The 95% paired-bootstrap interval for `B − A` on the primary metric is above zero, **and** so is `B − C`.
2. **Retention.** On tasks the baseline solves reliably (≥ 80%, chosen on half of the seeds), B's pass@1 on the *other* half of the seeds is no more than 5 points below A's. (Choosing and measuring on the same runs would select tasks the baseline got lucky on, and regression to the mean would look like forgetting; the dashboard exposed this.) With one seed, or no mastered task, the gate is inconclusive.
3. **Auditability.** Every memory write has provenance (task, run, seed, version) and sits in a hash chain; `verify_chain()` passes; rolling back to version *n* reproduces version *n* exactly.

## Statistics
- Unit of analysis is the **task** (average its seeds first), bootstrap over tasks, 10,000 resamples, 95% interval.
- At least 5 seeds per condition. Report intervals, not just means.
- With 24 tasks the interval will be wide. That is expected; the 24 tasks exist to test the harness. The real run needs 100+ tasks (see "Before the real run").

## Power: how many tasks are enough (measured on simulated agents)
Simulated learner (a real +20 point average effect on similar and transfer tasks), 5 seeds, **60 simulated experiments per row**; "passed" means gate 1 passed (both intervals above zero). A simulated agent that cannot learn gives the false-alarm column.

| similar + transfer tasks | gate 1 passed (real effect) | gate 1 passed (no effect) |
|---|---|---|
| 12 (first 24-task set) | 19 of 60 (32%) | 0 of 60 |
| 24 | 43 of 60 (72%) | 1 of 60 |
| **26 (current 50-task set)** | 32 of 60 (53%) | 1 of 60 |
| 48 | 59 of 60 (98%) | 3 of 60 |
| **52 (current set, repeated twice)** | 59 of 60 (98%) | 0 of 60 |
| 72 | 60 of 60 | 1 of 60 |

(An earlier 20-run table said 90% at 24 tasks. That was a lucky draw; 60 runs corrected it. Even 60 runs leave about ±6 points of noise.)

The current 50-task set has 26 similar + transfer tasks, which detects a real +20 point effect about half the time. A "no effect" from it is therefore still weak evidence. The real run needs **at least about 48 similar + transfer tasks** (the current set doubled, or a second batch of new families); smaller true effects need more (not measured yet). These rows repeat the same tasks under new ids, so real, varied tasks will behave a little worse.

## Before the real run (do not skip)
1. **Harness controls (done in tests).** A simulated agent that cannot learn must fail gate 1 almost always; one that learns must pass; one that is hurt by memory must fail. If the harness cannot tell these apart, no result from it means anything.
2. **Calibrate difficulty.** Run the baseline alone. Keep tasks where it passes 20–80% of the time. At ~0% or ~100% there is no room to show an effect.
3. **Grow the task set** to 100+ tasks (for example a vetted slice of MBPP-style problems plus these pitfall families), split into experience / similar / transfer *before* looking at any results.
4. **Pin everything:** model tag and quantisation, temperature, seeds, prompt templates, git commit. Free hosted APIs change under you; use a model you run yourself.
5. **Pre-register the stop rule:** if gate 1 fails on the calibrated 100-task set with 5 seeds, the result is "no measurable effect of this mechanism" and we say so.

## Threats to validity (known, to be tracked)
- Memorisation of the task set by the base model (check against replay and a fresh task family).
- Retrieval that leaks the answer from a near-duplicate task (similar tasks must differ in function, not just names).
- Prompt-length effects (condition C).
- Small samples (intervals), temperature noise (seeds), and a lenient lexical retriever.
- Model-written code runs on the machine doing the evaluation. Tasks here are tiny, but untrusted scale needs a container sandbox.

## Compute budget (estimates; replace with measured numbers)
24 tasks × 3 conditions × 5 seeds × ≤ 2 attempts ≈ 720 generations for the harness test set; about 3,000 for a 100-task run. At ~150 output tokens and 10–15 tokens/s on an M1 Air, a 100-task run is several hours: an overnight job on a 7–8B model, or minutes on a rented GPU.
