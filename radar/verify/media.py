"""Media match against the archive by pHash (task V2)."""

from __future__ import annotations

from pathlib import Path

from radar.core.models import Check, Event, Post


def media_archive(event: Event, posts: list[Post], archive_dir: Path) -> Check:
    """fail with a link to the archive record if the event's media appeared earlier."""
    # TODO(V2): imagehash.phash over archive/index.json, Hamming distance threshold,
    # robust to recompression and cropping.
    # Done when "flood" fails and a recompressed, cropped copy is found (docs/tasks.md, V2).
    return Check(
        name="media_archive",
        status="n/a",
        summary="Сверка медиа с архивом пока не выполняется.",
        evidence=[],
    )
