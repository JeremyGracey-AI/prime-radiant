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

    # The five rejection cases below were demonstrated slipping through (or crashing)
    # by adversarial review 2026-08-31: the old check's second condition was a
    # mathematical tautology and the first was blind to all-below-0.5 sets.

    def test_rejects_level_set_entirely_below_half(self) -> None:
        with pytest.raises(ValueError, match="symmetric"):
            wis(np.array([0.1, 0.2, 0.3]), np.array([1.0, 2.0, 3.0]), 1.0)

    def test_rejects_even_length_set_without_median(self) -> None:
        # Even symmetric sets make wis() and wis_components() disagree by exactly
        # (K+0.5)/K — the pinball equivalence holds only for 2K+1 levels + median.
        with pytest.raises(ValueError, match="median"):
            wis(np.array([0.25, 0.75]), np.array([1.0, 3.0]), 0.0)

    def test_rejects_boundary_levels_zero_and_one(self) -> None:
        # alpha = 0 divides by zero in the interval form; both scorers must refuse.
        with pytest.raises(ValueError, match="0 and 1"):
            wis(np.array([0.0, 0.5, 1.0]), np.array([0.0, 5.0, 10.0]), -1.0)

    def test_rejects_duplicate_levels_with_informative_message(self) -> None:
        with pytest.raises(ValueError, match="duplicate"):
            wis(np.array([0.25, 0.25, 0.5, 0.75, 0.75]), np.arange(5.0), 1.0)

    def test_lone_median_is_a_valid_level_set(self) -> None:
        # K=0: WIS reduces to |y - m|.
        assert wis(np.array([0.5]), np.array([15.0]), 22.0) == pytest.approx(7.0)

    def test_rejects_crossed_quantiles(self) -> None:
        # Non-monotone quantile vectors previously produced NEGATIVE dispersion.
        with pytest.raises(ValueError, match="non-decreasing"):
            wis(np.array(LEVELS), np.array([3.0, 2.0, 1.0]), 2.0)


class TestComponentsRejectionsMatchWis:
    def test_components_reject_crossed_quantiles_too(self) -> None:
        with pytest.raises(ValueError, match="non-decreasing"):
            wis_components(np.array(LEVELS), np.array([3.0, 2.0, 1.0]), 2.0)

    def test_components_reject_below_half_sets_too(self) -> None:
        with pytest.raises(ValueError, match="symmetric"):
            wis_components(np.array([0.1, 0.2, 0.3]), np.array([1.0, 2.0, 3.0]), 1.0)


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


def test_relative_wis_rejects_mismatched_task_sets() -> None:
    with pytest.raises(ValueError, match="identical task sets"):
        relative_wis(np.array([1.0, 2.0]), np.array([1.0]))
