"""Season-vintaged population tables (closes the Phase C anachronism)."""

from datetime import date
from pathlib import Path

import pytest

from prime_radiant.epi.data.locations import load_locations, season_locations_filename

pytestmark = pytest.mark.unit

FIXTURES = Path(__file__).parent.parent / "fixtures"


class TestSeasonLocationsFilename:
    def test_2023_24_origins_use_the_202324_snapshot(self) -> None:
        assert season_locations_filename(date(2023, 10, 14)) == "locations_202324.csv"
        assert season_locations_filename(date(2024, 5, 4)) == "locations_202324.csv"

    def test_2024_25_origins_use_the_202425_snapshot(self) -> None:
        assert season_locations_filename(date(2024, 11, 23)) == "locations_202425.csv"
        assert season_locations_filename(date(2025, 5, 31)) == "locations_202425.csv"

    def test_current_season_uses_the_live_file(self) -> None:
        assert season_locations_filename(date(2025, 11, 22)) == "locations.csv"
        assert season_locations_filename(date(2026, 5, 30)) == "locations.csv"


class TestSnapshotLoading:
    def test_202324_snapshot_loads_despite_unnamed_column(self) -> None:
        # The 202324 file carries an empty-named 5th header column (verified).
        frame = load_locations(FIXTURES / "locations_202324.csv")
        assert len(frame) == 53
        assert "Unnamed: 4" not in frame.columns

    def test_populations_differ_across_snapshots(self) -> None:
        pop_2324 = load_locations(FIXTURES / "locations_202324.csv")
        pop_current = load_locations(FIXTURES / "locations.csv")
        us_2324 = int(pop_2324.loc[pop_2324["location"] == "US", "population"].iloc[0])
        us_now = int(pop_current.loc[pop_current["location"] == "US", "population"].iloc[0])
        assert us_2324 == 332_200_066  # Census 2022 vintage (verified)
        assert us_now > us_2324
