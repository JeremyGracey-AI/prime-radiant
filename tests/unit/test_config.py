"""Tests for config: cost caps must exist as configurable values."""

import pytest

from prime_radiant.config import Settings


def test_default_cost_caps() -> None:
    # _env_file is a runtime-valid pydantic-settings kwarg missing from its stubs;
    # None keeps a developer's real .env out of the test.
    settings = Settings(_env_file=None)  # pyright: ignore[reportCallIssue]

    assert settings.per_question_budget_usd == 0.25
    assert settings.per_run_budget_usd == 2.50


def test_env_overrides_per_question_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PER_QUESTION_BUDGET_USD", "0.10")

    settings = Settings(_env_file=None)  # pyright: ignore[reportCallIssue]

    assert settings.per_question_budget_usd == 0.10
