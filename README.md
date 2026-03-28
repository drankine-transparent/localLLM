# Local LLM Productivity System

A lightweight, privacy-first task and knowledge management app powered by a local LLM via [LM Studio](https://lmstudio.ai/).

All processing happens on your machine — no data leaves your network.

## Features

- **Kanban task board** — Active, Waiting On, Someday, and Done columns displayed simultaneously
- **Transcript extraction** — Paste a meeting transcript and the LLM extracts action items into the right column. Darren's tasks go to Active; tasks owned by others go to Waiting On with a `Person: ` prefix. Every card includes the meeting name, date, and a rich description
- **Task management** — Create, move, complete, and delete tasks. All state lives in a plain `data/TASKS.md` file
- **Memory system** — A file-based knowledge base (`data/memory/`) with a glossary, people directory, and project notes
- **Decode** — Paste workplace shorthand and the LLM expands it using your glossary
- **Search** — Semantic search across your memory files
- **Chat** — Ask questions with your memory context automatically included

## Architecture

```
Browser (static/index.html)
   ↕ REST API
FastAPI (main.py)
   ↕ OpenAI-compatible API
LM Studio (localhost:1234)
```

| File | Purpose |
|------|---------|
| `main.py` | FastAPI routes and request handling |
| `llm.py` | LM Studio client (OpenAI-compatible) |
| `prompts.py` | Prompt templates for extraction, decode, search, chat |
| `tasks.py` | TASKS.md parser/writer |
| `memory.py` | Memory directory read/write/search |
| `static/index.html` | Single-page frontend (kanban board + nav) |
| `data/TASKS.md` | Task state (plain markdown) |
| `data/memory/` | Knowledge base files |

## Prerequisites

- Python 3.12+
- [LM Studio](https://lmstudio.ai/) running on `localhost:1234` with a model loaded (tested with `qwen/qwen3-32b`)

## Setup

```bash
cd localLLM
python3 -m venv venv
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

Example output:

```
Active:
  Book meeting with Lauren to show UI and gather feedback
  — Darren will walk Lauren through the tool today. `Call with Oliver · 2026-03-19`

Waiting On:
  Oliver: Update interview cleanup skill metadata tags
  — Oliver to align metadata tags with MCP server extraction before rolling out. `Call with Oliver · 2026-03-19`
```

Long transcripts are automatically split into ~12K character chunks, extracted in parallel, and deduplicated by title.

## API

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | LM Studio connection status |
| GET | `/api/tasks` | List all tasks |
| POST | `/api/tasks` | Create a task |
| POST | `/api/tasks/extract` | Extract tasks from transcript text |
| PUT | `/api/tasks/{id}/toggle` | Toggle task done state |
| PUT | `/api/tasks/{id}/move` | Move task to different section |
| DELETE | `/api/tasks/{id}` | Delete a task |
| GET | `/api/memory` | List memory files |
| GET | `/api/memory/{path}` | Read a memory file |
| POST | `/api/memory` | Write a memory file |
| POST | `/api/memory/decode` | Decode shorthand using glossary |
| POST | `/api/memory/search` | Search memory files via LLM |
| POST | `/api/chat` | Chat with memory context |
