"""Locations: the hub's 53-jurisdiction universe and the NHSN->FIPS bridge."""

from pathlib import Path

import pytest

from prime_radiant.epi.data.locations import (
    fips_for_nhsn_jurisdiction,
    hub_location_codes,
    load_locations,
)

pytestmark = pytest.mark.unit

FIXTURE = Path(__file__).parent.parent / "fixtures" / "locations.csv"


class TestLoadLocations:
    def test_loads_all_53_hub_locations(self) -> None:
        frame = load_locations(FIXTURE)
        assert len(frame) == 53

    def test_fips_codes_keep_leading_zeros(self) -> None:
        frame = load_locations(FIXTURE)
        assert "01" in set(frame["location"])  # Alabama, not 1
        assert "06" in set(frame["location"])  # California

    def test_population_is_numeric(self) -> None:
        frame = load_locations(FIXTURE)
        assert int(frame.loc[frame["location"] == "US", "population"].iloc[0]) > 300_000_000


class TestHubLocationCodes:
    def test_exactly_53_codes_including_dc_and_pr(self) -> None:
        codes = hub_location_codes(FIXTURE)
        assert len(codes) == 53
        assert {"US", "06", "11", "72"} <= codes  # national, CA, DC, PR

    def test_excludes_non_hub_territories(self) -> None:
        codes = hub_location_codes(FIXTURE)
        assert "60" not in codes  # American Samoa
        assert "66" not in codes  # Guam


class TestNhsnJurisdictionBridge:
    def test_usa_maps_to_us(self) -> None:
        assert fips_for_nhsn_jurisdiction("USA", FIXTURE) == "US"

    def test_state_abbreviation_maps_to_fips(self) -> None:
        assert fips_for_nhsn_jurisdiction("AL", FIXTURE) == "01"
        assert fips_for_nhsn_jurisdiction("PR", FIXTURE) == "72"

    def test_hhs_region_aggregates_are_rejected(self) -> None:
        assert fips_for_nhsn_jurisdiction("Region 4", FIXTURE) is None

    def test_non_hub_territories_are_rejected(self) -> None:
        for territory in ("AS", "GU", "MP", "VI"):
            assert fips_for_nhsn_jurisdiction(territory, FIXTURE) is None
