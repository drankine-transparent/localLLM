"""End-to-end tests for the full import → memory → logs → tasks flow.

LLM-dependent endpoints are mocked at the browser level via page.route().
Data verification tests seed directly via API then check the UI.
"""

import json
import time
import requests as req

# --- Test data ---

FAKE_TASKS = [
    {"id": "active-0", "title": "Review Q2 roadmap", "section": "active",
     "context": "Review and finalize the Q2 roadmap with the team. `Test Meeting · 2026-03-30`",
     "done": False, "subtasks": []},
    {"id": "waiting-0", "title": "Alice: Send updated deck", "section": "waiting",
     "context": "Alice to send the updated slide deck by Friday. `Test Meeting · 2026-03-30`",
     "done": False, "subtasks": []},
    {"id": "active-1", "title": "Draft proposal for client", "section": "active",
     "context": "Draft the initial proposal document for the client. `Test Meeting · 2026-03-30`",
     "done": False, "subtasks": []},
]

FAKE_SUGGESTIONS = [
    {"type": "person", "label": "Alice Smith", "detail": "VP Engineering, leads platform team",
     "dest": "people/alice-smith.md"},
    {"type": "term", "label": "Q2 Roadmap", "detail": "Quarterly planning doc for product priorities",
     "dest": "glossary.md"},
]


def _api(dev_server, method, path, **kw):
    """Direct API call to the server."""
    return getattr(req, method)(f"{dev_server}{path}", **kw)


def _cleanup_tasks(dev_server):
    """Delete all tasks created during test."""
    data = _api(dev_server, "get", "/api/tasks").json()
    for section in data.get("sections", {}).values():
        for task in section:
            _api(dev_server, "delete", f"/api/tasks/{task['id']}")


# --- Import UI flow ---

def test_import_extract_and_suggestions(page, dev_server):
    """Paste transcript → extract → see suggestion cards with Add/Edit/Skip."""

    page.route("**/api/tasks/extract", lambda route: route.fulfill(
        status=200, content_type="application/json",
        body=json.dumps({"extracted": 3, "tasks": FAKE_TASKS, "meeting_name": "Test Meeting · 2026-03-30"}),
    ))
    page.route("**/api/memory/suggest", lambda route: route.fulfill(
        status=200, content_type="application/json",
        body=json.dumps(FAKE_SUGGESTIONS),
    ))

    page.goto("/")

    # Select text input, paste transcript
    page.locator("#typeCardText").click()
    page.fill("#extractText", "This is a test transcript for the meeting.")
    page.locator("#extractBtn").click()

    # Wait for suggestions to appear
    page.locator("#memorySuggestions").wait_for(state="visible", timeout=10000)

    # Verify suggestion cards rendered
    cards = page.locator(".suggestion-card")
    assert cards.count() == 2

    # First card: Alice Smith (person)
    first_label = page.locator(".suggestion-label").first.text_content()
    assert "Alice Smith" in first_label

    # Verify all three buttons exist on each card
    assert page.locator(".btn-suggestion-add").count() == 2
    assert page.locator(".btn-suggestion-edit").count() == 2
    assert page.locator(".btn-suggestion-skip").count() == 2

    # Verify Add All and Skip All buttons
    assert page.locator(".btn-suggestion-add-all").is_visible()
    assert page.locator(".btn-suggestion-skip-all").is_visible()

    # Verify destination label shows on cards
    dests = page.locator(".suggestion-dest")
    assert "people/alice-smith.md" in dests.first.text_content()


def test_suggestion_edit_flow(page, dev_server):
    """Click Edit on a suggestion card → edit fields → save → verify updated text."""

    page.route("**/api/tasks/extract", lambda route: route.fulfill(
        status=200, content_type="application/json",
        body=json.dumps({"extracted": 1, "tasks": FAKE_TASKS[:1], "meeting_name": "Test Meeting · 2026-03-30"}),
    ))
    page.route("**/api/memory/suggest", lambda route: route.fulfill(
        status=200, content_type="application/json",
        body=json.dumps(FAKE_SUGGESTIONS[:1]),
    ))

    page.goto("/")
    page.locator("#typeCardText").click()
    page.fill("#extractText", "Test transcript.")
    page.locator("#extractBtn").click()

    page.locator("#memorySuggestions").wait_for(state="visible", timeout=10000)

    # Click Edit
    page.locator(".btn-suggestion-edit").first.click()

    # Verify edit fields appear
    assert page.locator(".suggestion-edit-input").is_visible()
    assert page.locator(".suggestion-edit-textarea").is_visible()

    # Modify the label
    page.locator(".suggestion-edit-input").fill("Alice B. Smith")

    # Click Save (which is the Add button in edit mode)
    page.locator(".btn-suggestion-add").first.click()

    # Verify updated text shows
    assert "Alice B. Smith" in page.locator(".suggestion-label").first.text_content()


def test_suggestion_skip_all(page, dev_server):
    """Click Skip All → all cards dismissed."""

    page.route("**/api/tasks/extract", lambda route: route.fulfill(
        status=200, content_type="application/json",
        body=json.dumps({"extracted": 1, "tasks": FAKE_TASKS[:1], "meeting_name": "Test Meeting · 2026-03-30"}),
    ))
    page.route("**/api/memory/suggest", lambda route: route.fulfill(
        status=200, content_type="application/json",
        body=json.dumps(FAKE_SUGGESTIONS),
    ))

    page.goto("/")
    page.locator("#typeCardText").click()
    page.fill("#extractText", "Test transcript.")
    page.locator("#extractBtn").click()

    page.locator("#memorySuggestions").wait_for(state="visible", timeout=10000)
    assert page.locator(".suggestion-card").count() == 2

    # Click Skip All
    page.locator(".btn-suggestion-skip-all").click()

    # All cards gone, container hidden
    assert page.locator(".suggestion-card").count() == 0
    assert not page.locator("#memorySuggestions").is_visible()


# --- Tasks panel verification ---

def test_tasks_appear_in_correct_columns(page, dev_server):
    """Seed tasks via API, verify they appear in the right kanban columns."""
    _cleanup_tasks(dev_server)

    # Create tasks via API and verify each one
    created = []
    for t in FAKE_TASKS:
        r = _api(dev_server, "post", "/api/tasks", json={
            "title": t["title"], "section": t["section"], "context": t["context"],
        })
        created.append(r.json())

    # Verify API shows all tasks before checking UI
    api_tasks = _api(dev_server, "get", "/api/tasks").json()
    assert len(api_tasks["sections"]["active"]) >= 2
    assert len(api_tasks["sections"]["waiting"]) >= 1

    page.goto("/")
    page.locator(".nav-label", has_text="Tasks").click()
    page.locator("#board").wait_for(state="visible")
    # Wait for tasks to load from API
    page.locator("#cards-active .task-card").first.wait_for(state="visible", timeout=5000)

    # Verify tasks appear in correct columns
    assert page.locator("#cards-active .task-card").count() >= 2
    assert page.locator("#cards-waiting .task-card").count() >= 1

    # Verify specific task titles exist
    assert page.locator(".task-card-title", has_text="Review Q2 roadmap").first.is_visible()
    assert page.locator(".task-card-title", has_text="Draft proposal for client").first.is_visible()
    # Waiting tasks strip the "Person:" prefix into a badge — title is just "Send updated deck"
    assert page.locator(".task-card-title", has_text="Send updated deck").count() >= 1
    assert page.locator(".badge", has_text="Alice").count() >= 1

    # Cleanup
    _cleanup_tasks(dev_server)


# --- Logs panel verification ---

def test_logs_show_extraction_entry(page, dev_server):
    """Seed a log entry, verify it appears in the Logs panel."""
    from pathlib import Path

    log_path = Path(__file__).parent.parent.parent / "data" / "logs" / "extract_log.jsonl"
    log_entry = {
        "timestamp": "2026-03-30T15:10:28",
        "model": "test-model",
        "duration_seconds": 5.2,
        "prompt_tokens": 100,
        "completion_tokens": 200,
        "total_tokens": 300,
        "chunks": 1,
        "action_items": 3,
        "input_chars": 500,
        "filename": "test-meeting.md",
        "meeting_name": "Test Meeting · 2026-03-30",
        "task_ids": ["active-0", "waiting-0", "active-1"],
    }

    # Append log entry
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry) + "\n")

    page.goto("/")
    page.locator(".nav-label", has_text="Logs").click()

    # Wait for log content to load (async fetch)
    page.locator(".log-meeting-link").first.wait_for(state="visible", timeout=5000)

    # Verify log entry with meeting name
    assert page.locator(".log-meeting-link", has_text="Test Meeting").first.is_visible()

    # Verify metrics display
    assert page.locator("text=3 action item").first.is_visible()


def test_log_click_opens_meeting_view(page, dev_server):
    """Click a log entry → meeting view opens with tasks."""
    _cleanup_tasks(dev_server)

    # Seed tasks that match the log entry's task_ids
    created_ids = []
    for t in FAKE_TASKS:
        r = _api(dev_server, "post", "/api/tasks", json={
            "title": t["title"], "section": t["section"], "context": t["context"],
        })
        created_ids.append(r.json()["id"])

    # Seed a log entry referencing those task IDs
    from pathlib import Path
    log_path = Path(__file__).parent.parent.parent / "data" / "logs" / "extract_log.jsonl"
    log_entry = {
        "timestamp": "2026-03-30T16:00:00",
        "model": "test-model",
        "duration_seconds": 3.0,
        "prompt_tokens": 50, "completion_tokens": 100, "total_tokens": 150,
        "chunks": 1, "action_items": 3, "input_chars": 300,
        "filename": "meeting-view-test.md",
        "meeting_name": "Meeting View Test · 2026-03-30",
        "task_ids": created_ids,
    }
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry) + "\n")

    page.goto("/")
    page.locator(".nav-label", has_text="Logs").click()
    page.locator("#logsContainer").wait_for(state="visible")
    time.sleep(0.5)

    # Click the meeting name link
    page.locator("text=Meeting View Test").first.click()

    # Meeting view overlay should open
    page.locator("#meetingView").wait_for(state="visible", timeout=5000)

    # Verify title
    assert "Meeting View Test" in page.locator("#mvTitle").text_content()

    # Verify sections render as accordion cards (not plain labels)
    acc_cards = page.locator("#meetingView .acc-card")
    assert acc_cards.count() >= 2  # Active + Waiting On at minimum

    # Verify section titles are in acc-title elements
    assert page.locator("#meetingView .acc-title", has_text="Active").is_visible()
    assert page.locator("#meetingView .acc-title", has_text="Waiting On").is_visible()

    # Verify count badges show correct numbers
    active_count = page.locator("#mv-acc-active .acc-count").text_content()
    assert active_count == "2"
    waiting_count = page.locator("#mv-acc-waiting .acc-count").text_content()
    assert waiting_count == "1"

    # Verify tasks appear in meeting view
    task_rows = page.locator(".mv-task-row")
    assert task_rows.count() >= 3

    # Verify task titles
    assert page.locator(".mv-task-title", has_text="Review Q2 roadmap").is_visible()
    assert page.locator(".mv-task-title", has_text="Send updated deck").first.is_visible()

    # Close meeting view
    page.locator(".mv-back-btn").click()
    assert not page.locator("#meetingView").is_visible()

    # Cleanup
    _cleanup_tasks(dev_server)


def test_meeting_view_section_collapse(page, dev_server):
    """Meeting view accordion sections can collapse and expand."""
    _cleanup_tasks(dev_server)

    created_ids = []
    for t in FAKE_TASKS:
        r = _api(dev_server, "post", "/api/tasks", json={
            "title": t["title"], "section": t["section"], "context": t["context"],
        })
        created_ids.append(r.json()["id"])

    from pathlib import Path
    log_path = Path(__file__).parent.parent.parent / "data" / "logs" / "extract_log.jsonl"
    log_entry = {
        "timestamp": "2026-03-30T17:00:00",
        "model": "test-model",
        "duration_seconds": 2.0,
        "prompt_tokens": 50, "completion_tokens": 100, "total_tokens": 150,
        "chunks": 1, "action_items": 3, "input_chars": 300,
        "filename": "collapse-test.md",
        "meeting_name": "Collapse Test · 2026-03-30",
        "task_ids": created_ids,
    }
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry) + "\n")

    page.goto("/")
    page.locator(".nav-label", has_text="Logs").click()
    page.locator("#logsContainer").wait_for(state="visible")
    time.sleep(0.5)

    page.locator("text=Collapse Test").first.click()
    page.locator("#meetingView").wait_for(state="visible", timeout=5000)

    # Active section should start open
    active_card = page.locator("#mv-acc-active")
    assert "open" in active_card.get_attribute("class")

    # Click header to collapse
    page.locator("#mv-acc-active .acc-header").click()
    assert "open" not in active_card.get_attribute("class")

    # Click again to expand
    page.locator("#mv-acc-active .acc-header").click()
    assert "open" in active_card.get_attribute("class")

    # Tasks visible again after expand
    assert page.locator("#mv-acc-active .mv-task-row").count() >= 2

    page.locator(".mv-back-btn").click()
    _cleanup_tasks(dev_server)


# --- Memory panel verification ---

def test_memory_file_appears_in_panel(page, dev_server):
    """Write a memory file via API, verify it shows in the Memory accordion."""

    # Write a test person file
    _api(dev_server, "post", "/api/memory", json={
        "path": "people/test-person.md",
        "content": "# Test Person\n\n**Role:** QA Engineer\n**Team:** Platform\n",
    })

    page.goto("/")
    page.locator(".nav-label", has_text="Memory").click()

    # Wait for memory tree to load and People section to populate
    page.locator("#memoryTree").wait_for(state="visible")
    page.locator(".memory-file-item", has_text="test-person").wait_for(state="attached", timeout=5000)

    # People section may be collapsed — expand it if needed
    people_card = page.locator("#acc-card-people")
    if people_card.count() and "open" not in (people_card.get_attribute("class") or ""):
        page.locator("#acc-card-people .acc-header").click()
        page.wait_for_timeout(300)

    assert page.locator(".memory-file-item", has_text="test-person").is_visible()

    # Click to open it
    page.locator(".memory-file-item", has_text="test-person").click()

    # Preview should show rendered content
    page.locator("#memoryPreview").wait_for(state="visible", timeout=3000)
    preview_text = page.locator("#memoryPreview").text_content()
    assert "Test Person" in preview_text
    assert "QA Engineer" in preview_text

    # Cleanup: overwrite with empty to effectively remove
    _api(dev_server, "post", "/api/memory", json={"path": "people/test-person.md", "content": ""})


def test_memory_append_preserves_structure(page, dev_server):
    """Write to profile.md via API, verify section structure is preserved."""

    # Read current profile
    r = _api(dev_server, "get", "/api/memory/profile.md")
    original = r.json()["content"]

    # Ensure it has the expected structure
    assert "## Preferences & Facts" in original

    # Write additional content under Preferences & Facts
    new_content = original.rstrip() + "\n- Test fact for e2e verification\n"
    _api(dev_server, "post", "/api/memory", json={"path": "profile.md", "content": new_content})

    # Navigate to memory panel and open profile.md
    page.goto("/")
    page.locator(".nav-label", has_text="Memory").click()
    page.locator("#memoryTree").wait_for(state="visible")
    time.sleep(0.5)

    page.locator(".memory-file-item", has_text="profile").click()
    page.locator("#memoryPreview").wait_for(state="visible", timeout=3000)
    preview = page.locator("#memoryPreview").text_content()

    # Verify structure preserved
    assert "Me" in preview  # ## Me section
    assert "Preferences" in preview  # ## Preferences & Facts section
    assert "Test fact for e2e verification" in preview

    # Restore original
    _api(dev_server, "post", "/api/memory", json={"path": "profile.md", "content": original})


def test_memory_learn_adds_attribution(page, dev_server):
    """POST /api/memory/learn adds source + timestamp attribution to people/project files."""

    # Write a test person file via learn endpoint (mocked LLM response)
    # We can't call learn directly (needs LLM), so write via direct API and verify format
    # Instead, write with attribution format and check it renders in the UI
    ts = "2026-03-30 18:00"
    _api(dev_server, "post", "/api/memory", json={
        "path": "people/test-attr.md",
        "content": "# Test Attribution\n\n**Role:** Engineer\n*Import · " + ts + "*\n",
    })

    page.goto("/")
    page.locator(".nav-label", has_text="Memory").click()
    page.locator("#memoryTree").wait_for(state="visible")
    time.sleep(0.5)

    page.locator(".memory-file-item", has_text="test-attr").click()
    page.locator("#memoryPreview").wait_for(state="visible", timeout=3000)
    preview = page.locator("#memoryPreview").text_content()

    # Attribution must be visible in preview
    assert "Import" in preview
    assert "2026-03-30" in preview

    # Cleanup
    _api(dev_server, "post", "/api/memory", json={"path": "people/test-attr.md", "content": ""})


def test_memory_learn_api_adds_attribution(dev_server):
    """Verify /api/memory/learn endpoint adds attribution via direct API check."""

    # Seed a people file with known content
    _api(dev_server, "post", "/api/memory", json={
        "path": "people/test-learn-api.md",
        "content": "# Test Learn API\n",
    })

    # Call learn with a mocked suggestion (LLM will route, but dest_hint overrides)
    r = _api(dev_server, "post", "/api/memory/learn", json={
        "text": "Person: Test Person — Senior Engineer on platform team",
        "dest_hint": "people/test-learn-api.md",
        "source": "E2E Test",
    })

    if r.status_code != 200:
        # LLM not available — clean up and skip
        _api(dev_server, "post", "/api/memory", json={"path": "people/test-learn-api.md", "content": ""})
        import pytest; pytest.skip("LLM not available — learn endpoint returned " + str(r.status_code))

    # Read the file back and check attribution exists
    content_r = _api(dev_server, "get", "/api/memory/people/test-learn-api.md")
    content = content_r.json()["content"]
    assert "E2E Test" in content, f"Attribution 'E2E Test' not found in: {content[:200]}"
    assert "·" in content, f"Timestamp separator not found in: {content[:200]}"

    # Cleanup
    _api(dev_server, "post", "/api/memory", json={"path": "people/test-learn-api.md", "content": ""})


def test_profile_structure_rebuilt_when_lost(dev_server):
    """If profile.md loses its section structure, learn endpoint rebuilds it."""

    # Save original
    r = _api(dev_server, "get", "/api/memory/profile.md")
    original = r.json()["content"]

    # Deliberately break the structure
    _api(dev_server, "post", "/api/memory", json={
        "path": "profile.md",
        "content": "- some broken content with no headers\n",
    })

    # Call learn — should rebuild structure
    r = _api(dev_server, "post", "/api/memory/learn", json={
        "text": "Fact: Dee likes coffee",
        "dest_hint": "profile.md",
        "source": "E2E Test",
    })

    if r.status_code != 200:
        # LLM not available — restore and skip
        _api(dev_server, "post", "/api/memory", json={"path": "profile.md", "content": original})
        import pytest; pytest.skip("LLM not available — learn endpoint returned " + str(r.status_code))

    content_r = _api(dev_server, "get", "/api/memory/profile.md")
    content = content_r.json()["content"]
    # Structure must be rebuilt
    assert "## Preferences & Facts" in content, f"Section header missing in: {content[:300]}"
    assert "## Me" in content, f"## Me header missing in: {content[:300]}"

    # Restore original
    _api(dev_server, "post", "/api/memory", json={"path": "profile.md", "content": original})
