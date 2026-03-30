# Review/Improve Loop — Usage Guide

## What it does

Two agents you run inside a Claude Code session:

- **`/review-agent`** — reviews your changed code against quality gates, writes findings to `review-findings.json`
- **`/improve-agent`** — reads `review-findings.json`, plans fixes, applies them, runs tests

Run them manually before pushing. The full autonomous loop (up to 3 iterations) is handled by `ralph-loop`.

---

## Normal workflow

**Quick review before pushing:**
```
/review-agent
```
Claude reviews the diff, scores six criteria, and writes `review-findings.json`.
If everything scores 4+, you're good to push.

**If issues are found, fix them:**
```
/improve-agent
```
Claude reads the findings, writes a plan, fixes the issues, runs tests, then signals it's ready for re-review.

**Full autonomous loop (review → fix → review, up to 3 cycles):**
```
/ralph-loop
```
Point it at `scripts/review_loop.sh` as its instructions. It will loop until everything passes or hits the iteration limit, then open a PR.

---

## Quality gates

All six criteria must score 4 or above to pass.

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

Created and deleted automatically — do not commit them.

| File | Created by | Purpose |
|------|-----------|---------|
| `review-findings.json` | review-agent | Scores and blocking issues |
| `improve-plan.md` | improve-agent | Plan written before any code is touched |
| `review-status.json` | improve-agent | Signals fixes are done |
| `review-blocked.md` | loop | Summary when max iterations hit without passing |

---

## Calibration (first-time only)

Before using on real code, run the calibration steps in `REVIEW_AGENT_SETUP.md` (steps 3 and 4) to verify the agents are scoring sensibly.

---

## Troubleshooting

**Scores are all 5s and it passes immediately**
The working tree may be clean — nothing to review. Run `git diff --name-only HEAD` to check.

**Improve agent edits code before writing improve-plan.md**
Add `CRITICAL:` to the top of rule 2 in the `/improve-agent` section of `CLAUDE.md`.

**Loop hits 3 iterations without passing**
Read `review-blocked.md`. The remaining issue needs manual judgment — fix it, delete `review-blocked.md`, then run the loop again.

**github plugin can't find the repo**
Run `/github auth status` to check authentication.
