"""CLI auto-date selection: latest enumerated round <= live reference date whose
vintage passes the untouched guard."""

from datetime import date
from pathlib import Path

import pytest

from prime_radiant.epi.cli import auto_reference_date, enumerated_reference_dates

pytestmark = pytest.mark.unit

TASKS_JSON = Path(__file__).parent.parent / "fixtures" / "tasks.json"


class TestEnumeratedReferenceDates:
    def test_reads_the_hub_round_list(self) -> None:
        dates = enumerated_reference_dates(TASKS_JSON)
        assert dates[0] == date(2023, 10, 7)
        assert dates[-1] == date(2026, 5, 30)
        assert len(dates) == 89  # verified count


class TestAutoReferenceDate:
    def test_selects_latest_guard_passing_round(self) -> None:
        picked = auto_reference_date(
            TASKS_JSON,
            today=date(2026, 8, 31),
            vintage_check=lambda d: True,
        )
        assert picked == date(2026, 5, 30)  # clamp: latest round <= live ref date

    def test_walks_back_past_guard_failures(self) -> None:
        picked = auto_reference_date(
            TASKS_JSON,
            today=date(2026, 8, 31),
            vintage_check=lambda d: d < date(2026, 5, 1),
        )
        assert picked == date(2026, 4, 25)

    def test_clamp_prevents_future_round_overshoot(self) -> None:
        # mid-season: live reference date for a Wednesday 2026-01-07 is Saturday
        # 2026-01-10; enumerated rounds run months further — must not overshoot.
        picked = auto_reference_date(
            TASKS_JSON,
            today=date(2026, 1, 7),
            vintage_check=lambda d: True,
        )
        assert picked == date(2026, 1, 10)

    def test_raises_when_nothing_passes(self) -> None:
        with pytest.raises(LookupError, match="no enumerated round"):
            auto_reference_date(TASKS_JSON, today=date(2026, 8, 31), vintage_check=lambda d: False)
