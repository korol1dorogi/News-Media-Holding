"""Deterministic offline provider (task AI1)."""

from __future__ import annotations


class MockProvider:
    """Same input gives the same output. No network, no key."""

    def complete(self, system: str, user: str) -> str:
        # TODO(AI1): build outlet-specific text from post facts; with inject_error
        # distort exactly one number (docs/tasks.md, AI1).
        return user.strip()
