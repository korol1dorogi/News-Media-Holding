"""S2: make eval writes deterministic metrics that match truth.yaml on the synthetic data."""

import importlib.util
import json
from pathlib import Path

import pytest

from radar.core.settings import ROOT

SPEC = importlib.util.spec_from_file_location("radar_eval", ROOT / "scripts" / "eval.py")
assert SPEC and SPEC.loader
eval_script = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(eval_script)

SYNTHETIC = ROOT / "data" / "synthetic"
MINI = ROOT / "tests" / "fixtures" / "mini"


@pytest.fixture(scope="module")
def synthetic() -> tuple[dict, str]:
    return eval_script.evaluate(SYNTHETIC)


def test_demo_scenario_matches_truth(synthetic) -> None:
    summary = synthetic[0]["summary"]
    assert summary["truth_events_found"] == summary["truth_events"] == 6
    for key in (
        "dossier_level_accuracy",
        "expected_fail_accuracy",
        "first_source_accuracy",
        "independent_sources_accuracy",
        "cluster_recall_mean",
    ):
        assert summary[key] == 1.0, key


def test_claim_check_catches_injected_error_without_false_alarms(synthetic) -> None:
    claims = synthetic[0]["claims"]
    assert claims["injected_drafts"] == claims["injected_caught"] == 3
    assert claims["false_alarms"] == 0


def test_feed_does_not_call_llm(synthetic) -> None:
    summary = synthetic[0]["summary"]
    assert summary["llm_calls_feed_per_100_posts"] == 0.0
    assert summary["llm_calls_per_draft"] == 1.0


def test_each_check_catches_its_fake(synthetic) -> None:
    changed = {row["without"]: row["changed"] for row in synthetic[0]["ablations"]}
    assert any(c.startswith("plant_rumor") for c in changed["provenance"])
    assert any(c.startswith("flood_old_photo") for c in changed["media_archive"])
    assert any(c.startswith("snowfall") for c in changed["weather"])
    assert any(c.startswith("mall_fire") for c in changed["official"])


def test_eval_is_deterministic(synthetic) -> None:
    again = eval_script.evaluate(SYNTHETIC)
    assert json.dumps(again[0], ensure_ascii=False) == json.dumps(synthetic[0], ensure_ascii=False)
    assert again[1] == synthetic[1]


def test_markdown_has_all_sections(synthetic) -> None:
    markdown = synthetic[1]
    for title in ("## Сводка", "## Демо-события", "## Сверка утверждений", "## Абляции"):
        assert title in markdown


def test_main_writes_reports(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("sys.argv", ["eval.py", "--data", str(MINI), "--out", str(tmp_path)])
    eval_script.main()
    metrics = json.loads((tmp_path / "metrics.json").read_text(encoding="utf-8"))
    assert metrics["summary"]["truth_events"] == 2
    assert (tmp_path / "metrics.md").read_text(encoding="utf-8").startswith("# Замеры")
