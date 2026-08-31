"""Weighted Interval Score, per Bracher et al. 2021 (PLOS Comp Bio 10.1371/1008618).

Implementation uses the pinball (quantile-loss) formulation, verified equivalent to
the paper's interval form for symmetric level sets: with K central intervals plus the
median (2K+1 levels), WIS = (2/(2K+1)) * sum of classic pinball losses. FluSight's
23 levels give WIS = (2/23)*sum — i.e. 2x the mean pinball loss.

Component decomposition follows the scoringutils naming convention: "overprediction"
is the penalty fired when the observation falls BELOW the interval (the forecast was
too high), "underprediction" when it falls above; the median term |y - m| lands in
over/underprediction, never in dispersion.

"Relative WIS" here is the plain ratio mean(WIS_model)/mean(WIS_reference) over an
IDENTICAL task set. Official FluSight reports use the pairwise geometric-mean variant
(Cramer et al. 2022), which coincides with the plain ratio on identical task sets.
"""

from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

FloatArray = npt.NDArray[np.floating]


def pinball_loss(levels: FloatArray, quantiles: FloatArray, observed: float) -> FloatArray:
    """Classic pinball loss rho_tau(q, y) per level (no factor 2)."""
    indicator = (observed <= quantiles).astype(float)
    return (indicator - levels) * (quantiles - observed)


def _validate(levels: FloatArray, quantiles: FloatArray) -> tuple[FloatArray, FloatArray]:
    """Enforce the 2K+1 contract the pinball<->interval equivalence is proved for.

    Rewritten after adversarial review (2026-08-31) demonstrated the previous
    check's second condition was a tautology and its first was blind to level
    sets lying entirely below 0.5; even-length sets also slipped through and made
    the two scorers disagree by exactly (K+0.5)/K, and crossed quantile vectors
    produced negative dispersion.
    """
    order = np.argsort(levels)
    ordered_levels = np.asarray(levels, dtype=float)[order]
    ordered_quantiles = np.asarray(quantiles, dtype=float)[order]

    if len(np.unique(np.round(ordered_levels, 10))) != len(ordered_levels):
        raise ValueError(f"duplicate quantile levels: {ordered_levels.tolist()}")
    if ordered_levels[0] <= 0.0 or ordered_levels[-1] >= 1.0:
        raise ValueError("quantile levels must lie strictly between 0 and 1")
    if len(ordered_levels) % 2 == 0:
        raise ValueError(
            "level set must include the median (K interval pairs + 0.5, odd count); "
            f"got even count {len(ordered_levels)}"
        )
    middle = ordered_levels[len(ordered_levels) // 2]
    if not np.isclose(middle, 0.5):
        raise ValueError(
            f"level set must be symmetric around the median 0.5; middle level is {middle}"
        )
    if not np.allclose(ordered_levels + ordered_levels[::-1], 1.0):
        raise ValueError(
            f"quantile levels must form symmetric pairs (tau, 1-tau); got {ordered_levels.tolist()}"
        )
    if np.any(np.diff(ordered_quantiles) < 0):
        raise ValueError("quantile values must be non-decreasing in level (crossed quantiles)")
    return ordered_levels, ordered_quantiles


def wis(levels: FloatArray, quantiles: FloatArray, observed: float) -> float:
    """WIS via the pinball formulation: (2 / n_levels) * sum of pinball losses."""
    levels, quantiles = _validate(levels, quantiles)
    return float(2.0 / len(levels) * pinball_loss(levels, quantiles, observed).sum())


@dataclass(frozen=True)
class WisComponents:
    dispersion: float
    overprediction: float
    underprediction: float

    @property
    def total(self) -> float:
        return self.dispersion + self.overprediction + self.underprediction


def wis_components(levels: FloatArray, quantiles: FloatArray, observed: float) -> WisComponents:
    """Dispersion / over / underprediction via the interval form (paper eq. 1-2)."""
    levels, quantiles = _validate(levels, quantiles)
    n = len(levels)
    k_intervals = n // 2
    norm = 1.0 / (k_intervals + 0.5)

    dispersion = 0.0
    over = 0.0
    under = 0.0

    if n % 2 == 1:
        median = float(quantiles[k_intervals])
        # zero-width interval: |y - m| is pure penalty, weighted w0 = 1/2
        if observed < median:
            over += 0.5 * (median - observed)
        else:
            under += 0.5 * (observed - median)

    for k in range(k_intervals):
        lower, upper = float(quantiles[k]), float(quantiles[n - 1 - k])
        alpha = 2.0 * float(levels[k])
        weight = alpha / 2.0
        dispersion += weight * (upper - lower)
        if observed < lower:
            over += weight * (2.0 / alpha) * (lower - observed)
        elif observed > upper:
            under += weight * (2.0 / alpha) * (observed - upper)

    return WisComponents(
        dispersion=norm * dispersion,
        overprediction=norm * over,
        underprediction=norm * under,
    )


def interval_coverage(
    levels: FloatArray, quantiles: FloatArray, observed: float, width: float
) -> bool:
    """Is `observed` inside the central `width` interval? Bounds inclusive
    (scoringutils v1 and v2 convention)."""
    lower_level = round((1.0 - width) / 2.0, 10)
    upper_level = round(1.0 - lower_level, 10)
    lower = quantiles[np.isclose(levels, lower_level)]
    upper = quantiles[np.isclose(levels, upper_level)]
    if len(lower) != 1 or len(upper) != 1:
        raise ValueError(f"levels for a central {width:.0%} interval not present")
    return bool(lower[0] <= observed <= upper[0])


def relative_wis(model_scores: FloatArray, reference_scores: FloatArray) -> float:
    """mean(model) / mean(reference) over an identical task set; < 1 beats reference."""
    if len(model_scores) != len(reference_scores):
        raise ValueError("relative WIS requires identical task sets on both sides")
    return float(np.mean(model_scores) / np.mean(reference_scores))
