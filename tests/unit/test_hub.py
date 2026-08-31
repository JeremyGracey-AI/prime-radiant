"""Hub target-data loader: raw CSV (recorded slice) -> sorted, schema-valid frame."""

from pathlib import Path

import pandas as pd
import pytest

from prime_radiant.epi.data.hub import load_target_data

pytestmark = pytest.mark.unit

FIXTURE = Path(__file__).parent.parent / "fixtures" / "target_hospital_admissions_sample.csv"


class TestLoadTargetData:
    def test_columns_match_recorded_hub_shape(self) -> None:
        frame = load_target_data(FIXTURE)
        assert list(frame.columns) == ["date", "location", "location_name", "value", "weekly_rate"]

    def test_sorted_by_location_then_date(self) -> None:
        # The raw hub file is NOT chronologically sorted (verified 2026-08-30);
        # downstream lag features silently corrupt on unsorted input.
        frame = load_target_data(FIXTURE)
        resorted = frame.sort_values(["location", "date"]).reset_index(drop=True)
        pd.testing.assert_frame_equal(frame, resorted)

    def test_dates_are_datetimes_and_saturdays(self) -> None:
        frame = load_target_data(FIXTURE)
        assert pd.api.types.is_datetime64_any_dtype(frame["date"])
        assert (frame["date"].dt.weekday == 5).all()

    def test_fips_keep_leading_zeros(self) -> None:
        frame = load_target_data(FIXTURE)
        assert frame["location"].str.match(r"^(US|\d{2})$").all()

    def test_values_non_negative(self) -> None:
        frame = load_target_data(FIXTURE)
        assert (frame["value"] >= 0).all()
