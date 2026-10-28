"""V4: an official channel confirms, denies or stays silent."""

import random
from datetime import datetime, timedelta

from radar.core.models import Channel, Event, Post
from radar.ingest import load_replay
from radar.verify import official

TS = datetime.fromisoformat("2026-10-27T10:00:00+03:00")

PUBLIC = Channel("ch_public", "Городской паблик (синтетика)", "public", "demo-city")
READER = Channel("ch_reader", "Бот читателей (синтетика)", "reader_bot", "demo-city")
MCHS = Channel("ch_mchs", "МЧС города (синтетика)", "official", "demo-city")
GIBDD = Channel("ch_gibdd", "ГИБДД города (синтетика)", "official", "demo-city")
CHANNELS = [PUBLIC, READER, MCHS, GIBDD]

# Fire in a mall: two retellings with little word overlap between them.
FIRE = [
    ("f_1", PUBLIC, 0, "Горит ТЦ «Галерея», чёрный дым над Лесной улицей, людей выводят."),
    ("f_2", READER, 7, "У торгового центра на Лесной пожарные машины, все в дыму"),
]
FIRE_DENIAL = "Сообщения о возгорании в торговом центре на Лесной — фейк, вызовов не поступало."
# Official noise that shares words with the fire ("пожар", "улице") but is about something else.
NOISE = [
    ("n_1", MCHS, 30, "Напоминаем: при пожаре звоните 112, не пользуйтесь лифтом."),
    ("n_2", MCHS, 60, "В субботу на водохранилище пройдут учения спасателей, купаться запрещено."),
    ("n_3", GIBDD, 90, "С 1 ноября на Садовой улице плановый ремонт дороги, возможны пробки."),
]


def make_post(post_id: str, channel: Channel, minutes: float, text: str) -> Post:
    return Post(
        id=post_id,
        channel_id=channel.id,
        ts=TS + timedelta(minutes=minutes),
        text=text,
        url=f"https://example.invalid/{post_id}",
        media=[],
        forward_from=None,
    )


def make_posts(rows: list[tuple]) -> list[Post]:
    return [make_post(*row) for row in rows]


def make_event(post_ids: list[str], first_ts: datetime = TS, **kwargs) -> Event:
    fields = {"geo": None, "topic": None} | kwargs
    return Event(id="ev_test", post_ids=post_ids, first_ts=first_ts, title="", scores={}, **fields)


def fire_event() -> Event:
    return make_event(["f_1", "f_2"])


def evidence_ids(check) -> list[str]:
    return [e["post_id"] for e in check.evidence]


def test_mini_crash_confirmed_by_gibdd(mini_dir) -> None:
    channels, posts = load_replay(mini_dir)
    event = make_event(["m_001", "m_002", "m_003"], posts[0].ts)
    check = official(event, posts, channels)
    assert check.name == "official"
    assert check.status == "ok"
    assert evidence_ids(check) == ["m_003"]
    assert (
        check.summary == "Официальный канал «ГИБДД города (синтетика)» подтвердил событие в 08:40."
    )
    assert "подтверждение" in check.evidence[0]["note"]


def test_mini_flood_has_no_official_post(mini_dir) -> None:
    channels, posts = load_replay(mini_dir)
    by_id = {p.id: p for p in posts}
    event = make_event(["m_004", "m_005", "m_006"], by_id["m_004"].ts)
    check = official(event, posts, channels)
    assert check.status == "n/a"
    assert check.summary == "Официальные каналы молчат по этому событию."
    assert check.evidence == []


def test_mini_road_works_stick_to_nothing(mini_dir) -> None:
    channels, posts = load_replay(mini_dir)
    by_id = {p.id: p for p in posts}
    for ids in (["m_001", "m_002"], ["m_004", "m_005", "m_006"]):
        check = official(make_event(ids, by_id[ids[0]].ts), posts, channels)
        assert "m_008" not in evidence_ids(check)


def test_fire_denied_by_mchs_outside_cluster() -> None:
    posts = make_posts([*FIRE, ("f_9", MCHS, 50, FIRE_DENIAL), *NOISE])
    check = official(fire_event(), posts, CHANNELS)
    assert check.status == "fail"
    assert evidence_ids(check) == ["f_9"]
    assert check.summary == "Официальный канал «МЧС города (синтетика)» опроверг событие в 10:50."
    assert check.evidence[0]["note"].startswith("опровержение")


def test_noise_with_shared_words_is_not_linked() -> None:
    posts = make_posts([*FIRE, *NOISE])
    check = official(fire_event(), posts, CHANNELS)
    assert check.status == "n/a"
    assert check.evidence == []


def test_confirmation_with_negated_casualties_is_not_a_denial() -> None:
    rows = [
        ("c_1", PUBLIC, 0, "ДТП на северном въезде: автобус столкнулся с грузовиком."),
        (
            "c_2",
            GIBDD,
            25,
            "На северном въезде столкнулись автобус и грузовик, пострадавших не зафиксировано.",
        ),
    ]
    check = official(make_event(["c_1"]), make_posts(rows), CHANNELS)
    assert check.status == "ok"
    assert evidence_ids(check) == ["c_2"]


def test_denial_beats_confirmation() -> None:
    confirm = "В торговом центре на Лесной горит второй этаж, идёт эвакуация."
    rows = [*FIRE, ("f_8", MCHS, 20, confirm), ("f_9", MCHS, 50, FIRE_DENIAL)]
    check = official(fire_event(), make_posts(rows), CHANNELS)
    assert check.status == "fail"
    assert evidence_ids(check) == ["f_8", "f_9"]
    assert "опроверг" in check.summary


def test_post_outside_time_window_is_ignored() -> None:
    for minutes in (-3 * 60, 25 * 60):
        posts = make_posts([*FIRE, ("f_9", MCHS, minutes, FIRE_DENIAL)])
        assert official(fire_event(), posts, CHANNELS).status == "n/a"
    posts = make_posts([*FIRE, ("f_9", MCHS, -60, FIRE_DENIAL)])
    assert official(fire_event(), posts, CHANNELS).status == "fail"


def test_official_post_in_cluster_counts_regardless_of_window() -> None:
    rows = [*FIRE, ("f_9", MCHS, 30 * 60, "Пожар в ТЦ «Галерея» потушен.")]
    check = official(make_event(["f_1", "f_2", "f_9"]), make_posts(rows), CHANNELS)
    assert check.status == "ok"
    assert evidence_ids(check) == ["f_9"]


def test_geo_and_topic_decide_when_filled() -> None:
    posts = make_posts([*FIRE, ("f_9", MCHS, 50, FIRE_DENIAL), ("n_1", MCHS, 30, NOISE[0][3])])
    for post in posts:
        post.geo, post.topic = "lesnaya", "fire"
    posts[2].geo = "sadovaya"  # same text as a real denial, but another place
    event = make_event(["f_1", "f_2"], geo="lesnaya", topic="fire")
    check = official(event, posts, CHANNELS)
    # n_1 shares geo and topic and is linked; f_9 is from another place and is not.
    assert check.status == "ok"
    assert evidence_ids(check) == ["n_1"]


def test_empty_event_is_not_applicable() -> None:
    check = official(make_event([]), make_posts(FIRE), CHANNELS)
    assert check.status == "n/a"
    assert "не найдены" in check.summary
    check = official(make_event(["missing"]), make_posts(FIRE), CHANNELS)
    assert check.status == "n/a"


def test_no_official_channels_is_not_applicable() -> None:
    posts = make_posts([*FIRE, ("f_9", MCHS, 50, FIRE_DENIAL)])
    check = official(fire_event(), posts, [PUBLIC, READER])
    assert check.status == "n/a"
    assert "нет официальных каналов" in check.summary


def test_deterministic_on_shuffled_input() -> None:
    confirm = "В торговом центре на Лесной горит второй этаж, идёт эвакуация."
    rows = [*FIRE, ("f_8", MCHS, 20, confirm), ("f_9", MCHS, 50, FIRE_DENIAL), *NOISE]
    posts = make_posts(rows)
    expected = official(fire_event(), posts, CHANNELS)
    rng = random.Random(4)
    for _ in range(5):
        shuffled_posts, shuffled_channels = posts[:], CHANNELS[:]
        rng.shuffle(shuffled_posts)
        rng.shuffle(shuffled_channels)
        assert official(fire_event(), shuffled_posts, shuffled_channels) == expected
