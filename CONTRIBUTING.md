# Contributing

Thanks for looking. The most useful contribution is scrutiny: find where a result is weak, and show it with evidence.

**Where to start:** the open goals are the issues in the milestone [V1.2: validate with a language model](https://github.com/Lakshit-Startup-Ideas/Lucifer-BenchMarks/milestone/2). Issues labelled `good first issue` are self-contained. The full history, with each milestone's pass or fail, is on the [milestones page](https://lucifer-update.vercel.app/milestones).

## Rules this project follows (please keep them)
1. **Pre-register.** For anything that claims a result, write the hypothesis, the baseline, the metric and the failure condition in a file and commit it **before** the code or the run. Changes afterwards go in an "Amendments" section with the reason.
2. **Report failures.** A negative result is published the same way as a positive one. Do not move a threshold after seeing data.
3. **Test the tests.** A new safeguard needs a test that fails when the safeguard is removed.
4. **Say what is not shown.** Every result file ends with what it does not establish. Do not describe a simulation as a validated real-model result.
5. **No secrets, no private data** in commits, issues or logs.
6. **Version 1 stays reproducible.** Version 1 lives outside `v1.1/` and is not changed without a reason. Work for Version 1.1 and later goes under `v1.1/` (or a new versioned folder).

## Running things
```bash
# Version 1
pip install -e ".[dev]" && python -m pytest
# Version 1.1
cd v1.1 && python -m venv .venv && .venv/bin/pip install -e ".[dev]" && .venv/bin/python -m pytest -q
```
Open a pull request; the V1 and V1.1 workflows run on it.
