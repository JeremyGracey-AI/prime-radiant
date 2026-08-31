"""Benchmark loader: official S3 mirror parquet -> our 8-column submission frame."""

from pathlib import Path

import pandas as pd
import pytest

from prime_radiant.epi.data.benchmarks import normalize_model_output

pytestmark = pytest.mark.unit

FIXTURE = Path(__file__).parent.parent / "fixtures" / "2024-11-23-FluSight-baseline.parquet"


@pytest.fixture(scope="module")
def official_frame() -> pd.DataFrame:
    return pd.read_parquet(FIXTURE)


class TestNormalizeModelOutput:
    def test_keeps_only_quantile_rows_and_8_columns(self, official_frame: pd.DataFrame) -> None:
        frame = normalize_model_output(official_frame)
        # 23 levels x 53 locations x 5 horizons in the recorded file
        assert len(frame) == 6095
        assert list(frame.columns) == [
            "reference_date",
            "target",
            "horizon",
            "target_end_date",
            "location",
            "output_type",
            "output_type_id",
            "value",
        ]

    def test_output_type_id_becomes_float(self, official_frame: pd.DataFrame) -> None:
        frame = normalize_model_output(official_frame)
        assert frame["output_type_id"].dtype == float
        assert 0.5 in set(frame["output_type_id"])

    def test_real_official_file_passes_our_submission_schema(
        self, official_frame: pd.DataFrame
    ) -> None:
        # The strongest schema validation available: the hub's own accepted output
        # must pass our SubmissionSchema unchanged.
        from prime_radiant.epi.schemas import SubmissionSchema

        SubmissionSchema.validate(normalize_model_output(official_frame))
