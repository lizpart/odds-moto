import re
from typing import Any, Dict, List, Optional

from openai import AsyncOpenAI

from app_config import settings


_THINK_BLOCK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)


def strip_thinking(raw: str) -> str:
    """
    Remove DeepSeek R1 <think>...</think> blocks before parsing/validation.

    Groq often uses the OpenAI-compatible chat format but may wrap reasoning in <think>.
    """
    if not raw:
        return ""
    return _THINK_BLOCK_RE.sub("", raw).strip()


_llm_client: Optional[AsyncOpenAI] = None


def _get_llm_client() -> AsyncOpenAI:
    global _llm_client
    if _llm_client is not None:
        return _llm_client

    if not settings.groq_api_key:
        raise RuntimeError("GROQ_API_KEY is not configured.")

    _llm_client = AsyncOpenAI(
        api_key=settings.groq_api_key,
        base_url=settings.groq_base_url,
    )
    return _llm_client


async def call_llm(
    *,
    messages: List[Dict[str, Any]],
    temperature: float = 0.7,
    max_tokens: int = 1000,
) -> str:
    """
    Call the Groq OpenAI-compatible endpoint and return stripped content.
    """
    client = _get_llm_client()

    resp = await client.chat.completions.create(
        model=settings.groq_model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )

    raw = resp.choices[0].message.content or ""
    return strip_thinking(raw)

