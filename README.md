# lucifer-lab

A small laboratory that tests **one claim**:

> An ordinary open-weight language model, given persistent memory of its own earlier attempts and a feedback signal, solves later, related tasks at a higher rate than the same model without them.

This is Lucifer V1: not a new model and not AGI, only the experiment that decides whether the central idea is worth building on. The plan, controls, gates and statistics are in [`docs/EXPERIMENT-PLAN.md`](docs/EXPERIMENT-PLAN.md).

## Status (honest)
- **Done and tested (125 tests):** 80 coding tasks (50 pitfall tasks in 8 families plus a transfer set, and 30 hidden-convention tasks) with hidden tests, a sandboxed runner, hash-chained versioned memory with rollback, relevance retrieval, three conditions (baseline, lucifer, irrelevant-notes control), a task-level bootstrap, the three promotion gates, a report, and an Ollama backend (tested against a stand-in server).
- **Proven by simulation:** the harness gives the right answer about agents whose behaviour is known: one that cannot learn is reported as improving 0 times in 20 to 40 runs; one that learns is detected; one hurt by memory is reported as hurt; forgetting is caught.
- **Calibrated on real models (baseline only):** see [`docs/CALIBRATION.md`](docs/CALIBRATION.md). Those runs used the first 24 tasks, which were too easy for strong models (96–100% pass@1). The set has since been extended with four harder families (interval merging, exact money arithmetic, quoted-text parsing, search boundaries); their difficulty is **not yet calibrated** on any model.
- **First real result (12 Nov 2026):** `qwen2.5-coder:14b`, 30 convention tasks (18 scored: 12 similar + 6 transfer), 5 seeds, three conditions, run on GitHub Actions. First-try success on similar + transfer tasks: lucifer 50% (similar 67%, transfer 17%), no memory 0%, wrong notes 0%; lucifer − baseline +0.50 (95% interval +0.30 to +0.70). After one retry the baseline reaches 52% (lucifer 82%). Gate 1 passes, gate 2 (retention) is inconclusive because the baseline masters no task, gate 3 passes, so the overall verdict is "not all gates passed". The run is 630 task runs (1,115 model generations counting retries). Files: [`results/published/qwen14b-convention/`](results/published/qwen14b-convention/); write-up: section 7 of [`docs/IMPLEMENTATION-GUIDE.md`](docs/IMPLEMENTATION-GUIDE.md). This is a first look, not proof: one model, 18 scored tasks, tasks written by the author.
- **Not done:** a second model, a held-out task family, and a set large enough to detect smaller effects reliably. The plan's power table (12 tasks 32%, 26 tasks 53%, 52 tasks 98%) says at least about 48 similar + transfer tasks are needed; this run had 18.

## Dashboard: see every step of the processing
```bash
.venv/bin/lucifer run --backend sim-learner --seeds 5 --run-id demo   # records traces for every task solve
.venv/bin/lucifer dashboard                                            # opens http://127.0.0.1:8765
```
It is a local web app (no internet, no build step, bound to 127.0.0.1 only):
- **Overview:** plain-language findings generated from the run, the three promotion gates with their intervals, key measures with change versus the baseline, first-attempt success by phase and task family, a learning curve, outcomes, retrieval quality, time per processing step, an operations table (count, mean, p50, p95, errors per step), results by phase and the hardest tasks.
- **Traces:** one trace per task solve. Open one to see a waterfall of its steps (retrieve memory, build prompt, each model call, each test run, the memory write); click a step to read the prompt, the model's reply, the code, the test feedback and the lessons involved.
- **Memory:** the lessons the agent wrote, chained by hash, with their kind, task and seed.
- **Guide:** how a run works, what each measure and gate means, how to read a trace, the colour key, limitations, and a searchable glossary.

**Explanations everywhere.** Hover any underlined term for a definition. Click any term, value, chart element, table row or ⓘ button to open a side panel with what it is, how it is calculated, how to read it and what to keep in mind, plus the exact numbers behind that value. Colours carry one meaning each (see the Guide).

Times in a **simulated** run are made up (the badge says so); with a real model they are real. Traces are saved next to the results as `spans.jsonl`.

## Try it
```bash
uv venv --python 3.13 && uv pip install -e ".[dev]"
.venv/bin/pytest                                        # 125 tests, about four minutes
.venv/bin/lucifer run --backend sim-learner --seeds 3   # simulated agent that learns (checks the machinery only)
.venv/bin/lucifer run --backend sim-null --seeds 3      # simulated agent that cannot learn: gate 1 should fail
.venv/bin/lucifer report results/sim-learner-sim
```
With Groq's free tier (put the key in your shell, never in a file): `export GROQ_API_KEY=...` then `.venv/bin/lucifer calibrate --backend groq --model openai/gpt-oss-20b --reasoning-effort low`.

With a local model (needs [Ollama](https://ollama.com) and a pulled model):
```bash
ollama pull qwen3:8b
.venv/bin/lucifer run --backend ollama --model qwen3:8b --seeds 5
```

## Safety note
Model-written code is run in a separate process with CPU and file limits, but that is **not** a security boundary. The tasks are tiny; anything larger belongs in a container or on a cloud runner.

## Version 1.1

[`v1.1/`](v1.1/) holds the Version 1.1 research log: eight pre-registered milestones on small simulated learners (no language model), with 21 registered hypotheses of which 10 passed and 11 failed, all kept. Version 1 (everything else here) is unchanged. See [`v1.1/README.md`](v1.1/README.md) and the append-only [milestones page](https://lucifer-update.vercel.app/milestones).
