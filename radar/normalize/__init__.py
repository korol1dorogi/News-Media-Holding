"""Post normalization: geo and topic (task C1)."""

from __future__ import annotations

from radar.core.models import Post


def enrich(post: Post) -> Post:
    """Return the post with geo and topic filled in."""
    # TODO(C1): geo from the fictional city dictionary, topic from keywords.
    # Done when geo and topic match expectations on 20 posts (docs/tasks.md, C1).
    return post
