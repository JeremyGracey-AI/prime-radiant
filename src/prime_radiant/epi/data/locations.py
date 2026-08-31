"""The hub's location universe (auxiliary-data/locations.csv) and the NHSN bridge.

The hub speaks 2-digit FIPS strings plus "US" (53 codes). NHSN Socrata speaks
jurisdiction abbreviations and carries 67 values including "USA", HHS "Region 1".."10"
aggregates, and territories (AS/GU/MP/VI) that are not in the hub set — those map to
None so callers filter them out instead of double-counting.
"""

from datetime import date
from functools import lru_cache
from pathlib import Path

import pandas as pd


def load_locations(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path, dtype={"abbreviation": str, "location": str})
    # The 2023-24 hub snapshot carries an empty-named 5th header column.
    frame = frame.drop(columns=[c for c in frame.columns if str(c).startswith("Unnamed")])
    frame["population"] = pd.to_numeric(frame["population"])
    return frame


def season_locations_filename(origin: date) -> str:
    """Season-correct hub population snapshot (auxiliary-data/), per the hub's
    own README mapping — closes the Phase C anachronism where current-census
    populations reached 2024-25 origins."""
    if date(2023, 7, 1) <= origin < date(2024, 7, 1):
        return "locations_202324.csv"
    if date(2024, 7, 1) <= origin < date(2025, 7, 1):
        return "locations_202425.csv"
    return "locations.csv"


@lru_cache(maxsize=8)
def _location_maps(path: Path) -> tuple[frozenset[str], dict[str, str]]:
    frame = load_locations(path)
    codes = frozenset(frame["location"])
    abbrev_to_fips = dict(zip(frame["abbreviation"], frame["location"], strict=True))
    return codes, abbrev_to_fips


def hub_location_codes(path: Path) -> frozenset[str]:
    return _location_maps(path)[0]


def fips_for_nhsn_jurisdiction(jurisdiction: str, path: Path) -> str | None:
    if jurisdiction == "USA":
        return "US"
    return _location_maps(path)[1].get(jurisdiction)
