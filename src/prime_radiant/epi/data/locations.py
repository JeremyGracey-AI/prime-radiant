"""The hub's location universe (auxiliary-data/locations.csv) and the NHSN bridge.

The hub speaks 2-digit FIPS strings plus "US" (53 codes). NHSN Socrata speaks
jurisdiction abbreviations and carries 67 values including "USA", HHS "Region 1".."10"
aggregates, and territories (AS/GU/MP/VI) that are not in the hub set — those map to
None so callers filter them out instead of double-counting.
"""

from functools import lru_cache
from pathlib import Path

import pandas as pd


def load_locations(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path, dtype={"abbreviation": str, "location": str})
    frame["population"] = pd.to_numeric(frame["population"])
    return frame


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
