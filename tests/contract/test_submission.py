"""Submission formatter + validator: model quantiles -> hub-valid frame."""

from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from prime_radiant.epi.schemas import QUANTILE_LEVELS
from prime_radiant.epi.submission.format import build_submission_frame
from prime_radiant.epi.submission.validate import SubmissionInvalidError, validate_submission

pytestmark = pytest.mark.contract

TASKS_JSON = Path(__file__).parent.parent / "fixtures" / "tasks.json"
REFERENCE_DATE = date(2024, 11, 23)  # present in tasks.json's enumerated round ids


def _model_quantiles() -> pd.DataFrame:
    rows = [
        {"location": loc, "horizon": h, "output_type_id": q, "value": int(50 * q) + h + 1}
        for loc in ("06", "US")
        for h in (-1, 0, 1, 2, 3)
        for q in QUANTILE_LEVELS
    ]
    return pd.DataFrame(rows)


class TestBuildSubmissionFrame:
    def test_produces_schema_valid_8_column_frame(self) -> None:
        frame = build_submission_frame(_model_quantiles(), REFERENCE_DATE)
        assert len(frame) == 2 * 5 * 23
        assert set(frame["target"]) == {"wk inc flu hosp"}
        assert set(frame["output_type"]) == {"quantile"}

    def test_target_end_dates_follow_hub_arithmetic(self) -> None:
        frame = build_submission_frame(_model_quantiles(), REFERENCE_DATE)
        h2 = frame[frame["horizon"] == 2]
        assert set(h2["target_end_date"]) == {pd.Timestamp(2024, 12, 7)}

    def test_rejects_non_saturday_reference_date(self) -> None:
        with pytest.raises(ValueError, match="Saturday"):
            build_submission_frame(_model_quantiles(), date(2024, 11, 25))


class TestValidateSubmission:
    def test_valid_frame_passes_against_recorded_tasks_json(self) -> None:
        frame = build_submission_frame(_model_quantiles(), REFERENCE_DATE)
        validate_submission(frame, TASKS_JSON)

    def test_rejects_reference_date_outside_hub_rounds(self) -> None:
        # A Saturday, but not among tasks.json's enumerated reference_dates
        frame = build_submission_frame(_model_quantiles(), date(2022, 1, 8))
        with pytest.raises(SubmissionInvalidError, match="reference_date"):
            validate_submission(frame, TASKS_JSON)

    def test_rejects_quantile_level_drift(self) -> None:
        # If the hub ever changes its level set, our constant must fail loudly
        # against the recorded config rather than silently submitting.
        frame = build_submission_frame(_model_quantiles(), REFERENCE_DATE)
        frame.loc[frame.index[0], "output_type_id"] = 0.02  # not a hub level
        with pytest.raises(SubmissionInvalidError, match="quantile"):
            validate_submission(frame, TASKS_JSON)
