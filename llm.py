"""
One place that builds the chat model, and the seam the tests use.

The previous agent built ``ChatOpenAI`` inline with a hardcoded DeepSeek base
URL and model, and ``model_kwargs={"top_p": 0.1}`` -- a parameter recent
``langchain-openai`` releases refuse to accept through ``model_kwargs``.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from config import settings

_factory: Callable[[], Any] | None = None


class LLMNotConfigured(RuntimeError):
    pass


def set_model_factory(factory: Callable[[], Any] | None) -> None:
    global _factory
    _factory = factory


def get_chat_model() -> Any:
    if _factory is not None:
        return _factory()
    if not settings.has_llm_key:
        raise LLMNotConfigured(
            "LLM_API_KEY is not set (DEEPSEEK_API_KEY is accepted as an alias). "
            "Any OpenAI-compatible endpoint works; set LLM_BASE_URL and LLM_MODEL to change it."
        )
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=settings.LLM_MODEL,
        api_key=settings.LLM_API_KEY,
        base_url=settings.LLM_BASE_URL,
        temperature=0,
        timeout=settings.LLM_TIMEOUT_SECONDS,
        max_retries=2,
    )
