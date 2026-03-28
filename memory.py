"""Memory file management — read/write/list the memory/ directory tree."""

from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
MEMORY_DIR = DATA_DIR / "memory"
CLAUDE_MD = MEMORY_DIR / "CLAUDE.md"
GLOSSARY_MD = MEMORY_DIR / "glossary.md"

# Templates for initialization
CLAUDE_MD_TEMPLATE = """# Memory

## Me
[Your name], [Your role]. [What you do.]

## People
| Who | Role |
|-----|------|
> Full list: memory/glossary.md, profiles: memory/people/

## Terms
| Term | Meaning |
|------|---------|
> Full glossary: memory/glossary.md

## Projects
| Name | What |
|------|------|
> Details: memory/projects/

## Preferences
-
"""

GLOSSARY_TEMPLATE = """# Glossary

Workplace shorthand, acronyms, and internal language.

## Acronyms
| Term | Meaning | Context |
|------|---------|---------|

## Internal Terms
| Term | Meaning |
|------|---------|

## Nicknames
| Nickname | Person |
|----------|--------|

## Project Codenames
| Codename | Project |
|----------|---------|
"""


def _ensure_structure():
    """Create memory directory structure if it doesn't exist."""
    for d in [MEMORY_DIR, MEMORY_DIR / "people", MEMORY_DIR / "projects", MEMORY_DIR / "context"]:
        d.mkdir(parents=True, exist_ok=True)
    if not CLAUDE_MD.exists():
        CLAUDE_MD.write_text(CLAUDE_MD_TEMPLATE)
    if not GLOSSARY_MD.exists():
        GLOSSARY_MD.write_text(GLOSSARY_TEMPLATE)


def list_files() -> list[dict]:
    """List all memory files as a tree structure."""
    _ensure_structure()
    files = []
    for p in sorted(MEMORY_DIR.rglob("*.md")):
        rel = p.relative_to(MEMORY_DIR)
        files.append({
            "path": str(rel),
            "name": p.name,
            "directory": str(rel.parent) if str(rel.parent) != "." else None,
            "size": p.stat().st_size,
        })
    return files


def read_file(relative_path: str) -> str | None:
    """Read a memory file by its relative path."""
    _ensure_structure()
    target = MEMORY_DIR / relative_path
    if not target.exists() or not target.is_file():
        return None
    # Security: ensure we're still inside MEMORY_DIR
    try:
        target.resolve().relative_to(MEMORY_DIR.resolve())
    except ValueError:
        return None
    return target.read_text()


def write_file(relative_path: str, content: str) -> dict:
    """Create or update a memory file."""
    _ensure_structure()
    target = MEMORY_DIR / relative_path
    # Security check
    try:
        target.resolve().relative_to(MEMORY_DIR.resolve())
    except ValueError:
        raise ValueError("Path traversal not allowed")

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content)
    return {"path": relative_path, "size": len(content)}


def get_hot_cache() -> str:
    """Read CLAUDE.md (the hot cache)."""
    _ensure_structure()
    return CLAUDE_MD.read_text()


def get_glossary() -> str:
    """Read the full glossary."""
    _ensure_structure()
    return GLOSSARY_MD.read_text()


def get_all_content() -> str:
    """Read all memory files concatenated with file path labels.
    Used for semantic search."""
    _ensure_structure()
    parts = []
    for p in sorted(MEMORY_DIR.rglob("*.md")):
        rel = p.relative_to(MEMORY_DIR)
        content = p.read_text().strip()
        if content:
            parts.append(f"[file: {rel}]\n{content}")
    return "\n\n---\n\n".join(parts)
