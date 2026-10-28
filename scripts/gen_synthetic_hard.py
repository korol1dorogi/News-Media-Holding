"""Hard synthetic data (task S3).

The base replay from scripts/gen_synthetic.py with three times more noise, a second fictional
city that shares street names, and tricky fakes on top: a copy without a forward that changes
a number, an archive photo that is mirrored and cropped, a denial six hours after the event and
an official post about another crash at the same place. Fixed seed: every run gives the same
files. Failures are expected and go to reports/hard/ as they are.
"""

from __future__ import annotations

import argparse
import dataclasses
import importlib.util
import json
import random
import shutil
import sys
from pathlib import Path

import yaml
from PIL import ImageOps

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "data" / "synthetic_hard"
SEED = 20261028

_spec = importlib.util.spec_from_file_location(
    "gen_synthetic", ROOT / "scripts" / "gen_synthetic.py"
)
assert _spec and _spec.loader
base = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = base  # dataclasses look the module up by name
_spec.loader.exec_module(base)

Spec, Demo, at = base.Spec, base.Demo, base.at

SECOND_CITY = "second-city"
SECOND_CHANNELS = [
    ("ch_second_public_01", "Соседний город онлайн (синтетика)"),
    ("ch_second_public_02", "Новости соседнего города (синтетика)"),
]
MIRRORED = "zarechye.jpg"

TRUTH_HEADER = """\
# Ожидаемые исходы для усложнённой синтетики (S3). Город, места и каналы вымышлены.
# Файл генерирует scripts/gen_synthetic_hard.py, руками не править.
# Базовые демо-события те же, что в data/synthetic; hard_* — хитрые фейки.
"""


def channels() -> list[dict]:
    rows = base.channels()
    rows += [
        {"id": cid, "title": title, "kind": "public", "region": SECOND_CITY}
        for cid, title in SECOND_CHANNELS
    ]
    return sorted(rows, key=lambda row: row["id"])


def fwd(tag: str, ts, channel: str, src: Spec) -> Spec:
    return Spec(tag, ts, channel, src.text, src.media, forward=src.tag)


def hard_events() -> tuple[list[Demo], list[Spec]]:
    """Tricky events with their truth, and extra posts that must not join them."""
    # 1. A copy without a forward changes the number of victims: still one source.
    scooter = Spec(
        "h_scooter_a",
        at(2, 13, 0),
        "ch_public_02",
        "ДТП на набережной: самокатчик сбил пешехода, пострадал один человек.",
    )
    copy_numbers = Demo(
        "hard_copy_numbers",
        [
            scooter,
            fwd("h_scooter_f1", at(2, 13, 6), "ch_public_06", scooter),
            Spec(
                "h_scooter_copy",
                at(2, 13, 20),
                "ch_public_05",
                "ДТП на набережной: самокатчик сбил пешехода, пострадали трое.",
            ),
        ],
        {"first_source": "h_scooter_a", "independent_sources": 1, "expected_level": "yellow"},
    )

    # 2. An archive photo, mirrored and cropped, passed off as today's flood.
    tunnel = Spec(
        "h_tunnel_a",
        at(1, 14, 0),
        "ch_public_04",
        "В Заречье затопило подземный переход, вода по пояс!",
        (MIRRORED,),
    )
    mirrored = Demo(
        "hard_mirrored_photo",
        [
            tunnel,
            fwd("h_tunnel_f1", at(1, 14, 5), "ch_district_zarechye", tunnel),
            Spec(
                "h_tunnel_b",
                at(1, 14, 25),
                "ch_reader_bot",
                "Переход в Заречье залит водой, люди идут в обход по дороге.",
                (MIRRORED,),
            ),
        ],
        {"expected_level": "red", "expected_fail": "media_archive"},
    )

    # 3. MChS denies the fire six hours later.
    house = [
        Spec(
            "h_house_a",
            at(1, 13, 0),
            "ch_public_03",
            "На Парковой улице горит жилой дом, дым валит из окон!",
        ),
        Spec(
            "h_house_b",
            at(1, 13, 12),
            "ch_public_11",
            "Пожар на Парковой: из окон пятиэтажки идёт дым, приехали пожарные.",
        ),
        Spec(
            "h_house_deny",
            at(1, 19, 10),
            "ch_mchs",
            "Информация о возгорании жилого дома на Парковой улице не подтвердилась: "
            "расчёты выезжали на ложный вызов.",
        ),
    ]
    late_denial = Demo(
        "hard_late_denial",
        house,
        {"expected_level": "red", "expected_fail": "official"},
    )

    # 4. GIBDD confirms another crash at the same square, not this one.
    minibus = Spec(
        "h_minibus_a",
        at(2, 9, 0),
        "ch_public_10",
        "ДТП на Вокзальной площади: маршрутка врезалась в столб.",
    )
    other_official = Demo(
        "hard_official_other_event",
        [
            minibus,
            fwd("h_minibus_f1", at(2, 9, 4), "ch_district_vokzal", minibus),
            fwd("h_minibus_f2", at(2, 9, 9), "ch_public_15", minibus),
        ],
        {"first_source": "h_minibus_a", "independent_sources": 1, "expected_level": "yellow"},
    )
    official_other = Spec(
        "h_minibus_gibdd",
        at(2, 8, 20),
        "ch_gibdd",
        "На Вокзальной площади столкнулись два легковых автомобиля, пострадавших нет.",
    )

    # 5. The second city has its own embankment and its own scooter crash at the same time.
    second = [
        Spec(
            "h_second_a",
            at(2, 13, 10),
            "ch_second_public_01",
            "ДТП на набережной: самокатчик врезался в ограждение, без пострадавших.",
        ),
        Spec(
            "h_second_b",
            at(2, 13, 30),
            "ch_second_public_02",
            "На набережной самокатчик врезался в ограждение, скорая не понадобилась.",
        ),
    ]
    events = [copy_numbers, mirrored, late_denial, other_official]
    return events, [official_other, *second]


def retag(specs: list[Spec], prefix: str) -> list[Spec]:
    return [
        dataclasses.replace(
            spec,
            tag=f"{prefix}{spec.tag}",
            forward=f"{prefix}{spec.forward}" if spec.forward else None,
        )
        for spec in specs
    ]


def write_images(out: Path) -> None:
    base.write_images(out)
    stadium = base.other_frames()["stadium_2024"]
    ImageOps.mirror(base.leaked_copy(stadium)).save(out / "media" / MIRRORED, quality=70)
    meta_path = out / "media" / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta[MIRRORED] = {"scene": "rain", "daylight": True}
    base.write_json(meta_path, meta)


def generate(out: Path) -> None:
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    chans = channels()
    demos = base.demo_events()
    hard, extra = hard_events()
    specs = [spec for demo in [*demos, *hard] for spec in demo.specs] + extra
    for k in range(3):
        specs += retag(base.noise(random.Random(SEED + k), base.channels()), f"n{k}_")
    posts, ids = base.assemble(specs)

    base.write_json(out / "channels.json", chans)
    lines = [json.dumps(post, ensure_ascii=False) for post in posts]
    base.write_text(out / "posts.jsonl", "\n".join(lines) + "\n")
    weather = {**base.WEATHER, SECOND_CITY: base.WEATHER[base.REGION]}
    base.write_json(out / "weather.json", weather)
    dumped = yaml.safe_dump(
        base.truth([*demos, *hard], ids),
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=None,
        width=4096,
    )
    base.write_text(out / "truth.yaml", TRUTH_HEADER + dumped)
    write_images(out)


def main() -> None:
    parser = argparse.ArgumentParser(description="Rebuild hard synthetic data from scratch.")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    generate(args.out)
    print(f"hard synthetic data written to {args.out}")


if __name__ == "__main__":
    main()
