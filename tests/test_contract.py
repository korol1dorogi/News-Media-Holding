"""Contract: models survive JSON, API shapes match frontend/src/mock, replay loads."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest
import yaml
from fastapi.testclient import TestClient

from radar.api.app import MOCK_DIR, create_app, event_detail, event_item
from radar.core.models import Channel, Check, Claim, Dossier, Draft, Event, Post, from_dict, to_dict
from radar.core.settings import Settings
from radar.ingest import load_replay

TS = datetime.fromisoformat("2026-10-27T08:12:00+03:00")

POST = Post(
    id="p_1",
    channel_id="ch_1",
    ts=TS,
    text="ДТП на въезде",
    url="https://example.invalid/1",
    media=["a.jpg"],
    forward_from=None,
    geo="северный въезд",
    topic="ДТП",
)
EVENT = Event(
    id="ev_1",
    post_ids=["p_1"],
    first_ts=TS,
    title="ДТП на въезде",
    geo="северный въезд",
    topic="ДТП",
    scores={"mash": 0.9, "life": 0.8, "super": 0.1},
)
CHECK = Check(
    name="provenance",
    status="ok",
    summary="Первоисточник найден.",
    evidence=[{"post_id": "p_1", "note": "первая публикация"}],
)
DOSSIER = Dossier(
    event_id="ev_1",
    level="green",
    first_source_post_id="p_1",
    independent_sources=1,
    checks=[CHECK],
    todo=["Позвонить в ГИБДД"],
)
CLAIM = Claim(text="трое", kind="number", source_post_ids=["p_1"], supported=True)
DRAFT = Draft(event_id="ev_1", outlet="mash", text="Текст", claims=[CLAIM], warnings=["!"])
CHANNEL = Channel(id="ch_1", title="Паблик", kind="public", region="demo-city")
GRAPH = {
    "nodes": [{"id": "p_1", "channel_id": "ch_1", "ts": TS.isoformat()}],
    "edges": [{"from": "p_1", "to": "p_2", "kind": "forward"}],
}


def mock(name: str) -> Any:
    return json.loads((MOCK_DIR / f"{name}.json").read_text(encoding="utf-8"))


def assert_same_shape(actual: Any, expected: Any, path: str = "$") -> None:
    """Same keys at every level; lists are compared by their first elements."""
    if actual is None or expected is None:
        return
    if isinstance(expected, dict):
        assert isinstance(actual, dict), path
        assert set(actual) == set(expected), f"{path}: {sorted(set(actual) ^ set(expected))}"
        for key in expected:
            assert_same_shape(actual[key], expected[key], f"{path}.{key}")
    elif isinstance(expected, list):
        assert isinstance(actual, list), path
        if actual and expected:
            assert_same_shape(actual[0], expected[0], f"{path}[0]")


@pytest.mark.parametrize("obj", [POST, EVENT, CHECK, DOSSIER, CLAIM, DRAFT, CHANNEL])
def test_models_roundtrip_json(obj: Any) -> None:
    data = json.loads(json.dumps(to_dict(obj), ensure_ascii=False))
    assert from_dict(type(obj), data) == obj


def test_load_replay_reads_mini(mini_dir: Path) -> None:
    channels, posts = load_replay(mini_dir)
    assert len(channels) == 3
    assert len(posts) == 8
    assert posts == sorted(posts, key=lambda post: (post.ts, post.id))
    assert all(post.ts.tzinfo is not None for post in posts)
    by_id = {post.id: post for post in posts}
    assert by_id["m_005"].forward_from == "m_004"
    assert by_id["m_004"].media == ["flood.jpg"]


def test_mini_truth_refers_to_existing_posts(mini_dir: Path) -> None:
    truth = yaml.safe_load((mini_dir / "truth.yaml").read_text(encoding="utf-8"))
    _, posts = load_replay(mini_dir)
    ids = {post.id for post in posts}
    assert len(truth["events"]) == 2
    for event in truth["events"]:
        assert set(event["post_ids"]) <= ids, event["key"]


def test_mocks_load_into_models() -> None:
    for item in mock("events"):
        from_dict(Event, item["event"])
    detail = mock("event_detail")
    from_dict(Event, detail["event"])
    from_dict(Dossier, detail["dossier"])
    for post in detail["posts"]:
        from_dict(Post, post)
    from_dict(Draft, mock("draft"))


def test_db_responses_match_mocks() -> None:
    assert_same_shape(event_item(EVENT, DOSSIER, "mash"), mock("events")[0])
    assert_same_shape(event_detail(EVENT, DOSSIER, [POST], GRAPH), mock("event_detail"))
    assert_same_shape(to_dict(DRAFT), mock("draft"))


def test_fixture_api_matches_mocks(settings: Settings) -> None:
    client = TestClient(create_app(settings))

    events = client.get("/api/events", params={"outlet": "life"})
    assert events.status_code == 200
    assert events.headers["X-Radar-Source"] == "fixtures"
    assert_same_shape(events.json(), mock("events"))
    scores = [item["score"] for item in events.json()]
    assert scores == sorted(scores, reverse=True)

    for item in events.json():
        event_id = item["event"]["id"]
        detail = client.get(f"/api/events/{event_id}")
        assert detail.status_code == 200
        assert_same_shape(detail.json(), mock("event_detail"))

    event_id = events.json()[0]["event"]["id"]
    draft = client.post(f"/api/events/{event_id}/draft", json={"outlet": "life"})
    assert draft.status_code == 200
    assert_same_shape(draft.json(), mock("draft"))
    assert draft.json()["outlet"] == "life"

    assert client.get("/api/events/nope").status_code == 404
    assert client.get("/api/metrics").json() == {}
