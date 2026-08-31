"""Old-form vintage adapter: pre-2024-05 hub files carry a leading index column.

Verified census (2026-08-31): 32 of 39 in-season 2023-24 vintages use the old form
'"","date","location",...' — identical 5 real columns behind a leading unnamed
index. The loader must accept both forms so 2023-24 vintages become usable.
"""

from pathlib import Path

import pytest

from prime_radiant.epi.data.hub import load_target_data

pytestmark = pytest.mark.unit

OLD_FORM = Path(__file__).parent.parent / "fixtures" / "target_old_form_sample.csv"
CLEAN_FORM = Path(__file__).parent.parent / "fixtures" / "target_hospital_admissions_sample.csv"


class TestOldFormAdapter:
    def test_old_form_loads_with_standard_columns(self) -> None:
        frame = load_target_data(OLD_FORM)
        assert list(frame.columns) == ["date", "location", "location_name", "value", "weekly_rate"]
        assert len(frame) == 59  # fixture: header + 59 data rows

    def test_old_form_keeps_fips_leading_zeros(self) -> None:
        frame = load_target_data(OLD_FORM)
        assert "02" in set(frame["location"])  # Alaska, not 2

    def test_clean_form_still_loads(self) -> None:
        frame = load_target_data(CLEAN_FORM)
        assert list(frame.columns) == ["date", "location", "location_name", "value", "weekly_rate"]
