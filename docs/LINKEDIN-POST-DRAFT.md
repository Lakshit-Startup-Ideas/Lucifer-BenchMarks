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

## Version B: results post (numbers filled from the real run, 12 Nov 2026; not posted)

**First real result: an open-weight model with memory vs without, on tasks with hidden conventions.**

Model: `qwen2.5-coder:14b` · 30 tasks (18 scored) · 5 seeds · same retries for everyone · run entirely on GitHub Actions

| | first-try success (similar + transfer) |
|---|---|
| No memory | 0% |
| Relevant memory (Lucifer) | 50% (similar 67%, transfer 17%) |
| Wrong memory (control) | 0% |

Lucifer − no memory: +50 points (95% interval +30 to +70)
Lucifer − wrong memory: +50 points (95% interval +30 to +70)
Gates: improvement pass · retention inconclusive · auditability pass

What it means: memory built from earlier test feedback lets the model get a hidden house convention right on the first try, on similar tasks.
What it doesn't: the 0% baseline is by design (the conventions are hidden), so the gain is mostly "skips the failed first try". After one retry, no memory already reaches 52%. Transfer to less similar tasks is weak (17%). Only 18 scored tasks, one model, tasks I wrote. A first look, not proof. Next: more tasks, a second model, a held-out task family.

Full method, raw numbers and every workflow: github.com/Lakshit-Startup-Ideas/Lucifer-BenchMarks

#AI #LLM #Benchmarks #BuildInPublic
