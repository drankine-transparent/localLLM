# Review/Improve Loop — Usage Guide

## How to use it

The review and improve agents are personas defined in `CLAUDE.md`. You invoke them
by telling Claude Code what to do in plain English — not as slash commands.

---

## Step-by-step workflow

### 1. Ask Claude to make changes
Tell Claude what you want built or fixed. Claude will edit whatever files are needed.

### 2. Ask Claude to run the review agent
Once Claude is done with the changes, type:

> **"Run the review agent"**

Claude will:
- Run `git diff --name-only HEAD` to find changed files
- Score each file against the 6 quality criteria
- Write results to `review-findings.json`
- Tell you if it passed or failed

### 4. If it failed — ask Claude to run the improve agent
In the Claude Code chat, type:

> **"Run the improve agent"**

Claude will:
- Read `review-findings.json`
- Write `improve-plan.md` before touching any code
- Fix the flagged issues
- Run `pytest tests/ -v` after each change
- Clean up the temp files when done

### 5. Review again if needed
Repeat steps 3–4 until the review passes.

### 6. Commit and push as normal
```bash
git commit -m "your message"
git push
```

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
| `review-blocked.md` | improve-agent | Summary if issues can't be resolved |

---

## Troubleshooting

**"Only data/ files changed — nothing to review"**
Stage a code file first: `git add main.py` (or whichever file you changed).

**Scores are all 5s immediately**
Either the change is genuinely clean, or the working tree was already clean before you staged.
Run `git diff --name-only HEAD` to confirm what's in scope.

**Improve agent edits code before writing improve-plan.md**
Add `CRITICAL:` to the top of rule 2 in the `/improve-agent` section of `CLAUDE.md`.

**Issues can't be resolved after 3 attempts**
Claude will write `review-blocked.md` explaining what's stuck. Fix it manually, then run the review agent again.
