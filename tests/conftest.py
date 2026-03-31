"""Root test conftest — ensures unit tests run before e2e to avoid event loop conflicts."""


def pytest_collection_modifyitems(items):
    """Sort test items so unit tests (non-e2e) run before Playwright e2e tests."""
    items.sort(key=lambda item: 1 if "/e2e/" in str(item.fspath) else 0)
