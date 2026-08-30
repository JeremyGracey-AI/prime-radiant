"""Metaculus boundary: thin fetch via forecasting-tools, pure parsing owned here.

The parsing layer takes raw Metaculus post JSON (the /api/posts/ shape) and
produces our own Question model, so the forecasting-tools dependency stays
swappable behind this module's interface.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class Question(BaseModel):
    post_id: int
    question_id: int
    title: str
    page_url: str
    state: str
    background: str | None = None
    resolution_criteria: str | None = None
    fine_print: str | None = None
    open_time: datetime | None = None
    close_time: datetime | None = None


def parse_binary_question(raw: dict) -> Question:
    question_json = raw["question"]
    question_type = question_json["type"]
    if question_type != "binary":
        raise ValueError(
            f"Post {raw['id']} is {question_type!r}, expected a binary question"
        )
    return Question(
        post_id=raw["id"],
        question_id=question_json["id"],
        title=question_json["title"],
        page_url=f"https://www.metaculus.com/questions/{raw['id']}",
        state=question_json["status"],
        background=question_json.get("description"),
        resolution_criteria=question_json.get("resolution_criteria"),
        fine_print=question_json.get("fine_print"),
        open_time=_parse_timestamp(question_json.get("open_time")),
        close_time=_parse_timestamp(question_json.get("scheduled_close_time")),
    )


def _parse_timestamp(value: str | None) -> datetime | None:
    if value is None:
        return None
    return datetime.fromisoformat(value)


def fetch_open_binary_questions(limit: int = 5) -> list[Question]:
    """Fetch open binary questions from Metaculus (needs METACULUS_TOKEN in env).

    forecasting-tools is imported here, not at module top: it drags in a heavy
    dependency tree (streamlit, litellm) that the pure parsing path never needs.
    """
    import asyncio

    from forecasting_tools import ApiFilter, MetaculusApi

    api_filter = ApiFilter(allowed_types=["binary"], allowed_statuses=["open"])
    fetched = asyncio.run(
        MetaculusApi.get_questions_matching_filter(
            api_filter, num_questions=limit, error_if_question_target_missed=False
        )
    )
    return [parse_binary_question(q.api_json) for q in fetched]
