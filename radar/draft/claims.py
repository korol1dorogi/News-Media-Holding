"""Claim check of a draft against its sources (task AI2).

Claims: numbers (digits and words like «трое»), times, dates, places from the city dictionary
(radar.normalize.GEO_PATTERNS) and names (quoted «...» and acronyms like ГИБДД). A claim is
supported if at least one of the event's posts has the same value after normalization.
Unsupported claims and «officially confirmed» without a source go to draft.warnings.
"""

from __future__ import annotations

import dataclasses
import re

from radar.core.models import Claim, Draft, Post
from radar.normalize import GEO_PATTERNS

MONTHS = {
    "январ": 1,
    "феврал": 2,
    "март": 3,
    "апрел": 4,
    "ма": 5,
    "июн": 6,
    "июл": 7,
    "август": 8,
    "сентябр": 9,
    "октябр": 10,
    "ноябр": 11,
    "декабр": 12,
}
NUMBER_WORDS = {
    1: ("один", "одна", "одно", "одного", "одной", "одному"),
    2: ("два", "две", "двое", "двух", "двоих", "двум"),
    3: ("три", "трое", "трех", "троих", "трем"),
    4: ("четыре", "четверо", "четырех", "четверых"),
    5: ("пять", "пятеро", "пяти", "пятерых"),
    6: ("шесть", "шестеро", "шести", "шестерых"),
    7: ("семь", "семеро", "семи", "семерых"),
    8: ("восемь", "восьми"),
    9: ("девять", "девяти"),
    10: ("десять", "десяти", "десяток"),
    12: ("двенадцать", "двенадцати"),
    15: ("пятнадцать", "пятнадцати"),
    20: ("двадцать", "двадцати"),
    100: ("сто", "сотня", "сотни"),
}
WORD_VALUES = {word: value for value, words in NUMBER_WORDS.items() for word in words}

TIME_RE = re.compile(r"(?<![\d.:])([01]?\d|2[0-3]):([0-5]\d)(?![\d:])")
MONTH_NAMES = "январ|феврал|март|апрел|ма[яй]|июн|июл|август|сентябр|октябр|ноябр|декабр"
MONTH_DATE_RE = re.compile(rf"(?<!\d)(\d{{1,2}})\s+({MONTH_NAMES})\w*")
DOT_DATE_RE = re.compile(r"(?<![\d.])(\d{1,2})\.(\d{1,2})(?:\.\d{2,4})?(?!\d)(?!\.\d)")
DIGITS_RE = re.compile(r"(?<!\d)\d+(?:[.,]\d+)?(?!\d)")
WORD_RE = re.compile(r"[а-яё]+", re.IGNORECASE)
QUOTED_RE = re.compile(r"«([^»]{2,60})»")
ACRONYM_RE = re.compile(r"(?<![А-ЯЁA-Z])[А-ЯЁ]{3,}(?![А-ЯЁA-Z])")
OFFICIAL_CLAIM_RE = re.compile(r"официально\s+подтвер|официальн\w*\s+подтвержд", re.IGNORECASE)
OFFICIAL_SOURCE_RE = re.compile(r"подтвержд|подтверди|сообщил[аи]?\s+в\s|пресс-служб")
GEO_REGEXES = tuple(
    (geo, tuple(re.compile(pattern) for pattern in patterns)) for geo, patterns in GEO_PATTERNS
)
UNIT_RE = re.compile(r"\s*([а-яё]+)", re.IGNORECASE)

OFFICIAL_WARNING = (
    "В черновике сказано, что событие официально подтверждено, но в источниках нет "
    "официального подтверждения."
)


@dataclasses.dataclass
class _Found:
    start: int
    end: int
    kind: str
    key: tuple
    text: str


def check_claims(draft: Draft, posts: list[Post]) -> Draft:
    """Fill draft.claims; unsupported claims also go to draft.warnings."""
    sources = [(post.id, _prepare(post.text), post) for post in posts]
    claims = []
    seen = set()
    for found in extract(draft.text):
        if (found.kind, found.key, found.text) in seen:
            continue
        seen.add((found.kind, found.key, found.text))
        ids = [pid for pid, text, post in sources if _supports(found, text, post)]
        claims.append(
            Claim(
                text=found.text,
                kind=_contract_kind(found.kind),
                source_post_ids=ids,
                supported=bool(ids),
            )
        )

    warnings = list(draft.warnings)
    for claim in claims:
        if not claim.supported:
            warnings.append(f"Не подтверждено источниками: «{claim.text}».")
    if OFFICIAL_CLAIM_RE.search(draft.text) and not any(
        OFFICIAL_SOURCE_RE.search(text) for _, text, _ in sources
    ):
        warnings.append(OFFICIAL_WARNING)
    return dataclasses.replace(draft, claims=claims, warnings=list(dict.fromkeys(warnings)))


def extract(text: str) -> list[_Found]:
    """Claims in the order they appear in the text. Times and dates hide their digits."""
    found: list[_Found] = []
    taken: list[tuple[int, int]] = []
    lowered = _prepare(text)

    def add(start: int, end: int, kind: str, key: tuple, shown: str | None = None) -> None:
        if any(start < t_end and t_start < end for t_start, t_end in taken):
            return
        taken.append((start, end))
        found.append(_Found(start, end, kind, key, shown or text[start:end]))

    for m in TIME_RE.finditer(text):
        add(m.start(), m.end(), "time", (int(m.group(1)), int(m.group(2))))
    for m in MONTH_DATE_RE.finditer(lowered):
        add(m.start(), m.end(), "date", (int(m.group(1)), _month(m.group(2))))
    for m in DOT_DATE_RE.finditer(text):
        day, month = int(m.group(1)), int(m.group(2))
        if 1 <= day <= 31 and 1 <= month <= 12:
            add(m.start(), m.end(), "date", (day, month))
    for m in DIGITS_RE.finditer(text):
        value = float(m.group(0).replace(",", "."))
        add(m.start(), m.end(), "number", (value,), _with_unit(text, m.start(), m.end()))
    for m in WORD_RE.finditer(lowered):
        value = WORD_VALUES.get(m.group(0))
        if value is not None:
            add(m.start(), m.end(), "number", (float(value),), _with_unit(text, m.start(), m.end()))
    for m in QUOTED_RE.finditer(text):
        add(m.start(), m.end(), "name", (_stem(m.group(1)),))
    for geo, regexes in GEO_REGEXES:
        for regex in regexes:
            for m in regex.finditer(lowered):
                start, end = m.start(), _word_end(lowered, m.end())
                add(start, end, "place", (geo,))
    for m in ACRONYM_RE.finditer(text):
        add(m.start(), m.end(), "acronym", (m.group(0),))
    return sorted(found, key=lambda f: f.start)


def _supports(found: _Found, text: str, post: Post) -> bool:
    """Does one post (text is already lower-cased) carry the claim's value?"""
    if found.kind == "time":
        return any((int(m.group(1)), int(m.group(2))) == found.key for m in TIME_RE.finditer(text))
    if found.kind == "date":
        return found.key in _dates(text) or found.key == (post.ts.day, post.ts.month)
    if found.kind == "number":
        return found.key[0] in _numbers(text)
    if found.kind == "place":
        return any(regex.search(text) for regex in dict(GEO_REGEXES)[found.key[0]])
    if found.kind == "name":
        return found.key[0] in text
    return found.key[0] in post.text


def _numbers(text: str) -> set[float]:
    values = {float(m.group(0).replace(",", ".")) for m in DIGITS_RE.finditer(text)}
    values |= {float(n) for n in re.findall(r"\d+", text)}
    values |= {float(WORD_VALUES[w]) for w in WORD_RE.findall(text) if w in WORD_VALUES}
    return values


def _dates(text: str) -> set[tuple[int, int]]:
    dates = {(int(m.group(1)), _month(m.group(2))) for m in MONTH_DATE_RE.finditer(text)}
    dates |= {(int(m.group(1)), int(m.group(2))) for m in DOT_DATE_RE.finditer(text)}
    return dates


def _month(word: str) -> int:
    return next(value for stem, value in MONTHS.items() if word.startswith(stem))


def _prepare(text: str) -> str:
    return text.lower().replace("ё", "е")


def _stem(name: str) -> str:
    words = _prepare(name).split()
    return " ".join(word[: max(4, len(word) - 2)] for word in words)


def _word_end(text: str, end: int) -> int:
    while end < len(text) and text[end].isalpha():
        end += 1
    return end


def _with_unit(text: str, start: int, end: int) -> str:
    """The number with the word after it, e.g. «15 домах», for the editor."""
    unit = UNIT_RE.match(text, end)
    return text[start : unit.end()] if unit else text[start:end]


def _contract_kind(kind: str) -> str:
    return {"time": "date", "acronym": "name"}.get(kind, kind)
