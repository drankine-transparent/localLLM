"""LLM client — supports LM Studio (local) and OpenAI (cloud)."""

import asyncio
import os
from dataclasses import dataclass
from dotenv import load_dotenv
from openai import OpenAI
import json

load_dotenv()

LM_STUDIO_URL = "http://localhost:1234/v1"
OPENAI_MODEL  = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

_provider: str = os.environ.get("LLM_PROVIDER", "lmstudio").lower()


def get_provider() -> str:
    return _provider


def set_provider(p: str) -> None:
    global _provider
    if p not in ("lmstudio", "openai"):
        raise ValueError(f"Unknown provider: {p}")
    if p == "openai" and not os.environ.get("OPENAI_API_KEY"):
        raise ValueError("OPENAI_API_KEY is not set in the environment.")
    _provider = p


def _make_client() -> OpenAI:
    if _provider == "openai":
        key = os.environ.get("OPENAI_API_KEY", "")
        if not key:
            raise RuntimeError("OPENAI_API_KEY is not set in the environment.")
        return OpenAI(api_key=key)
    return OpenAI(base_url=LM_STUDIO_URL, api_key="lm-studio")


def _get_model(client: OpenAI) -> str:
    if _provider == "openai":
        return OPENAI_MODEL
    try:
        models = client.models.list()
    except Exception as e:
        raise RuntimeError("Cannot reach LM Studio. Is it running?") from e
    if not models.data:
        raise RuntimeError(
            "No model loaded in LM Studio. "
            "Open LM Studio, go to the Developer tab, and load a model."
        )
    return models.data[0].id


async def health_check() -> dict:
    """Return connection status and active provider."""
    try:
        client = _make_client()
        if _provider == "openai":
            return {"status": "connected", "provider": "openai", "models": [OPENAI_MODEL]}
        models = client.models.list()
        model_list = [m.id for m in models.data]
        return {"status": "connected", "provider": "lmstudio", "models": model_list}
    except Exception as e:
        return {"status": "disconnected", "provider": _provider, "error": str(e)}


async def chat(system_prompt: str, user_message: str) -> str:
    """Send a chat completion request."""
    client = _make_client()
    model = _get_model(client)
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        temperature=0.3,
    )
    return response.choices[0].message.content


@dataclass
class ChatResult:
    content: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


async def chat_with_usage(system_prompt: str, user_message: str) -> ChatResult:
    """Same as chat() but returns content + token usage."""
    client = _make_client()
    model = _get_model(client)
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        temperature=0.3,
    )
    usage = response.usage
    return ChatResult(
        content=response.choices[0].message.content,
        model=response.model,
        prompt_tokens=usage.prompt_tokens if usage else 0,
        completion_tokens=usage.completion_tokens if usage else 0,
        total_tokens=usage.total_tokens if usage else 0,
    )


async def chat_stream_with_usage(
    system_prompt: str,
    user_message: str,
    on_progress=None,
) -> ChatResult:
    """Like chat_with_usage() but streams tokens, calling on_progress(chars, tokens) as they arrive."""
    client = _make_client()
    model = _get_model(client)

    stream = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        temperature=0.3,
        stream=True,
    )

    content = ""
    prompt_tokens = 0
    completion_tokens = 0

    for chunk in stream:
        delta = chunk.choices[0].delta.content if chunk.choices else None
        if delta:
            content += delta
            completion_tokens += 1  # approximate: one increment per stream chunk
            if on_progress:
                on_progress(len(content), completion_tokens)
        # Provider may include usage on the final chunk
        if hasattr(chunk, "usage") and chunk.usage:
            prompt_tokens = chunk.usage.prompt_tokens or prompt_tokens
            completion_tokens = chunk.usage.completion_tokens or completion_tokens
        # Yield to event loop so status-polling requests can be served mid-generation
        await asyncio.sleep(0)

    return ChatResult(
        content=content,
        model=model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=prompt_tokens + completion_tokens,
    )


def parse_json(text: str) -> list | dict:
    """Extract and parse JSON from LLM text response."""
    start = text.find("[")
    end = text.rfind("]") + 1
    if start >= 0 and end > start:
        return json.loads(text[start:end])
    start = text.find("{")
    end = text.rfind("}") + 1
    if start >= 0 and end > start:
        return json.loads(text[start:end])
    raise ValueError(f"Could not parse JSON from LLM response: {text[:200]}")
