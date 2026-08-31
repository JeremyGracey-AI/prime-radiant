"""Contract tests: pandera schemas guard every stage boundary of the epi pipeline."""

from datetime import date

import pandas as pd
import pandera.errors
import pytest

from prime_radiant.epi.schemas import (
    HUB_LOCATIONS,
    QUANTILE_LEVELS,
    FeatureSchema,
    RawTargetSchema,
    SubmissionSchema,
)

pytestmark = pytest.mark.contract


def _raw_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": pd.to_datetime(["2023-11-04", "2023-11-04"]),
            "location": ["06", "US"],
            "location_name": ["California", "US"],
            "value": [123.0, 4567.0],
            "weekly_rate": [0.31, 1.37],
        }
    )


def _submission_frame() -> pd.DataFrame:
    rows = []
    for level in QUANTILE_LEVELS:
        rows.append(
            {
                "reference_date": date(2026, 1, 3),
                "target": "wk inc flu hosp",
                "horizon": 1,
                "target_end_date": date(2026, 1, 10),
                "location": "06",
                "output_type": "quantile",
                "output_type_id": level,
                "value": int(100 * level),  # monotone by construction
            }
        )
    return pd.DataFrame(rows)


class TestHubLocations:
    def test_constant_matches_recorded_hub_fixture(self) -> None:
        # Cross-verification: the hardcoded constant must equal the recorded
        # auxiliary-data/locations.csv (fetched from the hub 2026-08-30).
        import csv
        from pathlib import Path

        fixture = Path(__file__).parent.parent / "fixtures" / "locations.csv"
        with fixture.open() as f:
            codes = {row["location"] for row in csv.DictReader(f)}
        assert set(HUB_LOCATIONS) == codes
        assert len(HUB_LOCATIONS) == 53


class TestQuantileLevels:
    def test_exactly_23_levels_matching_hub_schema(self) -> None:
        # Verified against hub-config/tasks.json 2026-08-30
        assert len(QUANTILE_LEVELS) == 23
        assert QUANTILE_LEVELS[0] == 0.01
        assert QUANTILE_LEVELS[-1] == 0.99
        assert 0.5 in QUANTILE_LEVELS
        assert list(QUANTILE_LEVELS) == sorted(QUANTILE_LEVELS)


class TestRawTargetSchema:
    def test_accepts_valid_frame(self) -> None:
        RawTargetSchema.validate(_raw_frame())

    def test_rejects_negative_value(self) -> None:
        bad = _raw_frame().assign(value=[-1.0, 10.0])
        with pytest.raises(pandera.errors.SchemaError):
            RawTargetSchema.validate(bad)

    def test_rejects_missing_column(self) -> None:
        with pytest.raises(pandera.errors.SchemaError):
            RawTargetSchema.validate(_raw_frame().drop(columns=["value"]))

    def test_accepts_fractional_values(self) -> None:
        # Early NHSN data contains weekly averages like 8.5 — the RAW layer must not
        # round; integer coercion belongs to the submission layer only.
        RawTargetSchema.validate(_raw_frame().assign(value=[8.5, 3.2]))

    def test_accepts_missing_values(self) -> None:
        # The real hub target file carries NA cells (verified against the full
        # clone 2026-08-30) — the raw layer represents reality; downstream stages
        # decide how to handle gaps.
        RawTargetSchema.validate(_raw_frame().assign(value=[None, 10.0]))


class TestSubmissionSchema:
    def test_accepts_valid_frame(self) -> None:
        SubmissionSchema.validate(_submission_frame())

    def test_rejects_float_values(self) -> None:
        # Hub README policy 2025-26: integer values required for wk inc flu hosp.
        # tasks.json only enforces double>=0, so this schema is the real gate.
        bad = _submission_frame().assign(value=lambda f: f["value"] + 0.5)
        with pytest.raises(pandera.errors.SchemaError):
            SubmissionSchema.validate(bad)

    def test_rejects_negative_values(self) -> None:
        bad = _submission_frame()
        bad.loc[0, "value"] = -3
        with pytest.raises(pandera.errors.SchemaError):
            SubmissionSchema.validate(bad)

    def test_rejects_unknown_quantile_level(self) -> None:
        bad = _submission_frame()
        bad.loc[0, "output_type_id"] = 0.33
        with pytest.raises(pandera.errors.SchemaError):
            SubmissionSchema.validate(bad)

    def test_rejects_non_monotone_quantiles(self) -> None:
        bad = _submission_frame()
        # cross the 0.9 and 0.95 values
        bad.loc[bad["output_type_id"] == 0.95, "value"] = 1
        with pytest.raises(pandera.errors.SchemaError):
            SubmissionSchema.validate(bad)

    def test_rejects_bad_horizon(self) -> None:
        bad = _submission_frame().assign(horizon=7)
        with pytest.raises(pandera.errors.SchemaError):
            SubmissionSchema.validate(bad)

    def test_rejects_non_hub_locations(self) -> None:
        # tasks.json enumerates exactly 53 locations; a regex is not enough —
        # gap FIPS ("03"), excluded territories ("60"), and nonsense ("99")
        # must all fail. Demonstrated over-permissive by adversarial review.
        for bad_code in ("03", "60", "99"):
            bad = _submission_frame().assign(location=bad_code)
            with pytest.raises(pandera.errors.SchemaError):
                SubmissionSchema.validate(bad)

    def test_rejects_incomplete_quantile_set(self) -> None:
        # All 23 levels are `required` in tasks.json — a partial frame is not
        # a valid submission unit.
        bad = _submission_frame().head(5)
        with pytest.raises(pandera.errors.SchemaError):
            SubmissionSchema.validate(bad)

    def test_rejects_duplicate_quantile_level(self) -> None:
        frame = _submission_frame()
        bad = pd.concat([frame, frame.head(1)], ignore_index=True)
        with pytest.raises(pandera.errors.SchemaError):
            SubmissionSchema.validate(bad)

    def test_rejects_targets_not_yet_shipped(self) -> None:
        # Phase A ships the primary target only; rate change is pmf-only in the
        # hub and would be hub-invalid as quantile rows anyway.
        bad = _submission_frame().assign(target="wk flu hosp rate change")
        with pytest.raises(pandera.errors.SchemaError):
            SubmissionSchema.validate(bad)

    def test_rejects_broken_date_arithmetic(self) -> None:
        # Hub rule: target_end_date == reference_date + 7*horizon days.
        bad = _submission_frame().assign(target_end_date=date(2026, 1, 17))  # +14 for horizon 1
        with pytest.raises(pandera.errors.SchemaError):
            SubmissionSchema.validate(bad)

    def test_rejects_non_saturday_reference_date(self) -> None:
        bad = _submission_frame().assign(
            reference_date=date(2026, 1, 6),  # a Tuesday
            target_end_date=date(2026, 1, 13),  # keeps +7*horizon consistent
        )
        with pytest.raises(pandera.errors.SchemaError):
            SubmissionSchema.validate(bad)

    def test_rejects_extra_column(self) -> None:
        # model-output/README: "No additional columns are allowed."
        # strict-mode violations surface as the aggregating SchemaErrors class.
        bad = _submission_frame().assign(comment="hi")
        with pytest.raises((pandera.errors.SchemaError, pandera.errors.SchemaErrors)):
            SubmissionSchema.validate(bad)


class TestFeatureSchema:
    def test_accepts_minimal_feature_frame(self) -> None:
        FeatureSchema.validate(
            pd.DataFrame(
                {
                    "date": pd.to_datetime(["2023-11-04"]),
                    "location": ["06"],
                    "value": [123.0],
                }
            )
        )
