"""Dossier assembly into a traffic light (task V4)."""

from __future__ import annotations

from radar.core.models import Check, Dossier, Event


def build_dossier(event: Event, checks: list[Check], first_id: str, independent: int) -> Dossier:
    """Combine checks into green/yellow/red and a todo list for the editor."""
    # TODO(V4): any fail -> red; one independent source without official confirmation ->
    # yellow; otherwise green. todo is built from warn and fail.
    # Done when dossier levels match truth.yaml (docs/tasks.md, V4).
    return Dossier(
        event_id=event.id,
        level="yellow",
        first_source_post_id=first_id,
        independent_sources=independent,
        checks=checks,
        todo=[],
    )
