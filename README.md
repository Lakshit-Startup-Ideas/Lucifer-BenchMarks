# lucifer-lab

A small laboratory that tests **one claim**:

> An ordinary open-weight language model, given persistent memory of its own earlier attempts and a feedback signal, solves later, related tasks at a higher rate than the same model without them.

This is Lucifer V1: not a new model and not AGI, only the experiment that decides whether the central idea is worth building on. The plan, controls, gates and statistics are in [`docs/EXPERIMENT-PLAN.md`](docs/EXPERIMENT-PLAN.md).

## Status (honest)
- **Done and tested (50 tests):** 24 coding tasks with hidden tests, a sandboxed runner, hash-chained versioned memory with rollback, relevance retrieval, three conditions (baseline, lucifer, irrelevant-notes control), a task-level bootstrap, the three promotion gates, a report, and an Ollama backend (tested against a stand-in server).
- **Proven by simulation:** the harness gives the right answer about agents whose behaviour is known: one that cannot learn is reported as improving 0 times in 20 to 40 runs; one that learns is detected; one hurt by memory is reported as hurt; forgetting is caught.
- **Calibrated on real models (baseline only):** see [`docs/CALIBRATION.md`](docs/CALIBRATION.md). The 24 tasks are too easy for strong models (96–100% pass@1), so the experiment itself has not been run.
- **Not done:** the Lucifer-vs-baseline experiment on a real model. The 24-task set is too small to trust a "no effect" result (the power table in the plan shows why); the real run needs 100+ tasks, calibrated so the baseline passes 20–80% of them.

## Try it
```bash
uv venv --python 3.13 && uv pip install -e ".[dev]"
.venv/bin/pytest                                        # 50 tests, about a minute
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
