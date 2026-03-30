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
