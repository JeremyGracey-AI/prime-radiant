"""Tests for the Metaculus parsing boundary (raw post JSON -> our Question model)."""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from prime_radiant.metaculus import fetch_open_binary_questions, parse_binary_question

FIXTURE = Path(__file__).parent.parent / "fixtures" / "posts_response.json"


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
    assert question.resolution_criteria.startswith("The question will resolve as **Yes**")
    assert question.open_time == datetime(2026, 8, 19, 1, 10, tzinfo=UTC)
    assert question.close_time == datetime(2030, 1, 1, 0, 59, tzinfo=UTC)


def test_parse_rejects_non_binary_question() -> None:
    raw = load_posts()[1]
    assert raw["question"]["type"] == "multiple_choice"

    with pytest.raises(ValueError, match="binary"):
        parse_binary_question(raw)


def test_missing_timestamps_parse_as_none() -> None:
    raw = json.loads(json.dumps(load_posts()[0]))  # deep copy of the recorded post
    raw["question"].pop("open_time", None)
    raw["question"].pop("scheduled_close_time", None)
    question = parse_binary_question(raw)
    assert question.open_time is None
    assert question.close_time is None


def test_fetch_wires_the_filter_and_parses_recorded_posts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # boundary replay in the cassette spirit: the third-party call is patched to
    # return the RECORDED live-API posts; everything asserted is OUR wiring —
    # the filter our code builds, the strictness flag, and the parse mapping
    import forecasting_tools

    binary_posts = [raw for raw in load_posts() if raw["question"]["type"] == "binary"]
    assert binary_posts, "recorded fixture must contain binary posts"
    captured: dict = {}

    async def fake_get(api_filter, num_questions, error_if_question_target_missed):
        captured["filter"] = api_filter
        captured["num"] = num_questions
        captured["strict"] = error_if_question_target_missed

        class Fetched:
            def __init__(self, raw: dict) -> None:
                self.api_json = raw

        return [Fetched(raw) for raw in binary_posts[:num_questions]]

    monkeypatch.setattr(
        forecasting_tools.MetaculusApi,
        "get_questions_matching_filter",
        staticmethod(fake_get),
    )
    questions = fetch_open_binary_questions(limit=len(binary_posts))
    assert captured["num"] == len(binary_posts)
    assert captured["strict"] is False
    assert captured["filter"].allowed_types == ["binary"]
    assert captured["filter"].allowed_statuses == ["open"]
    assert [q.post_id for q in questions] == [raw["id"] for raw in binary_posts]
    assert all(q.title for q in questions)
