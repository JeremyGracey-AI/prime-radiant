"""NHSN Socrata client: live jurisdiction feed -> hub-aligned (date, location, value)."""

from pathlib import Path

import pandas as pd
import pytest

from prime_radiant.epi.data.nhsn import dataset_url, fetch_admissions

pytestmark = pytest.mark.unit

LOCATIONS = Path(__file__).parent.parent / "fixtures" / "locations.csv"


class TestDatasetUrl:
    def test_final_dataset_is_ua7e(self) -> None:
        assert "ua7e-t2fy" in dataset_url("final")

    def test_preliminary_dataset_is_mpgq(self) -> None:
        assert "mpgq-jmmr" in dataset_url("preliminary")

    def test_unknown_dataset_rejected(self) -> None:
        with pytest.raises(ValueError, match="final|preliminary"):
            dataset_url("latest")


@pytest.mark.vcr
class TestFetchAdmissions:
    def test_returns_hub_aligned_frame(self) -> None:
        frame = fetch_admissions(locations_csv=LOCATIONS)
        assert list(frame.columns) == ["date", "location", "value"]
        assert pd.api.types.is_datetime64_any_dtype(frame["date"])
        assert (frame["value"] >= 0).all()

    def test_only_hub_locations_survive(self) -> None:
        # NHSN carries 67 jurisdictions incl. USA + HHS Region aggregates; summing
        # over unfiltered rows triple-counts. Only the hub's 53 may pass through.
        frame = fetch_admissions(locations_csv=LOCATIONS)
        codes = set(frame["location"])
        assert codes <= {"US"} | {f"{i:02d}" for i in range(1, 79)}
        assert "US" in codes  # mapped from 'USA'
        assert len(codes) == 53
        assert not any(code.startswith("Region") for code in codes)

    def test_week_ending_dates_are_saturdays(self) -> None:
        frame = fetch_admissions(locations_csv=LOCATIONS)
        assert (frame["date"].dt.weekday == 5).all()
