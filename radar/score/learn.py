"""Learned newsworthiness score (task C4).

Logistic regression on the same five features as the manual score (radar.score.FEATURES),
trained on "published / not published" labels. In production the labels come from the
outlet's archive and the editor's button; here they are synthetic: past events with random
features, labelled by a hidden editorial taste plus noise (data/labels/{outlet}.jsonl).
The manual score stays the default; S2 compares both by ROC AUC on a held-out split.
"""

from __future__ import annotations

import json
import math
import random
from pathlib import Path

from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score

from radar.score import FEATURES, _weights

ROOT = Path(__file__).resolve().parents[2]
LABELS_DIR = ROOT / "data" / "labels"
SEED = 20261028
N_EVENTS = 400
TEST_SHARE = 0.3

# Hidden editorial taste that produced the synthetic labels: what each outlet really published.
# It differs from the hand-written profiles on purpose, so learning has something to find.
TASTE = {
    "mash": {"topic": 2.0, "geo": 0.5, "reach": 0.5, "speed": 2.5, "media": 2.0},
    "life": {"topic": 2.0, "geo": 1.5, "reach": 2.5, "speed": 0.3, "media": 0.3},
    "super": {"topic": 3.0, "geo": 1.5, "reach": 0.8, "speed": 0.3, "media": 1.0},
}


def synthetic_labels(outlet: str, n: int = N_EVENTS, seed: int = SEED) -> list[dict]:
    """Past events: feature values 0..1 and whether the outlet published them."""
    rng = random.Random(f"{seed}:{outlet}")
    taste = TASTE[outlet]
    centre = sum(taste.values()) / 2
    rows = []
    for i in range(n):
        x = {name: round(rng.random(), 3) for name in FEATURES}
        x["media"] = float(rng.random() < 0.5)
        logit = sum(taste[name] * x[name] for name in FEATURES) - centre + rng.gauss(0, 0.7)
        rows.append({"id": f"{outlet}_{i:03d}", **x, "published": logit > 0})
    return rows


def write_labels(out: Path = LABELS_DIR) -> None:
    out.mkdir(parents=True, exist_ok=True)
    for outlet in TASTE:
        lines = [json.dumps(row, ensure_ascii=False) for row in synthetic_labels(outlet)]
        (out / f"{outlet}.jsonl").write_text(
            "\n".join(lines) + "\n", encoding="utf-8", newline="\n"
        )


def load_labels(outlet: str, labels_dir: Path = LABELS_DIR) -> list[dict]:
    path = labels_dir / f"{outlet}.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def split(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    """Deterministic split by id: the last TEST_SHARE of the ids go to the test set."""
    ordered = sorted(rows, key=lambda row: row["id"])
    cut = math.floor(len(ordered) * (1 - TEST_SHARE))
    return ordered[:cut], ordered[cut:]


def matrix(rows: list[dict]) -> list[list[float]]:
    return [[float(row[name]) for name in FEATURES] for row in rows]


def train(rows: list[dict]) -> LogisticRegression:
    model = LogisticRegression(random_state=0)
    model.fit(matrix(rows), [bool(row["published"]) for row in rows])
    return model


def manual_scores(rows: list[dict], profile: dict) -> list[float]:
    """The C3 formula on stored features: weighted mean with the profile's weights."""
    weights = _weights(profile)
    total = sum(weights.values())
    return [sum(weights[name] * float(row[name]) for name in FEATURES) / total for row in rows]


def compare(outlet: str, profile: dict, labels_dir: Path = LABELS_DIR) -> dict:
    """ROC AUC of the manual score and of the learned model on the held-out split."""
    train_rows, test_rows = split(load_labels(outlet, labels_dir))
    labels = [bool(row["published"]) for row in test_rows]
    model = train(train_rows)
    learned = model.predict_proba(matrix(test_rows))[:, 1]
    return {
        "outlet": outlet,
        "train": len(train_rows),
        "test": len(test_rows),
        "manual_auc": round(float(roc_auc_score(labels, manual_scores(test_rows, profile))), 3),
        "learned_auc": round(float(roc_auc_score(labels, learned)), 3),
        "learned_weights": {
            name: round(float(w), 2) for name, w in zip(FEATURES, model.coef_[0], strict=True)
        },
    }


if __name__ == "__main__":
    write_labels()
    print(f"labels written to {LABELS_DIR}")
