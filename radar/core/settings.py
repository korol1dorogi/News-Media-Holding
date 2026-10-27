"""Runtime settings from the environment and .env. An empty string means "not set"."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = ROOT / ".env"

# Same defaults as .env.example.
DEFAULTS = {
    "LLM_PROVIDER": "mock",
    "LLM_BASE_URL": "",
    "LLM_MODEL": "",
    "LLM_API_KEY": "",
    "DATA_DIR": "data/synthetic",
    "DB_PATH": "var/radar.sqlite3",
}


@dataclass(frozen=True)
class Settings:
    llm_provider: str = "mock"  # mock | openai
    llm_base_url: str = ""
    llm_model: str = ""
    llm_api_key: str = field(default="", repr=False)
    data_dir: Path = ROOT / "data" / "synthetic"
    db_path: Path = ROOT / "var" / "radar.sqlite3"
    profiles_dir: Path = ROOT / "data" / "profiles"
    reports_dir: Path = ROOT / "reports"


def read_env_file(path: Path) -> dict[str, str]:
    """Parse KEY=value lines. Comments and blank lines are skipped."""
    if not path.is_file():
        return {}
    values = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip("\"'")
    return values


def load_settings(
    env: Mapping[str, str] | None = None,
    env_file: Path | None = ENV_FILE,
) -> Settings:
    """Defaults < .env < process environment. Empty values do not override."""
    merged = dict(DEFAULTS)
    sources = [
        read_env_file(env_file) if env_file else {},
        os.environ if env is None else env,
    ]
    for source in sources:
        for key in DEFAULTS:
            value = source.get(key, "")
            if value != "":
                merged[key] = value
    return Settings(
        llm_provider=merged["LLM_PROVIDER"],
        llm_base_url=merged["LLM_BASE_URL"],
        llm_model=merged["LLM_MODEL"],
        llm_api_key=merged["LLM_API_KEY"],
        data_dir=_path(merged["DATA_DIR"]),
        db_path=_path(merged["DB_PATH"]),
    )


def _path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path
