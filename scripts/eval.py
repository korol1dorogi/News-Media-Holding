"""Metrics against truth.yaml (task S2).

Runs the pipeline on a replay directory and compares it with truth.yaml: time to signal,
cluster recall and purity, dossier levels, first source and independent sources, claim check
on drafts (inject_error), LLM calls and ablations without each dossier check. Writes
reports/metrics.json and reports/metrics.md. No wall-clock values: the output is deterministic.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import statistics
from pathlib import Path
from typing import Any

import yaml

from radar import verify
from radar.core.models import Dossier, Event, Post
from radar.draft import check_claims, generate
from radar.llm import MockProvider
from radar.pipeline import OUTLETS, Result, process

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA = ROOT / "data" / "synthetic"
DEFAULT_REPORTS = ROOT / "reports"
SIGNAL_POSTS = 2  # an event shows up in the feed once its cluster has this many posts
CHECKS = ("provenance", "media_archive", "weather", "official")
CHECK_TITLES = {
    "provenance": "первоисточник и независимые источники (V1)",
    "media_archive": "фото по архиву (V2)",
    "weather": "погода на фото (V3)",
    "official": "официальные каналы (V4)",
}


class CountingProvider:
    """Wraps the mock and counts calls."""

    def __init__(self, inner: MockProvider) -> None:
        self.inner = inner
        self.calls = 0

    def complete(self, system: str, user: str) -> str:
        self.calls += 1
        return self.inner.complete(system, user)


def match(truth: list[dict], events: list[Event]) -> dict[str, Event | None]:
    """truth key -> the event with the largest overlap of post ids."""
    result = {}
    for item in truth:
        wanted = set(item["post_ids"])
        best = max(events, key=lambda e: (len(wanted & set(e.post_ids)), e.id), default=None)
        result[item["key"]] = best if best and wanted & set(best.post_ids) else None
    return result


def minutes(later, earlier) -> float:
    return round((later - earlier).total_seconds() / 60, 1)


def per_event(truth: list[dict], result: Result, matched: dict[str, Event | None]) -> list[dict]:
    by_id = {post.id: post for post in result.posts}
    dossiers = {d.event_id: d for d in result.dossiers}
    rows = []
    for item in truth:
        event = matched[item["key"]]
        wanted = set(item["post_ids"])
        first_truth = min(by_id[i].ts for i in wanted if i in by_id)
        row: dict[str, Any] = {"key": item["key"], "found": event is not None}
        if event is None:
            rows.append(row)
            continue
        got = set(event.post_ids)
        dossier = dossiers[event.id]
        times = sorted(by_id[i].ts for i in event.post_ids)
        signal = times[min(SIGNAL_POSTS, len(times)) - 1]
        statuses = {c.name: c.status for c in dossier.checks}
        row.update(
            {
                "event_id": event.id,
                "recall": round(len(wanted & got) / len(wanted), 3),
                "purity": round(len(wanted & got) / len(got), 3),
                "minutes_to_signal": minutes(signal, first_truth),
                "level": dossier.level,
                "expected_level": item.get("expected_level"),
                "level_ok": item.get("expected_level") in (None, dossier.level),
                "expected_fail": item.get("expected_fail"),
                "fail_ok": item.get("expected_fail") is None
                or statuses.get(item["expected_fail"]) == "fail",
                "first_source": dossier.first_source_post_id,
                "first_source_ok": item.get("first_source") in (None, dossier.first_source_post_id),
                "independent": dossier.independent_sources,
                "independent_ok": item.get("independent_sources")
                in (None, dossier.independent_sources),
                "checks": statuses,
            }
        )
        rows.append(row)
    return rows


def claims_eval(truth: list[dict], result: Result, matched: dict[str, Event | None], llm) -> dict:
    """Unsupported claims per draft: injected events must have one, the others none."""
    by_id = {post.id: post for post in result.posts}
    injected = {item["key"] for item in truth if item.get("inject_error")}
    rows = []
    for item in truth:
        event = matched[item["key"]]
        if event is None:
            continue
        own = [by_id[i] for i in event.post_ids]
        for outlet in OUTLETS:
            draft = check_claims(generate(event, own, outlet, llm), own)
            flagged = [c.text for c in draft.claims if not c.supported]
            rows.append(
                {
                    "key": item["key"],
                    "outlet": outlet,
                    "claims": len(draft.claims),
                    "unsupported": flagged,
                    "injected": item["key"] in injected,
                }
            )
    inj = [r for r in rows if r["injected"]]
    clean = [r for r in rows if not r["injected"]]
    return {
        "drafts": len(rows),
        "claims": sum(r["claims"] for r in rows),
        "injected_drafts": len(inj),
        "injected_caught": sum(1 for r in inj if len(r["unsupported"]) == 1),
        "clean_drafts": len(clean),
        "false_alarms": sum(len(r["unsupported"]) for r in clean),
        "rows": rows,
    }


def ablations(truth: list[dict], result: Result, matched: dict[str, Event | None]) -> list[dict]:
    """Dossier levels when one check is switched off (its status becomes n/a)."""
    dossiers = {d.event_id: d for d in result.dossiers}
    events = {e.id: e for e in result.events}
    rows = []
    for name in CHECKS:
        missed, changed, correct, total = [], [], 0, 0
        for item in truth:
            event = matched[item["key"]]
            expected = item.get("expected_level")
            if event is None or expected is None:
                continue
            level = _ablated(events[event.id], dossiers[event.id], name).level
            total += 1
            correct += level == expected
            if level != expected:
                changed.append(f"{item['key']}: {expected} → {level}")
            if expected != "green" and level == "green":
                missed.append(item["key"])
        rows.append(
            {
                "without": name,
                "level_accuracy": round(correct / total, 3) if total else None,
                "missed_fakes": missed,
                "changed": changed,
            }
        )
    return rows


def _ablated(event: Event, dossier: Dossier, name: str) -> Dossier:
    checks = [dataclasses.replace(c, status="n/a") if c.name == name else c for c in dossier.checks]
    independent = dossier.independent_sources
    if name == "provenance":
        independent = max(independent, len(event.post_ids))  # every post counts as a source
    return verify.build_dossier(event, checks, dossier.first_source_post_id, independent)


def summarize(posts: list[Post], result: Result, rows: list[dict], claims: dict) -> dict:
    found = [r for r in rows if r["found"]]
    in_events = sum(len(e.post_ids) for e in result.events)
    waits = [r["minutes_to_signal"] for r in found]
    graded = [r for r in found if r["expected_level"]]
    return {
        "posts": len(posts),
        "events_in_feed": len(result.events),
        "truth_events": len(rows),
        "truth_events_found": len(found),
        "posts_per_event": round(in_events / len(result.events), 2) if result.events else 0,
        "posts_left_as_noise": len(posts) - in_events,
        "cluster_recall_mean": _mean(r["recall"] for r in found),
        "cluster_purity_mean": _mean(r["purity"] for r in found),
        "minutes_to_signal_median": statistics.median(waits) if waits else None,
        "minutes_to_signal_max": max(waits) if waits else None,
        "dossier_level_accuracy": _share(r["level_ok"] for r in graded),
        "expected_fail_accuracy": _share(r["fail_ok"] for r in found if r["expected_fail"]),
        "first_source_accuracy": _share(r["first_source_ok"] for r in found),
        "independent_sources_accuracy": _share(r["independent_ok"] for r in found),
        "llm_calls_feed_per_100_posts": 0.0,
        "llm_calls_per_draft": claims["llm_calls_per_draft"],
        "claim_check_injected_caught": f"{claims['injected_caught']}/{claims['injected_drafts']}",
        "claim_check_false_alarms": claims["false_alarms"],
    }


def _mean(values) -> float | None:
    values = list(values)
    return round(statistics.fmean(values), 3) if values else None


def _share(values) -> float | None:
    values = list(values)
    return round(sum(values) / len(values), 3) if values else None


def render_md(data_dir: str, summary: dict, rows: list[dict], claims: dict, abl: list) -> str:
    yes = {True: "да", False: "НЕТ"}
    lines = [
        "# Замеры «Сигнала»",
        "",
        f"Данные: `{data_dir}` (синтетика). Отчёт генерирует `make eval`, руками не править.",
        "",
        "## Сводка",
        "",
        "| Метрика | Значение |",
        "|---|---|",
        f"| Постов в потоке | {summary['posts']} |",
        f"| Событий в ленте | {summary['events_in_feed']} |",
        f"| Демо-событий найдено | {summary['truth_events_found']} из {summary['truth_events']} |",
        f"| Постов на событие (дубли схлопнуты) | {summary['posts_per_event']} |",
        f"| Постов отсеяно как шум | {summary['posts_left_as_noise']} |",
        f"| Полнота кластеров, среднее | {summary['cluster_recall_mean']} |",
        f"| Чистота кластеров, среднее | {summary['cluster_purity_mean']} |",
        f"| Минут до сигнала, медиана | {summary['minutes_to_signal_median']} |",
        f"| Минут до сигнала, максимум | {summary['minutes_to_signal_max']} |",
        f"| Точность уровня досье | {summary['dossier_level_accuracy']} |",
        f"| Нужная проверка дала fail | {summary['expected_fail_accuracy']} |",
        f"| Первоисточник найден верно | {summary['first_source_accuracy']} |",
        f"| Число независимых источников верно | {summary['independent_sources_accuracy']} |",
        f"| Вызовов LLM на 100 постов ленты | {summary['llm_calls_feed_per_100_posts']} |",
        f"| Вызовов LLM на один черновик | {summary['llm_calls_per_draft']} |",
        f"| Сверка: ошибка поймана | {summary['claim_check_injected_caught']} |",
        f"| Сверка: ложных тревог | {summary['claim_check_false_alarms']} |",
        "",
        "## Демо-события",
        "",
        "| Событие | Уровень | Ожидали | Верно | Мин. до сигнала | Полнота | Чистота "
        "| Первоисточник | Источников |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        if not r["found"]:
            lines.append(f"| {r['key']} | не найдено | | НЕТ | | | | | |")
            continue
        lines.append(
            f"| {r['key']} | {r['level']} | {r['expected_level'] or '—'} "
            f"| {yes[r['level_ok'] and r['fail_ok']]} | {r['minutes_to_signal']} "
            f"| {r['recall']} | {r['purity']} | {yes[r['first_source_ok']]} "
            f"| {r['independent']} ({yes[r['independent_ok']]}) |"
        )
    lines += [
        "",
        "## Сверка утверждений черновиков",
        "",
        f"Черновиков: {claims['drafts']}, утверждений: {claims['claims']}. "
        f"Событие с внедрённой ошибкой поймано в {claims['injected_caught']} "
        f"из {claims['injected_drafts']} черновиков, ложных тревог: {claims['false_alarms']}.",
        "",
        "| Событие | Издание | Утверждений | Не подтверждено |",
        "|---|---|---|---|",
    ]
    for r in claims["rows"]:
        flagged = ", ".join(f"«{t}»" for t in r["unsupported"]) or "—"
        lines.append(f"| {r['key']} | {r['outlet']} | {r['claims']} | {flagged} |")
    lines += [
        "",
        "## Абляции: что перестаём ловить без проверки",
        "",
        "| Без проверки | Точность уровня | Фейки, ставшие зелёными | Изменился уровень |",
        "|---|---|---|---|",
    ]
    for r in abl:
        missed = ", ".join(r["missed_fakes"]) or "—"
        title = CHECK_TITLES[r["without"]]
        changed = ", ".join(r["changed"]) or "—"
        lines.append(f"| {title} | {r['level_accuracy']} | {missed} | {changed} |")
    return "\n".join(lines) + "\n"


def evaluate(data_dir: Path) -> tuple[dict, str]:
    truth = yaml.safe_load((data_dir / "truth.yaml").read_text(encoding="utf-8"))["events"]
    result = process(data_dir)
    matched = match(truth, result.events)
    rows = per_event(truth, result, matched)
    llm = CountingProvider(MockProvider(truth_path=data_dir / "truth.yaml"))
    claims = claims_eval(truth, result, matched, llm)
    claims["llm_calls_per_draft"] = (
        round(llm.calls / claims["drafts"], 2) if claims["drafts"] else 0
    )
    abl = ablations(truth, result, matched)
    summary = summarize(result.posts, result, rows, claims)
    try:
        shown = data_dir.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        shown = data_dir.name
    metrics = {
        "data_dir": shown,
        "summary": summary,
        "events": rows,
        "claims": claims,
        "ablations": abl,
    }
    return metrics, render_md(shown, summary, rows, claims, abl)


def main() -> None:
    parser = argparse.ArgumentParser(description="Metrics against truth.yaml")
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--out", type=Path, default=DEFAULT_REPORTS)
    args = parser.parse_args()
    metrics, markdown = evaluate(args.data)
    args.out.mkdir(parents=True, exist_ok=True)
    text = json.dumps(metrics, ensure_ascii=False, indent=2) + "\n"
    (args.out / "metrics.json").write_text(text, encoding="utf-8", newline="\n")
    (args.out / "metrics.md").write_text(markdown, encoding="utf-8", newline="\n")
    print(markdown)


if __name__ == "__main__":
    main()
