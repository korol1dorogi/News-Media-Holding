"""OpenAI-compatible chat completions provider (task AI1). Used only when LLM_PROVIDER=openai."""

from __future__ import annotations

import httpx


class OpenAICompatProvider:
    def __init__(
        self,
        base_url: str,
        model: str,
        api_key: str = "",
        timeout: float = 30.0,
    ) -> None:
        if not base_url or not model:
            raise ValueError("LLM_PROVIDER=openai needs LLM_BASE_URL and LLM_MODEL")
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._api_key = api_key
        self._timeout = timeout

    def complete(self, system: str, user: str) -> str:
        # TODO(AI1): retries and a readable error for the editor.
        headers = {"Authorization": f"Bearer {self._api_key}"} if self._api_key else {}
        response = httpx.post(
            f"{self._base_url}/chat/completions",
            json={
                "model": self._model,
                "temperature": 0,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            },
            headers=headers,
            timeout=self._timeout,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
