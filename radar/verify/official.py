"""Confirmation or denial by an official channel (task V4).

Candidates are official posts inside the event or within a time window around event.first_ts.
An outside post belongs to the event if geo and topic match (when both sides have them) or,
as a fallback, if its char TF-IDF cosine to some event post reaches LINK_THRESHOLD (D-03).
A denial among linked posts beats any confirmation.
"""

from __future__ import annotations

from datetime import timedelta

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from radar.core.models import Channel, Check, Event, Post

WINDOW_BEFORE = timedelta(hours=2)
WINDOW_AFTER = timedelta(hours=24)
# Tuned on the mini set: related posts score 0.17+, unrelated ones 0.08 and below.
# Narrow margin; revisit after S1 and C1. When geo and topic are filled, they decide.
LINK_THRESHOLD = 0.12

# Lower-case substrings. Keep them specific: "пострадавших не зафиксировано" is a confirmation.
DENIAL_PHRASES = (
    "не соответствует действительности",
    "опроверг",
    "фейк",
    "ложн",
    "ложный вызов",
    "информация не подтвердилась",
    "не подтверждается",
    "вызовов не поступало",
    "происшествий не зафиксировано",
    "возгорания не зафиксировано",
)


def _is_denial(text: str) -> bool:
    lowered = text.lower()
    return any(phrase in lowered for phrase in DENIAL_PHRASES)


def _candidates(event: Event, posts: list[Post], official_ids: set[str]) -> list[Post]:
    """Official posts of the event plus official posts in the time window, by (ts, id)."""
    in_event = set(event.post_ids)
    start, end = event.first_ts - WINDOW_BEFORE, event.first_ts + WINDOW_AFTER
    found = [
        p
        for p in posts
        if p.channel_id in official_ids and (p.id in in_event or start <= p.ts <= end)
    ]
    return sorted(found, key=lambda p: (p.ts, p.id))


def _linked(event: Event, event_posts: list[Post], candidates: list[Post]) -> list[Post]:
    """Candidates that belong to the event, keeping the order of candidates."""
    in_event = set(event.post_ids)
    linked: dict[str, bool] = {}
    by_text: list[Post] = []
    for post in candidates:
        if post.id in in_event:
            linked[post.id] = True
        elif event.geo and event.topic and post.geo and post.topic:
            linked[post.id] = (event.geo, event.topic) == (post.geo, post.topic)
        else:
            by_text.append(post)

    event_texts = [p.text.strip() for p in sorted(event_posts, key=lambda p: p.id)]
    event_texts = [t for t in event_texts if t]
    outside = sorted((p for p in by_text if p.text.strip()), key=lambda p: p.id)
    if event_texts and outside:
        texts = event_texts + [p.text.strip() for p in outside]
        vectors = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5)).fit_transform(texts)
        sim = cosine_similarity(vectors[len(event_texts) :], vectors[: len(event_texts)])
        for row, post in zip(sim, outside, strict=True):
            linked[post.id] = bool(row.max() >= LINK_THRESHOLD)
    return [p for p in candidates if linked.get(p.id, False)]


def official(event: Event, posts: list[Post], channels: list[Channel]) -> Check:
    """ok if an official channel confirms, fail if it denies, n/a if it is silent."""
    titles = {c.id: c.title for c in channels if c.kind == "official"}
    by_id = {p.id: p for p in posts}
    event_posts = [by_id[i] for i in dict.fromkeys(event.post_ids) if i in by_id]

    def silent(summary: str) -> Check:
        return Check(name="official", status="n/a", summary=summary, evidence=[])

    if not event_posts:
        return silent("Посты события не найдены, сверить с официальными каналами нельзя.")
    if not titles:
        return silent("В данных нет официальных каналов, подтверждение проверить нельзя.")

    linked = _linked(event, event_posts, _candidates(event, posts, set(titles)))
    if not linked:
        return silent("Официальные каналы молчат по этому событию.")

    denials = [p for p in linked if _is_denial(p.text)]
    evidence = [
        {
            "post_id": p.id,
            "note": (
                f"опровержение официального канала {titles[p.channel_id]}"
                if _is_denial(p.text)
                else f"подтверждение официального канала {titles[p.channel_id]}"
            ),
        }
        for p in linked
    ]
    key = denials[0] if denials else linked[0]
    verb = "опроверг" if denials else "подтвердил"
    summary = f"Официальный канал «{titles[key.channel_id]}» {verb} событие в {key.ts:%H:%M}."
    return Check(
        name="official",
        status="fail" if denials else "ok",
        summary=summary,
        evidence=evidence,
    )
