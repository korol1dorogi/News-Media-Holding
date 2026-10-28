"""V1: first source, independent sources and repost graph match truth.yaml."""

import dataclasses
import random
from datetime import datetime, timedelta
from pathlib import Path

import pytest
import yaml

from radar.core.models import Event, Post
from radar.core.settings import ROOT
from radar.ingest import load_replay
from radar.verify import provenance, repost_graph

DATA_DIRS = [ROOT / "tests" / "fixtures" / "mini", ROOT / "data" / "synthetic"]
TS = datetime.fromisoformat("2026-10-27T10:00:00+03:00")


def truth_cases() -> list:
    cases = []
    for data_dir in DATA_DIRS:
        truth = yaml.safe_load((data_dir / "truth.yaml").read_text(encoding="utf-8"))
        for item in truth["events"]:
            cases.append(pytest.param(data_dir, item, id=f"{data_dir.name}-{item['key']}"))
    return cases


def make_event(post_ids: list[str]) -> Event:
    return Event(
        id="ev_test", post_ids=post_ids, first_ts=TS, title="", geo=None, topic=None, scores={}
    )


def make_post(post_id: str, minutes: int, text: str, forward_from: str | None = None) -> Post:
    return Post(
        id=post_id,
        channel_id="ch_city_public",
        ts=TS + timedelta(minutes=minutes),
        text=text,
        url=f"https://example.invalid/{post_id}",
        media=[],
        forward_from=forward_from,
    )


@pytest.mark.parametrize(("data_dir", "item"), truth_cases())
def test_matches_truth(data_dir: Path, item: dict) -> None:
    channels, posts = load_replay(data_dir)
    check, first_id, independent = provenance(make_event(item["post_ids"]), posts, channels)
    if "first_source" in item:
        assert first_id == item["first_source"]
    if "independent_sources" in item:
        assert independent == item["independent_sources"]
    assert check.name == "provenance"
    assert check.summary


def test_retellings_are_independent(mini_dir: Path) -> None:
    channels, posts = load_replay(mini_dir)
    event = make_event(["m_003", "m_001", "m_002"])
    check, first_id, independent = provenance(event, posts, channels)
    assert (first_id, independent, check.status) == ("m_001", 3, "ok")


def test_rumor_is_one_source(mini_dir: Path) -> None:
    channels, posts = load_replay(mini_dir)
    event = make_event(["m_004", "m_005", "m_006"])
    check, _, _ = provenance(event, posts, channels)
    assert check.status == "warn"
    assert [e["post_id"] for e in check.evidence] == ["m_004", "m_005", "m_006"]

    graph = repost_graph(event, posts)
    assert [n["id"] for n in graph["nodes"]] == ["m_004", "m_005", "m_006"]
    assert graph["edges"] == [
        {"from": "m_004", "to": "m_005", "kind": "forward"},
        {"from": "m_004", "to": "m_006", "kind": "copy"},
    ]


def test_root_outside_event() -> None:
    posts = [
        make_post("a", 0, "Оригинальный пост про пожар на складе."),
        make_post("b", 5, "Оригинальный пост про пожар на складе.", forward_from="a"),
        make_post("c", 9, "Совсем другой текст очевидца о дыме над районом."),
    ]
    event = make_event(["b", "c"])
    _, first_id, independent = provenance(event, posts, [])
    assert (first_id, independent) == ("a", 2)
    assert repost_graph(event, posts)["edges"] == [{"from": "a", "to": "b", "kind": "forward"}]


def test_forward_cycle_and_unknown_parent_terminate() -> None:
    posts = [
        make_post("x", 0, "Первый текст про перекрытие моста.", forward_from="y"),
        make_post("y", 1, "Второй текст про ремонт трамвайных путей.", forward_from="x"),
        make_post("z", 2, "Третий текст про отключение света.", forward_from="missing"),
    ]
    _, first_id, independent = provenance(make_event(["x", "y", "z"]), posts, [])
    assert (first_id, independent) == ("x", 2)


def test_empty_event_is_na() -> None:
    check, first_id, independent = provenance(make_event(["nope"]), [], [])
    assert (check.status, first_id, independent) == ("n/a", "", 0)
    assert repost_graph(make_event([]), []) == {"nodes": [], "edges": []}


def test_deterministic_under_shuffle(mini_dir: Path) -> None:
    channels, posts = load_replay(mini_dir)
    ids = ["m_001", "m_002", "m_003", "m_004", "m_005", "m_006"]
    expected = provenance(make_event(ids), posts, channels)
    expected_graph = repost_graph(make_event(ids), posts)
    rng = random.Random(0)
    for _ in range(5):
        shuffled_posts = [dataclasses.replace(p) for p in posts]
        rng.shuffle(shuffled_posts)
        shuffled_ids = ids[:]
        rng.shuffle(shuffled_ids)
        assert provenance(make_event(shuffled_ids), shuffled_posts, channels) == expected
        assert repost_graph(make_event(shuffled_ids), shuffled_posts) == expected_graph
