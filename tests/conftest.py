"""Shared test configuration: VCR cassettes live under tests/cassettes/<module>/."""

from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def vcr_cassette_dir(request: pytest.FixtureRequest) -> str:
    return str(Path(__file__).parent / "cassettes" / request.module.__name__)
