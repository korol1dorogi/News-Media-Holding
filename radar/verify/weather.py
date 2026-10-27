"""Media scene vs weather and daylight (task V3)."""

from __future__ import annotations

from radar.core.models import Check, Event, Post


def weather(event: Event, posts: list[Post], weather: dict, media_meta: dict) -> Check:
    """Compare scene/daylight from media/meta.json with weather.json and post time."""
    # TODO(V3): fail when the scene contradicts the weather for the post's geo and date.
    # Done when "snowfall" fails with a clear summary (docs/tasks.md, V3).
    return Check(
        name="weather",
        status="n/a",
        summary="Сверка с погодой пока не выполняется.",
        evidence=[],
    )
