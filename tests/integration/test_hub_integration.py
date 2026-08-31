"""Phase A done condition, asserted against the real FluSight hub clone.

Marked integration: needs network on first run (blobless sparse clone into
data/hub, gitignored) and lazily fetches historical blobs for vintage reads.
"""

from datetime import date
from pathlib import Path

import pytest

from prime_radiant.epi.data.hub import TARGET_FILE, ensure_hub_clone, load_target_data
from prime_radiant.epi.data.locations import hub_location_codes
from prime_radiant.epi.data.vintages import as_of, resolve_vintage

pytestmark = pytest.mark.integration

REPO_ROOT = Path(__file__).parents[2]
HUB_DIR = REPO_ROOT / "data" / "hub"
VINTAGE_CACHE = REPO_ROOT / "data" / "vintage_cache"

# (label, first Saturday considered, last Saturday considered)
SEASONS = [
    ("2022-23", date(2022, 10, 1), date(2023, 5, 31)),
    ("2023-24", date(2023, 10, 1), date(2024, 5, 31)),
    ("2024-25", date(2024, 10, 1), date(2025, 5, 31)),
    ("2025-26", date(2025, 10, 1), date(2026, 5, 31)),
]


@pytest.fixture(scope="module")
def hub_clone() -> Path:
    return ensure_hub_clone(HUB_DIR)


class TestDoneCondition:
    def test_all_53_locations_present_every_season_since_2022_23(self, hub_clone: Path) -> None:
        frame = load_target_data(hub_clone / TARGET_FILE)
        expected = hub_location_codes(hub_clone / "auxiliary-data" / "locations.csv")
        assert len(expected) == 53
        for label, start, end in SEASONS:
            in_season = frame[(frame["date"] >= str(start)) & (frame["date"] <= str(end))]
            present = set(in_season["location"])
            assert present == set(expected), f"season {label}: missing {set(expected) - present}"

    def test_real_vintage_respects_as_of_date(self, hub_clone: Path) -> None:
        as_of_date = date(2025, 1, 15)
        vintage = resolve_vintage(hub_clone, as_of_date)
        frame = as_of(hub_clone, as_of_date, cache_dir=VINTAGE_CACHE)
        assert vintage.committed_at.date() <= as_of_date
        assert frame["date"].max().date() <= as_of_date
        # the mid-January vintage must not know the season's spring tail
        assert frame["date"].max().date() >= date(2024, 12, 1)
