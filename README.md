# lucifer-lab

A small laboratory that tests **one claim**:

> An ordinary open-weight language model, given persistent memory of its own earlier attempts and a feedback signal, solves later, related tasks at a higher rate than the same model without them.

This is Lucifer V1: not a new model and not AGI, only the experiment that decides whether the central idea is worth building on. The plan, controls, gates and statistics are in [`docs/EXPERIMENT-PLAN.md`](docs/EXPERIMENT-PLAN.md).

## Status (honest)
- **Done and tested (89 tests):** 50 coding tasks (8 pitfall families plus a transfer set) with hidden tests, a sandboxed runner, hash-chained versioned memory with rollback, relevance retrieval, three conditions (baseline, lucifer, irrelevant-notes control), a task-level bootstrap, the three promotion gates, a report, and an Ollama backend (tested against a stand-in server).
- **Proven by simulation:** the harness gives the right answer about agents whose behaviour is known: one that cannot learn is reported as improving 0 times in 20 to 40 runs; one that learns is detected; one hurt by memory is reported as hurt; forgetting is caught.
- **Calibrated on real models (baseline only):** see [`docs/CALIBRATION.md`](docs/CALIBRATION.md). Those runs used the first 24 tasks, which were too easy for strong models (96–100% pass@1). The set has since been extended with four harder families (interval merging, exact money arithmetic, quoted-text parsing, search boundaries); their difficulty is **not yet calibrated** on any model.
- **Not done:** the Lucifer-vs-baseline experiment on a real model. The current set has 26 similar+transfer tasks, which detects a real effect only about half the time (the power table in the plan: 12 tasks 32%, 26 tasks 53%, 52 tasks 98%); the real run needs at least 48 similar+transfer tasks, calibrated so the baseline passes 20–80% of them.

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
.venv/bin/pytest                                        # 89 tests, about a minute
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
