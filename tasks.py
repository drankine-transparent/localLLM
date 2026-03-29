"""TASKS.md parser and writer."""

import re
from pathlib import Path
from datetime import date

TASKS_PATH = Path(__file__).parent / "data" / "TASKS.md"

TEMPLATE = """# Tasks

## Active

## Waiting On

## Someday

## Done
"""

SECTION_MAP = {
    "active": "Active",
    "waiting": "Waiting On",
    "someday": "Someday",
    "done": "Done",
}

SECTION_KEYS = {v.lower(): k for k, v in SECTION_MAP.items()}
# "active" -> "active", "waiting on" -> "waiting", etc.
SECTION_KEYS["active"] = "active"
SECTION_KEYS["waiting on"] = "waiting"
SECTION_KEYS["someday"] = "someday"
SECTION_KEYS["done"] = "done"


def _ensure_file():
    """Create TASKS.md with template if it doesn't exist."""
    if not TASKS_PATH.exists():
        TASKS_PATH.parent.mkdir(parents=True, exist_ok=True)
        TASKS_PATH.write_text(TEMPLATE)


def parse() -> dict:
    """Parse TASKS.md into structured data.

    Returns:
        {
            "sections": {
                "active": [{"id": "active-0", "title": "...", "context": "...", "done": False, "raw": "..."}],
                "waiting": [...],
                "someday": [...],
                "done": [...]
            }
        }
    """
    _ensure_file()
    content = TASKS_PATH.read_text()
    sections = {"active": [], "waiting": [], "someday": [], "done": []}
    current_section = None

    for line in content.split("\n"):
        # Detect section headers
        header_match = re.match(r"^## (.+)$", line.strip())
        if header_match:
            header = header_match.group(1).strip().lower()
            current_section = SECTION_KEYS.get(header)
            continue

        if current_section is None:
            continue

        # Parse indented subtask lines (must check before stripping)
        subtask_match = re.match(r"^  - \[([ xX])\] (.+)$", line)
        if subtask_match and sections[current_section]:
            checked = subtask_match.group(1).lower() == "x"
            text = subtask_match.group(2).strip()
            sections[current_section][-1].setdefault("subtasks", []).append(
                {"text": text, "checked": checked}
            )
            continue

        # Parse task lines
        task_match = re.match(r"^- \[([ xX])\] (.+)$", line.strip())
        if task_match:
            done = task_match.group(1).lower() == "x"
            text = task_match.group(2).strip()

            # Extract title (bold text) and context
            bold_match = re.match(r"\*\*(.+?)\*\*\s*[-–—]?\s*(.*)", text)
            if bold_match:
                title = bold_match.group(1)
                context = bold_match.group(2).strip() or None
            else:
                # Handle strikethrough done items
                strike_match = re.match(r"~~(.+?)~~\s*(.*)", text)
                if strike_match:
                    title = strike_match.group(1)
                    context = strike_match.group(2).strip() or None
                else:
                    title = text
                    context = None

            idx = len(sections[current_section])
            sections[current_section].append({
                "id": f"{current_section}-{idx}",
                "title": title,
                "context": context,
                "done": done,
                "subtasks": [],
                "raw": line.strip(),
            })

    return {"sections": sections}


def _serialize(data: dict) -> str:
    """Convert structured data back to TASKS.md format."""
    lines = ["# Tasks", ""]

    for key, header in SECTION_MAP.items():
        lines.append(f"## {header}")
        lines.append("")
        for task in data["sections"].get(key, []):
            if task["done"]:
                lines.append(f"- [x] ~~{task['title']}~~ {task.get('context') or ''}")
            else:
                ctx = f" - {task['context']}" if task.get("context") else ""
                lines.append(f"- [ ] **{task['title']}**{ctx}")
            for st in task.get("subtasks", []):
                check = "x" if st["checked"] else " "
                lines.append(f"  - [{check}] {st['text']}")
        lines.append("")

    return "\n".join(lines)


def add_task(title: str, section: str = "active", context: str | None = None) -> dict:
    """Add a new task to TASKS.md."""
    data = parse()
    section = section.lower()
    if section not in data["sections"]:
        section = "active"

    idx = len(data["sections"][section])
    task = {
        "id": f"{section}-{idx}",
        "title": title,
        "context": context,
        "done": False,
    }
    data["sections"][section].append(task)
    TASKS_PATH.write_text(_serialize(data))
    return task


def toggle_task(task_id: str) -> dict | None:
    """Toggle a task's done state. Returns the updated task or None."""
    data = parse()
    section_key, idx_str = task_id.rsplit("-", 1)
    idx = int(idx_str)

    tasks = data["sections"].get(section_key, [])
    if idx >= len(tasks):
        return None

    task = tasks[idx]
    task["done"] = not task["done"]

    # If completing, add date and move to done
    if task["done"]:
        task["context"] = f"({date.today().isoformat()})"
        tasks.pop(idx)
        data["sections"]["done"].insert(0, task)
    else:
        # Uncompleting — move back to active
        task["context"] = None
        tasks.pop(idx)
        data["sections"]["active"].append(task)

    TASKS_PATH.write_text(_serialize(data))
    return task


def move_task(task_id: str, target_section: str) -> dict | None:
    """Move a task to a different section."""
    data = parse()
    section_key, idx_str = task_id.rsplit("-", 1)
    idx = int(idx_str)

    tasks = data["sections"].get(section_key, [])
    if idx >= len(tasks):
        return None

    task = tasks.pop(idx)
    target = target_section.lower()
    if target not in data["sections"]:
        target = "active"

    data["sections"][target].append(task)
    TASKS_PATH.write_text(_serialize(data))
    return task


def delete_task(task_id: str) -> bool:
    """Delete a task. Returns True if found and deleted."""
    data = parse()
    section_key, idx_str = task_id.rsplit("-", 1)
    idx = int(idx_str)

    tasks = data["sections"].get(section_key, [])
    if idx >= len(tasks):
        return False

    tasks.pop(idx)
    TASKS_PATH.write_text(_serialize(data))
    return True


def _find_task(data: dict, task_id: str):
    """Return (task_dict, section_key) or (None, None)."""
    section_key, idx_str = task_id.rsplit("-", 1)
    idx = int(idx_str)
    tasks = data["sections"].get(section_key, [])
    if idx >= len(tasks):
        return None, None
    return tasks[idx], section_key


def add_subtask(task_id: str, text: str) -> dict | None:
    """Append a subtask to a task. Returns updated task or None."""
    data = parse()
    task, _ = _find_task(data, task_id)
    if task is None:
        return None
    task.setdefault("subtasks", []).append({"text": text, "checked": False})
    TASKS_PATH.write_text(_serialize(data))
    return task


def toggle_subtask(task_id: str, sub_idx: int) -> dict | None:
    """Toggle a subtask's checked state. Returns updated task or None."""
    data = parse()
    task, _ = _find_task(data, task_id)
    if task is None:
        return None
    subtasks = task.get("subtasks", [])
    if sub_idx >= len(subtasks):
        return None
    subtasks[sub_idx]["checked"] = not subtasks[sub_idx]["checked"]
    TASKS_PATH.write_text(_serialize(data))
    return task


def delete_subtask(task_id: str, sub_idx: int) -> dict | None:
    """Remove a subtask. Returns updated task or None."""
    data = parse()
    task, _ = _find_task(data, task_id)
    if task is None:
        return None
    subtasks = task.get("subtasks", [])
    if sub_idx >= len(subtasks):
        return None
    subtasks.pop(sub_idx)
    TASKS_PATH.write_text(_serialize(data))
    return task
