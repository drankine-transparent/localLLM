# Review/Improve Loop — Usage Guide

## What it does

Runs a two-agent loop that reviews your changed code against quality gates,
fixes any failures, and opens a GitHub PR when everything passes.
Max 3 iterations before it stops and asks for human input.

---

## Running it manually

```bash
bash scripts/review_loop.sh
```

Run this after making changes you want reviewed before pushing.

---

## Automatic on push (pre-push hook is active)

Every `git push` triggers the loop automatically. You don't need to do anything.

If the push is blocked, you'll see:
```
ERROR: Review loop could not resolve all issues after 3 iterations.
See review-blocked.md for details.
```

To bypass (use with caution):
```bash
rm -f review-blocked.md
git push
```

---

## Quality gates

The review agent scores six criteria. Everything must score 4 or above to pass.

| Criterion | What it checks |
|-----------|----------------|
| `provider-abstraction` | All LLM calls go through `llm.py` only |
| `frontend-containment` | No new `.js` or `.css` files — everything stays in `static/index.html` |
| `css-variable-discipline` | No hardcoded hex colors outside `:root` |
| `memory-write-safety` | Memory writes use append-only pattern via `/api/memory/learn` |
| `deny-list-respect` | Nothing touches `data/TASKS.md` or `data/logs/` outside designated endpoints |
| `test-coverage` | Changed `.py` files have tests, or absence is explained |

---

## Runtime files

These are created and deleted automatically during the loop. Don't commit them.

| File | Created by | When |
|------|-----------|------|
| `review-findings.json` | review-agent | After each review cycle |
| `improve-plan.md` | improve-agent | Before any code is touched |
| `review-status.json` | improve-agent | After fixes are applied |
| `review-blocked.md` | loop | When max iterations hit without passing |

---

## Running agents individually

You can run either agent on its own outside the loop:

**Review only** (writes `review-findings.json`):
```
/review-agent
```

**Improve only** (reads existing `review-findings.json`):
```
/improve-agent
```

---

## Calibration (first-time setup only)

Before using the loop on real code, calibrate both agents. See `REVIEW_AGENT_SETUP.md` steps 3 and 4.

---

## Troubleshooting

**Scores are all 5s (nothing fails)**
The working tree may be clean. Run `git diff --name-only HEAD` — if it returns nothing, there's nothing to review.

**Improve agent touches code before writing improve-plan.md**
Update the `/improve-agent` section in `CLAUDE.md` — add `CRITICAL:` to the top of the plan-first rule.

**Loop hits 3 iterations without passing**
Read `review-blocked.md`. The issue needs manual judgment. Fix it, delete `review-blocked.md`, then push again.

**github plugin can't find the repo**
Run `/github auth status` to check authentication.
