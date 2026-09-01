"""Vintage usability guard: schema-pass is NOT enough (verified trap: a clean-form
but 106-row truncated vintage exists at 2024-11-15)."""

from datetime import date

import pandas as pd
import pytest

from prime_radiant.epi.backtest.rolling import to_integer_submission, vintage_is_usable

pytestmark = pytest.mark.unit

CUTOFF = date(2025, 11, 29)


def _vintage(start: str, end: str) -> pd.DataFrame:
    dates = pd.date_range(start, end, freq="7D")
    return pd.DataFrame({"date": dates, "location": "US", "value": 10.0})


class TestVintageIsUsable:
    def test_full_history_recent_vintage_passes(self) -> None:
        assert vintage_is_usable(_vintage("2022-02-05", "2025-11-22"), CUTOFF)

    def test_truncated_vintage_rejected(self) -> None:
        # the 2024-11-15 mode: clean header, ~2 weeks of rows
        assert not vintage_is_usable(_vintage("2025-11-15", "2025-11-22"), CUTOFF)

    def test_stale_vintage_rejected(self) -> None:
        # deep history but last row far behind the cutoff (same-day divergent
        # commit mode): max date must be within 14 days of the cutoff
        assert not vintage_is_usable(_vintage("2022-02-05", "2025-09-06"), CUTOFF)

    def test_all_nan_vintage_rejected(self) -> None:
        # a vintage whose values are entirely missing has no usable history at
        # all — the guard must reject it before span math divides by nothing
        frame = _vintage("2022-02-05", "2025-11-22").assign(value=float("nan"))
        assert not vintage_is_usable(frame, CUTOFF)


class TestToIntegerSubmission:
    def _continuous(self, crossing: bool = False) -> pd.DataFrame:
        # two locations x two horizons, full 23-level grid, shuffled row order.
        # Contract: the model layer has already sorted quantiles (in transformed
        # space); this boundary clips, hub-rounds, and validates.
        from prime_radiant.epi.schemas import QUANTILE_LEVELS

        rows = []
        for location in ("06", "48"):
            for horizon in (0, 1):
                base = 40.0 if location == "06" else 15.0
                for i, level in enumerate(QUANTILE_LEVELS):
                    value = base + (i - 11) * 2.4  # monotone, fractional, first two negative for 48
                    if crossing and i == 5:
                        value = base + 30.0
                    rows.append(
                        {
                            "location": location,
                            "horizon": horizon,
                            "output_type_id": float(level),
                            "value": value,
                        }
                    )
        return pd.DataFrame.from_records(rows).sample(frac=1.0, random_state=7)

    def test_emits_a_hub_valid_integer_grid(self) -> None:
        from prime_radiant.epi.schemas import QUANTILE_LEVELS

        frame = to_integer_submission(self._continuous(), date(2025, 11, 29))
        assert len(frame) == 2 * 2 * len(QUANTILE_LEVELS)
        assert (frame["reference_date"] == pd.Timestamp("2025-11-29")).all()
        assert all(float(v).is_integer() for v in frame["value"])
        assert (frame["value"] >= 0).all()  # location 48's negative tail clipped
        assert sorted(frame["output_type_id"].unique()) == sorted(float(q) for q in QUANTILE_LEVELS)

    def test_hub_rounding_rule_floor_below_median_ceil_at_or_above(self) -> None:
        # official convention (flusight-baseline.R): floor for levels < 0.5,
        # ceiling for levels >= 0.5 — widens intervals, preserves monotonicity
        frame = to_integer_submission(self._continuous(), date(2025, 11, 29))
        group = frame.loc[(frame["location"] == "06") & (frame["horizon"] == 0)]
        by_level = dict(zip(group["output_type_id"], group["value"], strict=False))
        # level index 10 (0.45): 40 + (10-11)*2.4 = 37.6 -> floor 37
        assert by_level[0.45] == 37
        # level index 12 (0.55): 40 + (12-11)*2.4 = 42.4 -> ceil 43
        assert by_level[0.55] == 43

    def test_crossed_quantiles_fail_loudly_at_the_boundary(self) -> None:
        # sorting is the MODEL layer's job; a crossing reaching this boundary is
        # a bug upstream and must raise, never ship
        import pandera.errors

        with pytest.raises(pandera.errors.SchemaError, match="non-decreasing"):
            to_integer_submission(self._continuous(crossing=True), date(2025, 11, 29))
