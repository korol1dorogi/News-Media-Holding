"""First source, repost graph and independent sources (task V1).

A post's parent is the post it forwards (forward_from) or, for a non-forward, the earlier post
whose text it copies (char TF-IDF cosine >= COPY_THRESHOLD, D-03). The root of the parent chain is
the post's source: independent sources = distinct roots, first source = the earliest root.
"""

from __future__ import annotations

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from radar.core.models import Channel, Check, Event, Post

# Copies of one post differ by punctuation or a word; retellings of one event score far lower.
COPY_THRESHOLD = 0.85

Link = tuple[str, str]  # (parent_id, kind), kind is "forward" or "copy"


def _forward_chain(post: Post, by_id: dict[str, Post]) -> list[Post]:
    """The post and the posts it forwards, newest first; stops at unknown ids and cycles."""
    chain = [post]
    seen = {post.id}
    while chain[-1].forward_from in by_id and chain[-1].forward_from not in seen:
        chain.append(by_id[chain[-1].forward_from])
        seen.add(chain[-1].id)
    return chain


def _links(event: Event, posts: list[Post]) -> tuple[list[Post], dict[str, Link]]:
    """Event posts plus their forward ancestors sorted by (ts, id), and each post's parent."""
    by_id = {p.id: p for p in posts}
    nodes: dict[str, Post] = {}
    for post_id in event.post_ids:
        if post_id in by_id:
            for post in _forward_chain(by_id[post_id], by_id):
                nodes[post.id] = post
    ordered = sorted(nodes.values(), key=lambda p: (p.ts, p.id))
    position = {p.id: i for i, p in enumerate(ordered)}

    # Parents are always earlier, so the graph has no cycles even if forward_from has one.
    links: dict[str, Link] = {
        p.id: (p.forward_from, "forward")
        for p in ordered
        if p.forward_from in position and position[p.forward_from] < position[p.id]
    }

    texts = [p.text.strip() for p in ordered]
    if sum(1 for t in texts if t) < 2:
        return ordered, links
    sim = cosine_similarity(
        TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5)).fit_transform(texts)
    )
    for i, post in enumerate(ordered):
        if post.id in links or not texts[i]:
            continue
        earlier = [j for j in range(i) if texts[j] and sim[i, j] >= COPY_THRESHOLD]
        if earlier:
            best = max(earlier, key=lambda j: (sim[i, j], -j))
            links[post.id] = (ordered[best].id, "copy")
    return ordered, links


def _root(post_id: str, links: dict[str, Link]) -> str:
    while post_id in links:
        post_id = links[post_id][0]
    return post_id


def provenance(event: Event, posts: list[Post], channels: list[Channel]) -> tuple[Check, str, int]:
    """Return (check, first_source_post_id, independent_sources)."""
    ordered, links = _links(event, posts)
    if not ordered:
        check = Check(
            name="provenance",
            status="n/a",
            summary="Посты события не найдены, первоисточник определить нельзя.",
            evidence=[],
        )
        return check, "", 0

    position = {p.id: i for i, p in enumerate(ordered)}
    roots = sorted({_root(p.id, links) for p in ordered}, key=position.__getitem__)
    first_id, independent = roots[0], len(roots)
    titles = {c.id: c.title for c in channels}

    evidence: list[dict] = []
    for post in ordered:
        channel = titles.get(post.channel_id, post.channel_id)
        if post.id == first_id:
            note = f"первая публикация ({channel})"
        elif post.id in links:
            parent, kind = links[post.id]
            note = f"пересылка {parent}" if kind == "forward" else f"копия {parent} без пересылки"
        else:
            note = f"независимый источник ({channel})"
        evidence.append({"post_id": post.id, "note": note})

    repeats = len(ordered) - independent
    if independent >= 2:
        status = "ok"
        summary = (
            f"Независимых источников: {independent}, первым написал пост {first_id}; "
            f"пересылок и копий: {repeats}."
        )
    elif repeats:
        status = "warn"
        summary = (
            f"Все публикации ({len(ordered)}) восходят к одному посту {first_id}, "
            "независимого подтверждения нет."
        )
    else:
        status = "warn"
        summary = f"Событие известно только из одного поста {first_id}, подтверждения нет."
    check = Check(name="provenance", status=status, summary=summary, evidence=evidence)
    return check, first_id, independent


def repost_graph(event: Event, posts: list[Post]) -> dict:
    """{"nodes": [{"id", "channel_id", "ts"}], "edges": [{"from", "to", "kind"}]}.

    kind is "forward" or "copy".
    """
    ordered, links = _links(event, posts)
    nodes = [{"id": p.id, "channel_id": p.channel_id, "ts": p.ts.isoformat()} for p in ordered]
    edges = [
        {"from": links[p.id][0], "to": p.id, "kind": links[p.id][1]}
        for p in ordered
        if p.id in links
    ]
    return {"nodes": nodes, "edges": edges}
