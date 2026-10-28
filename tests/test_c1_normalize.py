"""C1: geo and topic of a post from the city dictionary and keywords."""

import copy
from datetime import datetime

import pytest
import yaml

from radar.core.models import Post
from radar.core.settings import ROOT
from radar.ingest import load_replay
from radar.normalize import enrich

SYNTHETIC = ROOT / "data" / "synthetic"
# geo and topic of every demo event, as in frontend/src/mock/events.json.
EXPECTED = {
    "dtp_entry": ("северный въезд", "ДТП"),
    "flood_old_photo": ("Речная улица", "ЧС"),
    "plant_rumor": ("промзона", "общество"),
    "mall_fire": ("центр", "пожар"),
    "snowfall": ("южный район", "погода"),
    "water_outage": ("южный район", "ЖКХ"),
}
RUMOR = (
    "Говорят, машиностроительный завод «Прибор» в промзоне закрывают в декабре, "
    "всех сотрудников сократят."
)
# Texts from scripts/gen_synthetic.py (S1) with the expected (geo, topic).
CASES = [
    # dtp_entry: all six retellings
    (
        "ДТП на северном въезде: автобус столкнулся с грузовиком, трое пострадавших.",
        ("северный въезд", "ДТП"),
    ),
    (
        "Стою в пробке на северном въезде, впереди авария с автобусом, скорая уже приехала.",
        ("северный въезд", "ДТП"),
    ),
    (
        "Северный въезд встал: рейсовый автобус и фура не разъехались у поворота "
        "на объездную, работают медики.",
        ("северный въезд", "ДТП"),
    ),
    (
        "Очевидцы пишут, что грузовик не успел затормозить и ударил автобус прямо "
        "на северном въезде в город. Есть раненые.",
        ("северный въезд", "ДТП"),
    ),
    (
        "На северном въезде столкнулись автобус и грузовик. Пострадали три человека, "
        "движение затруднено. Просим водителей объезжать участок.",
        ("северный въезд", "ДТП"),
    ),
    (
        "Утренняя пробка на северном въезде — из-за аварии: грузовик въехал "
        "в пассажирский автобус, в больницу увезли троих.",
        ("северный въезд", "ДТП"),
    ),
    # flood_old_photo
    (
        "Наводнение на Речной улице прямо сейчас, вода по колено! Машины стоят в воде.",
        ("Речная улица", "ЧС"),
    ),
    # plant_rumor: the original and a copy with an emoji
    (RUMOR, ("промзона", "общество")),
    (RUMOR + " 😱", ("промзона", "общество")),
    # mall_fire: three posts and the official denial
    (
        "Горит ТЦ «Галерея» на Лесной улице! Чёрный дым видно со всего центра.",
        ("центр", "пожар"),
    ),
    (
        "У торгового центра «Галерея» на Лесной пожарные машины, людей выводят на улицу.",
        ("центр", "пожар"),
    ),
    (
        "В центре задымление: пишут, что в ТЦ «Галерея» на Лесной улице пожар и эвакуация.",
        ("центр", "пожар"),
    ),
    (
        "Информация о пожаре в ТЦ «Галерея» на Лесной улице не соответствует "
        "действительности. Пожарные расчёты выезжали на место, возгорания нет, "
        "торговый центр работает в обычном режиме.",
        ("центр", "пожар"),
    ),
    # snowfall
    (
        "Снегопад в южном районе! Всё белое, как зимой, дороги замело.",
        ("южный район", "погода"),
    ),
    (
        "Южный район засыпало снегом: во дворах сугробы, машины под белыми шапками.",
        ("южный район", "погода"),
    ),
    # water_outage
    (
        "Южный район: 27 октября с 9:00 до 18:00 не будет холодной воды в 12 домах "
        "на Ключевой улице (дома 2–24). Причина — ремонт магистрального водопровода.",
        ("южный район", "ЖКХ"),
    ),
    (
        "Жителям южного района: на Ключевой улице сегодня отключают воду, без воды "
        "останутся 12 домов, дать обещают к 18:00.",
        ("южный район", "ЖКХ"),
    ),
    (
        "У нас на Ключевой, дом 14, воды уже нет. Сказали, что включат только в 18:00.",
        ("южный район", "ЖКХ"),
    ),
    # noise
    ("Скидки до 30% на зимние шины на Парковой улице. Реклама.", ("Парковая улица", None)),
    (
        "Соседи, на Садовой улице опять не вывезли мусор. Кто знает, куда писать?",
        ("Садовая улица", "ЖКХ"),
    ),
    ("Напоминаем: не оставляйте обогреватели включёнными без присмотра.", (None, None)),
    ("Как подготовить дом к холодам: проверьте печи и дымоходы заранее.", (None, None)),
    # guards against false substrings: "Заречье" is not "речн", "ключи" is not "ключев"
    (
        "В Заречье громко играет музыка по ночам. Пишите в комментарии, если что-то знаете.",
        ("Заречье", None),
    ),
    ("Нашли ключи с брелоком-мишкой. Пишите в комментарии, если что-то знаете.", (None, None)),
]


def make_post(text: str) -> Post:
    return Post(
        id="p_test",
        channel_id="ch_test",
        ts=datetime.fromisoformat("2026-10-27T08:00:00+03:00"),
        text=text,
        url="https://example.invalid/ch_test/1",
        media=[],
        forward_from=None,
    )


@pytest.mark.parametrize(("text", "expected"), CASES)
def test_geo_and_topic_on_generator_texts(text, expected):
    post = enrich(make_post(text))
    assert (post.geo, post.topic) == expected


@pytest.fixture(scope="module")
def synthetic():
    _, posts = load_replay(SYNTHETIC)
    truth = yaml.safe_load((SYNTHETIC / "truth.yaml").read_text(encoding="utf-8"))
    return {post.id: enrich(post) for post in posts}, truth["events"]


def test_every_demo_event_gets_its_geo_and_topic(synthetic):
    enriched, events = synthetic
    assert {event["key"] for event in events} == set(EXPECTED)
    for event in events:
        pairs = {(enriched[pid].geo, enriched[pid].topic) for pid in event["post_ids"]}
        assert pairs == {EXPECTED[event["key"]]}, event["key"]


def test_noise_never_gets_a_demo_pair(synthetic):
    enriched, events = synthetic
    in_events = {pid for event in events for pid in event["post_ids"]}
    demo_pairs = set(EXPECTED.values())
    leaked = [
        (post.id, post.text)
        for pid, post in enriched.items()
        if pid not in in_events and (post.geo, post.topic) in demo_pairs
    ]
    assert leaked == []


def test_enrich_does_not_mutate_and_is_stable():
    post = make_post(CASES[0][0])
    before = copy.deepcopy(post)
    first = enrich(post)
    assert post == before
    assert first is not post
    assert enrich(post) == first
    assert enrich(first) == first
