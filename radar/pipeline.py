"""End-to-end pipeline (task L3): replay -> normalize -> cluster -> score -> verify -> storage."""

from __future__ import annotations

import dataclasses
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from radar import verify
from radar.cluster import build_events
from radar.core.models import Channel, Dossier, Event, Post
from radar.core.settings import ROOT, Settings, load_settings
from radar.ingest import load_replay
from radar.normalize import enrich
from radar.score import score
from radar.storage import Storage

OUTLETS = ("mash", "life", "super")
PROFILES_DIR = ROOT / "data" / "profiles"


@dataclass
class Result:
    channels: list[Channel]
    posts: list[Post]
    events: list[Event]
    dossiers: list[Dossier]


def run(data_dir: Path) -> list[Event]:
    """Scored events for a replay directory."""
    return process(Path(data_dir)).events


def process(data_dir: Path, profiles_dir: Path = PROFILES_DIR) -> Result:
    # Drafts are not generated here: the LLM runs only on the editor's button.
    channels, posts = load_replay(data_dir)
    posts = [enrich(post) for post in posts]
    profiles = load_profiles(profiles_dir)
    weather = _read_json(data_dir / "weather.json")
    media_meta = _read_json(data_dir / "media" / "meta.json")

    events = []
    dossiers = []
    for raw in build_events(posts):
        scores = {outlet: score(raw, posts, profiles[outlet]) for outlet in OUTLETS}
        event = dataclasses.replace(raw, scores=scores)
        events.append(event)
        dossiers.append(verify_event(event, posts, channels, data_dir, weather, media_meta))
    return Result(channels=channels, posts=posts, events=events, dossiers=dossiers)


def verify_event(
    event: Event,
    posts: list[Post],
    channels: list[Channel],
    data_dir: Path,
    weather: dict,
    media_meta: dict,
) -> Dossier:
    check, first_id, independent = verify.provenance(event, posts, channels)
    checks = [
        check,
        verify.media_archive(event, posts, data_dir / "archive"),
        verify.weather(event, posts, weather, media_meta),
        verify.official(event, posts, channels),
    ]
    return verify.build_dossier(event, checks, first_id, independent)


def rebuild(settings: Settings) -> int:
    """Recompute everything from settings.data_dir into the DB. Returns the number of events."""
    result = process(settings.data_dir, settings.profiles_dir)
    Storage(settings.db_path).replace_all(
        result.channels,
        result.posts,
        result.events,
        result.dossiers,
    )
    return len(result.events)


def load_profiles(profiles_dir: Path) -> dict[str, dict]:
    profiles = {}
    for outlet in OUTLETS:
        path = profiles_dir / f"{outlet}.yaml"
        data = yaml.safe_load(path.read_text(encoding="utf-8")) if path.is_file() else None
        profiles[outlet] = data or {}
    return profiles


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


if __name__ == "__main__":
    print(f"events: {rebuild(load_settings())}")
