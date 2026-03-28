"""LM Studio client using OpenAI-compatible API."""

import asyncio
from dataclasses import dataclass
from openai import OpenAI
import json

LM_STUDIO_URL = "http://localhost:1234/v1"

client = OpenAI(base_url=LM_STUDIO_URL, api_key="lm-studio")


async def health_check() -> dict:
    """Check if LM Studio is running and has a model loaded."""
    try:
        models = client.models.list()
        model_list = [m.id for m in models.data]
        return {"status": "connected", "models": model_list}
    except Exception as e:
        return {"status": "disconnected", "error": str(e)}


async def chat(system_prompt: str, user_message: str) -> str:
    """Send a chat completion request to LM Studio."""
    # Discover the loaded model; raise a clear error if none is loaded.
    try:
        models = client.models.list()
        model_list = [m.id for m in models.data]
    except Exception as e:
        raise RuntimeError("Cannot reach LM Studio. Is it running?") from e

    if not model_list:
        raise RuntimeError(
            "No model is loaded in LM Studio. "
            "Open LM Studio, go to the Developer tab, and load a model."
        )

    response = client.chat.completions.create(
        model=model_list[0],
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
    try:
        models = client.models.list()
        model_list = [m.id for m in models.data]
    except Exception as e:
        raise RuntimeError("Cannot reach LM Studio. Is it running?") from e

    if not model_list:
        raise RuntimeError(
            "No model is loaded in LM Studio. "
            "Open LM Studio, go to the Developer tab, and load a model."
        )

    response = client.chat.completions.create(
        model=model_list[0],
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
    try:
        models = client.models.list()
        model_list = [m.id for m in models.data]
    except Exception as e:
        raise RuntimeError("Cannot reach LM Studio. Is it running?") from e

    if not model_list:
        raise RuntimeError(
            "No model is loaded in LM Studio. "
            "Open LM Studio, go to the Developer tab, and load a model."
        )

    stream = client.chat.completions.create(
        model=model_list[0],
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
    model_name = model_list[0]

    for chunk in stream:
        delta = chunk.choices[0].delta.content if chunk.choices else None
        if delta:
            content += delta
            completion_tokens += 1  # approximate: one increment per stream chunk
            if on_progress:
                on_progress(len(content), completion_tokens)
        # LM Studio may include usage on the final chunk
        if hasattr(chunk, "usage") and chunk.usage:
            prompt_tokens = chunk.usage.prompt_tokens or prompt_tokens
            completion_tokens = chunk.usage.completion_tokens or completion_tokens
        # Yield to event loop so status-polling requests can be served mid-generation
        await asyncio.sleep(0)

    return ChatResult(
        content=content,
        model=model_name,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=prompt_tokens + completion_tokens,
    )


def parse_json(text: str) -> list | dict:
    """Extract and parse JSON from LLM text response."""
    # Try to find JSON array first, then object
    start = text.find("[")
    end = text.rfind("]") + 1
    if start >= 0 and end > start:
        return json.loads(text[start:end])
    start = text.find("{")
    end = text.rfind("}") + 1
    if start >= 0 and end > start:
        return json.loads(text[start:end])
    raise ValueError(f"Could not parse JSON from LLM response: {text[:200]}")
