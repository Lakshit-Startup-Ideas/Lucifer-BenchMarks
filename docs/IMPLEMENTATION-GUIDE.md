# Lucifer Lab: the implementation guide

> **Status date:** 11 Nov 2026 · **Repo:** `Lakshit-Startup-Ideas/Lucifer-BenchMarks` (local: `~/Personal/lucifer-lab`)
> **Who this is for:** you. Every part is explained twice: first **like you are 10 years old** (🧒), then **like an engineer** (🛠️). Read only the 🧒 parts for the story, only the 🛠️ parts for the mechanics, or both.

---

## Table of contents

1. [The one-minute version](#1-the-one-minute-version)
2. [The question we are trying to answer](#2-the-question-we-are-trying-to-answer)
3. [The big picture (one diagram)](#3-the-big-picture-one-diagram)
4. [Follow one task from start to finish](#4-follow-one-task-from-start-to-finish)
5. [Every part, one by one](#5-every-part-one-by-one)
   - 5.1 [Tasks (the exam questions)](#51-tasks-the-exam-questions)
   - 5.2 [The sandbox (the referee)](#52-the-sandbox-the-referee)
   - 5.3 [Backends (the students)](#53-backends-the-students)
   - 5.4 [Prompts and lessons](#54-prompts-and-lessons)
   - 5.5 [Memory (the notebook)](#55-memory-the-notebook)
   - 5.6 [Retrieval (finding the right page)](#56-retrieval-finding-the-right-page)
   - 5.7 [The experiment loop](#57-the-experiment-loop)
   - 5.8 [Statistics (is the difference real?)](#58-statistics-is-the-difference-real)
   - 5.9 [The three gates (the final verdict)](#59-the-three-gates-the-final-verdict)
   - 5.10 [Tracing (a flight recorder)](#510-tracing-a-flight-recorder)
   - 5.11 [The dashboard](#511-the-dashboard)
   - 5.12 [Calibration (is the exam the right difficulty?)](#512-calibration-is-the-exam-the-right-difficulty)
   - 5.13 [Simulated agents (testing the tester)](#513-simulated-agents-testing-the-tester)
   - 5.14 [The command line](#514-the-command-line)
   - 5.15 [The tests](#515-the-tests)
6. [What we have learned so far](#6-what-we-have-learned-so-far)
7. [Where the real experiment stands right now](#7-where-the-real-experiment-stands-right-now)
8. [Safety, secrets and honesty rules](#8-safety-secrets-and-honesty-rules)
9. [What is NOT done, and what could fool us](#9-what-is-not-done-and-what-could-fool-us)
10. [What happens next](#10-what-happens-next)
11. [How to run everything](#11-how-to-run-everything)
12. [File map](#12-file-map)
13. [Glossary](#13-glossary)

---

## 1. The one-minute version

🧒 **Like you are 10.**
Imagine two students take the same coding exam, many times.

- **Student A** has no notebook. Every time, they start from zero.
- **Student B** has a notebook. After each practice question they write down what went wrong and what the teacher said. On the next, similar question they flip to the right page first.

We ask a simple question: **does Student B really do better, or does it only *look* that way?** Everything in this project is the machinery that answers it fairly: the questions, a strict referee, the notebooks, a scoreboard, and a flight recorder that shows every step.

🛠️ **Like an engineer.**
Lucifer V1 is an experiment harness (not a new model, not AGI) for one hypothesis:

> **H1.** An ordinary open-weight LLM, given persistent memory of its own earlier attempts and a feedback signal, solves *later, related* tasks at a higher first-attempt rate than the same model without them.

The repo contains: a task bank with hidden tests, a sandboxed code runner, a hash-chained versioned memory store with rollback, TF-IDF retrieval, three experimental conditions, a task-level paired bootstrap, three pass/fail "promotion gates", OpenTelemetry-style tracing, a local web dashboard, a difficulty-calibration tool, simulated agents with known behaviour to test the harness itself, and backends for Groq, Ollama and the simulators. A "no effect" result is a valid, reportable outcome.

**Where we are in one line:** the harness is built and tested (121 tests pass); the first real Lucifer-vs-baseline run on a real model (`openai/gpt-oss-20b` via Groq, 30 "hidden convention" tasks, 3 seeds) is **running now**, and no results are in yet.

---

## 2. The question we are trying to answer

🧒 *Why is this hard to test fairly?*
If Student B gets a higher score, maybe it is not the notebook. Maybe B simply got easier questions, or just got more text to read, or got lucky. So we add careful rules:

- Same questions, same teacher, same number of retries for everyone.
- A **third student, C**, gets a notebook too, but with the **wrong pages**. If B beats A *and* C, the notebook content really matters, not just "having more words on the desk".
- We repeat many times and report a *range* ("the gain is probably between +15 and +50 points"), not a single lucky number.

🛠️ *Design of the claim.*

| Condition | Writes lessons | Reads lessons at evaluation | Purpose |
|---|---|---|---|
| **baseline** (A) | no | no | The model as it is |
| **lucifer** (B) | yes | the **most relevant** lessons (top *k* = 3, TF-IDF) | The idea under test |
| **irrelevant** (C) | yes | the **least relevant** lessons, same count | Control: separates "learning" from "longer prompt" |

> Naming note: `docs/EXPERIMENT-PLAN.md` calls the control "shuffled/random". The code uses `irrelevant` (the *least* relevant lessons), because with a small memory random picks are often relevant by luck, which blurs the comparison. The code is the truth.

**Primary metric:** `pass@1`, meaning the first attempt passes all hidden tests, measured on the **similar** and **transfer** tasks (defined below). Secondary: `pass@2` (after one retry with feedback), attempts, tokens, latency.

**Fairness rule:** within a task, *every* condition gets one retry that shows the failing test's output. The baseline is not handicapped; memory has to help beyond what feedback alone gives.

---

## 3. The big picture (one diagram)

```
                       ┌──────────────────────────────────────────────┐
                       │                TASK BANK (80)                │
                       │  50 "pitfall" tasks + 30 "convention" tasks  │
                       │  each: spec, hidden tests, reference, naive  │
                       └───────────────┬──────────────────────────────┘
                                       │ split into: experience / similar / transfer
                                       ▼
 ┌────────────┐   for every seed (0,1,2…) and every condition (baseline, lucifer, irrelevant)
 │  BACKEND   │   ┌────────────────────────────────────────────────────────────────────────┐
 │ (the model)│   │ PHASE 1  EXPERIENCE: solve exp tasks; B and C WRITE lessons to memory  │
 │ groq/ollama│   │ PHASE 2  FROZEN EVAL: memory is READ-ONLY                              │
 │ /simulated │   │          similar tasks · transfer tasks · replay (exp tasks again)     │
 └─────┬──────┘   └──────────────┬─────────────────────────────────────────────────────────┘
       │                         │ each task solve =
       │   ┌─────────────────────▼───────────────────────────────────────────┐
       └──▶│ retrieve lessons → build prompt → model attempt 1 → run hidden  │
           │ tests in SANDBOX → (if failed) retry with test output → attempt │
           │ 2 → (experience phase only) write lessons                       │
           └─────────────────────┬───────────────────────────────────────────┘
                                 │ every step is recorded as a TRACE SPAN
                                 ▼
        results/<run>/ rows.json · attempts.jsonl · spans.jsonl · memories.json · audits.json · meta.json
                                 │
              ┌──────────────────┼───────────────────────┐
              ▼                  ▼                       ▼
        STATS (bootstrap)   GATES (3 verdicts)    DASHBOARD (visual, local only)
```

---

## 4. Follow one task from start to finish

We follow a real task from the convention set: `ident-1`.

> **Spec shown to the model:** "`order_id(n)` returns the identifier of order number n."
> **Hidden tests:** `order_id(7) == 'ORD-00007'`, `order_id(12345) == 'ORD-12345'`, `order_id(1) == 'ORD-00001'`.

Notice the spec never says "prefix ORD-" or "pad to 5 digits". That is a *house convention* the model cannot guess. It can only learn it from a failing test, and then (maybe) remember it.

🧒 **The story.**
1. The teacher asks: "Write `order_id`."
2. Student A (no notebook) writes `return str(n)`. The referee runs the hidden tests: *fail*. The referee says: "this check failed: `assert order_id(7) == 'ORD-00007'`".
3. Student A reads that, fixes the code, tries again: *pass* on attempt 2.
4. Student B does the same, but afterwards **writes in the notebook**: "For `order_id`, the first try failed; the check that failed was `order_id(7) == 'ORD-00007'`."
5. Later, a *similar* question appears: "`invoice_id(n)`…" with a different prefix but the same style. Student B flips to the right page, sees `ORD-00007`, and now writes a padded, prefixed ID **on the first try**. Student A has to fail first again.

That "first try now works" is exactly what we measure.

🛠️ **The mechanics, in order** (`_solve` in `src/lucifer/experiment.py`):

1. **`retrieve_memory`** — `lucifer` gets the top-*k* most relevant lessons for `task.spec + task.entry`; `irrelevant` gets the *k* least relevant; `baseline` gets none.
2. **`build_prompt`** — if there are lessons, prefix `Notes from earlier tasks (they may or may not apply to this one):` plus bullets, then the task prompt.
3. **`attempt 1`** — `llm.generate` (seeded: `seed*1000 + attempt`) then `sandbox.run_tests` (hidden asserts in a separate process).
4. If it failed and a retry remains: **`attempt 2`** with `retry_prompt` (the previous code and the test feedback appended).
5. **`memory.write`** — only in the **experience** phase and only for `lucifer`/`irrelevant`:
   - first attempt failed → a `failure` lesson (task, spec, failing-test text);
   - failed first, passed after retry → also a `fix` lesson (the passing code, truncated to 500 chars).
6. One row is stored (`pass_at_1`, `pass_at_2`, attempts, tokens, wall time, which lessons were shown, memory version), plus one trace with all spans.

---

## 5. Every part, one by one

### 5.1 Tasks (the exam questions)

File: `src/lucifer/tasks.py` (308 lines)

🧒 A task is one exam question: a description, secret checks, a "right answer" and a "careless answer".

🛠️ Each `Task` has: `id, family, split, entry, spec, tests, reference, naive, set`.

| Field | Meaning |
|---|---|
| `spec` | what the model is asked (shown) |
| `tests` | assert statements (**hidden**, only the failing one is revealed after a failure) |
| `reference` | a solution that passes all tests |
| `naive` | the plausible careless solution that must **fail** |
| `split` | `exp` (experience), `sim` (same pitfall, new problem), `xfer` (pitfalls mixed in a new way) |
| `set` | `pitfall` or `convention` |

A test in `tests/test_tasks.py` checks **for all 80 tasks** that the reference passes and the naive solution fails. This proves every task can actually tell good from careless; a task that can't is a broken ruler.

**Two task sets (80 tasks total):**

| Set | Count | Idea | Splits (exp / sim / xfer) |
|---|---|---|---|
| **pitfall** | 50 | Fully specified problems with a classic trap (empty input, off-by-one, ordering, text edge cases, interval merging, exact money arithmetic, quoted-text parsing, search boundaries) | 24 / 16 / 10 |
| **convention** | 30 | The spec **hides** a house rule (ID format, price format `₹1,234.56`, date `05-Mar-2026`, exact error message). Only test feedback reveals it | 12 / 12 / 6 |

Families (12): `empty, range, order, text, interval, money, parse, boundary` (pitfall) and `ident, price, date, errors` (convention), plus `mixed` for transfer tasks.

**Why the convention set exists (an important design discovery):** strong models solved ~99–100% of the pitfall tasks with no memory at all, leaving no room to improve. Memory can only help where a model *can't* know something up front but *can* learn it from feedback. Hidden conventions are exactly that. A test (`convention specs hide conventions`) guards that the spec text never leaks the convention.

### 5.2 The sandbox (the referee)

File: `src/lucifer/sandbox.py`

🧒 The referee takes the student's code into a separate room, runs the secret checks, and only says *pass* or *"this check failed: …"*.

🛠️ `SandboxExecutor.run(task, code)`:
- writes `cand.py`, `tests.json`, `run.py` into a fresh temp directory;
- runs `python -I run.py` in a **separate process** with an **empty environment** (`env={}`), CPU limit 5 s, file-size limit 1 MB, wall timeout 8 s;
- the runner `exec`s the candidate, then each assert; the first failure produces feedback `this check failed: <assert> (<ErrorType>: <message>)`, capped at 400 chars;
- `extract_code` takes the first fenced ```` ```python ```` block (or the whole reply if none).

`FastExecutor` is used **only with simulated agents** (a candidate passes iff it equals the reference). It is never used for real models.

> ⚠️ **Not a security boundary.** The code can still reach the network and your files. The tasks are tiny; anything bigger or untrusted must run in a container/cloud runner.

### 5.3 Backends (the students)

Files: `src/lucifer/backends/{base,groq,ollama,sim}.py`

🧒 A "backend" is *which student is taking the exam*: a cloud brain (Groq), a brain on your own laptop (Ollama), or a pretend student we program ourselves. (Decision: we use hosted models; your Mac does not run a local model, because that makes it heavy.)

🛠️ All implement `generate(prompt, *, seed, task=None) -> Generation(text, prompt_tokens, completion_tokens, ms)`.

| Backend | What it is | Notes |
|---|---|---|
| `groq` | Groq free-tier, OpenAI-compatible API | key read **only** from env `GROQ_API_KEY`; throttle `--min-interval` (default 2.2 s); retries on HTTP 429/5xx honouring `Retry-After`; **retries on dropped connections** (added after a `RemoteDisconnected` crash); errors redact the key |
| `ollama` | local model server | optional and **unused by decision** (it makes the Mac heavy); tested only against a stand-in server |
| `sim-null` / `sim-learner` / `sim-harmful` | programmed pretend agents | see [5.13](#513-simulated-agents-testing-the-tester) |

Models seen on Groq: `openai/gpt-oss-20b`, `openai/gpt-oss-120b`, `qwen/qwen3.8-27b`, `allam-2-7b`.

### 5.4 Prompts and lessons

File: `src/lucifer/agent.py` (25 lines, deliberately tiny so prompts are easy to read and pin)

- `build_prompt(task, notes)` — task prompt, optionally preceded by the notes block.
- `retry_prompt(base, previous_code, feedback)` — base prompt + `Your previous attempt failed.` + the code + the test feedback + "Reply with the corrected function…".
- `failure_lesson(task, feedback)` → `A first attempt at 'order_id' failed. The spec said: … <failing check>`
- `fix_lesson(task, fixed_code)` → `For 'order_id' (<spec>) this version passed after a failed first attempt: <code>`

🧒 Two kinds of notebook entries: "what went wrong" and "what finally worked".

### 5.5 Memory (the notebook)

File: `src/lucifer/memory.py` (SQLite)

🧒 A notebook where nobody can secretly rip out or edit a page without it being noticed, and where you can "go back to how it looked last Tuesday" without throwing away the newer pages.

🛠️ Properties (these are what **Gate 3** audits):

| Property | How |
|---|---|
| **Append-only** | `add()` only inserts; version = previous + 1 |
| **Provenance** | every lesson stores `task_id, run_id, seed, kind, version` |
| **Hash chain** | `hash = sha256(parent_hash | version | task_id | kind | text)`; editing any old lesson breaks every later hash, and `verify_chain()` returns `False` |
| **Rollback** | `rollback(n)` moves lessons with version > n into an `archived` table (with `archived_by_rollback_to`), it does **not** delete them, so an audit can still see what was undone |
| **Self-audit** | `audit()` checks the chain, then rolls a **copy** back to the middle and verifies the history is reproduced exactly, and that provenance is present |

### 5.6 Retrieval (finding the right page)

File: `src/lucifer/retrieval.py` (48 lines, no model, no download)

🧒 When a new question arrives, flip to the notebook pages that share the most *rare, meaningful words* with it.

🛠️ TF-IDF cosine similarity over unigrams (lowercase, stop-words removed). `relevant()` returns the top-*k* with a minimum score of 0.08; ties go to the newer version. `least_relevant()` ranks everything and takes the bottom *k* (the control).

Experiments recorded: bigrams and stemming were tried; **none beat plain unigram TF-IDF** on precision plus coverage, so it stays unchanged. Semantic embeddings are a deferred idea. The dashboard shows a "retrieval quality" card (precision/coverage per condition).

### 5.7 The experiment loop

File: `src/lucifer/experiment.py`

🧒 For each "round" (a seed), each student gets the same practice questions in the same order, then the real quiz with the notebook **closed for writing** (they can read but not add pages).

🛠️ `run_experiment(Config)`:

```
for seed in seeds:
    shuffle experience tasks with Random("order-<seed>")
    eval_items = similar + transfer + replay(experience tasks again), shuffled ONCE per seed
                 (identical order for every condition → a fair paired comparison)
    for condition in (baseline, lucifer, irrelevant):
        memory = fresh Memory()  (none for baseline)
        PHASE experience:  solve each experience task, writing lessons
        audit memory (chain, rollback, provenance)
        PHASE evaluation:  solve similar, transfer, replay — memory READ-ONLY
```

Phases explained:

| Phase | What it tests |
|---|---|
| **experience** | where learning (writing) happens |
| **similar** | same pitfall, new problem → "did it learn the lesson?" |
| **transfer** | pitfalls mixed in a new way → "can it generalise?" |
| **replay** | the experience tasks again → "forgetting vs plain memorisation" |

`Config` knobs: `seeds`, `conditions`, `k` (lessons shown, default 3), `retries` (default 1), `tasks` (which task set), `out_dir`.

Output files per run (`results/<run-id>/`, git-ignored): `rows.json` (one row per solve), `attempts.jsonl` (one per model call), `spans.jsonl` (traces), `memories.json` (what each notebook held), `audits.json`, `meta.json`.

### 5.8 Statistics (is the difference real?)

File: `src/lucifer/stats.py` (29 lines)

🧒 If Student B scores 6 points higher, was that luck? We redo the comparison thousands of times in our heads, shuffling which questions we "pretend" we got, and see how much the gap wobbles. If it still stays above zero almost every time, we believe it.

🛠️ **Unit of analysis = the task.** For each task, average its pass/fail over seeds; then do a **paired bootstrap** over tasks (10,000 resamples, fixed RNG seed 0) on `condition_B − condition_A`. We report the mean difference and a **95% interval**. Bootstrapping over *tasks* (not over seeds or attempts) avoids pretending that repeated runs of the same task are independent evidence.

**Power (how many tasks we need).** Measured on simulated learners with a true +20 point effect (60 simulated experiments per row):

| similar + transfer tasks | gate 1 passes when effect is real | false alarm when there is no effect |
|---|---|---|
| 12 | 32% | 0% |
| 26 (current pitfall set) | 53% | ~2% |
| 48 | 98% | ~5% |
| 52 | 98% | 0% |

Takeaway: with about 26 primary tasks, a "no effect" verdict is weak evidence; about 48+ are needed to detect a +20 point effect reliably. (An earlier 20-run table was too optimistic; it was a lucky draw and was corrected with 60 runs.)

### 5.9 The three gates (the final verdict)

File: `src/lucifer/gates.py`

🧒 Three "traffic lights". All three must be green before we say the idea is worth building on.

🛠️ 

| Gate | Pass condition | Why |
|---|---|---|
| **1 · Improvement** | 95% interval of `lucifer − baseline` **and** `lucifer − irrelevant` are both entirely above zero | must beat "no memory" **and** "wrong memory". Verdict text: `improves` / `hurts` / `no effect detected` |
| **2 · Retention** | On tasks the baseline already masters (≥ 80% on half the seeds), lucifer loses at most 5 points on the *other* half | memory must not make the model worse at what it already did well. **Inconclusive** (not a pass) if no task is mastered or only one seed |
| **3 · Auditability** | hash chain verifies, rollback reproduces history exactly, every lesson has provenance, for every memory-using run | the "memory you can trust and undo" promise must be real |

**A bug the dashboard exposed in Gate 2** (fixed): choosing "mastered" tasks and measuring the drop on the *same* runs picked tasks the baseline got lucky on, so *regression to the mean* looked like a 30-point "forgetting". Fix: select on half the seeds, measure on the other half, with a regression test.

### 5.10 Tracing (a flight recorder)

File: `src/lucifer/tracing.py`

🧒 Like the black box in an aeroplane: for every question, it records each step, how long it took, and what was said.

🛠️ OpenTelemetry-style: **one trace per solve**, nested **spans**: `solve <task>` (root) → `retrieve_memory`, `build_prompt`, `attempt n` → (`llm.generate`, `sandbox.run_tests`), `memory.write`. Each span has `trace_id, span_id, parent_id, name, kind, start_ms, duration_ms, status, attrs`. Times use a **trace-local virtual clock** starting at 0 so a trace draws as a waterfall; real backends report real latency, simulated ones report a made-up latency and flag `simulated: true`. Span kinds: `root, retrieval, prompt, attempt, llm, execution, memory`. Spans carry the prompt, reply, code, feedback and the lessons involved (truncated for size).

### 5.11 The dashboard

Files: `src/lucifer/server.py`, `insights.py`, `web/*` (HTML + vanilla JS ES modules + inline SVG charts, **no build step, no internet**)

🧒 A TV-style control room: big numbers, coloured charts, and a magnifying glass. Hover any underlined word to get its meaning; click any number to see how it was calculated.

🛠️ 
- **Server:** stdlib `ThreadingHTTPServer` bound to `127.0.0.1` only. API: `/api/runs`, `/summary`, `/traces`, `/traces/<id>`, `/memory`. Run ids are validated (`^[\w.\-]+$`) and paths are traversal-safe. Runs reload automatically if files change.
- **Tabs:**

| Tab | What you see |
|---|---|
| **Overview** | generated plain-language *key findings*; the 3 gates with intervals; KPIs with change vs baseline; pass@1 by phase and family; learning curve; outcomes; **retrieval quality**; time per step; operations table (count, mean, p50, p95, errors); hardest tasks |
| **Traces** | list of every solve; open one → waterfall; click a step to read prompt, reply, code, test feedback, lessons |
| **Memory** | the lessons written, with kind, task, seed, hash |
| **Guide** | how a run works, what each measure/gate means, colour key, limitations, searchable glossary |

- **Explanations everywhere:** `glossary.js` (~50 terms), `info.js` implements hover tooltips (`data-term`) and a click-through side drawer (`data-info`) showing *what it is · how it is calculated · how to read it · caution · the exact numbers behind it*.
- **Colour language (one meaning each):** baseline = slate, lucifer = blue, control = violet; good/warn/bad = green/amber/red; span kinds have their own colours; a dark theme is included.
- **Honesty detail:** simulated runs carry a badge, because their timings are made up.

> Your own running dashboard (port 8765) was started with **older code**. Restart it to see the latest version: `lucifer dashboard`.

### 5.12 Calibration (is the exam the right difficulty?)

Files: `src/lucifer/calibrate.py`, `docs/CALIBRATION.md`, `docs/calibration/`

🧒 If the exam is so easy that everyone gets 100%, or so hard that everyone gets 0%, you can't see who has a better notebook. We first give the exam to the plain student to find questions that are "just right".

🛠️ Run the **baseline only**; keep tasks whose first-attempt pass rate is **20–80%** ("usable"); below 20% is "too hard", above 80% "too easy". Results so far:

| Task set | Model | Mean pass@1 | Reading |
|---|---|---|---|
| pitfall (first 24) | `qwen/qwen3.8-27b` | 100% | all too easy |
| pitfall (first 24) | `openai/gpt-oss-20b` (effort low) | 96% | all but one too easy |
| pitfall (first 24) | `allam-2-7b` | 42% | bimodal: 13 tasks at 0%, 9 at 100% |
| pitfall (50) | `gpt-oss-20b` | 99% | too easy |
| pitfall (50) | `qwen3.8-27b` | 100% | too easy |
| pitfall (50) | `allam-2-7b` | 26% | near 0% / 100%, little in between |
| **convention (30)** | `gpt-oss-20b`, temp 0.7, 3 seeds | **1%** (29 of 30 tasks < 20%) | baseline almost never right first time |

**Convention set, first try vs after one retry** (gpt-oss-20b baseline):

| Family | pass@1 | pass@2 (after feedback) |
|---|---|---|
| ident | 7% | 96% |
| price | 0% | 67% |
| date | 0% | 100% |
| errors | 0% | 70% |
| mixed | 0% | 67% |

🧒 *What this means:* the student can't guess the house rules, but fixes them quickly once told. So the question becomes: **can the notebook make them right on the very first try?**

🛠️ Caveat: a baseline at ~0% pass@1 is outside the 20–80% "usable" band by the original rule. We proceed anyway because the primary metric is still sensitive here: a large Lucifer gain on pass@1 is detectable against a ~0% floor, and the retry data shows the tasks are solvable. This is a **deliberate deviation** from the plan and is stated here so it is not hidden.

### 5.13 Simulated agents (testing the tester)

File: `src/lucifer/backends/sim.py`; tests in `tests/test_controls.py`

🧒 Before trusting a scale, put a known 1 kg weight on it. We build pretend students whose behaviour we *know*, and check the scoreboard gives the right answer about them.

🛠️ 
| Simulated agent | Behaviour | The harness must say |
|---|---|---|
| `sim-null` | memory makes no difference | gate 1 fails (no effect) in almost all runs |
| `sim-learner` | a relevant lesson raises first-try success | gate 1 passes |
| `sim-harmful` | any notes lower success | reported as **hurts** |

A "correct" reply is the task's `reference`; a "wrong" reply is its `naive` code, so retries, sandbox, memory and statistics run exactly as with a real model. Also tested: forgetting is caught, and regression to the mean does not trigger a false "forgetting". **Simulated results never say anything about real models.**

### 5.14 The command line

File: `src/lucifer/cli.py`

| Command | Purpose |
|---|---|
| `lucifer run` | run the 3-condition experiment |
| `lucifer calibrate` | baseline-only difficulty check |
| `lucifer dashboard` | start the local dashboard |
| `lucifer report <run-dir>` | text report of a finished run |

Flags for `run`: `--backend {sim-null,sim-learner,sim-harmful,ollama,groq}` · `--model` · `--seeds N` · `--k` · `--taskset {pitfall,convention,all}` · `--temperature` · `--reasoning-effort {low,medium,high}` · `--min-interval` (seconds between Groq calls) · `--run-id` · `--out`.

### 5.15 The tests

121 tests, all passing at the time of writing (about 2 minutes).

| File | What it protects |
|---|---|
| `test_tasks.py` | every task: reference passes, naive fails; set shapes; conventions are hidden |
| `test_memory.py` | hash chain, tampering detection, rollback, archive |
| `test_pipeline.py` | end-to-end run with simulated agents, files written |
| `test_controls.py` | null/learner/harmful behave as known; power documentation; regression to the mean |
| `test_groq.py` | key handling, retry on 429/5xx, retry on dropped connections, key redaction |
| `test_dashboard.py` | API, path-traversal safety, glossary keys exist, JS syntax |

---

## 6. What we have learned so far

1. **Strong models saturate fully-specified tasks.** 96–100% first-try pass rates leave nothing for memory to improve. Difficulty by "more of the same" does not help.
2. **Memory can only matter where knowledge is hidden but learnable.** Hence the convention set. This was the key design insight of the project so far.
3. **Feedback alone already fixes most conventions** (pass@2 of 67–100%). So any Lucifer gain must show up as *first-try* success, which is the primary metric.
4. **Choosing and measuring on the same data creates fake results.** The retention gate bug is the proof; the fix is split-seed selection.
5. **Small task sets give weak verdicts.** About 26 primary tasks detect a +20 point effect about half the time; ~48+ are needed. The convention set has 18 similar+transfer tasks, so the first real run is a *first look*, not a final verdict.
6. **Retrieval:** plain unigram TF-IDF was as good as anything we tried (bigrams, stemming). Keep it simple until semantic embeddings are tried.

---

## 7. Where the real experiment stands right now

| Item | Value |
|---|---|
| Command | `lucifer run --backend groq --model openai/gpt-oss-20b --reasoning-effort low --taskset convention --seeds 3 --temperature 0.7 --run-id real-conv-gpt-oss-20b` |
| Size | 30 tasks × 3 conditions × 3 seeds; roughly 580 model calls expected (sized with a simulated run) |
| Throttle | at least 2.2 s between calls; wall time ≈ 25–40 min (Groq free tier rate limits can add waiting) |
| Progress at time of writing | running; seed 0 baseline finished; **no results yet** |
| Output when done | `results/real-conv-gpt-oss-20b/` (open with the dashboard) |

**Results section (to be filled in when the run finishes; nothing is invented here):**

- lucifer − baseline (pass@1, similar+transfer): *pending*
- lucifer − irrelevant: *pending*
- Gate 1 / 2 / 3: *pending*

How to read it when it lands: Gate 1 passing with an interval above zero would be the first real evidence for H1 on this model and this task family. With only 3 seeds and 18 primary tasks, even a pass should be followed by a bigger run before any claim is made; a fail would mean "no effect detected at this size", **not** "no effect exists".

---

## 8. Safety, secrets and honesty rules

- **Secrets:** the Groq key is read only from the environment (`GROQ_API_KEY`), never from a file in the repo, never printed, and redacted in error messages. A temporary env file (mode 600) lives outside the repo and is deleted when the work is done. The GitHub token is passed for a single push via an HTTP header, not stored in git config or remotes. Tokens you pasted into chat should be **revoked** after use, and a fine-grained, repo-scoped token is safer next time.
- **Scope:** personal tokens and personal repo only; nothing here touches company Vercel/Supabase CLIs or MCPs.
- **Code execution:** model-written code runs in a separate, resource-limited process. This is hygiene, **not a security boundary**.
- **Honesty:** simulated numbers are labelled simulated; deviations from the plan (e.g. a ~0% baseline band) are written down; failed or inconclusive results are reported as such. No attribution lines in commits.
- **Git hygiene:** explicit file staging only (no `git add -A`); `results/` is git-ignored.

---

## 9. What is NOT done, and what could fool us

**Not done**
- No finished real Lucifer-vs-baseline result yet (run in progress).
- Task counts are below the plan's target: the plan wants ~48+ calibrated similar+transfer tasks (ideally 100+ overall); the convention set has 18.
- No mid-strength model yet. By decision we do **not** run local models (Ollama would make the Mac heavy); the next candidates are other hosted models (for example a larger or smaller Groq model) or a cloud runner.
- Semantic (embedding) retrieval not built.
- Container sandbox not built.
- Doc drift to fix: `README.md` still says "89 tests" and the plan still calls the control "shuffled"; the real numbers are 121 tests and `irrelevant`.

**Threats to validity** (things that could make a result misleading)
- **Memorisation:** the base model may have seen similar tasks. Mitigation: the replay phase and fresh task families.
- **Answer leakage via near-duplicates:** similar tasks must differ in function, not just names.
- **Prompt-length effect:** handled by the `irrelevant` control.
- **Noise:** few seeds and task-level sampling at temperature 0.7 → wide intervals.
- **Hosted-model drift:** a free API can change under the same model name. A pinned local model is more reproducible.
- **Lesson content is easy here:** in the convention tasks the lesson literally contains the failing test, so the result measures "can the model use a pasted correct example", a modest but real form of learning. It does not yet show broad skill transfer.

---

## 10. What happens next

1. **Read the real run** in the dashboard; report Lucifer vs baseline vs control with intervals and gate verdicts.
2. **If promising:** grow the convention set to ≥ 48 primary tasks (new conventions, not renamed copies), run 5+ seeds, re-check the gates; try a second model.
3. **If not:** report "no measurable effect at this size", inspect traces for *why* (retrieval misses? lessons ignored by the model?), and change one thing at a time.
4. **Strengthen the evidence:** a mid-strength hosted model (no local models, by decision); semantic retrieval; a container sandbox; a held-out task family never seen during design.
5. **Housekeeping:** fix the doc drift above, update the hand-off memory, rotate/revoke the pasted tokens.

---

## 11. How to run everything

```bash
# one-time setup
cd ~/Personal/lucifer-lab
uv venv --python 3.13 && uv pip install -e ".[dev]"

# tests (about 2 minutes)
.venv/bin/pytest

# harness check with a pretend learner (no internet, no key)
.venv/bin/lucifer run --backend sim-learner --seeds 3 --run-id demo
.venv/bin/lucifer report results/demo

# see it visually (http://127.0.0.1:8765)
.venv/bin/lucifer dashboard

# difficulty check on a real model (key in your shell, never in a file)
export GROQ_API_KEY=...   # your key
.venv/bin/lucifer calibrate --backend groq --model openai/gpt-oss-20b --reasoning-effort low

# the real experiment
.venv/bin/lucifer run --backend groq --model openai/gpt-oss-20b --reasoning-effort low \
    --taskset convention --seeds 3 --temperature 0.7 --run-id real-conv-gpt-oss-20b

# optional, not used here: a local model through Ollama (heavy on the Mac)
# ollama pull qwen3:8b && .venv/bin/lucifer run --backend ollama --model qwen3:8b --seeds 5
```

---

## 12. File map

| Path | Purpose |
|---|---|
| `src/lucifer/tasks.py` | 80 tasks, families, splits, task sets |
| `src/lucifer/sandbox.py` | hidden-test runner (separate process, limits) |
| `src/lucifer/agent.py` | prompt and lesson templates |
| `src/lucifer/memory.py` | hash-chained, versioned SQLite memory |
| `src/lucifer/retrieval.py` | TF-IDF relevant / least-relevant |
| `src/lucifer/experiment.py` | conditions × seeds × phases loop |
| `src/lucifer/stats.py` | task means, paired bootstrap |
| `src/lucifer/gates.py` | the 3 promotion gates |
| `src/lucifer/tracing.py` | OpenTelemetry-style spans |
| `src/lucifer/insights.py` | summaries for the dashboard |
| `src/lucifer/server.py` | local JSON API + static web |
| `src/lucifer/web/*` | dashboard front end (HTML, CSS, JS, glossary) |
| `src/lucifer/calibrate.py` | baseline difficulty calibration |
| `src/lucifer/report.py` | text report |
| `src/lucifer/cli.py` | `lucifer` command |
| `src/lucifer/backends/*` | groq, ollama, simulated agents |
| `tests/*` | 121 tests |
| `docs/EXPERIMENT-PLAN.md` | the plan, gates, power table |
| `docs/CALIBRATION.md`, `docs/calibration/` | calibration write-up and raw numbers |
| `results/` | run outputs (git-ignored) |

---

## 13. Glossary

| Term | 🧒 Kid meaning | 🛠️ Technical meaning |
|---|---|---|
| **Agent / model** | the student | the LLM behind a backend |
| **Memory** | the notebook | persistent, hash-chained store of lessons |
| **Lesson** | one notebook entry | a `failure` or `fix` record with provenance |
| **Baseline** | student with no notebook | condition with memory disabled |
| **Lucifer** | student with the right pages | condition retrieving the most relevant lessons |
| **Irrelevant / control** | student with wrong pages | condition retrieving the least relevant lessons |
| **Seed** | a different shuffle/roll of the dice | integer fixing task order and generation seeds |
| **Phase** | a stage of the day | experience / similar / transfer / replay |
| **pass@1** | right on the first try | first attempt passes all hidden tests |
| **pass@2** | right after one retry | passes on attempt 1 or after one feedback retry |
| **Hidden tests** | the secret checks | asserts executed in the sandbox; only the failing one is revealed |
| **Reference / naive** | the right and the careless answers | known-good solution / plausible wrong solution used to validate tasks |
| **Calibration** | picking the right exam difficulty | baseline-only run; keep tasks at 20–80% pass@1 |
| **Bootstrap** | re-shuffling the scores to see how much luck matters | resampling tasks with replacement to get a 95% interval |
| **95% interval** | the likely range of the true gain | percentile interval of the bootstrap distribution |
| **Power** | how likely the exam is to spot a real improvement | probability gate 1 passes when a true effect exists |
| **Gate** | a traffic light | pass/fail criterion for promoting the idea (improvement, retention, auditability) |
| **Regression to the mean** | lucky winners usually do worse next time | selecting on noisy results then re-measuring shows a fake drop |
| **Hash chain** | pages glued together so tampering shows | each record's hash covers the previous hash |
| **Rollback** | undo, but keep the undone pages in a drawer | move later versions to `archived`, not delete |
| **TF-IDF** | weigh rare words more | term-frequency × inverse-document-frequency vectors, cosine similarity |
| **Trace / span** | the flight recorder / one step on it | one solve / one timed step with attributes |
| **Sandbox** | the referee's separate room | child process with CPU/file/time limits (not a security boundary) |
| **Backend** | which student takes the exam | adapter implementing `generate()` |
| **Convention task** | a house rule nobody tells you | hidden formatting/error rule revealed only by test feedback |
| **Pitfall task** | a question with a classic trap | fully specified problem with an edge-case trap |
