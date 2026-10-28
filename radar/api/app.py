"""HTTP API for the editor UI (task L2).

While the DB has no events, the API serves fixtures from frontend/src/mock, so the UI and the
API share one shape from day one. Responses from fixtures carry the header X-Radar-Source.
"""

import json
from datetime import datetime
from functools import lru_cache
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from radar import verify
from radar.core.models import Channel, Dossier, Event, Post, Publication, to_dict
from radar.core.settings import ROOT, Settings, load_settings
from radar.draft import check_claims, generate
from radar.ingest import load_replay
from radar.llm import get_provider
from radar.pipeline import process, rebuild
from radar.storage import Storage

MOCK_DIR = ROOT / "frontend" / "src" / "mock"
FIXTURES_HEADER = "X-Radar-Source"

Outlet = Literal["mash", "life", "super"]


class DraftRequest(BaseModel):
    outlet: Outlet


class PublishRequest(BaseModel):
    outlet: Outlet
    at: datetime | None = None  # model time; default is the event's last public post


def event_item(event: Event, dossier: Dossier, outlet: str) -> dict[str, Any]:
    """One row of GET /api/events."""
    return {
        "event": to_dict(event),
        "level": dossier.level,
        "score": event.scores.get(outlet, 0.0),
    }


def event_detail(event: Event, dossier: Dossier, posts: list[Post], graph: dict) -> dict[str, Any]:
    """Body of GET /api/events/{id}."""
    return {
        "event": to_dict(event),
        "dossier": to_dict(dossier),
        "posts": to_dict(posts),
        "graph": graph,
    }


def default_publish_time(event: Event, posts: list[Post], channels: list[Channel]) -> datetime:
    """The editor publishes right after the public buzz: the last non-official post."""
    official = {c.id for c in channels if c.kind == "official"}
    public = [p.ts for p in posts if p.channel_id not in official]
    return max(public) if public else event.first_ts


def stream_item(event: Event, dossier: Dossier, posts: list[Post], outlet: str) -> dict[str, Any]:
    """Feed row of /api/replay/stream: the event rises with its second post."""
    times = sorted(p.ts for p in posts if p.id in set(event.post_ids))
    rose_at = times[min(1, len(times) - 1)] if times else event.first_ts
    return {
        **event_item(event, dossier, outlet),
        "rose_at": rose_at.isoformat(),
        "minutes_to_signal": round((rose_at - event.first_ts).total_seconds() / 60, 1),
    }


def load_mock(name: str) -> Any:
    return json.loads((MOCK_DIR / f"{name}.json").read_text(encoding="utf-8"))


def mock_events(outlet: str) -> list[dict[str, Any]]:
    items = load_mock("events")
    for item in items:
        item["score"] = item["event"]["scores"].get(outlet, item["score"])
    return sorted(items, key=lambda item: -item["score"])


def mock_detail(event_id: str) -> dict[str, Any]:
    """The full example from event_detail.json, or a short stub for other mock events."""
    items = {item["event"]["id"]: item for item in load_mock("events")}
    if event_id not in items:
        raise HTTPException(status_code=404, detail="Событие не найдено")
    detail = load_mock("event_detail")
    if detail["event"]["id"] == event_id:
        return detail
    item = items[event_id]
    return {
        "event": item["event"],
        "dossier": {
            **detail["dossier"],
            "event_id": event_id,
            "level": item["level"],
            "checks": [],
            "todo": [],
        },
        "posts": [],
        "graph": {"nodes": [], "edges": []},
    }


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()
    storage = Storage(settings.db_path)

    app = FastAPI(title="Сигнал API")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/ready")
    def ready() -> dict[str, bool]:
        return {"ok": True}

    @app.get("/api/events")
    def list_events(response: Response, outlet: Outlet = "mash") -> list[dict[str, Any]]:
        events = storage.events()
        if not events:
            response.headers[FIXTURES_HEADER] = "fixtures"
            return mock_events(outlet)
        items = []
        for event in events:
            dossier = storage.dossier(event.id)
            if dossier is not None:
                items.append(event_item(event, dossier, outlet))
        return sorted(items, key=lambda item: (-item["score"], item["event"]["id"]))

    @app.get("/api/events/{event_id}")
    def get_event(event_id: str, response: Response) -> dict[str, Any]:
        if not storage.has_events():
            response.headers[FIXTURES_HEADER] = "fixtures"
            return mock_detail(event_id)
        event = storage.event(event_id)
        dossier = storage.dossier(event_id)
        if event is None or dossier is None:
            raise HTTPException(status_code=404, detail="Событие не найдено")
        all_posts = storage.posts()
        wanted = set(event.post_ids)
        event_posts = [post for post in all_posts if post.id in wanted]
        graph = verify.repost_graph(event, all_posts)
        return event_detail(event, dossier, event_posts, graph)

    @app.post("/api/events/{event_id}/draft")
    def make_draft(event_id: str, body: DraftRequest, response: Response) -> dict[str, Any]:
        if not storage.has_events():
            response.headers[FIXTURES_HEADER] = "fixtures"
            mock_detail(event_id)
            return {**load_mock("draft"), "event_id": event_id, "outlet": body.outlet}
        event = storage.event(event_id)
        if event is None:
            raise HTTPException(status_code=404, detail="Событие не найдено")
        posts = storage.posts(event.post_ids)
        draft = generate(event, posts, body.outlet, get_provider(settings))
        return to_dict(check_claims(draft, posts))

    @app.post("/api/events/{event_id}/publish")
    def publish(event_id: str, body: PublishRequest, response: Response) -> dict[str, Any]:
        if not storage.has_events():
            response.headers[FIXTURES_HEADER] = "fixtures"
            mock_detail(event_id)
            return {**load_mock("publication"), "event_id": event_id, "outlet": body.outlet}
        event = storage.event(event_id)
        if event is None:
            raise HTTPException(status_code=404, detail="Событие не найдено")
        posts = storage.posts(event.post_ids)
        at = body.at or default_publish_time(event, posts, storage.channels())
        publication = Publication(event_id=event_id, outlet=body.outlet, published_at=at)
        storage.publish(publication)
        return to_dict(publication)

    @app.get("/api/alerts")
    def alerts(response: Response) -> list[dict[str, Any]]:
        if not storage.has_events():
            response.headers[FIXTURES_HEADER] = "fixtures"
            return load_mock("alerts")
        publications = storage.publications()
        if not publications:
            return []
        posts, channels = storage.posts(), storage.channels()
        found = []
        for publication in publications:
            event = storage.event(publication.event_id)
            if event is not None:
                found += verify.watchdog(event, publication, posts, channels)
        found.sort(key=lambda alert: (alert.ts, alert.event_id, alert.outlet))
        return to_dict(found)

    @lru_cache(maxsize=1)
    def replay_bounds() -> tuple[datetime, datetime]:
        _, posts = load_replay(settings.data_dir)
        return posts[0].ts, posts[-1].ts

    @lru_cache(maxsize=256)
    def feed_at(until: datetime) -> tuple[list[Event], list[Dossier], list[Post]]:
        result = process(settings.data_dir, settings.profiles_dir, until)
        return result.events, result.dossiers, result.posts

    @app.get("/api/replay/stream")
    def stream(until: datetime | None = None, outlet: Outlet = "mash") -> dict[str, Any]:
        """The feed as it looked at model time until (default: the end of the replay)."""
        start, end = replay_bounds()
        if until is None:
            until = end
        elif until.tzinfo is None:
            until = until.replace(tzinfo=start.tzinfo)
        until = min(max(until, start), end)
        events, dossiers, posts = feed_at(until)
        by_event = {d.event_id: d for d in dossiers}
        items = [stream_item(e, by_event[e.id], posts, outlet) for e in events]
        items.sort(key=lambda item: (item["rose_at"], item["event"]["id"]))
        return {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "until": until.isoformat(),
            "events": items,
        }

    @app.post("/api/replay/reset")
    def reset() -> dict[str, int]:
        feed_at.cache_clear()
        replay_bounds.cache_clear()
        return {"events": rebuild(settings)}

    @app.get("/api/metrics")
    def metrics() -> dict[str, Any]:
        path = settings.reports_dir / "metrics.json"
        return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}

    return app


app = create_app()
