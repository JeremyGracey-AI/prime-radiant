"""Shared test configuration: VCR cassettes live under tests/cassettes/<module>/.

dashboard/ goes on sys.path because its modules ship flat to the HF Space root
and import as siblings (`import panel_data`) — mirrored here and in pyright's
executionEnvironments.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "dashboard"))


@pytest.fixture(scope="module")
def vcr_cassette_dir(request: pytest.FixtureRequest) -> str:
    return str(Path(__file__).parent / "cassettes" / request.module.__name__)
