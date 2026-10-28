"""Dossier assembly into a traffic light (task V4).

red: any check failed. yellow: at most one independent source and no official confirmation.
green: otherwise. A missing check counts as "n/a"; provenance "warn" alone is not red.
"""

from __future__ import annotations

from radar.core.models import Check, Dossier, Event


def _status(checks: list[Check], name: str) -> str:
    return next((c.status for c in checks if c.name == name), "n/a")


def _level(checks: list[Check], independent: int) -> str:
    if any(c.status == "fail" for c in checks):
        return "red"
    if independent <= 1 and _status(checks, "official") != "ok":
        return "yellow"
    return "green"


def _todo_item(check: Check, first_id: str, level: str) -> str | None:
    if check.name == "provenance" and check.status == "warn":
        return f"Найти второй независимый источник или связаться с автором поста {first_id}"
    if check.name == "media_archive" and check.status == "fail":
        archive_id = next((e["archive_id"] for e in check.evidence if "archive_id" in e), None)
        suffix = f" (запись {archive_id})" if archive_id else ""
        return f"Не использовать фото: оно уже было в архиве{suffix}"
    if check.name == "weather" and check.status == "fail":
        return "Запросить у автора оригинал фото и место съёмки"
    if check.name == "official":
        if check.status == "fail":
            return "Не подавать как факт: официальный канал опроверг, запросить комментарий"
        if check.status == "n/a" and level != "green":
            return "Запросить комментарий у профильного ведомства"
        if check.status == "ok":
            return None
    if check.status in ("warn", "fail"):
        return f"Проверить вручную: {check.summary}"
    return None


def build_dossier(event: Event, checks: list[Check], first_id: str, independent: int) -> Dossier:
    """Combine checks into green/yellow/red and a todo list for the editor."""
    level = _level(checks, independent)
    todo = [_todo_item(c, first_id, level) for c in checks]
    if level != "green" and not any(c.name == "official" for c in checks):
        todo.append("Запросить комментарий у профильного ведомства")
    return Dossier(
        event_id=event.id,
        level=level,
        first_source_post_id=first_id,
        independent_sources=independent,
        checks=checks,
        todo=list(dict.fromkeys(t for t in todo if t)),
    )
