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
