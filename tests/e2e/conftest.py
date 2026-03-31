import socket
import subprocess
import time
import pytest
from playwright.sync_api import sync_playwright


def _port_free(port: int) -> bool:
    with socket.socket() as s:
        return s.connect_ex(("localhost", port)) != 0


@pytest.fixture(scope="session")
def dev_server():
    """Start uvicorn for the test session if not already running, then tear it down."""
    already_running = not _port_free(8000)
    if already_running:
        yield "http://localhost:8000"
        return

    proc = subprocess.Popen(
        ["uvicorn", "main:app", "--port", "8000"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    time.sleep(2)  # allow server to bind
    yield "http://localhost:8000"
    proc.terminate()
    proc.wait()


@pytest.fixture(scope="session")
def browser():
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        yield b
        b.close()


@pytest.fixture
def page(browser, dev_server):
    ctx = browser.new_context(base_url=dev_server)
    pg = ctx.new_page()
    yield pg
    ctx.close()
