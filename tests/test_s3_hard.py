"""S3: hard synthetic data is deterministic, labelled, and S2 runs on it."""

import importlib.util
from pathlib import Path

import pytest
import yaml

from radar.core.settings import ROOT
from radar.ingest import load_replay

HARD = ROOT / "data" / "synthetic_hard"
HARD_KEYS = {
    "hard_copy_numbers",
    "hard_mirrored_photo",
    "hard_late_denial",
    "hard_official_other_event",
}


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def truth() -> list[dict]:
    return yaml.safe_load((HARD / "truth.yaml").read_text(encoding="utf-8"))["events"]


def test_committed_data_matches_generator(tmp_path: Path) -> None:
    generator = load("gen_synthetic_hard", ROOT / "scripts" / "gen_synthetic_hard.py")
    fresh = tmp_path / "hard"
    generator.generate(fresh)
    for name in ("channels.json", "posts.jsonl", "truth.yaml", "weather.json"):
        assert (fresh / name).read_bytes() == (HARD / name).read_bytes(), name
    assert sorted(p.name for p in (fresh / "media").iterdir()) == sorted(
        p.name for p in (HARD / "media").iterdir()
    )


def test_hard_events_are_labelled(truth) -> None:
    keys = {item["key"] for item in truth}
    assert HARD_KEYS <= keys
    assert {"dtp_entry", "flood_old_photo", "plant_rumor", "mall_fire", "snowfall"} <= keys
    _, posts = load_replay(HARD)
    ids = {post.id for post in posts}
    assert len(posts) > 3 * 500
    for item in truth:
        assert set(item["post_ids"]) <= ids, item["key"]


def test_second_city_exists() -> None:
    channels, _ = load_replay(HARD)
    assert len({channel.region for channel in channels}) == 2


def test_eval_runs_and_reports_honestly(truth) -> None:
    evaluate = load("radar_eval_hard", ROOT / "scripts" / "eval.py").evaluate
    metrics, markdown = evaluate(HARD)
    summary = metrics["summary"]
    assert summary["truth_events"] == len(truth)
    assert summary["truth_events_found"] == len(truth)
    assert summary["claim_check_false_alarms"] == 0
    assert "## Демо-события" in markdown
