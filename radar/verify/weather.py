"""Media scene vs weather and daylight (task V3).

Scene features come from media/meta.json (D-07): {file: {"scene": ..., "daylight": bool}}.
Weather: {city: {"YYYY-MM-DD": {"t_min", "t_max", "precip"}}}. Weather keys are cities, while
post/event geo may be a street, so the city is picked by _pick_city.
"""

from __future__ import annotations

from datetime import date, datetime

from radar.core.models import Check, Event, Post

DAY_HOURS = range(7, 19)  # local hours of the post that count as daylight
SNOW_MAX_T_MIN = 2  # snow on the photo is impossible when the day's minimum is above this
SCENES = ("snow", "rain", "clear")
PRECIPS = ("snow", "rain", "none")
SEVERITY = {"ok": 0, "warn": 1, "fail": 2}

PRECIP_TEXT = {"snow": "снег", "rain": "дождь", "none": "без осадков"}

NO_PHOTOS = "В событии нет фото, сверять с погодой нечего."
NO_META = "Для фото события нет признаков сцены в meta.json."
NO_CITY = "Не знаю, по какому городу брать погоду."
NO_WEATHER = "Нет погоды за {dates}."


def weather(event: Event, posts: list[Post], weather: dict, media_meta: dict) -> Check:
    """Compare scene/daylight from media/meta.json with weather.json and post time."""
    event_posts = _event_posts(event, posts)
    items = [(post, file) for post in event_posts for file in sorted(post.media)]
    if not items:
        return _na(NO_PHOTOS)
    if not any(_scene(media_meta, file) for _, file in items):
        return _na(NO_META)
    city = _pick_city(event, event_posts, weather)
    if city is None:
        return _na(NO_CITY)

    findings = []  # (index, status, summary, post_id, note); index keeps (ts, id, file) order
    skipped = []  # (index, post_id, note)
    checked = 0
    for index, (post, file) in enumerate(items):
        scene = _scene(media_meta, file)
        day = post.ts.date()
        conditions = _conditions(weather[city], day)
        if scene is None:
            skipped.append((index, post.id, f"фото {file} не проверено: нет признаков в meta.json"))
            continue
        if conditions is None:
            note = f"фото {file} не проверено: нет погоды за {_fmt_date(day)}"
            skipped.append((index, post.id, note))
            continue
        checked += 1
        for status, summary, note in _check_file(post, file, scene, day, conditions):
            findings.append((index, status, summary, post.id, note))

    if not checked:
        dates = sorted({post.ts.date() for post, file in items if _scene(media_meta, file)})
        return _na(NO_WEATHER.format(dates=", ".join(_fmt_date(d) for d in dates)))

    worst = max(SEVERITY[f[1]] for f in findings)
    reported = [f for f in findings if SEVERITY[f[1]] == worst]
    status, summary = reported[0][1], reported[0][2]
    if skipped:
        summary += f" Проверено {checked} из {len(items)} фото."

    entries = [(f[0], f[3], f[4]) for f in reported] + skipped
    evidence = [
        {"post_id": post_id, "note": note}
        for _, post_id, note in sorted(entries, key=lambda e: e[0])
    ]
    return Check(name="weather", status=status, summary=summary, evidence=evidence)


def _event_posts(event: Event, posts: list[Post]) -> list[Post]:
    ids = set(event.post_ids)
    return sorted((p for p in posts if p.id in ids), key=lambda p: (p.ts, p.id))


def _pick_city(event: Event, event_posts: list[Post], weather: dict) -> str | None:
    """event.geo, then the first post geo that is a weather key, then the only weather key."""
    if event.geo in weather:
        return event.geo
    for post in event_posts:
        if post.geo in weather:
            return post.geo
    if len(weather) == 1:
        return next(iter(weather))
    return None


def _scene(media_meta: dict, file: str) -> dict | None:
    meta = media_meta.get(file)
    if not isinstance(meta, dict):
        return None
    if meta.get("scene") not in SCENES or not isinstance(meta.get("daylight"), bool):
        return None
    return meta


def _conditions(by_date: object, day: date) -> dict | None:
    """Weather record for the date, or None when it is missing or malformed."""
    if not isinstance(by_date, dict):
        return None
    record = by_date.get(day.isoformat())
    if not isinstance(record, dict):
        return None
    t_min, t_max = record.get("t_min"), record.get("t_max")
    if not all(isinstance(t, int | float) and not isinstance(t, bool) for t in (t_min, t_max)):
        return None
    if record.get("precip") not in PRECIPS:
        return None
    return record


def _check_file(
    post: Post, file: str, meta: dict, day: date, conditions: dict
) -> list[tuple[str, str, str]]:
    """(status, summary, note) for every contradiction, or a single ok."""
    scene, precip, t_min = meta["scene"], conditions["precip"], conditions["t_min"]
    span = f"{_fmt_temp(t_min)}..{_fmt_temp(conditions['t_max'])}"
    when = _fmt_date(day)
    found = []
    if scene == "snow" and precip != "snow" and t_min > SNOW_MAX_T_MIN:
        found.append(
            (
                "fail",
                f"На фото снег, а {when} в городе было от {_fmt_temp(t_min)} "
                f"до {_fmt_temp(conditions['t_max'])} {_precip_phrase(precip)}.",
                f"{file}: снег на фото, а {when} было {span}, {PRECIP_TEXT[precip]}",
            )
        )
    if scene == "rain" and precip == "none":
        found.append(
            (
                "warn",
                "На фото дождь, а осадков в этот день не было.",
                f"{file}: дождь на фото, а {when} осадков не было",
            )
        )
    if meta["daylight"] != _is_day(post.ts):
        shot = "дневной" if meta["daylight"] else "ночной"
        at = post.ts.strftime("%H:%M")
        found.append(
            (
                "warn",
                f"Кадр {shot}, а пост опубликован в {at} — возможно, фото не отсюда.",
                f"{file}: кадр {shot}, пост опубликован в {at}",
            )
        )
    if found:
        return found
    return [
        (
            "ok",
            f"Погода на фото совпадает с данными за {when}: {PRECIP_TEXT[precip]}, {span}.",
            f"{file}: совпадает с погодой за {when} ({PRECIP_TEXT[precip]}, {span})",
        )
    ]


def _is_day(ts: datetime) -> bool:
    return ts.hour in DAY_HOURS  # hour in the post's own timezone


def _precip_phrase(precip: str) -> str:
    return "без осадков" if precip == "none" else f"и шёл {PRECIP_TEXT[precip]}"


def _fmt_date(day: date) -> str:
    return day.strftime("%d.%m")


def _fmt_temp(t: float) -> str:
    value = int(t) if float(t).is_integer() else t
    return f"+{value}" if value > 0 else str(value)


def _na(reason: str) -> Check:
    return Check(name="weather", status="n/a", summary=reason, evidence=[])
