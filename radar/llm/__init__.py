"""LLM providers. The default is the offline MockProvider."""

from __future__ import annotations

from typing import Protocol

from radar.core.settings import Settings, load_settings
from radar.llm.mock import MockProvider
from radar.llm.openai_compat import OpenAICompatProvider


class Provider(Protocol):
    def complete(self, system: str, user: str) -> str: ...


def get_provider(settings: Settings | None = None) -> Provider:
    """Pick the provider by LLM_PROVIDER: mock (default) or openai."""
    settings = settings or load_settings()
    if settings.llm_provider == "mock":
        return MockProvider(truth_path=settings.data_dir / "truth.yaml")
    if settings.llm_provider == "openai":
        return OpenAICompatProvider(
            base_url=settings.llm_base_url,
            model=settings.llm_model,
            api_key=settings.llm_api_key,
        )
    raise ValueError(f"Unknown LLM_PROVIDER: {settings.llm_provider!r}")


__all__ = ["MockProvider", "OpenAICompatProvider", "Provider", "get_provider"]
