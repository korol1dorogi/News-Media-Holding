"""Post normalization: geo and topic (task C1).

Dictionary and keywords, no models (docs/assumptions.md). Text is lower-cased with ё -> е
and matched against the patterns below; every pattern is a regex, most are plain stems.
"""

from __future__ import annotations

import dataclasses
import re

from radar.core.models import Post

# Canonical geo -> patterns. The earliest match in the text wins; on a tie, dictionary order.
GEO_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("северный въезд", (r"северн\w*\s+въезд",)),
    ("Речная улица", ("речн",)),
    ("промзона", ("промзон",)),
    # The «Галерея» mall on Лесная street is in the city centre.
    ("центр", ("центр", "галере", "лесн")),
    # Ключевая street is inside the southern district.
    ("южный район", ("южн", "ключев")),
    ("Садовая улица", ("садов",)),
    ("Парковая улица", ("парков",)),
    ("Школьная улица", ("школьн",)),
    ("Вокзальная площадь", ("вокзальн",)),
    ("набережная", ("набережн",)),
    ("микрорайон Сосновый", ("соснов",)),
    ("Заречье", ("заречь",)),
)

# Topic -> stems. Rules are tried in order and the first match wins, so "возгорания нет"
# stays a fire and "вода по колено" is an emergency, not utilities. No bare "дым": it catches
# "дымоходы" in fire-safety tips. Ads, posters, horoscopes, polls and sport get no topic.
TOPIC_STEMS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("пожар", ("пожар", "горит", "задымл", "возгоран")),
    ("ДТП", ("дтп", "авари", "столкн", "автобус", "грузовик", "фура")),
    ("ЧС", ("наводнен", "затоп", "по колено")),
    ("погода", ("снег", "сугроб", "мороз", "гололед")),
    ("ЖКХ", ("отключ", "водопровод", "холодной воды", "без воды", "воды", "мусор", "фонар")),
    ("общество", ("завод", "сократ", "увольн", "закрыва")),
)

_GEO_REGEXES = tuple(
    (geo, tuple(re.compile(pattern) for pattern in patterns)) for geo, patterns in GEO_PATTERNS
)


def _prepare(text: str) -> str:
    return text.lower().replace("ё", "е")


def _geo(text: str) -> str | None:
    best: tuple[int, str] | None = None
    for geo, regexes in _GEO_REGEXES:
        for regex in regexes:
            match = regex.search(text)
            if match and (best is None or match.start() < best[0]):
                best = (match.start(), geo)
    return best[1] if best else None


def _topic(text: str) -> str | None:
    for topic, stems in TOPIC_STEMS:
        if any(stem in text for stem in stems):
            return topic
    return None


def enrich(post: Post) -> Post:
    """Return a copy of the post with geo and topic filled in; the input is not changed."""
    text = _prepare(post.text)
    return dataclasses.replace(post, geo=_geo(text), topic=_topic(text))
