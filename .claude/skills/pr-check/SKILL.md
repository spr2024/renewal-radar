---
name: pr-check
description: Validates renewal-radar's code (backend/fetcher.py, backend/generator.py, frontend/app.py, scripts/) before opening a pull request - syntax/import checks, git hygiene, a no-cost fetcher smoke test, and (when generator.py changed) the paid Claude-output eval suite. Use before creating a PR, or whenever asked to validate, check, or sanity-test the code pre-PR.
---

# Pre-PR validation for renewal-radar

Run the checks below in order and finish with one pass/fail summary. If a step
turns up something destructive or a possible secret exposure, stop and show
the user before doing anything else - don't run git add/commit/push past that
point until they've seen it.

Use the project venv for every Python command: `.venv/Scripts/python.exe` and
`.venv/Scripts/pip.exe` (this is a Windows/PowerShell project - do not assume
a bare `python`/`pip` on PATH is the right interpreter).

## 1. Working tree sanity

- `git status` - see what's staged, unstaged, and untracked. Confirm nothing
  that should be gitignored snuck in: `.env`, `data/raw/*.zip|csv|txt`,
  `data/processed/*.db`, `.venv/`, `__pycache__/`. If any of those show up as
  trackable, flag it before continuing.
- `git diff --stat` then `git diff` for the full changes - know what's
  actually in this PR before validating it.

## 2. Python syntax & import check

For every changed `.py` file, plus always the core modules regardless of
whether they show as changed:

```
.venv/Scripts/python.exe -m py_compile backend/fetcher.py backend/generator.py frontend/app.py scripts/run_evals.py scripts/build_db.py
.venv/Scripts/python.exe -c "import sys; sys.path.insert(0, '.'); from backend import fetcher, generator; import frontend.app" 2>&1 || true
```

(The `frontend.app` import will run Streamlit's script-execution machinery
oddly outside `streamlit run` - if it errors specifically because it's not
running under Streamlit, that's expected and not a real failure; a genuine
`ImportError`/`SyntaxError`/`NameError` is not.) A cleaner check for the
frontend specifically:

```
.venv/Scripts/python.exe -m py_compile frontend/app.py
```

## 3. Dependency sync

- Check that every third-party import in changed files (`streamlit`,
  `anthropic`, `pandas`, `python-dotenv`, `fastapi`, `uvicorn`, ...) is listed
  in `requirements.txt`, and that `requirements.txt` versions match what's
  actually installed if that matters for the change.
- `.venv/Scripts/pip.exe check` - catches dependency conflicts.

## 4. Fetcher smoke test (no API cost - always run this one)

```
.venv/Scripts/python.exe -c "
import sys; sys.path.insert(0, '.')
from backend import fetcher
r = fetcher.search_and_enrich('LL Bean')
assert r, 'no results - DB missing or search broken'
assert 'renewal' in r[0] and 'premium_estimate' in r[0] and 'coverage_gaps' in r[0]
print('fetcher OK:', len(r), 'result(s) for', r[0]['sponsor_name'])
"
```

If this fails with `FileNotFoundError` about `data/processed/form5500.db`,
that means the DB just isn't built locally - tell the user to run
`scripts/build_db.py` first. That is not a code defect; don't report it as
one.

## 5. Claude output eval suite (real API cost - gate this on relevance)

Run this only when `backend/generator.py` changed (prompt text, output
schema, model choice, or the JSON-parsing/validation logic), or when the user
explicitly asks for it:

```
.venv/Scripts/python.exe scripts/run_evals.py
```

This calls the live Anthropic API 5 times against `claude-sonnet-5` (small
but real cost - tell the user before running it if they haven't already run
it themselves earlier in the session). Any `FAIL` or `ERROR` in the output
blocks the PR until resolved - either the change broke grounding/urgency
behavior, or the golden set's `expected` rubric in `data/golden_set.json` is
now stale and needs updating alongside the prompt change.

If `backend/generator.py` did not change, skip this step by default - it's
not free, and the fetcher smoke test plus the syntax/import checks already
cover code correctness for everything else.

## 6. Secrets check

- Scan `git diff` (and any newly staged file contents) for hardcoded
  Anthropic keys (`sk-ant-...`) or `ANTHROPIC_API_KEY=<real value>` outside
  `.env`. Confirm `.env` itself does not appear in `git status` as
  staged/tracked - it must stay local-only per `.gitignore`.

## 7. Report

Give a short checklist (pass/fail per numbered step above) and one final
go/no-go line. If everything passes, say so plainly and offer to proceed
with the PR. If anything failed, stop there and fix it - don't open the PR
with a known-failing check.
