"""CDC epiweek arithmetic for FluSight dates.

Hub rules (verified against hub-config/tasks.json + model-output/README 2026-08-30):
reference_date is the Saturday ending the CDC epiweek of submission;
target_end_date = reference_date + 7*horizon days.
"""

from datetime import date, timedelta

from epiweeks import Week

_SATURDAY = 5


def target_end_date(reference_date: date, horizon: int) -> date:
    if reference_date.weekday() != _SATURDAY:
        raise ValueError(f"reference_date {reference_date} is not a Saturday")
    return reference_date + timedelta(days=7 * horizon)


def reference_date_for(submission_date: date) -> date:
    return Week.fromdate(submission_date, system="cdc").enddate()
