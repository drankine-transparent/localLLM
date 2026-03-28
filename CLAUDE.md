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
| `llm.py` | LM Studio OpenAI-compatible client wrapper |
| `tasks.py` | `data/TASKS.md` parser and section manager |
| `memory.py` | Memory file system (`data/memory/`) |
| `prompts.py` | Prompt templates for extract, decode, search, chat |
| `static/index.html` | **All** frontend: HTML + CSS + JS in one file |
| `data/TASKS.md` | Task state — plain markdown, app-owned |
| `data/memory/` | Knowledge base markdown files |
| `data/logs/extract_log.jsonl` | Per-run extraction metrics |

---

## Key conventions

- **`data/memory/CLAUDE.md`** is the app's "hot cache" — Dee's personal context loaded into LLM prompts. It is NOT instructions for Claude Code. Do not confuse it with this file.
- **`data/TASKS.md`** is owned by the app — never edit manually; use `/api/tasks` endpoints only.
- All CSS, HTML, and JS live in `static/index.html` — do not create separate asset files.
- Design tokens are in `:root` (TP teal palette) — use CSS variables, not hardcoded hex values.
- LLM calls go through `llm.py` — do not call the OpenAI client directly from `main.py`.
- Chunk threshold: 12,000 chars per chunk (set in `main.py` `extractTasks`).
- LLM temperature: 0.3, fixed in `llm.py`.

---

## Testing

- `tests/test_streaming.py` — 7 unit tests covering `chat_stream_with_usage()` and extract status
- Tests mock the OpenAI client — no LM Studio needed
- Run `pytest tests/ -v` before declaring any work complete

---

## What NOT to do

- Always activate venv first — system Python on this machine is 3.14
- Do not edit `data/TASKS.md` or `data/memory/CLAUDE.md` directly in code sessions
- Do not add separate `.css` or `.js` files — keep everything in `static/index.html`
- Do not hardcode hex colors — use CSS variables from `:root`
