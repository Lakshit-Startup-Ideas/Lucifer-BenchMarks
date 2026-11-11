# lucifer-lab

A small laboratory that tests **one claim**:

> An ordinary open-weight language model, given persistent memory of its own earlier attempts and a feedback signal, solves later, related tasks at a higher rate than the same model without them.

This is Lucifer V1: not a new model and not AGI, only the experiment that decides whether the central idea is worth building on. The plan, controls, gates and statistics are in [`docs/EXPERIMENT-PLAN.md`](docs/EXPERIMENT-PLAN.md).

## Status (honest)
- **Done and tested (60 tests):** 24 coding tasks with hidden tests, a sandboxed runner, hash-chained versioned memory with rollback, relevance retrieval, three conditions (baseline, lucifer, irrelevant-notes control), a task-level bootstrap, the three promotion gates, a report, and an Ollama backend (tested against a stand-in server).
- **Proven by simulation:** the harness gives the right answer about agents whose behaviour is known: one that cannot learn is reported as improving 0 times in 20 to 40 runs; one that learns is detected; one hurt by memory is reported as hurt; forgetting is caught.
- **Calibrated on real models (baseline only):** see [`docs/CALIBRATION.md`](docs/CALIBRATION.md). The 24 tasks are too easy for strong models (96–100% pass@1), so the experiment itself has not been run.
- **Not done:** the Lucifer-vs-baseline experiment on a real model. The 24-task set is too small to trust a "no effect" result (the power table in the plan shows why: 12 primary tasks detect a real effect 32% of the time, 48 tasks 98%); the real run needs at least 48 similar+transfer tasks, calibrated so the baseline passes 20–80% of them.

## Dashboard: see every step of the processing
```bash
.venv/bin/lucifer run --backend sim-learner --seeds 5 --run-id demo   # records traces for every task solve
.venv/bin/lucifer dashboard                                            # opens http://127.0.0.1:8765
```
It is a local web app (no internet, no build step, bound to 127.0.0.1 only):
- **Overview:** first-try success per condition and phase, a family radar, the three gates with their intervals, a learning curve, outcomes, where the time goes, an operations table (count, mean, p50, p95, errors per step) and the hardest tasks.
- **Traces:** one trace per task solve, like a tracing tool. Open one to see a waterfall of its steps (retrieve memory, build prompt, each model call, each test run, the memory write), click a step to read the prompt, the model's reply, the code, the test feedback and the lessons it was shown.
- **Memory:** the lessons the agent wrote, chained by hash, with the kind (failure or fix), the task and seed they came from.

Times in a **simulated** run are made up (the badge says so); with a real model they are real. Traces are saved next to the results as `spans.jsonl`.

## Try it
```bash
uv venv --python 3.13 && uv pip install -e ".[dev]"
.venv/bin/pytest                                        # 60 tests, about a minute
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
