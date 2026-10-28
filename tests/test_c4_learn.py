"""C4: a learned score on published / not labels, compared with the manual weights."""

from pathlib import Path

from radar.pipeline import PROFILES_DIR, load_profiles
from radar.score.learn import (
    LABELS_DIR,
    TASTE,
    compare,
    load_labels,
    split,
    synthetic_labels,
    train,
    write_labels,
)


def test_committed_labels_match_generator(tmp_path: Path) -> None:
    write_labels(tmp_path)
    for outlet in TASTE:
        name = f"{outlet}.jsonl"
        assert (tmp_path / name).read_bytes() == (LABELS_DIR / name).read_bytes(), outlet


def test_labels_are_balanced_enough() -> None:
    for outlet in TASTE:
        rows = load_labels(outlet)
        share = sum(row["published"] for row in rows) / len(rows)
        assert 0.3 < share < 0.7, outlet


def test_split_is_deterministic_and_disjoint() -> None:
    rows = synthetic_labels("mash")
    train_rows, test_rows = split(rows)
    assert {r["id"] for r in train_rows}.isdisjoint({r["id"] for r in test_rows})
    assert split(list(reversed(rows))) == (train_rows, test_rows)


def test_training_is_deterministic() -> None:
    rows = split(load_labels("life"))[0]
    assert train(rows).coef_.tolist() == train(rows).coef_.tolist()


def test_model_recovers_editorial_taste() -> None:
    profiles = load_profiles(PROFILES_DIR)
    mash = compare("mash", profiles["mash"])["learned_weights"]
    life = compare("life", profiles["life"])["learned_weights"]
    assert mash["speed"] > mash["geo"]
    assert life["reach"] > life["speed"]


def test_both_scores_rank_well() -> None:
    profiles = load_profiles(PROFILES_DIR)
    for outlet in TASTE:
        result = compare(outlet, profiles[outlet])
        assert result["manual_auc"] > 0.8, outlet
        assert result["learned_auc"] > 0.8, outlet
