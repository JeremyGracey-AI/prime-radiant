"""Tests for the Metaculus parsing boundary (raw post JSON -> our Question model)."""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from prime_radiant.metaculus import parse_binary_question

FIXTURE = Path(__file__).parent / "fixtures" / "posts_response.json"


def load_posts() -> list[dict]:
    return json.loads(FIXTURE.read_text())["results"]


def test_parse_binary_question_maps_core_fields() -> None:
    raw = load_posts()[0]

    question = parse_binary_question(raw)

    assert question.post_id == 45207
    assert question.question_id == 45402
    assert question.title == (
        "Will a fault-tolerant quantum computer be available to commercial users"
        " before January 1, 2030?"
    )
    assert question.page_url == "https://www.metaculus.com/questions/45207"
    assert question.state == "open"
    assert question.background is not None
    assert question.background.startswith(
        "*This forecasting question is associated with the Verity"
    )
    assert question.resolution_criteria is not None
    assert question.resolution_criteria.startswith(
        "The question will resolve as **Yes**"
    )
    assert question.open_time == datetime(2026, 8, 19, 1, 10, tzinfo=UTC)
    assert question.close_time == datetime(2030, 1, 1, 0, 59, tzinfo=UTC)


def test_parse_rejects_non_binary_question() -> None:
    raw = load_posts()[1]
    assert raw["question"]["type"] == "multiple_choice"

    with pytest.raises(ValueError, match="binary"):
        parse_binary_question(raw)
