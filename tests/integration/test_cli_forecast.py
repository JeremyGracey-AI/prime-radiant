"""End-to-end dry run: the CLI emits a submission file that validates."""

import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

REPO_ROOT = Path(__file__).parents[2]


def test_forecast_then_validate_roundtrip(tmp_path: Path) -> None:
    out_dir = tmp_path / "model-output"
    run = subprocess.run(
        [
            sys.executable,
            "-m",
            "prime_radiant.epi.cli",
            "epi",
            "forecast",
            "--reference-date",
            "auto",
            "--out",
            str(out_dir),
            "--hub",
            "data/hub",
            "--vintage-cache",
            "data/vintage_cache",
            "--backtest-dir",
            "data/backtest",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=600,
    )
    assert run.returncode == 0, run.stderr
    files = list(out_dir.glob("*.csv"))
    assert len(files) == 1
    assert files[0].name.endswith("-JGracey-prime_radiant.csv")

    validate = subprocess.run(
        [sys.executable, "-m", "prime_radiant.epi.cli", "epi", "validate", str(files[0])],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert validate.returncode == 0, validate.stdout + validate.stderr
    assert "valid:" in validate.stdout
