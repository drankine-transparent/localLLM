# localLLM — Claude Code Instructions

## Dev setup

```bash
source venv/bin/activate                        # always activate venv first
uvicorn main:app --reload --port 8000           # start dev server
pytest tests/ -v                                # run tests
```

Requires **LM Studio** running at `localhost:1234` with a model loaded. Tests do NOT require LM Studio (they mock the client).

---

## Architecture

Single-page app — all frontend in one file, served by FastAPI.

| File | Role |
|------|------|
| `main.py` | FastAPI app — all API routes |
| `llm.py` | LLM client — supports LM Studio (local) and OpenAI (cloud), runtime-switchable |
| `tasks.py` | `data/TASKS.md` parser and section manager |
| `memory.py` | Memory file system (`data/memory/`) |
| `prompts.py` | Prompt templates for extract, chat, memory learn/suggest |
| `static/index.html` | **All** frontend: HTML + CSS + JS in one file |
| `scripts/import_people.py` | One-time TSV import tool for people directory |
| `data/TASKS.md` | Task state — plain markdown, app-owned |
| `data/memory/` | Knowledge base markdown files |
| `data/logs/extract_log.jsonl` | Per-run extraction metrics |

### Memory directory layout

```
data/memory/
  profile.md          ← hot cache: Dee's personal context loaded into LLM prompts
  glossary.md         ← acronyms, terms, project codenames
  people/             ← active staff, contractors, board (gitignored — contains PII)
  exits/              ← alumni / former staff (gitignored — contains PII)
  projects/           ← project context files
  context/            ← general context files
```

---

## UI panels

The app has two main panels accessible from the left sidebar:

- **Imports** (default) — drop or paste a transcript, trigger LLM task extraction
- **Tasks** — kanban board with Active / Waiting On / Someday / Done columns

Task cards support **drag-and-drop** between columns (no "Move to…" dropdown). Backend move endpoint: `PUT /api/tasks/:id/move`.

The **Memory** panel shows an accordion tree:
- Root files → "Backgrounds"
- `people/` → "People"
- `exits/` → "Exits"
- `projects/` → "Projects"
- `context/` → "Context"

Default view on file open is **Preview** (rendered markdown). Switch to Edit mode to modify.

---

## Key conventions

- **`data/memory/profile.md`** is the app's hot cache — loaded into LLM prompts. Do not confuse with this file.
- **`data/TASKS.md`** is owned by the app — never edit manually; use `/api/tasks` endpoints only.
- **`data/memory/`** is writable by Claude — `data/TASKS.md` and `data/logs/` are deny-listed in `.claude/settings.local.json`.
- All CSS, HTML, and JS live in `static/index.html` — do not create separate asset files.
- Design tokens are in `:root` (TP teal palette) — use CSS variables, not hardcoded hex values.
- LLM calls go through `llm.py` — do not call the OpenAI client directly from `main.py`.
- Provider is runtime-switchable: `GET/POST /api/settings` with `{"provider": "lmstudio"|"openai"}`. Toggle in sidebar footer.
- `OPENAI_API_KEY` must be in `.env` (not committed) to use OpenAI provider.
- Chunk threshold: 8,000 chars per chunk (`MAX_INPUT_CHARS` in `prompts.py`).
- LLM temperature: 0.3, fixed in `llm.py`.
- Extraction can be cancelled mid-run: `POST /api/tasks/extract/cancel` — checked between chunks, returns partial results.
- Memory learn API (`POST /api/memory/learn`) is append-only: LLM returns `{"file": "...", "append": "...snippet..."}`, server reads existing file and appends snippet + source attribution. Never rewrites full file content.
- Memory source attribution is injected server-side (not by LLM) — format: `*Source · YYYY-MM-DD HH:MM*`.

---

## Testing

- `tests/test_streaming.py` — 7 unit tests covering `chat_stream_with_usage()` and extract status
- Tests mock the OpenAI client — no LM Studio needed
- Run `pytest tests/ -v` before declaring any work complete

---

## What NOT to do

- Always activate venv first — system Python on this machine is 3.14
- Always restart uvicorn after editing any `.py` file — `pkill -f "uvicorn main:app"; uvicorn main:app --reload --port 8000`
- Do not edit `data/TASKS.md` or `data/logs/` directly — they are app-owned and deny-listed
- Do not add separate `.css` or `.js` files — keep everything in `static/index.html`
- Do not hardcode hex colors — use CSS variables from `:root`
- Do not commit `data/memory/people/` or `data/memory/exits/` — they contain PII (home addresses, personal phone numbers)

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
