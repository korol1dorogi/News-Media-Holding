"""Metrics against truth.yaml (task S2). Stub: writes an empty reports/metrics.json."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"


def main() -> None:
    # TODO(S2): time from the first post to the feed, posts per event, dossier level match
    # with truth.yaml, LLM calls per 100 posts. Done when make eval writes metrics.json and
    # metrics.md (docs/tasks.md, S2).
    metrics: dict = {}
    REPORTS.mkdir(exist_ok=True)
    path = REPORTS / "metrics.json"
    path.write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    print(f"metrics written to {path}: {metrics}")


if __name__ == "__main__":
    main()
