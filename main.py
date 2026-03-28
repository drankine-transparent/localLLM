"""FastAPI app — Local LLM Productivity System."""

from fastapi import FastAPI, HTTPException
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
    try:
        # Split long text into chunks and extract from each
        chunk_size = prompts.MAX_INPUT_CHARS
        text = body.text
        chunks = []
        for i in range(0, len(text), chunk_size):
            chunks.append(text[i:i + chunk_size])

        print(f"[EXTRACT] Processing {len(chunks)} chunk(s) from {len(text)} chars")

        all_tasks = []
        for idx, chunk in enumerate(chunks):
            prompt = prompts.TASK_EXTRACTION.format(text=chunk)
            raw = await llm.chat(
            "You are a precise task extractor. Output only valid JSON arrays. No markdown, no explanation.",
            prompt
        )
            print(f"[EXTRACT] Chunk {idx+1} raw: {raw[:300]}")
            try:
                result = llm.parse_json(raw)
                if isinstance(result, dict):
                    result = result.get("tasks", [result])
                if isinstance(result, list):
                    all_tasks.extend(result)
            except (ValueError, Exception) as e:
                print(f"[EXTRACT] Chunk {idx+1} parse error: {e}")
                continue

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

        print(f"[EXTRACT] Total: {len(added)} unique tasks from {len(all_tasks)} raw")
        return {"extracted": len(added), "tasks": added}
    except Exception as e:
        print(f"[EXTRACT] Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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


# Mount static files last (catch-all)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
