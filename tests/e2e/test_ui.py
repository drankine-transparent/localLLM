def test_app_loads(page):
    page.goto("/")
    assert page.title() != ""


def test_imports_panel_visible(page):
    page.goto("/")
    assert page.locator(".nav-label", has_text="Imports").first.is_visible()


def test_tasks_panel_navigates(page):
    page.goto("/")
    page.locator(".nav-label", has_text="Tasks").click()
    assert page.locator(".column-title", has_text="Active").is_visible()
    assert page.locator(".column-title", has_text="Waiting On").is_visible()


def test_memory_panel_accordion(page):
    page.goto("/")
    page.locator(".nav-label", has_text="Memory").click()
    assert page.locator("text=Backgrounds").is_visible()


def test_settings_toggle_visible(page):
    page.goto("/")
    assert page.locator("#ptog-lmstudio").is_visible()
