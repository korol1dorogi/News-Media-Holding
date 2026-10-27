"""Clustering posts into events (task C2)."""

from __future__ import annotations

from radar.core.models import Event, Post


def build_events(posts: list[Post]) -> list[Event]:
    """Group posts into events. Forwards always join the cluster of the original post."""
    # TODO(C2): TF-IDF + cosine threshold + time window.
    # Done when every event from truth.yaml is a single cluster (docs/tasks.md, C2).
    return []
