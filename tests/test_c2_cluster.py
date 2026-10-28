"""C2: every truth.yaml event is one cluster; forwards, gaps and noise behave."""

import random
from datetime import datetime, timedelta
from pathlib import Path

import pytest
import yaml

from radar.cluster import GAP, MIN_POSTS, TITLE_MAX, build_events
from radar.core.models import Post
from radar.core.settings import ROOT
from radar.ingest import load_replay
from radar.normalize import enrich

SYNTHETIC = ROOT / "data" / "synthetic"
MINI = ROOT / "tests" / "fixtures" / "mini"
T0 = datetime.fromisoformat("2026-10-27T08:00:00+03:00")


def load(data_dir: Path):
    _, posts = load_replay(data_dir)
    truth = yaml.safe_load((data_dir / "truth.yaml").read_text(encoding="utf-8"))
    return [enrich(post) for post in posts], truth["events"]


@pytest.fixture(scope="module")
def synthetic():
    posts, truth = load(SYNTHETIC)
    return posts, truth, build_events(posts)


def make_post(
    pid: str,
    minutes: float,
    text: str = "",
    geo: str | None = "северный въезд",
    topic: str | None = "ДТП",
    forward_from: str | None = None,
) -> Post:
    return Post(
        id=pid,
        channel_id="ch_test",
        ts=T0 + timedelta(minutes=minutes),
        text=text or f"Пост {pid}.",
        url=f"https://example.invalid/ch_test/{pid}",
        media=[],
        forward_from=forward_from,
        geo=geo,
        topic=topic,
    )


def assert_truth_clusters(events, truth):
    for item in truth:
        expected = set(item["post_ids"])
        overlapping = [event for event in events if set(event.post_ids) & expected]
        assert len(overlapping) == 1, (
            f"{item['key']}: posts spread over {[event.id for event in overlapping]}"
        )
        got = set(overlapping[0].post_ids)
        assert got == expected, (
            f"{item['key']}: extra {sorted(got - expected)}, missing {sorted(expected - got)}"
        )


def test_every_truth_event_is_one_cluster(synthetic):
    _, truth, events = synthetic
    assert_truth_clusters(events, truth)


def test_noise_events_exist_and_hold_no_demo_posts(synthetic):
    _, truth, events = synthetic
    demo = {pid for item in truth for pid in item["post_ids"]}
    truth_sets = [set(item["post_ids"]) for item in truth]
    noise = [event for event in events if set(event.post_ids) not in truth_sets]
    assert noise, "expected at least one noise event"
    for event in noise:
        assert not set(event.post_ids) & demo, event.id


def test_forward_is_in_the_cluster_of_its_original(synthetic):
    posts, _, events = synthetic
    event_of = {pid: event.id for event in events for pid in event.post_ids}
    forwards = [post for post in posts if post.forward_from is not None]
    assert forwards
    for post in forwards:
        assert event_of.get(post.id) == event_of.get(post.forward_from), post.id


def test_post_without_topic_never_starts_an_event(synthetic):
    posts, _, events = synthetic
    by_id = {post.id: post for post in posts}
    for event in events:
        assert by_id[event.post_ids[0]].topic is not None, event.id


def test_post_without_topic_joins_only_as_forward():
    posts = [
        make_post("a", 0),
        make_post("b", 5, topic=None),
        make_post("c", 10, forward_from="a", topic=None),
        make_post("d", 15, topic=None, geo=None),
        make_post("e", 20, forward_from="d", topic=None, geo=None),
    ]
    events = build_events(posts)
    assert [event.post_ids for event in events] == [["a", "c"]]


def test_same_key_after_a_long_pause_is_two_events():
    posts = [
        make_post("a", 0),
        make_post("b", 10),
        make_post("c", 10 + GAP.total_seconds() / 60 + 1),
        make_post("d", 20 + GAP.total_seconds() / 60 + 1),
    ]
    assert [event.post_ids for event in build_events(posts)] == [["a", "b"], ["c", "d"]]


def test_pause_of_exactly_gap_keeps_one_event():
    posts = [make_post("a", 0), make_post("b", GAP.total_seconds() / 60)]
    assert [event.post_ids for event in build_events(posts)] == [["a", "b"]]


def test_post_without_geo_joins_by_text():
    text = "Снегопад в южном районе! Всё белое, как зимой, дороги замело."
    posts = [
        make_post("a", 0, text, geo="южный район", topic="погода"),
        make_post("b", 5, text.replace("в южном районе", "у нас"), geo=None, topic="погода"),
        make_post("c", 10, "Гололед на дорогах, будьте осторожны.", geo=None, topic="погода"),
        make_post("d", 15, "Гололед на дорогах, будьте осторожны!", geo=None, topic="погода"),
    ]
    events = build_events(posts)
    assert [event.post_ids for event in events] == [["a", "b"], ["c", "d"]]
    assert events[0].geo == "южный район"
    assert events[1].geo is None


def test_single_post_cluster_is_dropped():
    assert MIN_POSTS == 2
    assert build_events([make_post("a", 0)]) == []


def test_event_fields():
    long_text = (
        "Говорят, машиностроительный завод «Прибор» в промзоне закрывают в декабре, "
        "всех сотрудников сократят. Подробностей пока нет."
    )
    posts = [
        make_post("a", 0, long_text, geo="промзона", topic="общество"),
        make_post("b", 3, long_text, geo="промзона", topic="общество", forward_from="a"),
    ]
    (event,) = build_events(posts)
    assert event.id == "ev_a"
    assert event.post_ids == ["a", "b"]
    assert event.first_ts == posts[0].ts
    assert (event.geo, event.topic) == ("промзона", "общество")
    assert event.scores == {}
    assert len(event.title) <= TITLE_MAX
    assert event.title.endswith("…")
    assert long_text.startswith(event.title[:-1].rstrip())


def test_title_from_first_post_without_forward():
    posts = [
        make_post("x", 0, "Горит ТЦ «Галерея» на Лесной улице! Чёрный дым.", forward_from="gone"),
        make_post("y", 5, "В центре задымление. Пишут про эвакуацию."),
    ]
    (event,) = build_events(posts)
    assert event.id == "ev_x"
    assert event.title == "В центре задымление"


def test_shuffled_input_gives_same_events(synthetic):
    posts, _, events = synthetic
    shuffled = posts[:]
    random.Random(0).shuffle(shuffled)
    assert build_events(shuffled) == events


def test_mini_set_events_are_clusters():
    posts, truth = load(MINI)
    by_id = {post.id: post for post in posts}
    assert {(by_id["m_001"].geo, by_id["m_001"].topic)} == {("северный въезд", "ДТП")}
    assert {(by_id["m_004"].geo, by_id["m_004"].topic)} == {("Речная улица", "ЧС")}
    assert_truth_clusters(build_events(posts), truth)
