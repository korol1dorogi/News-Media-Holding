"""Deterministic offline provider (task AI1).

Reads the event from the <data> block of the prompt and writes an outlet-specific draft from
sentences of the posts, word for word. For events marked inject_error in truth.yaml it distorts
exactly one number, the way a real model hallucinates: this is the demo case for AI2.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

DATA_RE = re.compile(r"<data>\s*(.*?)\s*</data>", re.DOTALL)
SENTENCE_END = re.compile(r"(?<=[.!?…])\s+")
LEADING_NOISE = re.compile(r"^[^\w«\"(]+")
# A number that is not part of a time (9:00), a range (2–24), a date (27.10) or "27 октября".
MONTH_STEMS = "январ|феврал|март|апрел|ма[яй]|июн|июл|август|сентябр|октябр|ноябр|декабр"
COUNT = re.compile(rf"(?<![\d:.,–\-])(\d{{1,4}})(?![\d:.,–\-])(?!\s+(?:{MONTH_STEMS}))")
NUMBER_TOKEN = re.compile(r"\d+")
TITLE_MAX = 110

ENDINGS = {
    "mash": "Подробности уточняются.",
    "life": "Редакция уточняет детали у профильных служб.",
    "super": "Следим за развитием истории.",
}


class MockProvider:
    """Same input gives the same output. No network, no key."""

    def __init__(self, truth_path: Path | None = None) -> None:
        self._inject = _inject_post_ids(truth_path)

    def complete(self, system: str, user: str) -> str:
        data = _read_data(user)
        if data is None:
            return user.strip()
        outlet = data.get("outlet", "mash")
        event = data.get("event", {})
        posts = data.get("posts", [])
        title = _title(posts) or event.get("title", "").strip()
        sentences = _sentences(posts, skip=title)
        parts = _compose(outlet, title, sentences)
        if self._inject & set(event.get("post_ids", [])):
            parts = _distort(parts, posts)
        return json.dumps(parts, ensure_ascii=False)


def _inject_post_ids(truth_path: Path | None) -> set[str]:
    if truth_path is None or not Path(truth_path).is_file():
        return set()
    truth = yaml.safe_load(Path(truth_path).read_text(encoding="utf-8")) or {}
    return {
        post_id
        for item in truth.get("events", [])
        if item.get("inject_error")
        for post_id in item.get("post_ids", [])
    }


def _read_data(user: str) -> dict | None:
    match = DATA_RE.search(user)
    if match is None:
        return None
    try:
        data = json.loads(match.group(1))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _key(text: str) -> str:
    return re.sub(r"[^\w]+", "", text.lower().replace("ё", "е"))


def _split(text: str) -> list[str]:
    parts = (LEADING_NOISE.sub("", raw).strip() for raw in SENTENCE_END.split(text.strip()))
    return [part for part in parts if part]


def _title(posts: list[dict]) -> str:
    """First sentence of the first original post if it is short enough for a title."""
    first = next((post for post in posts if not post.get("forward_from")), None)
    sentences = _split(first.get("text", "")) if first else []
    if not sentences or len(sentences[0]) > TITLE_MAX:
        return ""
    return sentences[0].rstrip(".")


def _sentences(posts: list[dict], skip: str) -> list[str]:
    """Distinct sentences of original posts (no forwards), in post order."""
    seen = {_key(skip.rstrip("…"))}
    result = []
    for post in posts:
        if post.get("forward_from"):
            continue
        for sentence in _split(post.get("text", "")):
            key = _key(sentence)
            if len(key) < 12 or any(key in other or other in key for other in seen):
                continue
            seen.add(key)
            result.append(sentence)
    return result


def _compose(outlet: str, title: str, sentences: list[str]) -> dict[str, str]:
    ending = ENDINGS.get(outlet, ENDINGS["mash"])
    if outlet == "life":
        lead = sentences[0] if sentences else ""
        body = " ".join(sentences[1:5] + [ending])
        return {"title": title, "lead": lead, "text": body}
    if outlet == "super":
        lead = "Город обсуждает новость, вот что пишут горожане."
        return {"title": title, "lead": lead, "text": " ".join(sentences[:2] + [ending])}
    return {"title": title, "lead": "", "text": " ".join(sentences[:2] + [ending])}


def _distort(parts: dict[str, str], posts: list[dict]) -> dict[str, str]:
    """Change the first count number to one that no post mentions."""
    known = {int(n) for post in posts for n in NUMBER_TOKEN.findall(post.get("text", ""))}
    for key in ("title", "lead", "text"):
        match = COUNT.search(parts[key])
        if match is None:
            continue
        value = int(match.group(1)) + 3
        while value in known:
            value += 1
        start, end = match.span(1)
        return {**parts, key: parts[key][:start] + str(value) + parts[key][end:]}
    return parts
