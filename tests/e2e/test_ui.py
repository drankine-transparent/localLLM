def test_app_loads(page):
    page.goto("/")
    assert page.title() != ""


def test_imports_panel_visible(page):
    page.goto("/")
    assert page.locator(".nav-label", has_text="Imports").first.is_visible()


def test_tasks_panel_navigates(page):
    page.goto("/")
    page.locator(".nav-label", has_text="Tasks").click()
    page.locator(".column-title", has_text="Active").wait_for(state="visible", timeout=5000)
    assert page.locator(".column-title", has_text="Waiting On").is_visible()


def test_memory_panel_accordion(page):
    page.goto("/")
    page.locator(".nav-label", has_text="Memory").click()
    page.locator("text=Backgrounds").wait_for(state="visible", timeout=5000)


def test_settings_toggle_visible(page):
    page.goto("/")
    assert page.locator("#ptog-lmstudio").is_visible()
