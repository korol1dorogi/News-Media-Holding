"""Confirmation or denial by an official channel (task V4)."""

from __future__ import annotations

from radar.core.models import Channel, Check, Event, Post


def official(event: Event, posts: list[Post], channels: list[Channel]) -> Check:
    """ok if an official channel confirms, fail if it denies, n/a if it is silent."""
    # TODO(V4): official posts by geo, topic and time window; confirm/deny by key phrases.
    # Done when dossier levels match truth.yaml (docs/tasks.md, V4).
    return Check(
        name="official",
        status="n/a",
        summary="Официальные каналы пока не проверяются.",
        evidence=[],
    )
