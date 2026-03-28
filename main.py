"""FastAPI app — Local LLM Productivity System."""

import json as _json
import time
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from pathlib import Path

import tasks
import memory
import llm
import prompts

app = FastAPI(title="Local LLM Productivity")

STATIC_DIR = Path(__file__).parent / "static"
LOG_PATH = Path(__file__).parent / "data" / "logs" / "extract_log.jsonl"
_extract_status: dict = {"phase": "idle"}


def write_extract_log(entry: dict) -> None:
    """Append one JSON line to the extraction log."""
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(_json.dumps(entry) + "\n")


# --- Pydantic models ---

class TaskCreate(BaseModel):
    title: str
    section: str = "active"
    context: str | None = None


class TaskMove(BaseModel):
    section: str


class TextInput(BaseModel):
    text: str


class MemoryWrite(BaseModel):
    path: str
    content: str


class SearchQuery(BaseModel):
    query: str


class ChatMessage(BaseModel):
    message: str


class LearnInput(BaseModel):
    text: str


class SuggestInput(BaseModel):
    text: str


# --- Routes ---

@app.get("/")
async def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
async def health():
    return await llm.health_check()


# --- Tasks ---

@app.get("/api/tasks")
async def get_tasks():
    return tasks.parse()


@app.post("/api/tasks")
async def create_task(body: TaskCreate):
    task = tasks.add_task(body.title, body.section, body.context)
    return task


@app.post("/api/tasks/extract")
async def extract_tasks(body: TextInput):
    global _extract_status
    try:
        chunk_size = prompts.MAX_INPUT_CHARS
        text = body.text
        chunks = [text[i:i + chunk_size] for i in range(0, len(text), chunk_size)]

        print(f"[EXTRACT] Processing {len(chunks)} chunk(s) from {len(text)} chars")

        extract_start = time.monotonic()
        _extract_status = {
            "phase": "running",
            "total_chunks": len(chunks),
            "done_chunks": 0,
            "input_chars": len(text),
            "started_at": extract_start,
            "chunks": [],
            "current_chunk": None,
        }

        all_tasks = []
        total_prompt_tokens = 0
        total_completion_tokens = 0
        model_used = "unknown"

        for idx, chunk in enumerate(chunks):
            chunk_start = time.monotonic()
            prompt = prompts.TASK_EXTRACTION.format(text=chunk)
            _extract_status["current_chunk"] = {"index": idx + 1, "chars": 0, "tokens": 0}

            def on_progress(chars: int, tokens: int, _idx: int = idx) -> None:
                _extract_status["current_chunk"] = {"index": _idx + 1, "chars": chars, "tokens": tokens}

            cr = await llm.chat_stream_with_usage(
                "You are a precise task extractor. Output only valid JSON arrays. No markdown, no explanation.",
                prompt,
                on_progress=on_progress,
            )
            model_used = cr.model
            total_prompt_tokens += cr.prompt_tokens
            total_completion_tokens += cr.completion_tokens

            print(f"[EXTRACT] Chunk {idx+1} raw: {cr.content[:300]}")
            chunk_tasks = []
            try:
                result = llm.parse_json(cr.content)
                if isinstance(result, dict):
                    result = result.get("tasks", [result])
                if isinstance(result, list):
                    chunk_tasks = result
                    all_tasks.extend(result)
            except (ValueError, Exception) as e:
                print(f"[EXTRACT] Chunk {idx+1} parse error: {e}")

            chunk_elapsed = round(time.monotonic() - chunk_start, 1)
            _extract_status["current_chunk"] = None
            _extract_status["done_chunks"] = idx + 1
            _extract_status["chunks"].append({
                "index": idx + 1,
                "tasks_found": len(chunk_tasks),
                "tokens": cr.prompt_tokens + cr.completion_tokens,
                "elapsed_seconds": chunk_elapsed,
            })

        # Deduplicate by title (case-insensitive)
        seen = set()
        added = []
        for item in all_tasks:
            if not isinstance(item, dict):
                continue
            title = item.get("title", "Untitled")
            key = title.lower().strip()
            if key in seen:
                continue
            seen.add(key)
            task = tasks.add_task(
                title=title,
                section=item.get("section", "active"),
                context=item.get("context"),
            )
            added.append(task)

        duration = round(time.monotonic() - extract_start, 1)
        write_extract_log({
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"),
            "model": model_used,
            "duration_seconds": duration,
            "prompt_tokens": total_prompt_tokens,
            "completion_tokens": total_completion_tokens,
            "total_tokens": total_prompt_tokens + total_completion_tokens,
            "chunks": len(chunks),
            "action_items": len(added),
            "input_chars": len(text),
        })

        _extract_status["phase"] = "done"
        _extract_status["duration_seconds"] = duration
        _extract_status["extracted"] = len(added)

        print(f"[EXTRACT] Total: {len(added)} unique tasks from {len(all_tasks)} raw")
        return {"extracted": len(added), "tasks": added}
    except Exception as e:
        _extract_status = {"phase": "error", "message": str(e)}
        print(f"[EXTRACT] Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/extract/status")
async def extract_status():
    """Return current extraction progress state."""
    s = _extract_status.copy()
    if s.get("phase") == "running":
        s["elapsed_seconds"] = round(time.monotonic() - s["started_at"], 1)
    s.pop("started_at", None)
    return s


@app.put("/api/tasks/{task_id}/toggle")
async def toggle(task_id: str):
    task = tasks.toggle_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@app.put("/api/tasks/{task_id}/move")
async def move(task_id: str, body: TaskMove):
    task = tasks.move_task(task_id, body.section)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@app.delete("/api/tasks/{task_id}")
async def delete(task_id: str):
    if not tasks.delete_task(task_id):
        raise HTTPException(status_code=404, detail="Task not found")
    return {"deleted": True}


# --- Memory ---

@app.get("/api/memory")
async def list_memory():
    return memory.list_files()


@app.get("/api/memory/{path:path}")
async def read_memory(path: str):
    content = memory.read_file(path)
    if content is None:
        raise HTTPException(status_code=404, detail="File not found")
    return {"path": path, "content": content}


@app.post("/api/memory")
async def write_memory(body: MemoryWrite):
    try:
        return memory.write_file(body.path, body.content)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/memory/decode")
async def decode_memory(body: TextInput):
    try:
        glossary = prompts.truncate(memory.get_glossary(), 3000)
        prompt = prompts.MEMORY_DECODE.format(
            glossary=glossary, text=prompts.truncate(body.text)
        )
        result = await llm.chat(
            "You decode workplace shorthand using the provided glossary.", prompt
        )
        return {"original": body.text, "decoded": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/memory/learn")
async def learn_memory(body: LearnInput):
    try:
        claude_md = prompts.truncate(memory.get_hot_cache(), 2000)
        glossary_md = prompts.truncate(memory.get_glossary(), 2000)
        prompt = prompts.MEMORY_LEARN.format(
            text=prompts.truncate(body.text, 1000),
            claude_md=claude_md,
            glossary_md=glossary_md,
        )
        result = await llm.chat(
            "You manage a memory file system. Return only valid JSON.", prompt
        )
        parsed = llm.parse_json(result)
        if not isinstance(parsed, dict) or "file" not in parsed or "content" not in parsed:
            raise ValueError(f"Unexpected LLM response: {result[:200]}")
        saved = memory.write_file(parsed["file"], parsed["content"])
        return {"saved": True, "file": parsed["file"], "size": saved["size"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/memory/suggest")
async def suggest_memory(body: SuggestInput):
    """Scan transcript for new people/terms/facts not already in memory."""
    try:
        claude_md = prompts.truncate(memory.get_hot_cache(), 1500)
        prompt = prompts.MEMORY_SUGGEST.format(
            claude_md=claude_md,
            text=prompts.truncate(body.text, 8000),
        )
        result = await llm.chat(
            "You identify new information worth adding to a memory system. Return only valid JSON.",
            prompt,
        )
        suggestions = llm.parse_json(result)
        if not isinstance(suggestions, list):
            return []
        return suggestions
    except Exception:
        return []  # Suggestions are optional — fail silently


@app.post("/api/memory/search")
async def search_memory(body: SearchQuery):
    try:
        kb = prompts.truncate(memory.get_all_content(), 4000)
        prompt = prompts.MEMORY_SEARCH.format(
            knowledge_base=kb, query=body.query
        )
        result = await llm.chat(
            "You search a knowledge base and return relevant results.", prompt
        )
        return {"query": body.query, "results": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- Chat ---

@app.post("/api/chat")
async def chat_endpoint(body: ChatMessage):
    try:
        context = memory.get_hot_cache()
        system = prompts.CHAT_SYSTEM.format(context=context)
        result = await llm.chat(system, body.message)
        return {"response": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- Logs ---

@app.get("/api/logs")
async def get_logs(limit: int = 20):
    """Return last `limit` extraction log entries, newest first."""
    if not LOG_PATH.exists():
        return []
    lines = LOG_PATH.read_text(encoding="utf-8").strip().splitlines()
    entries = []
    for line in reversed(lines[-limit:]):
        try:
            entries.append(_json.loads(line))
        except _json.JSONDecodeError:
            continue
    return entries


@app.post("/api/parse-file")
async def parse_file(file: UploadFile = File(...)):
    """Extract plain text from an uploaded .txt, .md, or .pdf file."""
    filename = file.filename or ""
    ext = filename.rsplit(".", 1)[-1].lower()

    if ext in ("txt", "md"):
        content = await file.read()
        return {"text": content.decode("utf-8", errors="replace"), "filename": filename}

    if ext == "pdf":
        import pypdf
        import io
        content = await file.read()
        reader = pypdf.PdfReader(io.BytesIO(content))
        pages = [page.extract_text() or "" for page in reader.pages]
        text = "\n\n".join(p.strip() for p in pages if p.strip())
        return {"text": text, "filename": filename}

    raise HTTPException(
        status_code=415,
        detail=f"Unsupported file type: .{ext}. Use .txt, .md, or .pdf",
    )


# Mount static files last (catch-all)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
