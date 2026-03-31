"""FastAPI app — Local LLM Productivity System."""

import json as _json
import re as _re
import time
from datetime import datetime, timezone
from dotenv import load_dotenv
load_dotenv()
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
_cancel_requested: bool = False


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


class SubtaskCreate(BaseModel):
    text: str


class TextInput(BaseModel):
    text: str
    filename: str | None = None


class MemoryWrite(BaseModel):
    path: str
    content: str




class ProviderSwitch(BaseModel):
    provider: str  # "lmstudio" | "openai"


class ChatMessage(BaseModel):
    message: str


class LearnInput(BaseModel):
    text: str
    dest_hint: str | None = None
    source: str | None = None


class SuggestInput(BaseModel):
    text: str


# --- Routes ---

@app.get("/")
async def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
async def health():
    return await llm.health_check()


# --- Settings ---

@app.get("/api/settings")
async def get_settings():
    return {"provider": llm.get_provider(), "openai_model": llm.OPENAI_MODEL}


@app.post("/api/settings")
async def update_settings(body: ProviderSwitch):
    try:
        llm.set_provider(body.provider)
        return {"provider": llm.get_provider()}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# --- Tasks ---

@app.get("/api/tasks")
async def get_tasks():
    return tasks.parse()


@app.delete("/api/tasks")
async def clear_tasks():
    # Also clear extraction logs — they reference task IDs that no longer exist
    if LOG_PATH.exists():
        LOG_PATH.write_text("")
    return tasks.clear_all()


@app.post("/api/tasks")
async def create_task(body: TaskCreate):
    task = tasks.add_task(body.title, body.section, body.context)
    return task


@app.post("/api/tasks/extract/cancel")
async def cancel_extract():
    global _cancel_requested
    _cancel_requested = True
    return {"cancelled": True}


@app.post("/api/tasks/extract")
async def extract_tasks(body: TextInput):
    global _extract_status, _cancel_requested
    _cancel_requested = False
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
            if _cancel_requested:
                print(f"[EXTRACT] Cancelled after {idx} chunk(s)")
                break
            chunk_start = time.monotonic()
            prompt = prompts.build_extraction_prompt(chunk, llm.get_provider(), body.filename)
            _extract_status["current_chunk"] = {"index": idx + 1, "chars": 0, "tokens": 0}

            def on_progress(chars: int, tokens: int, _idx: int = idx) -> None:
                _extract_status["current_chunk"] = {"index": _idx + 1, "chars": chars, "tokens": tokens}

            try:
                cr = await llm.chat_stream_with_usage(
                    "You are a precise task extractor. Output only valid JSON arrays. No markdown, no explanation.",
                    prompt,
                    on_progress=on_progress,
                )
            except Exception as llm_err:
                msg = str(llm_err)
                if "tokens to keep" in msg or "context length" in msg.lower():
                    raise ValueError(
                        "Model context window is too small for this input. "
                        "In LM Studio \u2192 Model Settings, increase \u2018Context Length\u2019 "
                        "to at least 8192 tokens, then reload the model."
                    )
                raise
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

        # Extract meeting name from first task context tag: `Meeting Name · YYYY-MM-DD`
        meeting_name = None
        for item in all_tasks:
            ctx = item.get("context", "") if isinstance(item, dict) else ""
            m = _re.search(r"`([^`]+·[^`]+)`", ctx)
            if m:
                meeting_name = m.group(1).strip()
                break

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
            "filename": body.filename or None,
            "meeting_name": meeting_name,
            "task_ids": [t["id"] for t in added],
        })

        _extract_status["phase"] = "cancelled" if _cancel_requested else "done"
        _extract_status["duration_seconds"] = duration
        _extract_status["extracted"] = len(added)

        print(f"[EXTRACT] Total: {len(added)} unique tasks from {len(all_tasks)} raw")
        return {"extracted": len(added), "tasks": added, "meeting_name": meeting_name}
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


@app.post("/api/tasks/{task_id}/subtasks")
async def add_subtask(task_id: str, body: SubtaskCreate):
    task = tasks.add_subtask(task_id, body.text)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@app.put("/api/tasks/{task_id}/subtasks/{sub_idx}/toggle")
async def toggle_subtask(task_id: str, sub_idx: int):
    task = tasks.toggle_subtask(task_id, sub_idx)
    if task is None:
        raise HTTPException(status_code=404, detail="Not found")
    return task


@app.delete("/api/tasks/{task_id}/subtasks/{sub_idx}")
async def delete_subtask(task_id: str, sub_idx: int):
    task = tasks.delete_subtask(task_id, sub_idx)
    if task is None:
        raise HTTPException(status_code=404, detail="Not found")
    return task


# --- Memory ---

@app.delete("/api/memory")
async def reset_memory():
    """Reset all memory files to empty templates, delete people/ and projects/ files."""
    memory.reset_all()
    return {"reset": True}


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



def _insert_under_section(content: str, section_header: str, snippet: str) -> str:
    """Insert snippet under a ## section header, before the next ## or at EOF."""
    idx = content.index(section_header) + len(section_header)
    rest = content[idx:]
    next_section = rest.find("\n## ")
    if next_section >= 0:
        insert_at = idx + next_section
        return content[:insert_at].rstrip() + "\n" + snippet + "\n" + content[insert_at:]
    return content.rstrip() + "\n" + snippet + "\n"


def _insert_glossary_row_in_section(content: str, row: str, section: str = "## Internal Terms") -> str:
    """Insert a table row into a specific glossary section.

    Finds the section header, then its separator (|---|), and inserts
    after all data rows that follow the separator.
    """
    lines = content.split("\n")
    # Find the section header
    section_idx = -1
    for i, line in enumerate(lines):
        if line.strip() == section:
            section_idx = i
            break
    if section_idx < 0:
        # Section not found — fall back to last table
        return _insert_glossary_row(content, row)
    # Find the separator after this section header
    sep_idx = -1
    for i in range(section_idx + 1, len(lines)):
        if lines[i].strip().startswith("|--"):
            sep_idx = i
            break
        if lines[i].strip().startswith("## ") and i > section_idx:
            break  # Hit next section without finding separator
    if sep_idx < 0:
        return _insert_glossary_row(content, row)
    # Insert after all data rows following the separator
    insert_at = sep_idx + 1
    while insert_at < len(lines) and lines[insert_at].strip().startswith("|"):
        insert_at += 1
    lines.insert(insert_at, row)
    return "\n".join(lines)


def _insert_glossary_row(content: str, row: str) -> str:
    """Insert a table row into the last table in the glossary.

    Finds the last separator (|---|) and inserts after all data rows
    that follow it — never between header and separator.
    """
    lines = content.split("\n")
    separators = [i for i, l in enumerate(lines) if l.strip().startswith("|--")]
    if not separators:
        return content.rstrip() + "\n" + row + "\n"
    last_sep = separators[-1]
    insert_at = last_sep + 1
    while insert_at < len(lines) and lines[insert_at].strip().startswith("|"):
        insert_at += 1
    lines.insert(insert_at, row)
    return "\n".join(lines)


@app.post("/api/memory/learn")
async def learn_memory(body: LearnInput):
    try:
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
        source_label = body.source or "Manual"
        attribution = f"*{source_label} · {ts}*"

        # Fast path: glossary entries from suggestion cards — build row server-side, skip LLM
        if body.dest_hint == "glossary.md":
            existing = memory.read_file("glossary.md") or memory.GLOSSARY_TEMPLATE
            # Parse label and detail from "Term: label — detail" format
            text = body.text
            label, detail = "", text
            if " — " in text:
                parts = text.split(" — ", 1)
                label = _re.sub(r"^(Term|Person|Project|Fact):\s*", "", parts[0]).strip()
                detail = parts[1].strip()
            elif ": " in text:
                label = text.split(": ", 1)[-1].strip()
            row = f"| {label} | {detail} · {ts} |"
            print(f"[LEARN] glossary fast path: {row}")
            full_content = _insert_glossary_row_in_section(existing, row, "## Internal Terms")
            saved = memory.write_file("glossary.md", full_content)
            return {"saved": True, "file": "glossary.md", "size": saved["size"]}

        # Standard path: call LLM for routing and content
        claude_md = prompts.truncate(memory.get_hot_cache(), 2000)
        glossary_md = prompts.truncate(memory.get_glossary(), 2000)
        existing_files = "\n".join(f"- {f['path']}" for f in memory.list_files()) or "none"
        learn_text = body.text
        if body.dest_hint:
            learn_text += f"\nPreferred destination: {body.dest_hint}"
        prompt = prompts.MEMORY_LEARN.format(
            text=prompts.truncate(learn_text, 1000),
            claude_md=claude_md,
            glossary_md=glossary_md,
            existing_files=existing_files,
        )
        result = await llm.chat(
            "You manage a memory file system. Return only valid JSON.", prompt
        )
        parsed = llm.parse_json(result)
        if not isinstance(parsed, dict) or "file" not in parsed or "append" not in parsed:
            raise ValueError(f"Unexpected LLM response: {result[:200]}")
        if body.dest_hint:
            parsed["file"] = body.dest_hint
        target_file = parsed["file"]
        existing = memory.read_file(target_file) or ""
        snippet = parsed["append"].strip()
        # Strip any attribution the LLM might have echoed (server adds its own)
        for line in snippet.split("\n"):
            if line.strip().startswith("*") and "·" in line and line.strip().endswith("*"):
                snippet = snippet.replace(line, "").strip()

        # All non-glossary files: attribution on its own line
        new_snippet = snippet + f"\n{attribution}"

        print(f"[LEARN] file={target_file} snippet_len={len(snippet)} attribution={attribution}")

        # Profile.md: always insert under ## Preferences & Facts
        if target_file == "profile.md":
            if "## Preferences & Facts" not in existing:
                existing = memory.CLAUDE_MD_TEMPLATE.strip()
                print(f"[LEARN] profile.md structure lost — rebuilt from template")
            full_content = _insert_under_section(existing, "## Preferences & Facts", new_snippet)
        elif target_file == "glossary.md" and "|" in new_snippet:
            # Glossary table row: find the last table row in the right section and insert after it
            full_content = _insert_glossary_row(existing, new_snippet)
        else:
            full_content = (existing.rstrip() + "\n\n" + new_snippet + "\n") if existing else (new_snippet + "\n")
        saved = memory.write_file(target_file, full_content)
        return {"saved": True, "file": target_file, "size": saved["size"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/memory/suggest")
async def suggest_memory(body: SuggestInput):
    """Scan transcript for new people/terms/facts not already in memory."""
    try:
        claude_md = prompts.truncate(memory.get_hot_cache(), 1500)
        existing_files = "\n".join(f"- {f['path']}" for f in memory.list_files()) or "none"
        prompt = prompts.MEMORY_SUGGEST.format(
            claude_md=claude_md,
            existing_files=existing_files,
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
