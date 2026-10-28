"""L4: publish, alerts and replay stream endpoints, live and on fixtures."""

import json
from datetime import datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient

from radar.api.app import MOCK_DIR, create_app
from radar.core.models import Alert, Publication, from_dict
from radar.core.settings import ROOT, Settings

SYNTHETIC = ROOT / "data" / "synthetic"


def mock(name: str) -> Any:
    return json.loads((MOCK_DIR / f"{name}.json").read_text(encoding="utf-8"))


@pytest.fixture
def live(tmp_path) -> TestClient:
    client = TestClient(create_app(Settings(data_dir=SYNTHETIC, db_path=tmp_path / "db.sqlite3")))
    assert client.post("/api/replay/reset").json()["events"] > 0
    return client


def event_id(client: TestClient, title_start: str) -> str:
    items = client.get("/api/events").json()
    return next(i["event"]["id"] for i in items if i["event"]["title"].startswith(title_start))


def test_mocks_load_into_models() -> None:
    from_dict(Publication, mock("publication"))
    for alert in mock("alerts"):
        from_dict(Alert, alert)
    stream = mock("stream")
    assert set(stream) == {"start", "end", "until", "events"}
    assert set(stream["events"][0]) == {"event", "level", "score", "rose_at", "minutes_to_signal"}


def test_fixture_mode_serves_mocks(settings: Settings) -> None:
    client = TestClient(create_app(settings))
    event = client.get("/api/events").json()[0]["event"]["id"]
    published = client.post(f"/api/events/{event}/publish", json={"outlet": "life"})
    assert published.headers["X-Radar-Source"] == "fixtures"
    assert set(published.json()) == set(mock("publication"))
    assert published.json()["outlet"] == "life"
    assert client.get("/api/alerts").json() == mock("alerts")


def test_publish_defaults_to_the_last_public_post(live: TestClient) -> None:
    fire = event_id(live, "Горит ТЦ")
    body = live.post(f"/api/events/{fire}/publish", json={"outlet": "mash"}).json()
    assert body == {
        "event_id": fire,
        "outlet": "mash",
        "published_at": "2026-10-28T15:25:00+03:00",
    }
    explicit = live.post(
        f"/api/events/{fire}/publish",
        json={"outlet": "life", "at": "2026-10-28T17:00:00+03:00"},
    ).json()
    assert explicit["published_at"] == "2026-10-28T17:00:00+03:00"
    assert live.post("/api/events/nope/publish", json={"outlet": "mash"}).status_code == 404


def test_alert_after_publication_and_reset_clears_it(live: TestClient) -> None:
    assert live.get("/api/alerts").json() == []
    fire = event_id(live, "Горит ТЦ")
    live.post(f"/api/events/{fire}/publish", json={"outlet": "mash"})
    alerts = live.get("/api/alerts").json()
    assert [(a["event_id"], a["kind"], a["post_id"]) for a in alerts] == [
        (fire, "denial", "p_0446")
    ]
    assert "через 45 мин" in alerts[0]["summary"]
    live.post("/api/replay/reset")
    assert live.get("/api/alerts").json() == []


def test_confirmed_event_published_after_confirmation_has_no_alert(live: TestClient) -> None:
    dtp = event_id(live, "ДТП на северном")
    live.post(f"/api/events/{dtp}/publish", json={"outlet": "mash"})
    assert live.get("/api/alerts").json() == []


def test_stream_grows_with_model_time(live: TestClient) -> None:
    empty = live.get("/api/replay/stream", params={"until": "2026-10-27T00:10:00+03:00"}).json()
    assert empty["events"] == []
    early = live.get("/api/replay/stream", params={"until": "2026-10-27T08:30:00+03:00"}).json()
    titles = [item["event"]["title"] for item in early["events"]]
    assert any(t.startswith("ДТП на северном") for t in titles)
    assert not any(t.startswith("Горит ТЦ") for t in titles)
    dtp = next(i for i in early["events"] if i["event"]["title"].startswith("ДТП"))
    assert dtp["minutes_to_signal"] == 3.0
    full = live.get("/api/replay/stream").json()
    assert full["until"] == full["end"]
    assert len(full["events"]) == len(live.get("/api/events").json())
    rose = [item["rose_at"] for item in full["events"]]
    assert rose == sorted(rose)


def test_stream_clamps_and_accepts_naive_time(live: TestClient) -> None:
    body = live.get("/api/replay/stream", params={"until": "2030-01-01T00:00:00"}).json()
    assert body["until"] == body["end"]
    naive = live.get("/api/replay/stream", params={"until": "2026-10-27T08:30:00"}).json()
    assert datetime.fromisoformat(naive["until"]).utcoffset() is not None
