"""Newsworthiness score for an outlet profile (task C3).

Five features, each 0..1: topic and geo weights from the profile, reach (distinct channels),
speed (posts in the first hour) and media (any photo). The score is their weighted mean with
weights from profile["weights"]. Profiles live in data/profiles/{outlet}.yaml.
"""

from __future__ import annotations

import math
from datetime import timedelta

from radar.core.models import Event, Post

# Reach saturates at this many distinct channels.
REACH_FULL = 10
# Speed saturates at this many posts within SPEED_WINDOW of event.first_ts.
SPEED_FULL = 5
SPEED_WINDOW = timedelta(hours=1)
# Used when the profile has no default_topic / default_geo.
DEFAULT_TOPIC = 0.0
DEFAULT_GEO = 0.3
# Used when the profile has no weights (or they sum to zero).
DEFAULT_WEIGHTS: dict[str, float] = {
    "topic": 0.3,
    "geo": 0.1,
    "reach": 0.25,
    "speed": 0.2,
    "media": 0.15,
}
FEATURES = tuple(DEFAULT_WEIGHTS)


def event_posts(event: Event, posts: list[Post]) -> list[Post]:
    """Posts of the event in a stable order (ts, id)."""
    ids = set(event.post_ids)
    return sorted((post for post in posts if post.id in ids), key=lambda post: (post.ts, post.id))


def features(event: Event, posts: list[Post], profile: dict) -> dict[str, float]:
    """Feature values 0..1 for the event's posts (already selected by event_posts)."""
    topics = profile.get("topics") or {}
    geos = profile.get("geo") or {}
    channels = len({post.channel_id for post in posts})
    early = sum(1 for post in posts if post.ts - event.first_ts <= SPEED_WINDOW)
    return {
        "topic": _unit(topics.get(event.topic, profile.get("default_topic", DEFAULT_TOPIC))),
        "geo": _unit(geos.get(event.geo, profile.get("default_geo", DEFAULT_GEO))),
        "reach": _unit(math.log1p(channels) / math.log1p(REACH_FULL)),
        "speed": _unit(early / SPEED_FULL),
        "media": 1.0 if any(post.media for post in posts) else 0.0,
    }


def score(event: Event, posts: list[Post], profile: dict) -> float:
    """Score 0..1. posts are all replay posts; the event's posts are listed in event.post_ids."""
    own = event_posts(event, posts)
    if not own:
        return 0.0
    weights = _weights(profile)
    values = features(event, own, profile)
    total = sum(weights.values())
    return round(_unit(sum(weights[name] * values[name] for name in FEATURES) / total), 3)


def _weights(profile: dict) -> dict[str, float]:
    given = profile.get("weights") or {}
    weights = {name: max(0.0, float(given.get(name, 0.0))) for name in FEATURES}
    return weights if sum(weights.values()) > 0 else dict(DEFAULT_WEIGHTS)


def _unit(value: float) -> float:
    return min(1.0, max(0.0, float(value)))
