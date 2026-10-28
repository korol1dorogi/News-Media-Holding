"""C3: noise ranks below demo events, mash and life orders differ, score is sane."""

import random
from datetime import datetime, timedelta

import pytest
import yaml

from radar.cluster import build_events
from radar.core.models import Event, Post
from radar.core.settings import ROOT
from radar.ingest import load_replay
from radar.normalize import enrich
from radar.pipeline import OUTLETS, PROFILES_DIR, load_profiles
from radar.score import DEFAULT_WEIGHTS, score

SYNTHETIC = ROOT / "data" / "synthetic"
T0 = datetime.fromisoformat("2026-10-27T08:00:00+03:00")
MARGIN = 0.05


@pytest.fixture(scope="module")
def profiles():
    return load_profiles(PROFILES_DIR)


@pytest.fixture(scope="module")
def synthetic():
    _, posts = load_replay(SYNTHETIC)
    posts = [enrich(post) for post in posts]
    truth = yaml.safe_load((SYNTHETIC / "truth.yaml").read_text(encoding="utf-8"))["events"]
    truth_ids = [set(item["post_ids"]) for item in truth]
    demo, noise = [], []
    for event in build_events(posts):
        is_demo = any(set(event.post_ids) & ids for ids in truth_ids)
        (demo if is_demo else noise).append(event)
    return posts, demo, noise


def ranking(events, posts, profile):
    scored = [(score(event, posts, profile), event.id) for event in events]
    return [event_id for _, event_id in sorted(scored, key=lambda item: (-item[0], item[1]))]


def make_post(pid, minutes=0.0, channel="ch_a", media=None):
    return Post(
        id=pid,
        channel_id=channel,
        ts=T0 + timedelta(minutes=minutes),
        text=f"Пост {pid}.",
        url=f"https://example.invalid/{channel}/{pid}",
        media=media or [],
        forward_from=None,
        geo="северный въезд",
        topic="ДТП",
    )


def make_event(posts, topic="ДТП", geo="северный въезд"):
    return Event(
        id="ev_test",
        post_ids=[post.id for post in posts],
        first_ts=min(post.ts for post in posts) if posts else T0,
        title="Тест",
        geo=geo,
        topic=topic,
        scores={},
    )


def test_profiles_exist_for_every_outlet(profiles):
    for outlet in OUTLETS:
        assert profiles[outlet].get("weights"), outlet
        assert profiles[outlet].get("topics"), outlet


def test_synthetic_has_demo_and_noise(synthetic):
    _, demo, noise = synthetic
    assert demo
    assert noise


@pytest.mark.parametrize("outlet", OUTLETS)
def test_noise_below_every_demo_event(synthetic, profiles, outlet):
    posts, demo, noise = synthetic
    lowest_demo = min(score(event, posts, profiles[outlet]) for event in demo)
    for event in noise:
        value = score(event, posts, profiles[outlet])
        assert value + MARGIN <= lowest_demo, f"{outlet}: {event.id} {value} vs {lowest_demo}"


def test_mash_and_life_orders_differ(synthetic, profiles):
    posts, demo, noise = synthetic
    events = demo + noise
    mash = ranking(events, posts, profiles["mash"])
    life = ranking(events, posts, profiles["life"])
    assert mash != life
    assert mash[0] != life[0]


def test_scores_in_unit_range(synthetic, profiles):
    posts, demo, noise = synthetic
    for profile in [*profiles.values(), {}]:
        for event in demo + noise:
            assert 0.0 <= score(event, posts, profile) <= 1.0


def test_empty_profile_uses_default_weights():
    posts = [make_post("p1", media=["a.jpg"])]
    event = make_event(posts)
    explicit = {"weights": DEFAULT_WEIGHTS}
    assert 0.0 < score(event, posts, {}) <= 1.0
    assert score(event, posts, {}) == score(event, posts, explicit)


def test_zero_weights_fall_back_to_defaults():
    posts = [make_post("p1")]
    event = make_event(posts)
    zero = {"weights": {name: 0 for name in DEFAULT_WEIGHTS}}
    assert score(event, posts, zero) == score(event, posts, {})


def test_more_channels_never_lower():
    profile = {"weights": {"reach": 1}}
    few = [make_post(f"p{i}", minutes=i, channel=f"ch_{i % 2}") for i in range(4)]
    many = [make_post(f"p{i}", minutes=i, channel=f"ch_{i}") for i in range(4)]
    assert score(make_event(many), many, profile) > score(make_event(few), few, profile)
    for profile in ({}, {"weights": DEFAULT_WEIGHTS}):
        assert score(make_event(many), many, profile) >= score(make_event(few), few, profile)


def test_photo_never_lower():
    plain = [make_post("p1"), make_post("p2", minutes=5, channel="ch_b")]
    photo = [make_post("p1"), make_post("p2", minutes=5, channel="ch_b", media=["x.jpg"])]
    assert score(make_event(photo), photo, {}) > score(make_event(plain), plain, {})


def test_faster_growth_never_lower():
    fast = [make_post(f"p{i}", minutes=10 * i, channel=f"ch_{i}") for i in range(4)]
    slow = [make_post(f"p{i}", minutes=90 * i, channel=f"ch_{i}") for i in range(4)]
    assert score(make_event(fast), fast, {}) > score(make_event(slow), slow, {})


def test_unknown_topic_uses_default_topic():
    posts = [make_post("p1")]
    event = make_event(posts, topic="спорт")
    profile = {"weights": {"topic": 1}, "topics": {"ДТП": 1.0}, "default_topic": 0.25}
    assert score(event, posts, profile) == 0.25
    assert score(event, posts, {"weights": {"topic": 1}}) == 0.0


def test_unknown_geo_uses_default_geo():
    posts = [make_post("p1")]
    event = make_event(posts, geo="Садовая улица")
    profile = {"weights": {"geo": 1}, "geo": {"центр": 1.0}, "default_geo": 0.4}
    assert score(event, posts, profile) == 0.4


def test_empty_event_scores_zero(profiles):
    other = [make_post("p1")]
    event = make_event([])
    assert score(event, other, profiles["mash"]) == 0.0
    assert score(event, [], {}) == 0.0


def test_only_event_posts_count():
    own = [make_post("p1")]
    noise = [make_post(f"n{i}", channel=f"ch_n{i}", media=["n.jpg"]) for i in range(5)]
    event = make_event(own)
    assert score(event, own + noise, {}) == score(event, own, {})


def test_shuffled_posts_same_score(synthetic, profiles):
    posts, demo, noise = synthetic
    shuffled = list(posts)
    random.Random(7).shuffle(shuffled)
    for profile in profiles.values():
        for event in demo + noise:
            assert score(event, shuffled, profile) == score(event, posts, profile)
