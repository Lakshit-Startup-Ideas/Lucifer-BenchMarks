# Baseline calibration (11 Nov 2026)

Question: does the 24-task set leave room to show learning? The plan keeps tasks where the **baseline** (no memory) passes 20–80% of first attempts. Three models on Groq's free tier, 3 seeds, temperature 0.3, no memory. Raw per-task rates are in `docs/calibration/`.

| Model (Groq) | Mean pass@1 | Usable (20–80%) | Too easy | Too hard |
|---|---|---|---|---|
| `qwen/qwen3.8-27b` | 100% | 0 | 24 | 0 |
| `openai/gpt-oss-20b` (reasoning effort low) | 96% | 0 | 23 | 1 |
| `allam-2-7b` | 42% | 2 | 9 | 13 |

## What this means
- **The tasks are too easy for any strong model.** Two of the three models solve almost everything on the first try, so memory has nothing to improve. A real run on them would show "no effect" for a reason that says nothing about the idea.
- **The weak model is all-or-nothing.** `allam-2-7b` either always passes a task or never does (13 tasks at 0%, 9 at 100%), so there is little in between to move. It is also an Arabic-focused model, not a code model.
- **One task was flawed, and calibration caught it.** `range-3` (`days_between`) did not say the inputs are integers, so models wrote date code. The spec is fixed. The `allam-2-7b` and `gpt-oss-20b` numbers above were taken *before* that fix; only `qwen3.8-27b` ran after it.

## What to do next
1. **Make the tasks harder**, not just more numerous: several requirements at once, details given early in a long spec, and pitfalls that a strong model also falls for. Re-calibrate until the chosen model sits in the 20–80% band on at least half the tasks.
2. **Pick a model that is in the middle.** A small local code model (3–8B through Ollama) is a better subject than a 20B+ model. The hosted free tier has no small code model right now.
3. **Use enough sampling variety** (temperature around 0.7, 5+ seeds) so a task can land between 0% and 100%.
4. Only then grow to 100+ tasks and do the real run.

## Limits
Three seeds per task is thin; hosted models can change under the same name; the free tier returns whatever it serves that day.
