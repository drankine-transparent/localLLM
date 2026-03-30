"""Tests for chat_stream_with_usage() and related extract-status behaviour."""

import asyncio
import sys
import os
from unittest.mock import MagicMock, patch

import pytest

# Make project root importable
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import llm
from llm import ChatResult


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_chunk(content: str | None = None, usage=None):
    """Build a minimal fake OpenAI stream chunk."""
    chunk = MagicMock()
    if content is not None:
        delta = MagicMock()
        delta.content = content
        choice = MagicMock()
        choice.delta = delta
        chunk.choices = [choice]
    else:
        chunk.choices = []
    chunk.usage = usage
    return chunk


def _fake_model_list(model_id: str = "test-model"):
    models = MagicMock()
    m = MagicMock()
    m.id = model_id
    models.data = [m]
    return models


def _mock_client(chunks, model_id="test-model"):
    """Return a mock OpenAI client pre-configured for streaming."""
    client = MagicMock()
    client.models.list.return_value = _fake_model_list(model_id)
    client.chat.completions.create.return_value = iter(chunks)
    return client


def _run(coro):
    return asyncio.run(coro)


# ── Tests ──────────────────────────────────────────────────────────────────────

class TestChatStreamWithUsage:

    def test_stream_accumulates_content(self):
        """Tokens from all stream chunks are joined into a single content string."""
        chunks = [
            _make_chunk('["task'),
            _make_chunk(' one"'),
            _make_chunk("]"),
        ]
        with patch.object(llm, '_make_client', return_value=_mock_client(chunks)):
            result = _run(llm.chat_stream_with_usage("sys", "user"))

        assert result.content == '["task one"]'

    def test_stream_calls_on_progress(self):
        """on_progress is called after each content chunk with cumulative chars and tokens."""
        chunks = [
            _make_chunk("hello"),
            _make_chunk(" world"),
        ]
        calls = []
        with patch.object(llm, '_make_client', return_value=_mock_client(chunks)):
            _run(llm.chat_stream_with_usage("sys", "user", on_progress=lambda c, t: calls.append((c, t))))

        assert len(calls) == 2
        assert calls[0] == (5, 1)   # "hello" = 5 chars, 1 token increment
        assert calls[1] == (11, 2)  # "hello world" = 11 chars, 2 token increments

    def test_stream_returns_chat_result(self):
        """Return value is a ChatResult dataclass with expected fields."""
        chunks = [_make_chunk('[]')]
        with patch.object(llm, '_make_client', return_value=_mock_client(chunks, "my-model")):
            result = _run(llm.chat_stream_with_usage("sys", "user"))

        assert isinstance(result, ChatResult)
        assert result.content == "[]"
        assert result.model == "my-model"
        assert isinstance(result.completion_tokens, int)
        assert isinstance(result.total_tokens, int)

    def test_stream_no_progress_callback(self):
        """Works correctly when on_progress=None (default) — no error raised."""
        chunks = [_make_chunk("data")]
        with patch.object(llm, '_make_client', return_value=_mock_client(chunks)):
            result = _run(llm.chat_stream_with_usage("sys", "user"))

        assert result.content == "data"

    def test_stream_empty_chunks_ignored(self):
        """Chunks with no content delta don't affect content or trigger on_progress."""
        chunks = [
            _make_chunk(None),   # no content
            _make_chunk("ok"),
            _make_chunk(None),
        ]
        calls = []
        with patch.object(llm, '_make_client', return_value=_mock_client(chunks)):
            result = _run(llm.chat_stream_with_usage("sys", "user", on_progress=lambda c, t: calls.append((c, t))))

        assert result.content == "ok"
        assert len(calls) == 1


class TestExtractStatusCurrentChunk:

    def test_status_includes_current_chunk_field(self):
        """The /api/extract/status endpoint includes current_chunk when set."""
        import main as app_main
        from fastapi.testclient import TestClient

        client = TestClient(app_main.app)

        # Set a known status with current_chunk
        app_main._extract_status = {
            "phase": "running",
            "total_chunks": 3,
            "done_chunks": 1,
            "input_chars": 5000,
            "started_at": 0,
            "chunks": [],
            "current_chunk": {"index": 2, "chars": 1234, "tokens": 42},
        }

        r = client.get("/api/extract/status")
        assert r.status_code == 200
        data = r.json()
        assert data["phase"] == "running"
        assert data["current_chunk"] == {"index": 2, "chars": 1234, "tokens": 42}
        assert "started_at" not in data  # should be stripped by endpoint

    def test_status_current_chunk_none_when_idle(self):
        """current_chunk is None when idle."""
        import main as app_main
        from fastapi.testclient import TestClient

        client = TestClient(app_main.app)
        app_main._extract_status = {"phase": "idle"}

        r = client.get("/api/extract/status")
        assert r.status_code == 200
        assert r.json() == {"phase": "idle"}
