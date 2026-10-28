"""V3: photo scene vs weather and post time."""

import json
import random
from datetime import datetime
from pathlib import Path

import pytest
import yaml

from radar.core.models import Event, Post
from radar.core.settings import ROOT
from radar.ingest import load_replay
from radar.verify import weather

SYNTHETIC = ROOT / "data" / "synthetic"
MINI = ROOT / "tests" / "fixtures" / "mini"

WARM_DRY = {"t_min": 16, "t_max": 18, "precip": "none"}
SNOW_DAY = {"scene": "snow", "daylight": True}
RAIN_DAY = {"scene": "rain", "daylight": True}
CLEAR_DAY = {"scene": "clear", "daylight": True}


def post(pid: str, ts: str, media: list[str], geo: str | None = None) -> Post:
    return Post(
        id=pid,
        channel_id="ch_city_public",
        ts=datetime.fromisoformat(ts),
        text="",
        url=f"https://example.invalid/{pid}",
        media=media,
        forward_from=None,
        geo=geo,
    )


def event(post_ids: list[str], geo: str | None = None) -> Event:
    return Event(
        id="ev",
        post_ids=post_ids,
        first_ts=datetime.fromisoformat("2026-10-27T00:00:00+03:00"),
        title="",
        geo=geo,
        topic=None,
        scores={},
    )


def city(record: dict, day: str = "2026-10-27", name: str = "demo-city") -> dict:
    return {name: {day: record}}


def replay(data_dir: Path) -> tuple[list[Post], dict, dict]:
    _, posts = load_replay(data_dir)
    weather_data = json.loads((data_dir / "weather.json").read_text(encoding="utf-8"))
    meta = json.loads((data_dir / "media" / "meta.json").read_text(encoding="utf-8"))
    return posts, weather_data, meta


def test_flood_matches_weather() -> None:
    posts, weather_data, meta = replay(MINI)
    check = weather(event(["m_004", "m_005", "m_006"]), posts, weather_data, meta)
    assert check.name == "weather"
    assert check.status == "ok"
    assert check.summary == "Погода на фото совпадает с данными за 27.10: дождь, +6..+11."
    assert [e["post_id"] for e in check.evidence] == ["m_004", "m_005", "m_006"]
    assert all("flood.jpg" in e["note"] for e in check.evidence)


def test_accident_without_photos_is_na() -> None:
    posts, weather_data, meta = replay(MINI)
    check = weather(event(["m_001", "m_002", "m_003"]), posts, weather_data, meta)
    assert check.status == "n/a"
    assert "нет фото" in check.summary
    assert check.evidence == []


def test_synthetic_truth() -> None:
    posts, weather_data, meta = replay(SYNTHETIC)
    truth = yaml.safe_load((SYNTHETIC / "truth.yaml").read_text(encoding="utf-8"))
    for item in truth["events"]:
        check = weather(event(item["post_ids"]), posts, weather_data, meta)
        if item.get("expected_fail") == "weather":
            assert check.status == "fail", item["key"]
        else:
            assert check.status != "fail", item["key"]


def test_snowfall_fails_with_clear_summary() -> None:
    posts = [post("s_1", "2026-10-27T12:00:00+03:00", ["snow.jpg"])]
    check = weather(event(["s_1"]), posts, city(WARM_DRY), {"snow.jpg": SNOW_DAY})
    assert check.status == "fail"
    assert check.summary == "На фото снег, а 27.10 в городе было от +16 до +18 без осадков."
    assert check.evidence == [
        {"post_id": "s_1", "note": "snow.jpg: снег на фото, а 27.10 было +16..+18, без осадков"}
    ]


def test_snow_is_fine_when_it_snowed_or_was_cold() -> None:
    posts = [post("s_1", "2026-10-27T12:00:00+03:00", ["snow.jpg"])]
    meta = {"snow.jpg": SNOW_DAY}
    snowing = city({"t_min": 1, "t_max": 3, "precip": "snow"})
    cold = city({"t_min": -4, "t_max": 2, "precip": "none"})
    assert weather(event(["s_1"]), posts, snowing, meta).status == "ok"
    assert weather(event(["s_1"]), posts, cold, meta).status == "ok"


def test_rain_without_precipitation_warns() -> None:
    posts = [post("r_1", "2026-10-27T12:00:00+03:00", ["rain.jpg"])]
    check = weather(event(["r_1"]), posts, city(WARM_DRY), {"rain.jpg": RAIN_DAY})
    assert check.status == "warn"
    assert check.summary == "На фото дождь, а осадков в этот день не было."
    assert len(check.evidence) == 1


def test_day_shot_posted_at_night_warns() -> None:
    posts = [post("d_1", "2026-10-27T23:40:00+03:00", ["street.jpg"])]
    check = weather(event(["d_1"]), posts, city(WARM_DRY), {"street.jpg": CLEAR_DAY})
    assert check.status == "warn"
    assert check.summary == "Кадр дневной, а пост опубликован в 23:40 — возможно, фото не отсюда."


def test_night_shot_posted_by_day_warns() -> None:
    posts = [post("n_1", "2026-10-27T12:00:00+03:00", ["street.jpg"])]
    meta = {"street.jpg": {"scene": "clear", "daylight": False}}
    check = weather(event(["n_1"]), posts, city(WARM_DRY), meta)
    assert check.status == "warn"
    assert "Кадр ночной" in check.summary
    assert "12:00" in check.summary


def test_fail_beats_warn_and_every_contradiction_is_evidence() -> None:
    posts = [
        post("p_1", "2026-10-27T09:00:00+03:00", ["rain.jpg"]),
        post("p_2", "2026-10-27T23:40:00+03:00", ["snow.jpg"]),
    ]
    meta = {"rain.jpg": RAIN_DAY, "snow.jpg": SNOW_DAY}
    check = weather(event(["p_1", "p_2"]), posts, city(WARM_DRY), meta)
    assert check.status == "fail"
    assert "снег" in check.summary
    assert check.evidence == [
        {"post_id": "p_1", "note": "rain.jpg: дождь на фото, а 27.10 осадков не было"},
        {"post_id": "p_2", "note": "snow.jpg: снег на фото, а 27.10 было +16..+18, без осадков"},
        {"post_id": "p_2", "note": "snow.jpg: кадр дневной, пост опубликован в 23:40"},
    ]


def test_several_warnings_in_one_file_all_listed() -> None:
    posts = [post("p_1", "2026-10-27T23:40:00+03:00", ["rain.jpg"])]
    check = weather(event(["p_1"]), posts, city(WARM_DRY), {"rain.jpg": RAIN_DAY})
    assert check.status == "warn"
    assert check.summary.startswith("На фото дождь")
    assert [e["note"] for e in check.evidence] == [
        "rain.jpg: дождь на фото, а 27.10 осадков не было",
        "rain.jpg: кадр дневной, пост опубликован в 23:40",
    ]


def test_skipped_photos_are_reported() -> None:
    posts = [
        post("p_1", "2026-10-27T12:00:00+03:00", ["snow.jpg", "unknown.jpg"]),
        post("p_2", "2026-10-28T12:00:00+03:00", ["snow.jpg"]),
    ]
    check = weather(event(["p_1", "p_2"]), posts, city(WARM_DRY), {"snow.jpg": SNOW_DAY})
    assert check.status == "fail"
    assert check.summary == (
        "На фото снег, а 27.10 в городе было от +16 до +18 без осадков. Проверено 1 из 3 фото."
    )
    assert check.evidence == [
        {"post_id": "p_1", "note": "snow.jpg: снег на фото, а 27.10 было +16..+18, без осадков"},
        {"post_id": "p_1", "note": "фото unknown.jpg не проверено: нет признаков в meta.json"},
        {"post_id": "p_2", "note": "фото snow.jpg не проверено: нет погоды за 28.10"},
    ]


def test_skipped_photos_are_reported_when_ok() -> None:
    posts = [post("p_1", "2026-10-27T12:00:00+03:00", ["a.jpg", "b.jpg"])]
    rainy = city({"t_min": 6, "t_max": 11, "precip": "rain"})
    check = weather(event(["p_1"]), posts, rainy, {"a.jpg": RAIN_DAY})
    assert check.status == "ok"
    assert check.summary.endswith(" Проверено 1 из 2 фото.")
    assert [e["note"] for e in check.evidence] == [
        "a.jpg: совпадает с погодой за 27.10 (дождь, +6..+11)",
        "фото b.jpg не проверено: нет признаков в meta.json",
    ]


def test_no_weather_for_date_is_na() -> None:
    posts = [post("s_1", "2026-10-28T12:00:00+03:00", ["snow.jpg"])]
    check = weather(event(["s_1"]), posts, city(WARM_DRY), {"snow.jpg": SNOW_DAY})
    assert check.status == "n/a"
    assert check.summary == "Нет погоды за 28.10."


def test_file_without_meta_is_na() -> None:
    posts = [post("s_1", "2026-10-27T12:00:00+03:00", ["snow.jpg"])]
    check = weather(event(["s_1"]), posts, city(WARM_DRY), {"other.jpg": SNOW_DAY})
    assert check.status == "n/a"
    assert "meta.json" in check.summary


@pytest.mark.parametrize(
    "record",
    [
        {"t_min": 16, "t_max": 18},
        {"t_max": 18, "precip": "none"},
        {"t_min": 16, "precip": "none"},
        {"t_min": "16", "t_max": 18, "precip": "none"},
        {"t_min": 16, "t_max": 18, "precip": "hail"},
        "sunny",
        None,
    ],
)
def test_malformed_weather_record_is_no_weather(record: object) -> None:
    posts = [post("s_1", "2026-10-27T12:00:00+03:00", ["snow.jpg"])]
    check = weather(event(["s_1"]), posts, city(record), {"snow.jpg": SNOW_DAY})
    assert check.status == "n/a"
    assert check.summary == "Нет погоды за 27.10."


def test_two_cities_without_geo_is_na() -> None:
    posts = [post("s_1", "2026-10-27T12:00:00+03:00", ["snow.jpg"])]
    two = {**city(WARM_DRY), **city(WARM_DRY, name="other-city")}
    check = weather(event(["s_1"]), posts, two, {"snow.jpg": SNOW_DAY})
    assert check.status == "n/a"
    assert check.summary == "Не знаю, по какому городу брать погоду."


def test_city_from_event_geo() -> None:
    posts = [post("s_1", "2026-10-27T12:00:00+03:00", ["snow.jpg"], geo="other-city")]
    two = {**city(WARM_DRY), **city({"t_min": 0, "t_max": 1, "precip": "snow"}, name="north")}
    check = weather(event(["s_1"], geo="north"), posts, two, {"snow.jpg": SNOW_DAY})
    assert check.status == "ok"


def test_city_from_first_post_geo_that_is_a_weather_key() -> None:
    posts = [
        post("s_1", "2026-10-27T11:00:00+03:00", ["snow.jpg"], geo="северный въезд"),
        post("s_2", "2026-10-27T12:00:00+03:00", ["snow.jpg"], geo="north"),
        post("s_3", "2026-10-27T13:00:00+03:00", ["snow.jpg"], geo="demo-city"),
    ]
    two = {**city(WARM_DRY), **city({"t_min": 0, "t_max": 1, "precip": "snow"}, name="north")}
    check = weather(event(["s_1", "s_2", "s_3"]), posts, two, {"snow.jpg": SNOW_DAY})
    assert check.status == "ok"


def test_street_geo_falls_back_to_the_only_city() -> None:
    posts = [post("s_1", "2026-10-27T12:00:00+03:00", ["snow.jpg"], geo="северный въезд")]
    ev = event(["s_1"], geo="северный въезд")
    check = weather(ev, posts, city(WARM_DRY), {"snow.jpg": SNOW_DAY})
    assert check.status == "fail"


def test_date_and_hour_in_post_timezone() -> None:
    # 23:30 at -05:00 is already 28.10 in UTC, but the post was published on 27.10
    posts = [post("s_1", "2026-10-27T23:30:00-05:00", ["snow.jpg"])]
    check = weather(event(["s_1"]), posts, city(WARM_DRY), {"snow.jpg": SNOW_DAY})
    assert check.status == "fail"
    assert "27.10" in check.summary
    assert "23:30" in check.evidence[1]["note"]


def test_posts_outside_event_are_ignored() -> None:
    posts = [
        post("p_1", "2026-10-27T12:00:00+03:00", ["clear.jpg"]),
        post("other", "2026-10-27T12:00:00+03:00", ["snow.jpg"]),
    ]
    meta = {"clear.jpg": CLEAR_DAY, "snow.jpg": SNOW_DAY}
    check = weather(event(["p_1"]), posts, city(WARM_DRY), meta)
    assert check.status == "ok"
    assert [e["post_id"] for e in check.evidence] == ["p_1"]


def test_input_order_does_not_matter() -> None:
    posts = [
        post("p_1", "2026-10-27T09:00:00+03:00", ["rain.jpg", "snow.jpg"]),
        post("p_2", "2026-10-27T09:00:00+03:00", ["snow.jpg"]),
        post("p_3", "2026-10-27T23:40:00+03:00", ["snow.jpg", "x.jpg"]),
        post("p_4", "2026-10-28T10:00:00+03:00", ["rain.jpg"]),
    ]
    meta = {"rain.jpg": RAIN_DAY, "snow.jpg": SNOW_DAY}
    ids = [p.id for p in posts]
    expected = weather(event(ids), posts, city(WARM_DRY), meta)
    rng = random.Random(3)
    for _ in range(10):
        shuffled_posts = rng.sample(posts, len(posts))
        shuffled_ids = rng.sample(ids, len(ids))
        assert weather(event(shuffled_ids), shuffled_posts, city(WARM_DRY), meta) == expected
