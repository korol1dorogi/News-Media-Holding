"""Newsworthiness score for an outlet profile (task C3)."""

from __future__ import annotations

from radar.core.models import Event, Post


def score(event: Event, posts: list[Post], profile: dict) -> float:
    """Score 0..1. posts are all replay posts; the event's posts are listed in event.post_ids."""
    # TODO(C3): weighted sum of mention growth, independent sources, topic and geo weights.
    # Done when noise ranks below events and mash/life orders differ (docs/tasks.md, C3).
    return 0.0
