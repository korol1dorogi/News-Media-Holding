"""Clustering posts into events (task C2).

Posts come after normalize (C1). A post with a topic joins the open cluster with the same
(geo, topic) if the cluster's last post is at most GAP old. A post with a topic but no geo
joins a cluster with the same topic by char TF-IDF similarity (D-03). Forwards always go
to the cluster of their original. Posts without a topic never start or join a cluster.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from radar.core.models import Event, Post

GAP = timedelta(hours=3)  # max pause between neighbouring posts of one event
# Measured with geo stripped from the demo posts: the weakest in-event link is 0.14,
# the strongest link between different demo events is 0.10 (same value as in V1 and V4).
TEXT_THRESHOLD = 0.12
NGRAM = (3, 5)
MIN_POSTS = 2
TITLE_MAX = 90

_SENTENCE_END = re.compile(r"[.!?]+(?=\s|$)")


@dataclass
class _Cluster:
    key: tuple[str | None, str]
    posts: list[Post] = field(default_factory=list)
    last_ts: datetime | None = None

    def add(self, post: Post) -> None:
        self.posts.append(post)
        self.last_ts = post.ts if self.last_ts is None else max(self.last_ts, post.ts)


class _Similarity:
    """Char TF-IDF over all input texts, built only if some post needs it."""

    def __init__(self, posts: list[Post]):
        self._rows = {post.id: i for i, post in enumerate(posts)}
        vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=NGRAM)
        self._matrix = vectorizer.fit_transform([post.text for post in posts])

    def best(self, post: Post, others: list[Post]) -> float:
        rows = [self._rows[other.id] for other in others]
        return float(cosine_similarity(self._matrix[self._rows[post.id]], self._matrix[rows]).max())


def build_events(posts: list[Post]) -> list[Event]:
    """Group posts into events. Forwards always join the cluster of the original post."""
    ordered = sorted(posts, key=lambda post: (post.ts, post.id))
    by_id = {post.id: post for post in ordered}
    needs_text = any(post.topic is not None and post.geo is None for post in ordered)
    similarity = _Similarity(ordered) if needs_text else None

    clusters: list[_Cluster] = []
    latest: dict[tuple[str | None, str], _Cluster] = {}
    placed: dict[str, _Cluster | None] = {}  # post id -> its cluster, None if left out
    waiting: dict[str, list[Post]] = {}  # root id -> forwards seen before the root

    for post in ordered:
        root = _root(post, by_id)
        if root is not None:
            if root.id in placed:
                _join(placed, post, placed[root.id])
            else:
                waiting.setdefault(root.id, []).append(post)
            continue

        cluster = _match(post, clusters, latest, similarity)
        if cluster is None and post.topic is not None:
            cluster = _Cluster(key=(post.geo, post.topic))
            clusters.append(cluster)
            latest[cluster.key] = cluster
        _join(placed, post, cluster)
        for forward in waiting.pop(post.id, []):
            _join(placed, forward, cluster)

    events = [_event(cluster) for cluster in clusters if len(cluster.posts) >= MIN_POSTS]
    return sorted(events, key=lambda event: (event.first_ts, event.id))


def _root(post: Post, by_id: dict[str, Post]) -> Post | None:
    """The earliest post of the forward chain that is in the input, None if not a forward."""
    root = None
    seen = {post.id}
    current = post
    while current.forward_from in by_id and current.forward_from not in seen:
        current = by_id[current.forward_from]
        seen.add(current.id)
        root = current
    return root


def _join(placed: dict[str, _Cluster | None], post: Post, cluster: _Cluster | None) -> None:
    placed[post.id] = cluster
    if cluster is not None:
        cluster.add(post)


def _match(
    post: Post,
    clusters: list[_Cluster],
    latest: dict[tuple[str | None, str], _Cluster],
    similarity: _Similarity | None,
) -> _Cluster | None:
    """Open cluster the post joins, None if it starts a new one or stays out."""
    if post.topic is None:
        return None
    if post.geo is not None:
        cluster = latest.get((post.geo, post.topic))
        return cluster if cluster is not None and _open(cluster, post) else None

    best, best_score = None, 0.0
    for cluster in clusters:  # oldest first: on a tie the earlier cluster wins
        if cluster.key[1] != post.topic or not _open(cluster, post):
            continue
        score = similarity.best(post, cluster.posts)
        if score >= TEXT_THRESHOLD and score > best_score:
            best, best_score = cluster, score
    return best


def _open(cluster: _Cluster, post: Post) -> bool:
    return post.ts - cluster.last_ts <= GAP


def _event(cluster: _Cluster) -> Event:
    posts = sorted(cluster.posts, key=lambda post: (post.ts, post.id))
    lead = next((post for post in posts if post.forward_from is None), posts[0])
    return Event(
        id=f"ev_{posts[0].id}",
        post_ids=[post.id for post in posts],
        first_ts=posts[0].ts,
        title=_title(lead.text),
        geo=_most_common(post.geo for post in posts),
        topic=_most_common(post.topic for post in posts),
        scores={},
    )


def _most_common(values) -> str | None:
    """Most frequent non-empty value; on a tie, the one met first."""
    counts = Counter(value for value in values if value is not None)
    return max(counts, key=counts.__getitem__) if counts else None


def _title(text: str) -> str:
    """First sentence without the closing dot, cut by word to TITLE_MAX characters."""
    text = " ".join(text.split())
    end = _SENTENCE_END.search(text)
    sentence = text[: end.end()].rstrip(".") if end else text
    if len(sentence) <= TITLE_MAX:
        return sentence
    cut = sentence[: TITLE_MAX - 1]
    if " " in cut:
        cut = cut.rsplit(" ", 1)[0]
    return cut.rstrip(" ,:;—-") + "…"
