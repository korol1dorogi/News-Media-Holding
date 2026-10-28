"""V4: dossier levels match truth.yaml and the demo scenario; todo is plain and stable."""

from datetime import datetime, timedelta
from pathlib import Path

import pytest
import yaml

from radar.core.models import Channel, Check, Event, Post
from radar.core.settings import ROOT
from radar.ingest import load_replay
from radar.verify import build_dossier, official, provenance

DATA_DIRS = [ROOT / "tests" / "fixtures" / "mini", ROOT / "data" / "synthetic"]
TS = datetime.fromisoformat("2026-10-27T10:00:00+03:00")

PUBLIC = Channel("ch_public", "Городской паблик (синтетика)", "public", "demo-city")
READER = Channel("ch_reader", "Бот читателей (синтетика)", "reader_bot", "demo-city")
MCHS = Channel("ch_mchs", "МЧС города (синтетика)", "official", "demo-city")
CHANNELS = [PUBLIC, READER, MCHS]

RUMOR = "Говорят, завод «Прибор» закрывают в декабре, всех сотрудников сокращают."


def truth_cases() -> list:
    cases = []
    for data_dir in DATA_DIRS:
        truth = yaml.safe_load((data_dir / "truth.yaml").read_text(encoding="utf-8"))
        for item in truth["events"]:
            if "expected_level" in item:
                cases.append(pytest.param(data_dir, item, id=f"{data_dir.name}-{item['key']}"))
    return cases


def make_post(
    post_id: str, channel: Channel, minutes: float, text: str, forward_from: str | None = None
) -> Post:
    return Post(
        id=post_id,
        channel_id=channel.id,
        ts=TS + timedelta(minutes=minutes),
        text=text,
        url=f"https://example.invalid/{post_id}",
        media=[],
        forward_from=forward_from,
    )


def make_event(post_ids: list[str], first_ts: datetime = TS) -> Event:
    return Event(
        id="ev_test",
        post_ids=post_ids,
        first_ts=first_ts,
        title="",
        geo=None,
        topic=None,
        scores={},
    )


def stub(name: str, status: str = "n/a", evidence: list[dict] | None = None) -> Check:
    summary = f"{name}: проверка не выполнялась." if status == "n/a" else f"{name}: {status}."
    return Check(name=name, status=status, summary=summary, evidence=evidence or [])


def dossier_for(event: Event, posts: list[Post], channels: list[Channel], fails=()):
    """Real provenance (V1) and official; media_archive and weather are stubs until V2, V3."""
    check, first_id, independent = provenance(event, posts, channels)
    checks = [
        check,
        stub("media_archive", "fail" if "media_archive" in fails else "n/a"),
        stub("weather", "fail" if "weather" in fails else "n/a"),
        official(event, posts, channels),
    ]
    return build_dossier(event, checks, first_id, independent)


@pytest.mark.parametrize(("data_dir", "item"), truth_cases())
def test_level_matches_truth(data_dir: Path, item: dict) -> None:
    channels, posts = load_replay(data_dir)
    by_id = {p.id: p for p in posts}
    first_ts = min(by_id[i].ts for i in item["post_ids"])
    fails = item.get("expected_fail", [])
    fails = [fails] if isinstance(fails, str) else fails
    dossier = dossier_for(make_event(item["post_ids"], first_ts), posts, channels, fails)
    assert dossier.level == item["expected_level"]
    if "first_source" in item:
        assert dossier.first_source_post_id == item["first_source"]


def test_fire_denied_by_mchs_is_red() -> None:
    posts = [
        make_post("f_1", PUBLIC, 0, "Горит ТЦ «Галерея», чёрный дым над Лесной улицей."),
        make_post("f_2", READER, 7, "У торгового центра на Лесной пожарные машины, все в дыму"),
        make_post(
            "f_9",
            MCHS,
            50,
            "Сообщения о возгорании в торговом центре на Лесной — фейк, вызовов не поступало.",
        ),
    ]
    dossier = dossier_for(make_event(["f_1", "f_2"]), posts, CHANNELS)
    assert dossier.level == "red"
    assert dossier.checks[-1].status == "fail"
    assert "Не подавать как факт: официальный канал опроверг, запросить комментарий" in (
        dossier.todo
    )


def rumor_posts() -> list[Post]:
    posts = [make_post("r_01", PUBLIC, 0, RUMOR)]
    for i in range(2, 9):
        posts.append(make_post(f"r_{i:02d}", READER, i, RUMOR, forward_from="r_01"))
    for i in range(9, 16):
        posts.append(make_post(f"r_{i:02d}", PUBLIC, i, RUMOR.rstrip(".") + "!"))
    return posts


def test_rumor_from_one_source_is_yellow() -> None:
    posts = rumor_posts()
    dossier = dossier_for(make_event([p.id for p in posts]), posts, CHANNELS)
    assert dossier.level == "yellow"
    assert dossier.independent_sources == 1
    assert dossier.first_source_post_id == "r_01"
    assert dossier.todo == [
        "Найти второй независимый источник или связаться с автором поста r_01",
        "Запросить комментарий у профильного ведомства",
    ]


def test_rumor_confirmed_officially_is_green() -> None:
    posts = rumor_posts()
    event = make_event([p.id for p in posts])
    confirm = make_post(
        "r_99", MCHS, 40, "Завод «Прибор» закрывают в декабре, сотрудников сокращают."
    )
    dossier = dossier_for(event, [*posts, confirm], CHANNELS)
    assert dossier.checks[-1].status == "ok"
    assert dossier.level == "green"
    assert dossier.todo == ["Найти второй независимый источник или связаться с автором поста r_01"]


def test_provenance_warn_alone_is_not_red() -> None:
    checks = [stub("provenance", "warn"), stub("official", "ok")]
    assert build_dossier(make_event(["x"]), checks, "x", 1).level == "green"
    checks = [stub("provenance", "warn"), stub("official")]
    assert build_dossier(make_event(["x"]), checks, "x", 1).level == "yellow"


def test_any_fail_is_red() -> None:
    for name in ("media_archive", "weather", "official", "provenance"):
        checks = [stub("provenance", "ok"), stub(name, "fail"), stub("official", "ok")]
        assert build_dossier(make_event(["x"]), checks, "x", 5).level == "red"


def test_missing_checks_count_as_not_applicable() -> None:
    dossier = build_dossier(make_event(["x"]), [], "x", 1)
    assert dossier.level == "yellow"
    assert dossier.todo == ["Запросить комментарий у профильного ведомства"]
    dossier = build_dossier(make_event(["x"]), [], "x", 3)
    assert dossier.level == "green"
    assert dossier.todo == []


def test_todo_follows_checks_without_duplicates() -> None:
    checks = [
        stub("provenance", "warn"),
        stub("media_archive", "fail", [{"archive_id": "arc_2024_07", "note": "архив"}]),
        stub("weather", "fail"),
        stub("custom", "warn"),
        stub("official", "n/a"),
        stub("weather", "fail"),
    ]
    dossier = build_dossier(make_event(["x"]), checks, "x", 1)
    assert dossier.level == "red"
    assert dossier.todo == [
        "Найти второй независимый источник или связаться с автором поста x",
        "Не использовать фото: оно уже было в архиве (запись arc_2024_07)",
        "Запросить у автора оригинал фото и место съёмки",
        "Проверить вручную: custom: warn.",
        "Запросить комментарий у профильного ведомства",
    ]


def test_green_dossier_does_not_ask_for_official_comment() -> None:
    checks = [stub("provenance", "ok"), stub("official")]
    dossier = build_dossier(make_event(["x"]), checks, "x", 3)
    assert dossier.level == "green"
    assert dossier.todo == []


def test_fields_passed_through() -> None:
    checks = [stub("official", "ok"), stub("provenance", "ok")]
    dossier = build_dossier(make_event(["x"]), checks, "p_1", 4)
    assert dossier.event_id == "ev_test"
    assert dossier.first_source_post_id == "p_1"
    assert dossier.independent_sources == 4
    assert dossier.checks == checks
