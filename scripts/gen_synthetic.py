"""Synthetic data generator (task S1).

Rebuilds data/synthetic from scratch: channels, 48 hours of posts with the demo events
(docs/demo-scenario.md) hidden in noise, media and archive frames drawn with PIL,
weather and truth.yaml. Fixed seed and stable ordering: every run gives the same files.
The city, its places and channels are fictional (D-06).
"""

from __future__ import annotations

import argparse
import json
import random
import shutil
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "data" / "synthetic"

SEED = 20261027
TZ = timezone(timedelta(hours=3))
START = datetime(2026, 10, 27, tzinfo=TZ)
MINUTES = 48 * 60
REGION = "demo-city"

# Places of the demo events. Noise never mentions them (tests check the lower-case stems).
DEMO_PLACES = (
    "северный въезд",
    "Речная улица",
    "промзона",
    "центр",
    "ТЦ «Галерея» на Лесной улице",
    "южный район",
    "Ключевая улица",  # address of the water outage, inside the southern district
)
# Neutral places for noise, already in the prepositional case.
NEUTRAL_WHERE = (
    "на Садовой улице",
    "на Парковой улице",
    "на Школьной улице",
    "на Вокзальной площади",
    "на набережной",
    "в микрорайоне Сосновый",
    "в Заречье",
)

OFFICIAL = [
    ("ch_gibdd", "ГИБДД города (синтетика)"),
    ("ch_mchs", "МЧС города (синтетика)"),
    ("ch_vodokanal", "Водоканал города (синтетика)"),
    ("ch_admin", "Администрация города (синтетика)"),
]
PUBLIC_TITLES = [
    "Городской паблик",
    "Город онлайн",
    "Новости города 24",
    "Подслушано в городе",
    "Что случилось в городе",
    "Город сейчас",
    "Срочно. Город",
    "Наш город",
    "Инцидент. Город",
    "Городская афиша",
    "Типичный горожанин",
    "Город на связи",
    "Горожане пишут",
    "Новости без фильтров",
    "Городской вестник онлайн",
    "Город и люди",
    "Пульс города",
    "Городской дозор",
    "Город за минуту",
    "Объявления города",
    "Городские истории",
    "Город. Главное",
]
DISTRICTS = [
    ("north", "Северная сторона"),
    ("south", "Южный район"),
    ("center", "Центр"),
    ("river", "Приречье"),
    ("sosnovy", "Сосновый"),
    ("zarechye", "Заречье"),
    ("vokzal", "Привокзальный"),
    ("park", "Парковый"),
    ("school", "Школьный квартал"),
    ("sadovy", "Садовый"),
    ("embankment", "Набережная"),
]
OUTLETS = [
    ("ch_outlet_vestnik", "Газета «Городской вестник» (синтетика)"),
    ("ch_outlet_echo", "Радио «Эхо города» (синтетика)"),
]


def channels() -> list[dict]:
    rows = [{"id": cid, "title": title, "kind": "official"} for cid, title in OFFICIAL]
    rows.append({"id": "ch_reader_bot", "title": "Бот читателей (синтетика)", "kind": "reader_bot"})
    rows += [{"id": cid, "title": title, "kind": "outlet"} for cid, title in OUTLETS]
    rows += [
        {"id": f"ch_public_{i:02d}", "title": f"{title} (синтетика)", "kind": "public"}
        for i, title in enumerate(PUBLIC_TITLES, start=1)
    ]
    rows += [
        {"id": f"ch_district_{key}", "title": f"{title}: новости (синтетика)", "kind": "public"}
        for key, title in DISTRICTS
    ]
    for row in rows:
        row["region"] = REGION
    return sorted(rows, key=lambda row: row["id"])


@dataclass
class Spec:
    """A post before ids are assigned. forward is the tag of the forwarded post."""

    tag: str
    ts: datetime
    channel: str
    text: str
    media: tuple[str, ...] = ()
    forward: str | None = None


def at(day: int, hour: int, minute: int) -> datetime:
    """day 1 is 27.10, day 2 is 28.10."""
    return START + timedelta(days=day - 1, hours=hour, minutes=minute)


# --- demo events -------------------------------------------------------------------------------

DTP = {
    "a": "ДТП на северном въезде: автобус столкнулся с грузовиком, трое пострадавших.",
    "b": "Стою в пробке на северном въезде, впереди авария с автобусом, скорая уже приехала.",
    "c": (
        "Северный въезд встал: рейсовый автобус и фура не разъехались у поворота "
        "на объездную, работают медики."
    ),
    "d": (
        "Очевидцы пишут, что грузовик не успел затормозить и ударил автобус прямо "
        "на северном въезде в город. Есть раненые."
    ),
    "e": (
        "На северном въезде столкнулись автобус и грузовик. Пострадали три человека, "
        "движение затруднено. Просим водителей объезжать участок."
    ),
    "f": (
        "Утренняя пробка на северном въезде — из-за аварии: грузовик въехал "
        "в пассажирский автобус, в больницу увезли троих."
    ),
}
FLOOD = "Наводнение на Речной улице прямо сейчас, вода по колено! Машины стоят в воде."
RUMOR = (
    "Говорят, машиностроительный завод «Прибор» в промзоне закрывают в декабре, "
    "всех сотрудников сократят."
)
# Copies without a forward: an emoji or one or two changed characters (similarity >= 0.9).
RUMOR_COPIES = [
    RUMOR + " 😱",
    RUMOR[:-1],
    RUMOR.replace("Говорят", "говорят"),
    RUMOR + " 😢",
    "‼️ " + RUMOR,
    "⚡️ " + RUMOR,
    RUMOR + " 😡",
]
MALL = {
    "m1": "Горит ТЦ «Галерея» на Лесной улице! Чёрный дым видно со всего центра.",
    "m2": "У торгового центра «Галерея» на Лесной пожарные машины, людей выводят на улицу.",
    "m3": "В центре задымление: пишут, что в ТЦ «Галерея» на Лесной улице пожар и эвакуация.",
    "deny": (
        "Информация о пожаре в ТЦ «Галерея» на Лесной улице не соответствует "
        "действительности. Пожарные расчёты выезжали на место, возгорания нет, "
        "торговый центр работает в обычном режиме."
    ),
}
SNOW = {
    "s1": "Снегопад в южном районе! Всё белое, как зимой, дороги замело.",
    "s2": "Южный район засыпало снегом: во дворах сугробы, машины под белыми шапками.",
}
WATER = {
    "v": (
        "Южный район: 27 октября с 9:00 до 18:00 не будет холодной воды в 12 домах "
        "на Ключевой улице (дома 2–24). Причина — ремонт магистрального водопровода."
    ),
    "w": (
        "Жителям южного района: на Ключевой улице сегодня отключают воду, без воды "
        "останутся 12 домов, дать обещают к 18:00."
    ),
    "x": "У нас на Ключевой, дом 14, воды уже нет. Сказали, что включат только в 18:00.",
}


@dataclass
class Demo:
    key: str
    specs: list[Spec]
    truth: dict  # truth.yaml fields; first_source is a tag here


def demo_events() -> list[Demo]:
    """Demo events. Official posts stay out of 27.10 09:30 — 28.10 11:30 (rumor window, V4)."""

    def fwd(tag: str, ts: datetime, channel: str, src: Spec) -> Spec:
        return Spec(tag, ts, channel, src.text, src.media, forward=src.tag)

    water_v = Spec("water_v", at(1, 7, 0), "ch_vodokanal", WATER["v"])
    water = [
        water_v,
        fwd("water_v_f1", at(1, 7, 12), "ch_district_south", water_v),
        Spec("water_w", at(1, 7, 25), "ch_public_08", WATER["w"]),
        Spec("water_x", at(1, 7, 48), "ch_reader_bot", WATER["x"]),
    ]

    dtp_a = Spec("dtp_a", at(1, 8, 12), "ch_public_01", DTP["a"], ("dtp.jpg",))
    dtp_d = Spec("dtp_d", at(1, 8, 34), "ch_public_09", DTP["d"])
    dtp_e = Spec("dtp_e", at(1, 8, 40), "ch_gibdd", DTP["e"])
    dtp = [
        dtp_a,
        fwd("dtp_a_f1", at(1, 8, 15), "ch_public_07", dtp_a),
        Spec("dtp_b", at(1, 8, 20), "ch_reader_bot", DTP["b"]),
        fwd("dtp_a_f2", at(1, 8, 24), "ch_public_13", dtp_a),
        Spec("dtp_c", at(1, 8, 27), "ch_district_north", DTP["c"]),
        dtp_d,
        fwd("dtp_d_f1", at(1, 8, 38), "ch_public_19", dtp_d),
        dtp_e,
        fwd("dtp_e_f1", at(1, 8, 45), "ch_public_03", dtp_e),
        Spec("dtp_f", at(1, 8, 51), "ch_public_12", DTP["f"]),
    ]

    flood_0 = Spec("flood_0", at(1, 10, 5), "ch_public_04", FLOOD, ("flood.jpg",))
    flood = [
        flood_0,
        fwd("flood_f1", at(1, 10, 9), "ch_reader_bot", flood_0),
        fwd("flood_f2", at(1, 10, 20), "ch_district_river", flood_0),
        fwd("flood_f3", at(1, 10, 41), "ch_public_16", flood_0),
        Spec("flood_c1", at(1, 11, 2), "ch_public_11", FLOOD[:-1] + " 😨", ("flood.jpg",)),
        Spec("flood_c2", at(1, 11, 30), "ch_public_20", FLOOD.replace("!", "!!"), ("flood.jpg",)),
    ]

    rumor_0 = Spec("rumor_0", at(1, 11, 30), "ch_public_10", RUMOR)
    rumor = [rumor_0]
    fwd_channels = ["ch_public_02", "ch_public_05", "ch_reader_bot", "ch_public_14"]
    fwd_channels += ["ch_district_sosnovy", "ch_public_17", "ch_public_21"]
    copy_channels = ["ch_public_06", "ch_public_15", "ch_district_zarechye", "ch_public_18"]
    copy_channels += ["ch_public_22", "ch_district_vokzal", "ch_public_06"]
    for i, channel in enumerate(fwd_channels, start=1):
        ts = at(1, 11, 30) + timedelta(minutes=17 * i)
        rumor.append(fwd(f"rumor_f{i}", ts, channel, rumor_0))
    for i, (channel, text) in enumerate(zip(copy_channels, RUMOR_COPIES, strict=True), start=1):
        rumor.append(Spec(f"rumor_c{i}", at(1, 13, 10) + timedelta(minutes=58 * i), channel, text))

    snow_1 = Spec("snow_1", at(2, 12, 40), "ch_public_05", SNOW["s1"], ("snow.jpg",))
    snow = [
        snow_1,
        fwd("snow_f1", at(2, 12, 52), "ch_public_17", snow_1),
        Spec("snow_2", at(2, 13, 10), "ch_district_south", SNOW["s2"], ("snow.jpg",)),
    ]

    mall_1 = Spec("mall_1", at(2, 15, 0), "ch_public_02", MALL["m1"])
    mall = [
        mall_1,
        Spec("mall_2", at(2, 15, 8), "ch_reader_bot", MALL["m2"]),
        fwd("mall_f1", at(2, 15, 12), "ch_public_14", mall_1),
        Spec("mall_3", at(2, 15, 25), "ch_district_center", MALL["m3"]),
        Spec("mall_deny", at(2, 16, 10), "ch_mchs", MALL["deny"]),
    ]

    return [
        Demo(
            "dtp_entry",
            dtp,
            {"first_source": "dtp_a", "independent_sources": 6, "expected_level": "green"},
        ),
        Demo(
            "flood_old_photo",
            flood,
            {
                "first_source": "flood_0",
                "independent_sources": 1,
                "expected_level": "red",
                "expected_fail": "media_archive",
            },
        ),
        Demo(
            "plant_rumor",
            rumor,
            {"first_source": "rumor_0", "independent_sources": 1, "expected_level": "yellow"},
        ),
        Demo(
            "mall_fire",
            mall,
            {
                "first_source": "mall_1",
                "independent_sources": 4,
                "expected_level": "red",
                "expected_fail": "official",
            },
        ),
        Demo(
            "snowfall",
            snow,
            {
                "first_source": "snow_1",
                "independent_sources": 2,
                "expected_level": "red",
                "expected_fail": "weather",
            },
        ),
        Demo(
            "water_outage",
            water,
            {
                "first_source": "water_v",
                "independent_sources": 3,
                "expected_level": "green",
                "inject_error": True,
            },
        ),
    ]


# --- noise -------------------------------------------------------------------------------------

PRODUCTS = ["зимние шины", "пластиковые окна", "кухонные гарнитуры", "детские куртки", "ноутбуки"]
SHOWS = [
    "концерт духового оркестра",
    "ярмарка мёда",
    "спектакль детского театра",
    "мастер-класс по керамике",
    "забег на пять километров",
    "выставка рисунков школьников",
]
ISSUES = [
    "не горят фонари",
    "не вывезли мусор",
    "сломали лавочку у подъезда",
    "перекопали тротуар и бросили",
    "громко играет музыка по ночам",
    "потерялся рыжий кот, откликается на Барсик",
    "нашли ключи с брелоком-мишкой",
]
WORKS = ["тротуара", "детской площадки", "остановки", "освещения", "газона у сквера"]
SIGNS = ["Овен", "Телец", "Близнецы", "Рак", "Лев", "Дева", "Весы", "Скорпион", "Стрелец"]
ADVICE = [
    "день для новых знакомств",
    "не спешите с покупками",
    "позвоните старому другу",
    "отложите важные решения",
    "хорошее время для прогулки",
]
DAYS = ["в субботу", "в воскресенье", "1 ноября", "2 ноября", "в выходные"]
TIMES = ["10:00", "12:00", "15:00", "18:00", "19:30"]

NOISE_TEMPLATES = [
    "Скидки до {pct}% на {product} {where}. Реклама.",
    "Открылся новый магазин {where}: {product} по честным ценам. Реклама.",
    "{day} в {time} {where} — {show}. Вход свободный.",
    "Афиша: {show} {where}, {day} в {time}. Приходите всей семьёй!",
    "Соседи, {where} опять {issue}. Кто знает, куда писать?",
    "{where} {issue}. Пишите в комментарии, если что-то знаете.",
    "{day} {where} плановый ремонт {work}, возможны неудобства.",
    "Гороскоп на завтра: {sign} — {advice}.",
    "Гороскоп дня. {sign}: {advice}, а вечером {advice2}.",
    "Опрос: где лучше гулять с детьми — {where} или {where2}?",
    "Футбольная команда «Звезда» сыграет {day} в {time}, стадион {where}.",
]
OFFICIAL_NOISE = {
    "ch_gibdd": [
        "{day} {where} ремонт дорожного покрытия, просим водителей заранее планировать маршрут.",
        "Напоминаем пешеходам: в тёмное время суток нужны световозвращающие элементы.",
        "Сотрудники Госавтоинспекции проводят рейд «Ремень безопасности» {where}.",
    ],
    "ch_mchs": [
        "Напоминаем: не оставляйте обогреватели включёнными без присмотра.",
        "Учения спасателей {day} {where}, просим не беспокоиться.",
        "Как подготовить дом к холодам: проверьте печи и дымоходы заранее.",
    ],
    "ch_vodokanal": [
        "{day} {where} плановая промывка сетей, вода может быть мутной пару часов.",
        "Передайте показания счётчиков до 25 числа через личный кабинет.",
    ],
    "ch_admin": [
        "Глава администрации проведёт приём граждан {day} в {time}.",
        "Субботник {where} {day}: инвентарь выдадим на месте.",
        "Открыт приём заявок на благоустройство дворов на следующий год.",
    ],
}
# Official noise only outside the rumor window, so V4 finds no official post for the rumor.
OFFICIAL_SLOTS = [(at(1, 6, 0), at(1, 9, 20)), (at(2, 11, 40), at(2, 22, 0))]

N_NOISE = 440
N_NOISE_FORWARDS = 16
N_OFFICIAL_NOISE = 32


def fill(template: str, rng: random.Random) -> str:
    where, where2 = rng.sample(NEUTRAL_WHERE, 2)
    advice, advice2 = rng.sample(ADVICE, 2)
    text = template.format(
        pct=rng.choice([10, 15, 20, 30, 50]),
        product=rng.choice(PRODUCTS),
        where=where,
        where2=where2,
        day=rng.choice(DAYS),
        time=rng.choice(TIMES),
        show=rng.choice(SHOWS),
        issue=rng.choice(ISSUES),
        work=rng.choice(WORKS),
        sign=rng.choice(SIGNS),
        advice=advice,
        advice2=advice2,
    )
    return text[0].upper() + text[1:]


def noise_minute(rng: random.Random) -> int:
    """Minute of the 48 hours, three times rarer at night (00–06)."""
    while True:
        minute = rng.randrange(MINUTES)
        if (minute // 60) % 24 >= 7 or rng.random() < 0.33:
            return minute


def noise(rng: random.Random, chans: list[dict]) -> list[Spec]:
    posting = [c["id"] for c in chans if c["kind"] != "official"]
    specs = []
    for i in range(N_NOISE):
        ts = START + timedelta(minutes=noise_minute(rng))
        text = fill(rng.choice(NOISE_TEMPLATES), rng)
        specs.append(Spec(f"noise_{i:03d}", ts, rng.choice(posting), text))

    for i in range(N_OFFICIAL_NOISE):
        channel = sorted(OFFICIAL_NOISE)[i % len(OFFICIAL_NOISE)]
        lo, hi = rng.choice(OFFICIAL_SLOTS)
        ts = lo + timedelta(minutes=rng.randrange(int((hi - lo).total_seconds() // 60)))
        text = fill(rng.choice(OFFICIAL_NOISE[channel]), rng)
        specs.append(Spec(f"official_{i:03d}", ts, channel, text))

    originals = sorted(specs, key=lambda s: s.tag)
    for i in range(N_NOISE_FORWARDS):
        src = rng.choice(originals)
        delay = timedelta(minutes=rng.randrange(3, 90))
        if src.ts + delay >= START + timedelta(minutes=MINUTES):
            continue
        channel = rng.choice([c for c in posting if c != src.channel])
        specs.append(Spec(f"noise_fwd_{i:03d}", src.ts + delay, channel, src.text, forward=src.tag))
    return specs


# --- assembly ----------------------------------------------------------------------------------


def assemble(specs: list[Spec]) -> tuple[list[dict], dict[str, str]]:
    """Posts sorted by (ts, channel), ids p_0001…, and a tag -> id map."""
    ordered = sorted(enumerate(specs), key=lambda item: (item[1].ts, item[1].channel, item[0]))
    ids = {spec.tag: f"p_{n:04d}" for n, (_, spec) in enumerate(ordered, start=1)}
    assert len(ids) == len(specs), "duplicate tags"
    per_channel: dict[str, int] = {}
    posts = []
    for _, spec in ordered:
        n = per_channel[spec.channel] = per_channel.get(spec.channel, 0) + 1
        forward = ids[spec.forward] if spec.forward else None
        assert forward is None or forward < ids[spec.tag], f"{spec.tag}: forward to a later post"
        posts.append(
            {
                "id": ids[spec.tag],
                "channel_id": spec.channel,
                "ts": spec.ts.isoformat(),
                "text": spec.text,
                "url": f"https://example.invalid/{spec.channel}/{n}",
                "media": list(spec.media),
                "forward_from": forward,
            }
        )
    return posts, ids


def truth(demos: list[Demo], ids: dict[str, str]) -> dict:
    events = []
    for demo in demos:
        item = {"key": demo.key, "post_ids": sorted(ids[s.tag] for s in demo.specs)}
        for field, value in demo.truth.items():
            item[field] = ids[value] if field == "first_source" else value
        events.append(item)
    return {"events": events}


# --- images ------------------------------------------------------------------------------------

W, H = 320, 240


def gradient(draw: ImageDraw.ImageDraw, top: tuple, bottom: tuple, y0: int = 0, y1: int = H):
    for y in range(y0, y1):
        k = (y - y0) / max(1, y1 - y0 - 1)
        color = tuple(round(a + (b - a) * k) for a, b in zip(top, bottom, strict=True))
        draw.line([(0, y), (W - 1, y)], fill=color)


def flood_frame() -> Image.Image:
    """Rainy street under water: houses, trees, a sunk car and ripples."""
    rng = random.Random(SEED + 1)
    img = Image.new("RGB", (W, H))
    draw = ImageDraw.Draw(img)
    gradient(draw, (110, 120, 135), (175, 180, 185), 0, 120)
    draw.rectangle([10, 50, 95, 150], fill=(160, 80, 60))
    draw.polygon([(5, 52), (52, 15), (100, 52)], fill=(90, 40, 35))
    draw.rectangle([115, 30, 190, 150], fill=(215, 205, 175))
    draw.rectangle([210, 70, 300, 150], fill=(120, 140, 170))
    for x, y in [(25, 70), (60, 70), (130, 50), (160, 50), (130, 95), (160, 95), (230, 90)]:
        draw.rectangle([x, y, x + 18, y + 22], fill=(240, 225, 140))
    draw.ellipse([292, 40, 318, 120], fill=(50, 95, 55))
    draw.line([(200, 30), (200, 160)], fill=(30, 30, 30), width=4)
    gradient(draw, (75, 95, 105), (40, 60, 75), 140, H)
    for _ in range(60):
        x, y = rng.randrange(W), rng.randrange(145, H)
        draw.line([(x, y), (x + rng.randrange(10, 40), y)], fill=(130, 150, 160), width=1)
    draw.rectangle([140, 150, 230, 175], fill=(170, 30, 30))
    draw.rectangle([155, 135, 210, 152], fill=(140, 25, 25))
    return img


def snow_frame() -> Image.Image:
    """Daylight snowfall: white yard, snowy roofs, dark trunks and flakes."""
    rng = random.Random(SEED + 2)
    img = Image.new("RGB", (W, H))
    draw = ImageDraw.Draw(img)
    gradient(draw, (205, 210, 220), (240, 242, 245), 0, 150)
    draw.rectangle([0, 150, W, H], fill=(250, 250, 252))
    draw.rectangle([180, 60, 300, 160], fill=(150, 150, 160))
    draw.polygon([(170, 62), (240, 25), (310, 62)], fill=(255, 255, 255))
    for x in (40, 95):
        draw.rectangle([x, 70, x + 8, 175], fill=(60, 50, 45))
        draw.ellipse([x - 30, 40, x + 38, 100], fill=(235, 238, 240))
    draw.ellipse([120, 160, 190, 200], fill=(225, 228, 235))
    for _ in range(400):
        x, y = rng.randrange(W), rng.randrange(H)
        draw.ellipse([x, y, x + 2, y + 2], fill=(255, 255, 255))
    return img


def dtp_frame() -> Image.Image:
    """Road in perspective in the rain: a yellow bus and a truck at an angle."""
    img = Image.new("RGB", (W, H))
    draw = ImageDraw.Draw(img)
    gradient(draw, (95, 100, 110), (140, 145, 150), 0, 100)
    draw.rectangle([0, 100, W, H], fill=(85, 120, 70))
    draw.polygon([(140, 100), (180, 100), (W, H), (0, H)], fill=(60, 60, 65))
    draw.line([(160, 100), (160, H)], fill=(230, 230, 230), width=3)
    draw.polygon([(30, 150), (150, 130), (160, 190), (40, 215)], fill=(235, 190, 30))
    draw.polygon([(170, 140), (290, 160), (285, 215), (165, 195)], fill=(40, 70, 150))
    for x in range(0, W, 16):
        draw.line([(x, 0), (x - 8, 90)], fill=(160, 165, 175), width=1)
    return img


def other_frames() -> dict[str, Image.Image]:
    """Unrelated archive frames: nothing like the event photos."""
    frames = {}

    img = Image.new("RGB", (W, H), (10, 12, 30))
    draw = ImageDraw.Draw(img)
    for x in range(0, W, 40):
        draw.rectangle([x + 5, 60 + (x % 80), x + 35, H], fill=(25, 25, 45))
        for y in range(80 + (x % 80), H - 10, 20):
            draw.rectangle([x + 10, y, x + 18, y + 8], fill=(240, 200, 90))
    frames["night_city_2023"] = img

    img = Image.new("RGB", (W, H))
    draw = ImageDraw.Draw(img)
    gradient(draw, (60, 140, 230), (200, 230, 250), 0, 110)
    gradient(draw, (190, 160, 60), (120, 90, 30), 110, H)
    draw.ellipse([230, 15, 290, 75], fill=(255, 235, 120))
    frames["field_2022"] = img

    img = Image.new("RGB", (W, H), (240, 240, 235))
    draw = ImageDraw.Draw(img)
    for i, color in enumerate([(200, 30, 30), (30, 160, 60), (40, 60, 200), (220, 180, 20)]):
        draw.ellipse([20 + i * 70, 40 + (i % 2) * 90, 90 + i * 70, 110 + (i % 2) * 90], fill=color)
    frames["poster_2025"] = img

    img = Image.new("RGB", (W, H))
    draw = ImageDraw.Draw(img)
    for row in range(0, H, 30):
        for col in range(0, W, 30):
            dark = (row // 30 + col // 30) % 2
            color = (40, 40, 40) if dark else (220, 210, 190)
            draw.rectangle([col, row, col + 29, row + 29], fill=color)
    frames["interior_2021"] = img

    img = Image.new("RGB", (W, H))
    draw = ImageDraw.Draw(img)
    for i in range(8):
        shade = (i * 30, 255 - i * 30, 128)
        draw.polygon([(0, i * 30), (W, i * 30 + 60), (W, i * 30 + 90), (0, i * 30 + 30)], shade)
    frames["stadium_2024"] = img
    return frames


ARCHIVE = [
    ("arc_field_2022", "field_2022.png", "2022-08-14T16:20:00+03:00", "Городской паблик"),
    ("arc_flood_2024", "flood_2024.png", "2024-10-20T09:00:00+03:00", "Городской паблик"),
    ("arc_interior_2021", "interior_2021.png", "2021-03-02T11:00:00+03:00", "Город онлайн"),
    ("arc_night_city_2023", "night_city_2023.png", "2023-12-31T23:40:00+03:00", "Наш город"),
    ("arc_poster_2025", "poster_2025.png", "2025-05-09T10:00:00+03:00", "Городская афиша"),
    ("arc_stadium_2024", "stadium_2024.png", "2024-06-01T18:30:00+03:00", "Пульс города"),
]
MEDIA_META = {
    "dtp.jpg": {"scene": "rain", "daylight": True},
    "flood.jpg": {"scene": "rain", "daylight": True},
    "snow.jpg": {"scene": "snow", "daylight": True},
}
WEATHER = {
    REGION: {
        "2026-10-26": {"t_min": 7, "t_max": 12, "precip": "none"},
        "2026-10-27": {"t_min": 6, "t_max": 11, "precip": "rain"},
        "2026-10-28": {"t_min": 16, "t_max": 18, "precip": "none"},
    }
}


def leaked_copy(img: Image.Image) -> Image.Image:
    """Centre crop of 85%, downscaled; saved later as JPEG q70."""
    w, h = round(W * 0.85), round(H * 0.85)
    x, y = (W - w) // 2, (H - h) // 2
    return img.crop((x, y, x + w, y + h)).resize((240, 180), Image.Resampling.LANCZOS)


def write_images(out: Path) -> None:
    media, archive = out / "media", out / "archive"
    media.mkdir(parents=True)
    archive.mkdir(parents=True)

    flood = flood_frame()
    flood.save(archive / "flood_2024.png", optimize=False)
    for name, img in other_frames().items():
        img.save(archive / f"{name}.png", optimize=False)
    leaked_copy(flood).save(media / "flood.jpg", quality=70)
    snow_frame().save(media / "snow.jpg", quality=85)
    dtp_frame().save(media / "dtp.jpg", quality=85)

    index = [
        {"id": aid, "path": path, "published_at": ts, "source": f"{src} (синтетика), архив"}
        for aid, path, ts, src in ARCHIVE
    ]
    write_json(archive / "index.json", index)
    write_json(media / "meta.json", MEDIA_META)


# --- output ------------------------------------------------------------------------------------


def write_text(path: Path, text: str) -> None:
    """UTF-8 with LF on every OS, so committed files match a fresh run."""
    path.write_text(text, encoding="utf-8", newline="\n")


def write_json(path: Path, data: object) -> None:
    write_text(path, json.dumps(data, ensure_ascii=False, indent=2) + "\n")


TRUTH_HEADER = """\
# Ожидаемые исходы демо-событий. Данные синтетические: город, места и каналы вымышлены.
# Файл генерирует scripts/gen_synthetic.py, руками не править.
# post_ids — все посты события, включая пересылки и копии.
"""


def generate(out: Path) -> None:
    rng = random.Random(SEED)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    chans = channels()
    demos = demo_events()
    specs = [spec for demo in demos for spec in demo.specs] + noise(rng, chans)
    posts, ids = assemble(specs)

    write_json(out / "channels.json", chans)
    lines = [json.dumps(post, ensure_ascii=False) for post in posts]
    write_text(out / "posts.jsonl", "\n".join(lines) + "\n")
    write_json(out / "weather.json", WEATHER)
    dumped = yaml.safe_dump(
        truth(demos, ids), allow_unicode=True, sort_keys=False, default_flow_style=None, width=4096
    )
    write_text(out / "truth.yaml", TRUTH_HEADER + dumped)
    write_images(out)


def main() -> None:
    parser = argparse.ArgumentParser(description="Rebuild synthetic data from scratch.")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    generate(args.out)
    print(f"synthetic data written to {args.out}")


if __name__ == "__main__":
    main()
