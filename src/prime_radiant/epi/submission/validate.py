"""Validate a submission frame against the hub's own tasks.json.

The schema constants in epi/schemas.py are our recording of the hub contract; this
module re-checks a frame against the LIVE config (the clone's hub-config/tasks.json)
so contract drift on the hub side fails loudly before any submission.
"""

import json
from pathlib import Path

import pandas as pd
import pandera.errors

from prime_radiant.epi.schemas import SubmissionSchema
from prime_radiant.epi.submission.format import PRIMARY_TARGET


class SubmissionInvalidError(ValueError):
    """The frame does not satisfy the hub contract in tasks.json."""


def _primary_task(tasks_json_path: Path) -> dict:
    config = json.loads(tasks_json_path.read_text())
    for task in config["rounds"][0]["model_tasks"]:
        target_ids = task["task_ids"]["target"]
        listed = (target_ids.get("required") or []) + (target_ids.get("optional") or [])
        if PRIMARY_TARGET in listed:
            return task
    raise SubmissionInvalidError(f"{PRIMARY_TARGET!r} not found in {tasks_json_path}")


def _allowed(task: dict, task_id: str) -> set:
    ids = task["task_ids"][task_id]
    return set((ids.get("required") or []) + (ids.get("optional") or []))


def validate_submission(frame: pd.DataFrame, tasks_json_path: Path) -> None:
    task = _primary_task(tasks_json_path)

    allowed_dates = _allowed(task, "reference_date")
    frame_dates = {d.date().isoformat() for d in pd.to_datetime(frame["reference_date"])}
    if unknown := frame_dates - allowed_dates:
        raise SubmissionInvalidError(f"reference_date(s) not a hub round: {sorted(unknown)}")

    hub_levels = set(task["output_type"]["quantile"]["output_type_id"]["required"])
    frame_levels = set(frame["output_type_id"])
    if frame_levels != hub_levels:
        raise SubmissionInvalidError(
            "quantile levels differ from hub contract: "
            f"extra={sorted(frame_levels - hub_levels)}, "
            f"missing={sorted(hub_levels - frame_levels)}"
        )

    if unknown_locations := set(frame["location"]) - _allowed(task, "location"):
        raise SubmissionInvalidError(
            f"location(s) not in hub contract: {sorted(unknown_locations)}"
        )

    if unknown_horizons := set(frame["horizon"]) - _allowed(task, "horizon"):
        raise SubmissionInvalidError(f"horizon(s) not in hub contract: {sorted(unknown_horizons)}")

    try:
        SubmissionSchema.validate(frame)
    except (pandera.errors.SchemaError, pandera.errors.SchemaErrors) as error:
        raise SubmissionInvalidError(f"schema violation: {error}") from error
