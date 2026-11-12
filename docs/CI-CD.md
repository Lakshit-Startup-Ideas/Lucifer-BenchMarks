# CI/CD: everything runs on GitHub's runners

Nothing heavy runs on a laptop. Three workflows in `.github/workflows/`:

| Workflow | When | What it does |
|---|---|---|
| `ci.yml` | every push to `main` and every pull request | runs the test suite on Python 3.11 and 3.13 |
| `calibrate.yml` | manual (Actions tab → Run workflow) | baseline only on an Ollama model: which tasks are too easy or too hard |
| `experiment.yml` | manual | the real three-condition run: one parallel job per seed, then join, gates, report |

## How an experiment run works
1. **plan** turns "3 seeds" into jobs for seeds 0, 1, 2.
2. Each **run** job installs a pinned Ollama (`OLLAMA_VERSION`), pulls the model (cached between runs), runs its one seed on the runner's CPU, and uploads its folder as an artifact. A failed seed does not cancel the others.
3. **aggregate** downloads the seed folders, joins them with `lucifer merge` (refuses overlapping seeds or runs that differ in model/settings), runs `lucifer report` (results table and the three gates), writes it into the job summary and uploads the merged run (kept 90 days).
4. Optional `publish: true` commits `rows.json`, `audits.json`, `meta.json` and `report.txt` to `results/published/<name>/`, authored as `lllakshit`.

To look at a finished run in the dashboard: download the `merged-run` artifact, unzip it into `results/`, run `lucifer dashboard`.

## Limits to know
- Runners are CPU only (public repo: 4 vCPU, 16 GB). A 3B model gives roughly 5–10 tokens/s, so one seed takes a few hours. One job may run at most 6 hours (the workflows stop at 345 minutes).
- Model and Ollama versions are pinned and written into the results, so a run can be repeated.
- No secrets are used. Hosted-API runs (Groq) stay out of CI because their daily token cap is per organisation, not per machine.
- Model-written code runs in a resource-limited process on a throw-away runner: acceptable for these tiny tasks, not a security boundary.
- Actions are referenced by major version (`@v4`); pin to commit hashes before treating this as a hardened pipeline.

## Commit identity
All commits are authored by `lllakshit <llakshitmathur239@gmail.com>`; CI publishing uses the same identity.
