"""Denial watchdog after publication (task V5).

For a published event, official posts that appear after the publication time and belong to
the event (same linking as the official check, V4) raise an alert: a denial says "update or
take down", any other official post says "check the facts against the new statement".
"""

from __future__ import annotations

from radar.core.models import Alert, Channel, Event, Post, Publication
from radar.verify.official import _candidates, _is_denial, _linked


def watchdog(
    event: Event,
    publication: Publication,
    posts: list[Post],
    channels: list[Channel],
) -> list[Alert]:
    """Alerts for official posts about the event published after publication.published_at."""
    titles = {c.id: c.title for c in channels if c.kind == "official"}
    if not titles:
        return []
    by_id = {p.id: p for p in posts}
    event_posts = [by_id[i] for i in dict.fromkeys(event.post_ids) if i in by_id]
    if not event_posts:
        return []
    later = [
        p
        for p in _linked(event, event_posts, _candidates(event, posts, set(titles)))
        if p.ts > publication.published_at
    ]
    return [_alert(event, publication, post, titles[post.channel_id]) for post in later]


def _alert(event: Event, publication: Publication, post: Post, title: str) -> Alert:
    after = int((post.ts - publication.published_at).total_seconds() // 60)
    if _is_denial(post.text):
        kind = "denial"
        summary = (
            f"«{title}» опроверг событие через {after} мин после публикации в "
            f"{publication.outlet}: обновите материал или снимите его."
        )
    else:
        kind = "update"
        summary = (
            f"«{title}» написал о событии через {after} мин после публикации в "
            f"{publication.outlet}: сверьте факты материала с новым сообщением."
        )
    return Alert(
        event_id=event.id,
        outlet=publication.outlet,
        kind=kind,
        post_id=post.id,
        ts=post.ts,
        summary=summary,
    )
