# LinkedIn post draft (not posted)

Two versions. Fill the `[ ]` slots only from the real run. Do not post a claim the numbers don't support.

---

## Version A: milestone post (usable today, no result claimed)

**I'm testing one question: does an AI that remembers its mistakes actually get better, or does it just look like it?**

Most "AI with memory" demos show a lucky example. I wanted a fair test, so I built a small lab for it (Lucifer Lab):

→ The same model sits the same coding exam three ways: no memory, relevant memory, and deliberately wrong memory
→ Hidden tests mark every answer
→ Memory is hash-chained, versioned and can be rolled back
→ Every step is traced, like OpenTelemetry, with a dashboard where you can click into any attempt
→ Results come with confidence intervals, not a single lucky number

Three things I learned already:
1. Strong models score 96–100% on well-specified tasks with no memory, so those tasks can't show anything. The first exam was useless.
2. Memory only has room to help where the model *can't know* something up front but *can learn* it from feedback (house formats, exact error messages). So I built that exam.
3. My own scoring had a bug: it mistook luck for forgetting (regression to the mean). The dashboard exposed it, and I fixed it.

The first real run on an open-weight model is in progress. A "no effect" result is a result too, and I'll publish it either way.

Code and method are open: github.com/Lakshit-Startup-Ideas/Lucifer-BenchMarks

#AI #LLM #Benchmarks #BuildInPublic #OpenSource

---

## Version B: results post (fill after the run; delete lines that don't apply)

**Result: an open-weight model with memory vs without, on tasks with hidden conventions.**

Model: `openai/gpt-oss-20b` · 30 tasks · 3 seeds · same retries for everyone

| | first-try success (similar + transfer) |
|---|---|
| No memory | [ ]% |
| Relevant memory (Lucifer) | [ ]% |
| Wrong memory (control) | [ ]% |

Lucifer − no memory: [ ] points (95% interval [ ] to [ ])
Lucifer − wrong memory: [ ] points (95% interval [ ] to [ ])
Gates: improvement [pass/fail] · retention [pass/fail/inconclusive] · auditability [pass/fail]

What it means: [one honest sentence].
What it doesn't: only [ ] tasks, [ ] seeds, one model. This is a first look, not proof. Next: more tasks, a second model, a local model.

Full method and raw numbers: github.com/Lakshit-Startup-Ideas/Lucifer-BenchMarks

#AI #LLM #Benchmarks #BuildInPublic
