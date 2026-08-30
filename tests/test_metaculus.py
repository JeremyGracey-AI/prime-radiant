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

    assert question.post_id == 38195
    assert question.question_id == 37642
    assert question.title == (
        "Will SpaceX's Starship complete a successful orbital flight before 2027?"
    )
    assert question.page_url == "https://www.metaculus.com/questions/38195"
    assert question.state == "open"
    assert question.background is not None
    assert question.background.startswith("SpaceX has been developing")
    assert question.resolution_criteria is not None
    assert question.resolution_criteria.startswith("This question resolves Yes")
    assert question.open_time == datetime(2026, 1, 16, 12, 0, tzinfo=UTC)
    assert question.close_time == datetime(2026, 12, 31, 23, 0, tzinfo=UTC)


def test_parse_rejects_non_binary_question() -> None:
    raw = load_posts()[1]
    assert raw["question"]["type"] == "multiple_choice"

    with pytest.raises(ValueError, match="binary"):
        parse_binary_question(raw)
