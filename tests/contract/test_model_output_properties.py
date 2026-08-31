"""Quality-gate invariant: ANY history through replica + formatter is hub-valid.

Monotone quantiles, non-negative integers, and date arithmetic are all enforced by
SubmissionSchema (Phase 2A), so one property covers the whole gate.
"""

from datetime import date

import pandas as pd
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from prime_radiant.epi.models.baseline import BaselineConfig, flusight_baseline
from prime_radiant.epi.submission.format import build_submission_frame

pytestmark = pytest.mark.contract

REFERENCE = date(2025, 11, 29)  # a Saturday
FAST_CONFIG = BaselineConfig(nsims=201)  # full 23 levels, small grid for speed


@settings(max_examples=25, deadline=None)
@given(
    values=st.lists(
        st.floats(min_value=0.0, max_value=10_000.0, allow_nan=False, allow_infinity=False),
        min_size=4,
        max_size=30,
    )
)
def test_replica_output_always_passes_submission_schema(values: list[float]) -> None:
    end = pd.Timestamp(REFERENCE) - pd.Timedelta(days=7)
    dates = pd.date_range(end=end, periods=len(values), freq="7D")
    history = pd.DataFrame({"date": dates, "location": "US", "value": values})

    quantiles = flusight_baseline(history, REFERENCE, FAST_CONFIG)
    # build_submission_frame validates against SubmissionSchema internally;
    # reaching the end of this call IS the assertion.
    frame = build_submission_frame(quantiles, REFERENCE)
    assert len(frame) == 5 * 23
