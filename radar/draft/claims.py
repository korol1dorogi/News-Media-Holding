"""Claim check of a draft against its sources (task AI2)."""

from __future__ import annotations

from radar.core.models import Draft, Post


def check_claims(draft: Draft, posts: list[Post]) -> Draft:
    """Fill draft.claims; unsupported claims also go to draft.warnings."""
    # TODO(AI2): extract numbers, dates, names and places; a claim is supported if it is
    # found in at least one of the event's posts after normalization.
    # Done when the inject_error event has exactly one supported=false and the others
    # have none (docs/tasks.md, AI2).
    return draft
