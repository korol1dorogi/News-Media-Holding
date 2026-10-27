"""Smoke: the stub pipeline runs end to end and the API answers."""

from pathlib import Path

from fastapi.testclient import TestClient

from radar.api.app import create_app
from radar.core.settings import Settings
from radar.llm import MockProvider, get_provider
from radar.pipeline import OUTLETS, rebuild, run
from radar.storage import Storage


def test_pipeline_runs_on_mini(mini_dir: Path) -> None:
    events = run(mini_dir)
    assert isinstance(events, list)
    for event in events:
        assert set(event.scores) == set(OUTLETS)


def test_rebuild_fills_storage(settings: Settings) -> None:
    count = rebuild(settings)
    storage = Storage(settings.db_path)
    assert count == len(storage.events())
    assert len(storage.posts()) == 8
    assert len(storage.channels()) == 3


def test_api_ready(settings: Settings) -> None:
    client = TestClient(create_app(settings))
    response = client.get("/api/ready")
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_api_reset(settings: Settings) -> None:
    client = TestClient(create_app(settings))
    response = client.post("/api/replay/reset")
    assert response.status_code == 200
    assert isinstance(response.json()["events"], int)


def test_default_provider_is_offline_mock(settings: Settings) -> None:
    provider = get_provider(settings)
    assert isinstance(provider, MockProvider)
    assert provider.complete("s", "u") == provider.complete("s", "u")
