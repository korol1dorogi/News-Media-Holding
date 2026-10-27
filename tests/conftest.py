from pathlib import Path

import pytest

from radar.core.settings import ROOT, Settings

MINI = ROOT / "tests" / "fixtures" / "mini"


@pytest.fixture
def mini_dir() -> Path:
    return MINI


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    """Mini dataset, a fresh DB and an empty reports dir for every test."""
    return Settings(
        data_dir=MINI,
        db_path=tmp_path / "radar.sqlite3",
        reports_dir=tmp_path / "reports",
    )
