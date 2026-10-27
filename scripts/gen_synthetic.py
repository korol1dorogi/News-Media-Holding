"""Synthetic data generator (task S1). Stub: copies the mini fixture into data/synthetic."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MINI = ROOT / "tests" / "fixtures" / "mini"
DEFAULT_OUT = ROOT / "data" / "synthetic"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    # TODO(S1): ~40 channels, 400-600 posts over 48 hours, forwards and copies, noise,
    # PIL images with archive copies, weather.json, media/meta.json, truth.yaml for the demo.
    # Fixed seed. Done when the output is identical on every run and every demo event
    # is in truth.yaml (docs/tasks.md, S1).
    shutil.copytree(MINI, args.out, dirs_exist_ok=True)
    print(f"synthetic data written to {args.out}")


if __name__ == "__main__":
    main()
