"""Data contract shared by all modules. Only the lead changes this file."""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal, get_args, get_origin, get_type_hints


@dataclass
class Channel:
    id: str
    title: str
    kind: Literal["public", "official", "reader_bot", "outlet"]
    region: str


@dataclass
class Post:
    id: str
    channel_id: str
    ts: datetime
    text: str
    url: str
    media: list[str]  # paths relative to data/synthetic/media
    forward_from: str | None  # id of the original post for a forward
    geo: str | None = None  # filled by normalize (C1)
    topic: str | None = None  # filled by normalize (C1)


@dataclass
class Event:
    id: str
    post_ids: list[str]
    first_ts: datetime
    title: str
    geo: str | None
    topic: str | None
    scores: dict[str, float]  # outlet -> 0..1


@dataclass
class Check:
    name: str  # provenance | media_archive | weather | official
    status: Literal["ok", "warn", "fail", "n/a"]
    summary: str  # one sentence for the editor, in Russian
    evidence: list[dict]  # {"post_id"|"archive_id"|"url": ..., "note": ...}


@dataclass
class Dossier:
    event_id: str
    level: Literal["green", "yellow", "red"]
    first_source_post_id: str
    independent_sources: int
    checks: list[Check]
    todo: list[str]  # what to check by hand


@dataclass
class Claim:
    text: str
    kind: Literal["number", "name", "date", "place", "other"]
    source_post_ids: list[str]
    supported: bool


@dataclass
class Draft:
    event_id: str
    outlet: Literal["mash", "life", "super"]
    text: str
    claims: list[Claim]
    warnings: list[str]


@dataclass
class Publication:
    event_id: str
    outlet: Literal["mash", "life", "super"]
    published_at: datetime  # model time of the editor's "publish"


@dataclass
class Alert:
    event_id: str
    outlet: str
    kind: Literal["denial", "update"]
    post_id: str  # the official post that triggered the alert
    ts: datetime
    summary: str  # one sentence for the editor, in Russian


def to_dict(obj: Any) -> Any:
    """Model (or list/dict of models) -> JSON-ready value. datetime becomes ISO 8601."""
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {f.name: to_dict(getattr(obj, f.name)) for f in dataclasses.fields(obj)}
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, list):
        return [to_dict(item) for item in obj]
    if isinstance(obj, dict):
        return {key: to_dict(value) for key, value in obj.items()}
    return obj


def from_dict[T](cls: type[T], data: dict[str, Any]) -> T:
    """Inverse of to_dict: JSON value -> model of type cls."""
    hints = get_type_hints(cls)
    kwargs = {
        f.name: _decode(hints[f.name], data[f.name])
        for f in dataclasses.fields(cls)
        if f.name in data
    }
    return cls(**kwargs)


def _decode(hint: Any, value: Any) -> Any:
    if value is None:
        return None
    if hint is datetime:
        return datetime.fromisoformat(value)
    if get_origin(hint) is list:
        (item,) = get_args(hint)
        if dataclasses.is_dataclass(item):
            return [from_dict(item, x) for x in value]
        return list(value)
    return value
