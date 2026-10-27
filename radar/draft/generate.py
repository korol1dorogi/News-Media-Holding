"""Draft in the outlet's format (task AI1)."""

from __future__ import annotations

from radar.core.models import Draft, Event, Post
from radar.llm import Provider


def generate(event: Event, posts: list[Post], outlet: str, llm: Provider) -> Draft:
    """Build a draft for outlet (mash | life | super) from the event's posts."""
    # TODO(AI1): prompt templates per outlet (mash: short post, life: note with a lead,
    # super: celebrity tone); post texts are marked as data in the prompt.
    # Done when mash and life drafts differ without network or key (docs/tasks.md, AI1).
    text = llm.complete(system=f"Черновик для издания {outlet}.", user=event.title)
    return Draft(event_id=event.id, outlet=outlet, text=text, claims=[], warnings=[])
