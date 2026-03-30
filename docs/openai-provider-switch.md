# Plan: OpenAI / LM Studio Provider Toggle

## Context

The app already uses the `openai` Python SDK — LM Studio's local server is OpenAI-compatible, so it works by pointing the client at `http://localhost:1234/v1`. Switching to real OpenAI is a small config change, not an architectural one. The goal is to support both providers via an environment variable so either can be used without code changes.

---

## Scope — what needs to change

| File | Change | Size |
|------|--------|------|
| `llm.py` | Read env vars, build client conditionally, fix model selection | ~25 lines |
| `.env` (local, not committed) | Add `LLM_PROVIDER`, `OPENAI_API_KEY`, `OPENAI_MODEL` | 3 lines |
| `prompts.py` | Strip `/no_think` tag for OpenAI (Qwen-specific, harmless but noisy) | 1 line |

`main.py`, `static/index.html`, `tasks.py`, `memory.py` — **no changes needed**.

---

## Changes

### `llm.py` — conditional client init

```python
import os

LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "lmstudio").lower()  # "lmstudio" | "openai"
LM_STUDIO_URL = "http://localhost:1234/v1"
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

if LLM_PROVIDER == "openai":
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
else:
    client = OpenAI(base_url=LM_STUDIO_URL, api_key="lm-studio")
```

**Model selection** — replace the `models.list()` auto-discovery in all three functions (`chat`, `chat_with_usage`, `chat_stream_with_usage`) with a shared helper:

```python
def _get_model() -> str:
    if LLM_PROVIDER == "openai":
        return OPENAI_MODEL
    models = client.models.list()
    if not models.data:
        raise RuntimeError(
            "No model loaded in LM Studio. Open LM Studio → Developer tab and load a model."
        )
    return models.data[0].id
```

**`health_check()`** — for OpenAI, skip `models.list()` and return:
```python
{"status": "connected", "provider": "openai", "model": OPENAI_MODEL}
```

### `prompts.py` — strip `/no_think` for OpenAI

`/no_think` is a Qwen/DeepSeek instruction to suppress chain-of-thought. OpenAI ignores it but it's cleaner to omit. Add a helper:

```python
def build_extraction_prompt(text: str, provider: str = "lmstudio") -> str:
    prompt = TASK_EXTRACTION.format(text=text)
    if provider == "openai":
        prompt = prompt.replace("\n\n/no_think\n\n", "\n\n")
    return prompt
```

Then in `main.py`, replace:
```python
prompt = prompts.TASK_EXTRACTION.format(text=chunk)
```
with:
```python
prompt = prompts.build_extraction_prompt(chunk, llm.LLM_PROVIDER)
```

### `.env` (local only, never committed)

```
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
```

Switch back to LM Studio by removing `LLM_PROVIDER` or setting it to `lmstudio`.

---

## Cost note

OpenAI GPT-4o-mini pricing: ~$0.15/1M input tokens, ~$0.60/1M output tokens. A typical transcript extraction (1 chunk, ~2,500 tokens total) costs roughly $0.0004 — under half a cent.

---

## Verification

1. `pytest tests/ -v` — all 7 tests pass (tests mock the client, unaffected by provider)
2. `LLM_PROVIDER=lmstudio` (or unset) → health check shows LM Studio models, extraction works as before
3. `LLM_PROVIDER=openai` + valid key → health check returns `{"provider": "openai", "model": "gpt-4o-mini"}`, extraction works
4. Missing `OPENAI_API_KEY` with `LLM_PROVIDER=openai` → clear `KeyError` on startup (fails fast)
