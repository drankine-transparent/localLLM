# Code Review + Improve Agent Loop — Implementation Guide

This document tells Claude Code exactly what to build. Work through the steps in order.
Do not skip ahead. Each step has a verification check before moving to the next.

---

## What you are building

A two-agent loop that:
1. Reviews changed code against project-specific quality criteria
2. Writes structured findings to a JSON file
3. Passes findings to an improve agent that plans and fixes issues
4. Iterates up to 3 times, then opens a GitHub PR on pass or flags for human review on failure

The loop is orchestrated by `ralph-loop` and uses the `github`, `code-review`, and built-in
`/loop` plugins.

---

## Step 1 — Add agent personas to CLAUDE.md

Open `CLAUDE.md` and append the following block at the very end of the file,
after the existing "What NOT to do" section. Do not modify any existing content.

```markdown
---

## /review-agent

You are an adversarial code reviewer for the localLLM project.
Your job is to FIND problems, not to validate that code is acceptable.
Be skeptical by default. A score of 3 is NOT a pass.

### Scope

Before reviewing, run:

    git diff --name-only HEAD

Review only files that appear in this output.
Skip anything in: data/, tests/, .md files, and __pycache__.

### Grading criteria

Score each criterion 1–5. Minimum passing score per criterion is 4.
If ANY criterion scores below 4, the overall result is pass=false.

**provider-abstraction**
All LLM calls route through llm.py. No direct OpenAI or Anthropic client
calls anywhere else in the codebase. Check main.py, prompts.py, and any
new files for violations.

**frontend-containment**
All CSS, HTML, and JS remains in static/index.html. No new .js or .css
files have been created anywhere in the project. Check git diff for new files.

**css-variable-discipline**
No hardcoded hex colors exist outside the :root block in static/index.html.
All color references use CSS variables. Search for # followed by 3 or 6 hex
characters outside :root.

**memory-write-safety**
All memory writes use the append-only pattern via POST /api/memory/learn.
The LLM returns {"file": "...", "append": "..."} and the server appends only.
No code path does a full file overwrite in the learn or suggest flows.

**deny-list-respect**
No code touches data/TASKS.md or data/logs/ outside of the designated
API endpoints defined in main.py. Check for any direct file path references
to these locations in new or changed code.

**test-coverage**
Any changed .py file has a corresponding test in tests/ or the absence
is explicitly noted with a reason. Missing tests are not an automatic fail
but must be flagged in blocking_issues with explanation.

### Output format

Write findings ONLY to review-findings.json in the project root.
Do not write prose summaries or print to stdout.

Structure:

    {
      "pass": false,
      "iteration": 1,
      "scores": {
        "provider-abstraction":    { "score": 5, "notes": "" },
        "frontend-containment":    { "score": 3, "notes": "New file chart.js created at..." },
        "css-variable-discipline": { "score": 5, "notes": "" },
        "memory-write-safety":     { "score": 4, "notes": "" },
        "deny-list-respect":       { "score": 5, "notes": "" },
        "test-coverage":           { "score": 3, "notes": "memory.py changed, no test added" }
      },
      "blocking_issues": [
        "chart.js created outside static/index.html — all JS must stay in the single file",
        "memory.py changed with no corresponding test"
      ],
      "suggestions": []
    }

Do not pass a review if any criterion is below 4.
Set pass=true only when all six criteria score 4 or above.

---

## /improve-agent

You are a code improver for the localLLM project.
You receive review-findings.json as your primary input.

### Rules

1. Read review-findings.json fully before touching any file.
2. Write your improvement plan to improve-plan.md before writing any code.
   The plan must list: which files you will change, what change you will make,
   and which blocking issue each change addresses.
3. Do not modify any code until improve-plan.md is written.
4. Address blocking_issues first. Address suggestions only if blocking issues
   are all resolved and context allows.
5. Run `pytest tests/ -v` after every change to a .py file.
   If a test that was passing before is now failing, revert that specific change
   immediately and note it in improve-plan.md as unresolved.
6. After all fixes are applied and tests pass, delete review-findings.json
   and improve-plan.md.
7. Write {"status": "ready-for-review", "iteration": N} to review-status.json
   where N is the current iteration number.

### Hard constraints — never violate these

- The entire frontend lives in static/index.html. This is not a constraint
  to work around — it is the architecture. If a fix seems to require a new
  file, stop and flag it in improve-plan.md instead of creating the file.
- Do not touch data/TASKS.md or data/logs/ under any circumstances.
- Do not refactor code that was not flagged in review-findings.json.
  Scope every change to the findings only.
- Do not create new files unless the review explicitly identified a missing
  file as the required fix.
- LLM calls go through llm.py only. Do not call the OpenAI or Anthropic
  client directly from any other file.
```

**Verification:** After appending, run:

```bash
grep -n "review-agent\|improve-agent" CLAUDE.md
```

You should see both section headers. If not, the append failed — try again.

---

## Step 2 — Create the loop script

Create a new file at the project root called `scripts/review_loop.sh`:

```bash
#!/usr/bin/env bash
# review_loop.sh — triggers the full review/improve cycle
# Usage: bash scripts/review_loop.sh [optional: specific file to review]
set -euo pipefail

TIMESTAMP=$(date +%Y%m%d-%H%M)
BRANCH="review/session-${TIMESTAMP}"
MAX_ITERATIONS=3

echo "=== Review/Improve Loop ==="
echo "Branch: ${BRANCH}"
echo "Max iterations: ${MAX_ITERATIONS}"
echo ""

# Step 1: Create branch via github plugin
# Claude Code will interpret this comment and use the github plugin
# GITHUB: create branch ${BRANCH} from current HEAD

echo "Branch created. Starting review loop..."

/loop "
GOAL: Review changed files, fix any quality gate failures, open a PR on pass.

CONTEXT:
- Project root contains CLAUDE.md with /review-agent and /improve-agent instructions
- All conventions are defined in CLAUDE.md — read it before each agent step
- Branch: ${BRANCH}
- Max iterations: ${MAX_ITERATIONS}

STEPS:
1. Run /review-agent
   - It reads git diff to find changed files
   - It writes results to review-findings.json
   - Read review-findings.json after it completes

2. Check review-findings.json:
   - If pass=true: go to PASS STEPS below
   - If pass=false and iteration < ${MAX_ITERATIONS}: go to step 3
   - If pass=false and iteration = ${MAX_ITERATIONS}: go to BLOCKED STEPS below

3. Run /improve-agent
   - It reads review-findings.json
   - It writes improve-plan.md before touching code
   - It runs pytest after every .py change
   - It writes review-status.json when done
   - Increment iteration count and return to step 1

PASS STEPS:
1. Run: git add -A && git commit -m 'review: all criteria pass (iteration N)'
2. Use github plugin: push branch ${BRANCH} to origin
3. Use github plugin: open PR
   - Title: 'Automated review pass: ${BRANCH}'
   - Body: paste the full contents of review-findings.json
4. Delete review-findings.json, improve-plan.md, review-status.json if they exist
5. Print: 'Loop complete. PR opened.'
6. STOP

BLOCKED STEPS:
1. Write a file called review-blocked.md with:
   - Which criteria failed after ${MAX_ITERATIONS} iterations
   - The last review-findings.json content
   - A plain-English summary of what could not be resolved automatically
2. Print: 'Loop blocked after ${MAX_ITERATIONS} iterations. See review-blocked.md.'
3. STOP

STOP_CONDITION: pass=true in review-findings.json OR iteration=${MAX_ITERATIONS}
MAX_ITERATIONS: ${MAX_ITERATIONS}
"
```

Make it executable:

```bash
chmod +x scripts/review_loop.sh
```

**Verification:** Run `cat scripts/review_loop.sh` and confirm the file exists and is readable.

---

## Step 3 — Calibrate the review agent (do this before anything else)

Run the review agent alone against a known file to check that scores are reasonable.
This must be done before running the full loop.

```bash
# Stage a file you recently changed
git add main.py

# Run the review agent in isolation
/review-agent
```

Read the output:

```bash
cat review-findings.json
```

Check:
- Scores are not all 5 (too lenient — tighten the criteria prompt)
- Scores are not all 1 (miscalibrated — check the scope instruction found the right files)
- Blocking issues listed match real problems you can see in the diff
- The JSON is valid (run `python3 -m json.tool review-findings.json` to verify)

If scores look wrong, update the relevant criterion description in CLAUDE.md and re-run.
Do not proceed to step 4 until scores feel calibrated.

Clean up:

```bash
rm -f review-findings.json
git restore --staged main.py
```

---

## Step 4 — Calibrate the improve agent (do this before the full loop)

Manually create a test review-findings.json with one deliberate failure:

```bash
cat > review-findings.json << 'EOF'
{
  "pass": false,
  "iteration": 1,
  "scores": {
    "provider-abstraction":    { "score": 5, "notes": "" },
    "frontend-containment":    { "score": 2, "notes": "Test: hypothetical new file chart.js detected" },
    "css-variable-discipline": { "score": 5, "notes": "" },
    "memory-write-safety":     { "score": 5, "notes": "" },
    "deny-list-respect":       { "score": 5, "notes": "" },
    "test-coverage":           { "score": 5, "notes": "" }
  },
  "blocking_issues": [
    "CALIBRATION TEST: This is a fake issue to test improve-agent behavior. Do not change any code. Write improve-plan.md explaining what you would do, then stop."
  ],
  "suggestions": []
}
EOF
```

Run the improve agent:

```bash
/improve-agent
```

Check that it:
- Wrote improve-plan.md before touching any code file
- Did NOT create any new files
- Did NOT modify static/index.html or any .py file (because the blocking issue says to stop)
- Wrote review-status.json

If it started modifying files without writing improve-plan.md first, update the
improve-agent instructions in CLAUDE.md to make step 2 more explicit, then re-run.

Clean up:

```bash
rm -f review-findings.json improve-plan.md review-status.json
```

---

## Step 5 — Run the full loop on a low-stakes change

Make a small, intentional change to one file (add a comment, fix a minor issue).
Stage it and run the full loop:

```bash
# Make a small change
echo "# reviewed" >> main.py

git add main.py

# Run the loop
bash scripts/review_loop.sh
```

Watch what happens:
- A branch should be created
- review-findings.json should appear
- If pass=false, improve-plan.md should appear before any code changes
- After improvement, review-findings.json should be updated
- On pass, a PR should be opened

If anything goes wrong, check `review-blocked.md` for a summary.

Clean up the test change:

```bash
git checkout main.py
```

---

## Step 6 — Optional: add as a pre-push git hook

If you want the loop to run automatically before every push, create a pre-push hook:

```bash
cat > .git/hooks/pre-push << 'EOF'
#!/usr/bin/env bash
echo "Running automated review loop before push..."

bash scripts/review_loop.sh

if [ -f "review-blocked.md" ]; then
  echo ""
  echo "ERROR: Review loop could not resolve all issues after 3 iterations."
  echo "See review-blocked.md for details."
  echo "Fix the issues manually or delete review-blocked.md to force push."
  exit 1
fi

echo "Review loop passed. Proceeding with push."
EOF

chmod +x .git/hooks/pre-push
```

**Note:** This will add time to every push. Only add this if you want it enforced
automatically. You can always run `bash scripts/review_loop.sh` manually instead.

---

## File summary

After completing all steps, these files should exist:

| File | What it is |
|------|------------|
| `CLAUDE.md` | Updated with /review-agent and /improve-agent sections at the bottom |
| `scripts/review_loop.sh` | The loop script you run to trigger a cycle |
| `.git/hooks/pre-push` | Optional: auto-runs loop before every push |

These files are written and deleted by the loop at runtime (not committed):

| File | Written by | Purpose |
|------|-----------|---------|
| `review-findings.json` | review-agent | Structured findings with pass/fail and scores |
| `improve-plan.md` | improve-agent | Plan written before any code is touched |
| `review-status.json` | improve-agent | Signals completion of an improve cycle |
| `review-blocked.md` | loop script | Summary when max iterations hit without pass |

---

## Troubleshooting

**Review agent scores everything 5 and passes trivially**
The scope instruction is probably not finding any changed files.
Run `git diff --name-only HEAD` manually and check what it returns.
If the working tree is clean, there is nothing to review.

**Improve agent modifies files before writing improve-plan.md**
The agent is not reading the constraints carefully enough.
Add this line to the top of the /improve-agent section in CLAUDE.md:
`CRITICAL: Write improve-plan.md before touching a single line of code. This is non-negotiable.`

**pytest fails after an improve cycle**
The improve agent reverted the change that broke the test (per its instructions).
Check improve-plan.md — it should note which issue was left unresolved.
You will need to fix that issue manually.

**Loop hits 3 iterations without passing**
Read review-blocked.md. The issue is either too ambiguous for the improve agent
to resolve automatically, or it requires a structural change that needs human judgment.
Fix it manually, then run the loop again.

**github plugin cannot find the repo**
Run `/github auth status` to check authentication.
The plugin needs a valid GitHub token with repo write access.
