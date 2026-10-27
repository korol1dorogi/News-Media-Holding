"""Replay loader: channels.json and posts.jsonl from a data directory."""

from __future__ import annotations

import json
from pathlib import Path

from radar.core.models import Channel, Post, from_dict


def load_replay(dir: Path) -> tuple[list[Channel], list[Post]]:
    """Read channels and posts. Posts are sorted by (ts, id)."""
    dir = Path(dir)
    raw_channels = json.loads((dir / "channels.json").read_text(encoding="utf-8"))
    channels = [from_dict(Channel, item) for item in raw_channels]
    known = {channel.id for channel in channels}

    posts = []
    with (dir / "posts.jsonl").open(encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, start=1):
            if not line.strip():
                continue
            try:
                post = from_dict(Post, json.loads(line))
            except (json.JSONDecodeError, TypeError, ValueError) as exc:
                raise ValueError(f"posts.jsonl:{lineno}: {exc}") from exc
            if post.channel_id not in known:
                raise ValueError(f"posts.jsonl:{lineno}: unknown channel {post.channel_id!r}")
            posts.append(post)

    posts.sort(key=lambda post: (post.ts, post.id))
    return channels, posts
