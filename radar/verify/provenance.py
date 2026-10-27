"""First source, repost graph and independent sources (task V1)."""

from __future__ import annotations

from radar.core.models import Channel, Check, Event, Post


def provenance(event: Event, posts: list[Post], channels: list[Channel]) -> tuple[Check, str, int]:
    """Return (check, first_source_post_id, independent_sources)."""
    # TODO(V1): root of the forward chain; a later copy with similar text is the same source;
    # independent = number of distinct roots.
    # Done when independent and first_source match truth.yaml (docs/tasks.md, V1).
    first_id = event.post_ids[0] if event.post_ids else ""
    check = Check(
        name="provenance",
        status="n/a",
        summary="Первоисточник пока не определяется.",
        evidence=[],
    )
    return check, first_id, 0


def repost_graph(event: Event, posts: list[Post]) -> dict:
    """{"nodes": [{"id", "channel_id", "ts"}], "edges": [{"from", "to", "kind"}]}.

    kind is "forward" or "copy".
    """
    # TODO(V1): nodes for the event's posts, edges from forwards and copies.
    return {"nodes": [], "edges": []}
