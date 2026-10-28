"""V5: official posts after publication raise alerts."""

from datetime import datetime, timedelta

from radar.core.models import Channel, Event, Post, Publication
from radar.verify import watchdog

TS = datetime.fromisoformat("2026-10-28T14:00:00+03:00")
PUBLIC = Channel("ch_public", "Городской паблик (синтетика)", "public", "demo-city")
MCHS = Channel("ch_mchs", "МЧС города (синтетика)", "official", "demo-city")
CHANNELS = [PUBLIC, MCHS]


def post(post_id: str, channel: Channel, minutes: int, text: str) -> Post:
    return Post(
        id=post_id,
        channel_id=channel.id,
        ts=TS + timedelta(minutes=minutes),
        text=text,
        url=f"https://example.invalid/{post_id}",
        media=[],
        forward_from=None,
        geo="центр",
        topic="пожар",
    )


FIRE = [
    post("f_1", PUBLIC, 0, "Горит ТЦ «Галерея» на Лесной улице, чёрный дым."),
    post("f_2", PUBLIC, 10, "У ТЦ «Галерея» пожарные машины, людей выводят."),
]
DENIAL = post(
    "f_3", MCHS, 90, "Информация о пожаре в ТЦ «Галерея» не соответствует действительности."
)
UPDATE = post("f_4", MCHS, 120, "Пожарные расчёты завершили проверку ТЦ «Галерея» на Лесной улице.")
EVENT = Event(
    id="ev_fire",
    post_ids=["f_1", "f_2", "f_3"],
    first_ts=TS,
    title="Горит ТЦ «Галерея»",
    geo="центр",
    topic="пожар",
    scores={},
)


def published(minutes: int) -> Publication:
    return Publication(
        event_id="ev_fire", outlet="mash", published_at=TS + timedelta(minutes=minutes)
    )


def test_denial_after_publication_raises_alert() -> None:
    alerts = watchdog(EVENT, published(30), [*FIRE, DENIAL], CHANNELS)
    assert [(a.kind, a.post_id, a.outlet) for a in alerts] == [("denial", "f_3", "mash")]
    assert "через 60 мин" in alerts[0].summary
    assert "МЧС города" in alerts[0].summary
    assert alerts[0].ts == DENIAL.ts


def test_denial_before_publication_is_not_an_alert() -> None:
    assert watchdog(EVENT, published(100), [*FIRE, DENIAL], CHANNELS) == []


def test_other_official_post_is_an_update() -> None:
    alerts = watchdog(EVENT, published(100), [*FIRE, DENIAL, UPDATE], CHANNELS)
    assert [(a.kind, a.post_id) for a in alerts] == [("update", "f_4")]


def test_public_posts_and_missing_officials_do_not_alert() -> None:
    late = post("f_9", PUBLIC, 200, "ТЦ «Галерея» на Лесной: это был фейк, пожара нет.")
    assert watchdog(EVENT, published(30), [*FIRE, late], CHANNELS) == []
    assert watchdog(EVENT, published(30), [*FIRE, DENIAL], [PUBLIC]) == []
