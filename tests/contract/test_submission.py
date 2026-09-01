"""Submission formatter + validator: model quantiles -> hub-valid frame."""

from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from prime_radiant.epi.schemas import QUANTILE_LEVELS
from prime_radiant.epi.submission.format import build_submission_frame
from prime_radiant.epi.submission.validate import SubmissionInvalidError, validate_submission

pytestmark = pytest.mark.contract

TASKS_JSON = Path(__file__).parent.parent / "fixtures" / "tasks.json"
REFERENCE_DATE = date(2024, 11, 23)  # present in tasks.json's enumerated round ids


def _model_quantiles() -> pd.DataFrame:
    rows = [
        {"location": loc, "horizon": h, "output_type_id": q, "value": int(50 * q) + h + 1}
        for loc in ("06", "US")
        for h in (-1, 0, 1, 2, 3)
        for q in QUANTILE_LEVELS
    ]
    return pd.DataFrame(rows)


class TestBuildSubmissionFrame:
    def test_produces_schema_valid_8_column_frame(self) -> None:
        frame = build_submission_frame(_model_quantiles(), REFERENCE_DATE)
        assert len(frame) == 2 * 5 * 23
        assert set(frame["target"]) == {"wk inc flu hosp"}
        assert set(frame["output_type"]) == {"quantile"}

    def test_target_end_dates_follow_hub_arithmetic(self) -> None:
        frame = build_submission_frame(_model_quantiles(), REFERENCE_DATE)
        h2 = frame[frame["horizon"] == 2]
        assert set(h2["target_end_date"]) == {pd.Timestamp(2024, 12, 7)}

    def test_rejects_non_saturday_reference_date(self) -> None:
        with pytest.raises(ValueError, match="Saturday"):
            build_submission_frame(_model_quantiles(), date(2024, 11, 25))


class TestValidateSubmission:
    def test_valid_frame_passes_against_recorded_tasks_json(self) -> None:
        frame = build_submission_frame(_model_quantiles(), REFERENCE_DATE)
        validate_submission(frame, TASKS_JSON)

    def test_rejects_reference_date_outside_hub_rounds(self) -> None:
        # A Saturday, but not among tasks.json's enumerated reference_dates
        frame = build_submission_frame(_model_quantiles(), date(2022, 1, 8))
        with pytest.raises(SubmissionInvalidError, match="reference_date"):
            validate_submission(frame, TASKS_JSON)

    def test_rejects_quantile_level_drift(self) -> None:
        # Frame-side drift: a level the hub doesn't know fails loudly.
        frame = build_submission_frame(_model_quantiles(), REFERENCE_DATE)
        frame.loc[frame.index[0], "output_type_id"] = 0.02  # not a hub level
        with pytest.raises(SubmissionInvalidError, match="quantile"):
            validate_submission(frame, TASKS_JSON)

    def test_detects_hub_side_level_drift(self, tmp_path: Path) -> None:
        # HUB-side drift: if the hub changes ITS level set, a frame built from our
        # constants must fail against the live config. (Adversarial review found
        # no test mutated tasks.json itself.)
        import json

        config = json.loads(TASKS_JSON.read_text())
        for task in config["rounds"][0]["model_tasks"]:
            quantile = task.get("output_type", {}).get("quantile")
            if quantile is not None:
                required = quantile["output_type_id"]["required"]
                if 0.01 in required:
                    required.remove(0.01)
        drifted = tmp_path / "tasks.json"
        drifted.write_text(json.dumps(config))

        frame = build_submission_frame(_model_quantiles(), REFERENCE_DATE)
        with pytest.raises(SubmissionInvalidError, match="quantile"):
            validate_submission(frame, drifted)

    def test_structural_hub_drift_raises_submission_error_not_keyerror(
        self, tmp_path: Path
    ) -> None:
        # If the hub removes the quantile output type entirely, the declared
        # failure mode is SubmissionInvalidError — never a raw KeyError.
        import json

        config = json.loads(TASKS_JSON.read_text())
        for task in config["rounds"][0]["model_tasks"]:
            task.get("output_type", {}).pop("quantile", None)
        drifted = tmp_path / "tasks.json"
        drifted.write_text(json.dumps(config))

        frame = build_submission_frame(_model_quantiles(), REFERENCE_DATE)
        with pytest.raises(SubmissionInvalidError):
            validate_submission(frame, drifted)

    def test_counts_must_be_below_population(self) -> None:
        # The hub's own validations.yml runs a custom counts_lt_popn check we
        # lacked (adversarial recon finding). California's population is ~39M;
        # a 50M admissions count must fail.
        locations = Path(__file__).parent.parent / "fixtures" / "locations.csv"
        frame = build_submission_frame(_model_quantiles(), REFERENCE_DATE)
        ca_rows = frame.index[frame["location"] == "06"]
        frame.loc[ca_rows[-1], "value"] = 50_000_000  # CA pop ~39M
        with pytest.raises(SubmissionInvalidError, match="population"):
            validate_submission(frame, TASKS_JSON, locations_csv=locations)

    def test_value_exactly_at_population_fails(self) -> None:
        # hubValidations source: `value < popn` — equality is a breach. The >=
        # boundary was untested (the >-mutant survived; adversarial finding).
        locations = Path(__file__).parent.parent / "fixtures" / "locations.csv"
        frame = build_submission_frame(_model_quantiles(), REFERENCE_DATE)
        ca_rows = frame.index[frame["location"] == "06"]
        frame.loc[ca_rows[-1], "value"] = 39_431_263  # exactly CA's fixture population
        with pytest.raises(SubmissionInvalidError, match="population"):
            validate_submission(frame, TASKS_JSON, locations_csv=locations)

    def test_population_check_passes_for_sane_values(self) -> None:
        locations = Path(__file__).parent.parent / "fixtures" / "locations.csv"
        frame = build_submission_frame(_model_quantiles(), REFERENCE_DATE)
        validate_submission(frame, TASKS_JSON, locations_csv=locations)

    def test_primary_target_found_in_any_round(self, tmp_path: Path) -> None:
        # The hub may reorganize rounds; the validator must search all of them.
        import json

        config = json.loads(TASKS_JSON.read_text())
        config["rounds"] = [
            {"model_tasks": []},
            config["rounds"][0],
        ]
        moved = tmp_path / "tasks.json"
        moved.write_text(json.dumps(config))

        frame = build_submission_frame(_model_quantiles(), REFERENCE_DATE)
        validate_submission(frame, moved)  # must not raise
