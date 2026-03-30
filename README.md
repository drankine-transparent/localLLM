# Local LLM Productivity System

A lightweight, privacy-first task and knowledge management app powered by a local LLM via [LM Studio](https://lmstudio.ai/) — or Claude as a fallback.

All processing happens on your machine by default — no data leaves your network unless you switch to Claude.

## Features

- **Kanban task board** — Active, Waiting On, Someday, and Done columns displayed simultaneously with drag-and-drop between columns
- **Transcript extraction** — Paste a meeting transcript and the LLM extracts action items into the right column. Darren's tasks go to Active; tasks owned by others go to Waiting On with a `Person: ` prefix. Every card includes the meeting name, date, and rich context
- **Extraction log** — Each import run is logged with meeting name, task count, and timestamp. Click any log entry to view all tasks extracted from that meeting in a full-screen overlay
- **Cancel extraction** — Stop a running extraction job mid-flight with the Stop button
- **Task management** — Create, move, complete, and delete tasks. All state lives in a plain `data/TASKS.md` file
- **Memory system** — A file-based knowledge base (`data/memory/`) with a profile, glossary, people directory, and project notes. All memory writes are append-only and stamped with source + timestamp
- **Memory suggestions** — After an import, the LLM suggests new people, terms, projects, or facts to save. Each suggestion shows the destination file before you commit
- **Chat** — Ask questions with your memory context automatically included. Save any chat response to memory with one click
- **Provider toggle** — Switch between LM Studio (local) and Claude at runtime from the Settings panel

## Architecture

```
Browser (static/index.html)
   ↕ REST API
FastAPI (main.py)
   ↕ OpenAI-compatible API
LM Studio (localhost:1234)  ← default
   or
Claude API (claude-sonnet-4-6)  ← switchable at runtime
```

| File | Purpose |
|------|---------|
| `main.py` | FastAPI routes and request handling |
| `llm.py` | Dual-provider client — LM Studio (default) or Claude, runtime-switchable |
| `prompts.py` | Prompt templates for extraction, memory learn/suggest, chat |
| `tasks.py` | TASKS.md parser/writer |
| `memory.py` | Memory directory read/write |
| `static/index.html` | Single-page frontend (all HTML, CSS, JS in one file) |
| `data/TASKS.md` | Task state (plain markdown, app-owned) |
| `data/memory/` | Knowledge base files |
| `data/logs/extract_log.jsonl` | Per-run extraction metrics |

### Memory layout

```
data/memory/
  profile.md          ← personal context loaded into LLM prompts
  glossary.md         ← acronyms, terms, project codenames
  people/             ← staff profiles (gitignored — contains PII)
  exits/              ← alumni (gitignored — contains PII)
  projects/           ← project context files
  context/            ← general context files
```

## Prerequisites

- Python 3.12 (not 3.14 — pydantic-core wheel breaks)
- [LM Studio](https://lmstudio.ai/) running on `localhost:1234` with a model loaded (tested with `qwen/qwen3-32b`)
- Optional: `ANTHROPIC_API_KEY` env var to use Claude as provider

## Setup

```bash
cd localLLM
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Run

1. Open LM Studio, go to the **Developer** tab, and load a model
2. Start the app:

```bash
source venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000
```

3. Open [http://localhost:8000](http://localhost:8000)

## Task extraction conventions

The LLM follows these rules when extracting tasks from a transcript:

- **Darren / Dee / Darren Rankine** owns the task → placed in **Active**, no prefix
- **Anyone else** owns the task → placed in **Waiting On**, title starts with `FirstName: `
- Every task context ends with a meeting tag: `` `Meeting Name · YYYY-MM-DD` ``

Long transcripts are automatically split into ~8K character chunks, extracted sequentially, and deduplicated by title.

## API

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | LM Studio / Claude connection status |
| GET | `/api/settings` | Get current provider |
| POST | `/api/settings` | Set provider (`lmstudio` or `claude`) |
| GET | `/api/tasks` | List all tasks |
| POST | `/api/tasks` | Create a task |
| POST | `/api/tasks/extract` | Extract tasks from transcript text |
| GET | `/api/tasks/extract/status` | Extraction progress (SSE) |
| POST | `/api/tasks/extract/cancel` | Cancel in-progress extraction |
| PUT | `/api/tasks/{id}/toggle` | Toggle task done state |
| PUT | `/api/tasks/{id}/move` | Move task to different section |
| DELETE | `/api/tasks/{id}` | Delete a task |
| GET | `/api/memory` | List memory files |
| GET | `/api/memory/{path}` | Read a memory file |
| POST | `/api/memory` | Write a memory file (full overwrite) |
| POST | `/api/memory/learn` | Append a new fact to memory (LLM-routed, source-attributed) |
| POST | `/api/memory/suggest` | Suggest memory items from transcript text |
| POST | `/api/chat` | Chat with memory context |
| GET | `/api/logs` | List extraction log entries |
