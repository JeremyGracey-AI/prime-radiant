"""Hub-format CSV writer: round-trips through our own schema and matches the
official file's column conventions."""

from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from prime_radiant.epi.schemas import QUANTILE_LEVELS, SubmissionSchema
from prime_radiant.epi.submission.format import build_submission_frame
from prime_radiant.epi.submission.write import submission_filename, write_submission_csv

pytestmark = pytest.mark.unit

REFERENCE = date(2024, 11, 23)


def _frame() -> pd.DataFrame:
    rows = [
        {"location": loc, "horizon": h, "output_type_id": q, "value": int(40 * q) + h + 2}
        for loc in ("06", "US")
        for h in (0, 1)
        for q in QUANTILE_LEVELS
    ]
    return build_submission_frame(pd.DataFrame(rows), REFERENCE)


class TestSubmissionFilename:
    def test_hub_naming_convention(self) -> None:
        name = submission_filename(REFERENCE, "JGracey", "prime_radiant")
        assert name == "2024-11-23-JGracey-prime_radiant.csv"


class TestWriteSubmissionCsv:
    def test_round_trips_through_submission_schema(self, tmp_path: Path) -> None:
        path = write_submission_csv(_frame(), tmp_path, "JGracey", "prime_radiant")
        assert path.name == "2024-11-23-JGracey-prime_radiant.csv"
        back = pd.read_csv(path, dtype={"location": str})
        back["output_type_id"] = back["output_type_id"].astype(float)
        SubmissionSchema.validate(
            back.assign(
                reference_date=pd.to_datetime(back["reference_date"]),
                target_end_date=pd.to_datetime(back["target_end_date"]),
            )
        )

    def test_column_order_and_formats_match_hub_conventions(self, tmp_path: Path) -> None:
        path = write_submission_csv(_frame(), tmp_path, "JGracey", "prime_radiant")
        header, first = path.read_text().splitlines()[:2]
        assert header == (
            "reference_date,target,horizon,target_end_date,location,"
            "output_type,output_type_id,value"
        )
        fields = first.split(",")
        assert fields[0] == "2024-11-23"  # ISO date, no timestamp
        assert fields[1] == "wk inc flu hosp"
        assert fields[4] == "06"  # leading zero preserved
        assert fields[6] == "0.01"  # level as plain decimal string, not 1e-02
        assert "." not in fields[7]  # integer value, no float suffix

    def test_no_index_column(self, tmp_path: Path) -> None:
        path = write_submission_csv(_frame(), tmp_path, "JGracey", "prime_radiant")
        assert not path.read_text().startswith(",")
