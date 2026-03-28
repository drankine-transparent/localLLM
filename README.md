# Local LLM Productivity System

A lightweight, privacy-first task and knowledge management app powered by a local LLM via [LM Studio](https://lmstudio.ai/).

## What it does

- **Task extraction** — Paste a meeting transcript and the local LLM extracts action items, commitments, and follow-ups into a structured task board (Active / Waiting On / Someday / Done)
- **Task management** — Create, move, complete, and delete tasks. All state lives in a plain `data/TASKS.md` file
- **Memory system** — A file-based knowledge base (`data/memory/`) with a glossary, people directory, and project notes. The LLM can decode workplace shorthand and search your notes
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
| `prompts.py` | Prompt templates for extraction, decode, search |
| `tasks.py` | TASKS.md parser/writer |
| `memory.py` | Memory directory read/write/search |
| `static/index.html` | Single-page frontend |
| `data/TASKS.md` | Task state (markdown) |
| `data/memory/` | Knowledge base files |

## Prerequisites

- Python 3.12+
- [LM Studio](https://lmstudio.ai/) running on `localhost:1234` with a model loaded

## Setup

```bash
cd localLLM
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Run

1. Start LM Studio and load a model (the server must be running on port 1234)
2. Start the app:

```bash
source venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000
```

3. Open http://localhost:8000

## API

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | LM Studio connection status |
| GET | `/api/tasks` | List all tasks |
| POST | `/api/tasks` | Create a task |
| POST | `/api/tasks/extract` | Extract tasks from text via LLM |
| PUT | `/api/tasks/{id}/toggle` | Toggle task done state |
| PUT | `/api/tasks/{id}/move` | Move task to different section |
| DELETE | `/api/tasks/{id}` | Delete a task |
| GET | `/api/memory` | List memory files |
| GET | `/api/memory/{path}` | Read a memory file |
| POST | `/api/memory` | Write a memory file |
| POST | `/api/memory/decode` | Decode shorthand via LLM |
| POST | `/api/memory/search` | Search memory via LLM |
| POST | `/api/chat` | Chat with memory context |

## How extraction works

Long transcripts are automatically split into ~12K character chunks. Each chunk is sent to the LLM for task extraction, and results are deduplicated by title before being added to `TASKS.md`.
