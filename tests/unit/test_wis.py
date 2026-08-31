"""WIS scorer, TDD'd against the hand-computed example from Bracher et al. (2021).

Reference example (verified against the paper's own algebra, 2026-08-31):
levels tau = (0.25, 0.5, 0.75), quantiles q = (10, 15, 20), observed y = 22.
Pinball losses: 0.25*(22-10)=3, 0.5*(22-15)=3.5, 0.75*(22-20)=1.5; sum = 8.
K=1 interval + median => WIS = (2/(2K+1)) * sum = (2/3)*8 = 16/3.
Interval-form cross-check: IS_0.5 = (20-10) + (2/0.5)*(22-20) = 18;
WIS = (1/1.5)*(0.5*|22-15| + 0.25*18) = 16/3.
Decomposition: dispersion (1/1.5)*0.25*10 = 5/3; underprediction
(1/1.5)*(0.25*8 + 0.5*7) = 11/3; overprediction 0.
"""

import numpy as np
import pytest

from prime_radiant.eval.wis import (
    interval_coverage,
    pinball_loss,
    relative_wis,
    wis,
    wis_components,
)

pytestmark = pytest.mark.unit

LEVELS = (0.25, 0.5, 0.75)
QUANTILES = (10.0, 15.0, 20.0)
OBSERVED = 22.0


class TestPinballLoss:
    def test_hand_computed_values(self) -> None:
        losses = pinball_loss(np.array(LEVELS), np.array(QUANTILES), OBSERVED)
        assert losses == pytest.approx([3.0, 3.5, 1.5], abs=1e-12)

    def test_observation_below_quantile(self) -> None:
        # y=8 below q=10 at tau 0.25: (1 - 0.25) * (10 - 8) = 1.5
        losses = pinball_loss(np.array([0.25]), np.array([10.0]), 8.0)
        assert losses == pytest.approx([1.5], abs=1e-12)


class TestWis:
    def test_hand_computed_example_is_16_thirds(self) -> None:
        result = wis(np.array(LEVELS), np.array(QUANTILES), OBSERVED)
        assert abs(result - 16.0 / 3.0) < 1e-12

    def test_perfect_point_mass_forecast_scores_zero(self) -> None:
        result = wis(np.array(LEVELS), np.array([22.0, 22.0, 22.0]), OBSERVED)
        assert result == pytest.approx(0.0, abs=1e-12)

    def test_flusight_23_levels_equals_2_over_23_sum_pinball(self) -> None:
        from prime_radiant.epi.schemas import QUANTILE_LEVELS

        rng = np.random.default_rng(7)
        levels = np.array(QUANTILE_LEVELS)
        quantiles = np.sort(rng.uniform(0, 100, size=23))
        y = 40.0
        expected = (2.0 / 23.0) * pinball_loss(levels, quantiles, y).sum()
        assert abs(wis(levels, quantiles, y) - expected) < 1e-12

    def test_rejects_asymmetric_level_set(self) -> None:
        with pytest.raises(ValueError, match="symmetric"):
            wis(np.array([0.25, 0.5, 0.9]), np.array([1.0, 2.0, 3.0]), 1.0)


class TestWisComponents:
    def test_hand_computed_decomposition(self) -> None:
        parts = wis_components(np.array(LEVELS), np.array(QUANTILES), OBSERVED)
        assert abs(parts.dispersion - 5.0 / 3.0) < 1e-12
        assert parts.overprediction == pytest.approx(0.0, abs=1e-12)
        assert abs(parts.underprediction - 11.0 / 3.0) < 1e-12
        assert abs(parts.total - 16.0 / 3.0) < 1e-12

    def test_overprediction_fires_when_observation_below_interval(self) -> None:
        # scoringutils convention: forecast too HIGH (y below the band) = overprediction
        parts = wis_components(np.array(LEVELS), np.array(QUANTILES), 5.0)
        assert parts.overprediction > 0
        assert parts.underprediction == pytest.approx(0.0, abs=1e-12)

    def test_components_sum_to_wis(self) -> None:
        rng = np.random.default_rng(11)
        from prime_radiant.epi.schemas import QUANTILE_LEVELS

        levels = np.array(QUANTILE_LEVELS)
        for y in (0.0, 12.3, 55.0, 400.0):
            quantiles = np.sort(rng.uniform(0, 300, size=23))
            parts = wis_components(levels, quantiles, y)
            total = parts.dispersion + parts.overprediction + parts.underprediction
            assert abs(total - wis(levels, quantiles, y)) < 1e-10


class TestIntervalCoverage:
    def test_inclusive_bounds(self) -> None:
        # scoringutils v1/v2: inclusive on both ends
        levels = np.array([0.25, 0.5, 0.75])
        assert interval_coverage(levels, np.array([10.0, 15.0, 20.0]), 20.0, width=0.5)
        assert interval_coverage(levels, np.array([10.0, 15.0, 20.0]), 10.0, width=0.5)
        assert not interval_coverage(levels, np.array([10.0, 15.0, 20.0]), 21.0, width=0.5)


class TestRelativeWis:
    def test_plain_mean_ratio(self) -> None:
        assert relative_wis(np.array([2.0, 4.0]), np.array([4.0, 8.0])) == pytest.approx(0.5)

    def test_identical_scores_give_one(self) -> None:
        scores = np.array([1.0, 2.0, 3.0])
        assert relative_wis(scores, scores) == pytest.approx(1.0)
