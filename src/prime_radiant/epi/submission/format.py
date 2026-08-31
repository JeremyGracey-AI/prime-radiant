"""Model quantiles -> hubverse 8-column submission frame."""

from datetime import date

import pandas as pd

from prime_radiant.epi.data.epiweek import target_end_date
from prime_radiant.epi.schemas import SubmissionSchema

PRIMARY_TARGET = "wk inc flu hosp"


def build_submission_frame(quantiles: pd.DataFrame, reference_date: date) -> pd.DataFrame:
    """Assemble the hub's 8 columns from (location, horizon, output_type_id, value).

    Validates the reference date is a Saturday (via target_end_date) and the result
    against SubmissionSchema before returning — a frame that leaves here is hub-shaped.
    """
    frame = quantiles.loc[:, ["location", "horizon", "output_type_id", "value"]].copy()
    frame["reference_date"] = pd.Timestamp(reference_date)
    frame["target"] = PRIMARY_TARGET
    frame["target_end_date"] = frame["horizon"].map(
        lambda h: pd.Timestamp(target_end_date(reference_date, int(h)))
    )
    frame["output_type"] = "quantile"
    frame = frame.loc[
        :,
        [
            "reference_date",
            "target",
            "horizon",
            "target_end_date",
            "location",
            "output_type",
            "output_type_id",
            "value",
        ],
    ]
    return SubmissionSchema.validate(frame)
