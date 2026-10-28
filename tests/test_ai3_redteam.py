"""AI3: red team scenarios for drafts (tests/redteam/*.yaml); summary in reports/redteam.md."""

import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest
import yaml

from radar.core.models import Draft, Event, Post
from radar.core.settings import ROOT
from radar.draft import check_claims, generate
from radar.draft.generate import FALLBACK_WARNING
from radar.llm import MockProvider

SCENARIOS_DIR = ROOT / "tests" / "redteam"
REPORT = ROOT / "reports" / "redteam.md"
TS = datetime.fromisoformat("2026-10-27T08:00:00+03:00")


def load_scenarios() -> list[dict]:
    scenarios = []
    for path in sorted(SCENARIOS_DIR.glob("*.yaml")):
        scenarios += yaml.safe_load(path.read_text(encoding="utf-8"))
    return scenarios


SCENARIOS = load_scenarios()


class Scripted:
    def __init__(self, answers: list[str]) -> None:
        self.answers = answers
        self.calls = 0

    def complete(self, system: str, user: str) -> str:
        self.calls += 1
        return self.answers[min(self.calls, len(self.answers)) - 1]


def build(scenario: dict) -> tuple[Event, list[Post]]:
    texts = list(scenario["posts"])
    if texts and scenario.get("repeat_last"):
        texts[-1] = texts[-1] * scenario["repeat_last"]
    posts = [
        Post(
            id=f"p{i}",
            channel_id=f"ch{i}",
            ts=TS + timedelta(minutes=5 * i),
            text=text,
            url=f"https://example.invalid/{i}",
            media=[],
            forward_from=None,
        )
        for i, text in enumerate(texts, start=1)
    ]
    title = texts[0].split(".")[0][:90] if texts else "Событие без постов"
    event = Event(
        id=f"ev_{scenario['id']}",
        post_ids=[p.id for p in posts],
        first_ts=TS,
        title=title,
        geo=None,
        topic=None,
        scores={},
    )
    return event, posts


def provider(scenario: dict):
    if "answer" in scenario:
        return Scripted([json.dumps(scenario["answer"], ensure_ascii=False)])
    if "raw" in scenario:
        return Scripted(list(scenario["raw"]))
    return MockProvider()


def run(scenario: dict) -> Draft:
    event, posts = build(scenario)
    return check_claims(
        generate(event, posts, scenario.get("outlet", "mash"), provider(scenario)), posts
    )


def failures(scenario: dict, draft: Draft) -> list[str]:
    """What went wrong compared to expect; empty when the system behaved."""
    expect = scenario["expect"]
    problems = []
    unsupported = [c.text for c in draft.claims if not c.supported]
    if "unsupported" in expect and unsupported != expect["unsupported"]:
        problems.append(f"не подтверждено {unsupported}, ожидали {expect['unsupported']}")
    for needle in expect.get("warnings", []):
        if not any(needle in w for w in draft.warnings):
            problems.append(f"нет предупреждения «{needle}»")
    if expect.get("clean") and draft.warnings:
        problems.append(f"лишние предупреждения: {draft.warnings}")
    if "fallback" in expect and (FALLBACK_WARNING in draft.warnings) != expect["fallback"]:
        problems.append("неверный запасной черновик")
    return problems


def test_at_least_twenty_scenarios() -> None:
    assert len(SCENARIOS) >= 20
    assert len({s["id"] for s in SCENARIOS}) == len(SCENARIOS)


@pytest.mark.parametrize("scenario", SCENARIOS, ids=[s["id"] for s in SCENARIOS])
def test_scenario(scenario: dict) -> None:
    assert failures(scenario, run(scenario)) == []


def test_long_post_is_cut_in_the_prompt() -> None:
    from radar.draft.generate import MAX_POST_CHARS, build_user

    event, posts = build({"id": "long", "posts": ["а" * 50_000]})
    assert len(build_user(event, posts, "mash")) < MAX_POST_CHARS + 2_000


def render_report() -> str:
    lines = [
        "# Red team черновиков",
        "",
        "Сценарии — `tests/redteam/*.yaml`, прогон — `tests/test_ai3_redteam.py` в `make check`.",
        "Файл перезаписывается при каждом прогоне тестов.",
        "",
        "| Сценарий | Что проверяем | Итог | Предупреждения системы |",
        "|---|---|---|---|",
    ]
    passed = 0
    for scenario in SCENARIOS:
        draft = run(scenario)
        problems = failures(scenario, draft)
        passed += not problems
        verdict = "✅" if not problems else "❌ " + "; ".join(problems)
        shown = " / ".join(w.split(":")[0] for w in draft.warnings) or "—"
        lines.append(f"| `{scenario['id']}` | {scenario['title']} | {verdict} | {shown} |")
    lines[5:5] = [f"Пройдено: {passed} из {len(SCENARIOS)}.", ""]
    return "\n".join(lines) + "\n"


def test_report_is_written() -> None:
    report = render_report()
    REPORT.parent.mkdir(exist_ok=True)
    Path(REPORT).write_text(report, encoding="utf-8", newline="\n")
    assert f"Пройдено: {len(SCENARIOS)} из {len(SCENARIOS)}." in report
