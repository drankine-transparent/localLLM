# Feature List

Detailed inventory of everything in the app. Updated whenever features are added or removed.

---

## Task Extraction

- **Transcript import** — Paste text or upload .txt/.md/.pdf files via drag-and-drop
- **LLM extraction** — Extracts action items from meeting transcripts with owner detection
- **Owner routing** — Darren/Dee tasks go to Active; others go to Waiting On with `Person:` prefix badge
- **Meeting tagging** — Every task context ends with `` `Meeting Name · YYYY-MM-DD` ``
- **Chunked processing** — Long transcripts split into ~8K char chunks, processed sequentially
- **Deduplication** — Tasks deduplicated by title (case-insensitive) across chunks
- **Cancel extraction** — Stop button halts both extraction and memory suggestion scan mid-run
- **Extraction logs** — Every import logged with model, duration, tokens, chunk count, meeting name, task IDs

## Task Management

- **Kanban board** — Active, Waiting On, Someday, Done columns displayed simultaneously
- **Drag-and-drop** — Move tasks between columns by dragging
- **Create tasks** — Inline task creation per column
- **Subtasks** — Add, toggle, delete subtasks on any task card
- **Complete/delete** — Checkbox to mark done, delete button per card
- **Assignee badges** — `Person:` prefix stripped from title and shown as a coloured badge
- **Board summary strip** — Stat cards above the board showing counts per section
- **Clear Board** — Deletes all tasks and extraction logs to start fresh (confirmation required)

## Memory System

- **File-based knowledge base** — Markdown files in `data/memory/` with subdirectories
- **Profile hot cache** — `profile.md` loaded into every LLM prompt as personal context
- **Glossary** — Structured tables for acronyms, internal terms, nicknames, project codenames
- **People directory** — Individual markdown files per person in `people/`
- **Projects directory** — Individual markdown files per project in `projects/`
- **Append-only writes** — Server controls file writes; LLM only generates the snippet to append
- **Section-aware append** — Profile facts insert under `## Preferences & Facts`; glossary rows insert inside the correct table after the separator
- **Profile structure protection** — If profile.md loses section headers, server rebuilds from template before inserting
- **Glossary column matching** — LLM output trimmed to match table column count; date embedded in last cell
- **Source attribution** — Server stamps every memory entry with source and UTC timestamp
- **Duplicate prevention** — Existing file list passed to LLM in suggest and learn prompts to avoid re-creating files
- **Reset Memory** — Resets profile.md and glossary.md to empty templates, deletes all people/ and projects/ files (confirmation required)

## Memory Suggestions

- **Post-import suggestions** — After extraction, LLM scans transcript for new people/terms/projects/facts
- **Suggestion cards** — Each card shows type badge, label, detail, and destination file path
- **Add / Edit / Skip** — Per-card actions; Edit swaps to inline editable fields with Save/Cancel
- **Add All / Skip All** — Bulk action buttons in the suggestion header
- **Destination routing** — `dest_hint` from suggestion cards enforced server-side (overrides LLM routing)

## Logs

- **Extraction log panel** — Shows all past imports, newest first
- **Log entry details** — Meeting name, file name, date/time, model, action item count, duration, tokens, chunks, input size
- **Meeting task view** — Click a log entry's meeting name to open a full-screen overlay with tasks grouped in collapsible accordion cards (Active, Waiting On, Someday, Done) with icons and count badges
- **Back navigation** — Back button closes meeting view and returns to log list

## Chat

- **Chat panel** — Ask questions with `profile.md` loaded as context
- **Save to Memory** — One-click save any chat response to memory with `Chat` source attribution

## Provider & Settings

- **Dual LLM provider** — LM Studio (local, default) or OpenAI/Claude, runtime-switchable
- **Provider toggle** — Persistent toggle buttons in sidebar footer
- **Settings API** — `GET/POST /api/settings` for provider switching

## UI/UX

- **Single-file frontend** — All HTML, CSS, JS in `static/index.html`
- **TP design language** — Teal palette via CSS variables, Source Sans 3 font
- **Left sidebar nav** — Imports (default), Tasks, Memory, Chat, Logs panels
- **Activity bar** — Live progress during extraction with chunk-by-chunk stats, expandable log
- **File upload** — Drag-and-drop or click, supports .txt/.md/.pdf
- **Markdown preview** — Memory files render as formatted HTML by default, switch to Edit mode to modify
- **Memory accordion** — Collapsible sections for Backgrounds, People, Projects with file count badges and search filter
- **Toast notifications** — Transient status messages for save/error actions

---

## Quality & Testing

### Unit tests (7) — `tests/test_streaming.py`
| Test | What it covers |
|------|---------------|
| `test_stream_accumulates_content` | `chat_stream_with_usage()` accumulates streamed content |
| `test_stream_calls_on_progress` | Progress callback fires with char/token counts |
| `test_stream_returns_chat_result` | Returns ChatResult with content, model, token usage |
| `test_stream_no_progress_callback` | Works without a progress callback |
| `test_stream_empty_chunks_ignored` | Empty stream chunks don't corrupt output |
| `test_status_includes_current_chunk_field` | Extract status includes current_chunk when running |
| `test_status_current_chunk_none_when_idle` | Extract status current_chunk is null when idle |

### E2E Playwright tests (19) — `tests/e2e/`

**Smoke tests** (`test_ui.py`):
| Test | What it covers |
|------|---------------|
| `test_app_loads` | Page loads with a title |
| `test_imports_panel_visible` | Imports nav item visible on load |
| `test_tasks_panel_navigates` | Click Tasks shows Active and Waiting On columns |
| `test_memory_panel_accordion` | Click Memory shows Backgrounds accordion |
| `test_settings_toggle_visible` | Provider toggle button visible |

**Import flow tests** (`test_import_flow.py`):
| Test | What it covers |
|------|---------------|
| `test_import_extract_and_suggestions` | Paste transcript, extract, see suggestion cards with Add/Edit/Skip/Add All/Skip All |
| `test_suggestion_edit_flow` | Click Edit, modify fields, Save updates card text |
| `test_suggestion_skip_all` | Skip All dismisses all cards and hides container |
| `test_tasks_appear_in_correct_columns` | Seeded tasks appear in correct kanban columns with badges |
| `test_logs_show_extraction_entry` | Seeded log entry appears in Logs panel with meeting name and metrics |
| `test_log_click_opens_meeting_view` | Click log entry opens meeting view with accordion cards, count badges, task titles |
| `test_meeting_view_section_collapse` | Collapse/expand accordion sections in meeting view |
| `test_memory_file_appears_in_panel` | Written memory file appears in accordion, preview renders content |
| `test_memory_append_preserves_structure` | Append to profile.md preserves section headers |
| `test_memory_learn_adds_attribution` | Attribution (source + date) visible in memory file preview |
| `test_memory_learn_api_adds_attribution` | Learn endpoint adds attribution via API (LLM-dependent, skips if unavailable) |
| `test_profile_structure_rebuilt_when_lost` | Learn endpoint rebuilds profile.md template when structure is lost (LLM-dependent) |
| `test_clear_board` | Clear Board button deletes all tasks and logs |
| `test_reset_memory` | Reset Memory button clears people/projects, resets profile + glossary templates |

### Running tests
```bash
pytest tests/ -v              # all 26 tests
pytest tests/test_streaming.py -v   # unit tests only (no server needed)
pytest tests/e2e/ -v          # e2e tests only (needs server on port 8000)
```

---

## Removed Features

- **Decode panel** — Removed (was: paste shorthand, LLM expands using glossary)
- **Search panel** — Removed (was: semantic search across memory files)
- **Exits section** — Hidden from UI (files still exist on disk, directory no longer created on startup)
- **Context section** — Hidden from UI (empty, unused, no longer created on startup)
- **Pre-push hook** — Removed (`/loop` is a Claude Code command, not a shell command)
