"""`prime-radiant epi {forecast,validate}` — the weekly submission pipeline.

Dry-run is the only mode this code has; "live" exists solely as a gated CI job.
The submitted model is the ENSEMBLE (per-quantile median of the LightGBM model
and the baseline replica), matching the registered metadata
(ensemble_of_models: true).

Auto reference-date rule: the latest tasks.json-enumerated Saturday that is
<= reference_date_for(today) AND whose Wednesday-anchored vintage passes the
UNTOUCHED usability guard. The clamp prevents overshooting the live round once
a future season's rounds are enumerated upfront; the guard is never relaxed.
"""

import argparse
import json
import sys
from collections.abc import Callable
from datetime import date
from pathlib import Path

from prime_radiant.epi.data.epiweek import reference_date_for

REPO_ROOT = Path.cwd()


def enumerated_reference_dates(tasks_json_path: Path) -> list[date]:
    config = json.loads(tasks_json_path.read_text())
    dates: set[str] = set()
    for round_config in config.get("rounds", []):
        for task in round_config.get("model_tasks", []):
            ids = task["task_ids"]["reference_date"]
            dates.update((ids.get("required") or []) + (ids.get("optional") or []))
    return sorted(date.fromisoformat(d) for d in dates)


def auto_reference_date(
    tasks_json_path: Path,
    today: date,
    vintage_check: Callable[[date], bool],
) -> date:
    live_reference = reference_date_for(today)
    candidates = [d for d in enumerated_reference_dates(tasks_json_path) if d <= live_reference]
    for candidate in sorted(candidates, reverse=True):
        if vintage_check(candidate):
            return candidate
    raise LookupError(f"no enumerated round at or before {live_reference} has a usable vintage")


def _default_vintage_check(hub_clone: Path, vintage_cache: Path) -> Callable[[date], bool]:
    def check(candidate: date) -> bool:  # pragma: no cover — clone IO; integration-tested
        from prime_radiant.epi.backtest.rolling import resolve_usable_vintage

        try:
            resolve_usable_vintage(hub_clone, candidate, vintage_cache)
        except LookupError:
            return False
        return True

    return check


def _cmd_forecast(args: argparse.Namespace) -> int:  # pragma: no cover — integration-tested
    from prime_radiant.epi.backtest.rolling import run_origin
    from prime_radiant.epi.data.hub import ensure_hub_clone
    from prime_radiant.epi.submission.metadata import MODEL_ABBR, TEAM_ABBR
    from prime_radiant.epi.submission.write import write_submission_csv

    hub_clone = ensure_hub_clone(Path(args.hub))
    vintage_cache = Path(args.vintage_cache)
    tasks_json = hub_clone / "hub-config" / "tasks.json"

    if args.reference_date == "auto":
        reference = auto_reference_date(
            tasks_json, date.today(), _default_vintage_check(hub_clone, vintage_cache)
        )
    else:
        reference = date.fromisoformat(args.reference_date)

    frames = run_origin(hub_clone, reference, Path(args.backtest_dir), vintage_cache)
    out_path = write_submission_csv(frames["ensemble"], Path(args.out), TEAM_ABBR, MODEL_ABBR)
    print(f"wrote {out_path} (reference_date {reference})")
    return 0


def _cmd_validate(args: argparse.Namespace) -> int:  # pragma: no cover — integration-tested
    import pandas as pd

    from prime_radiant.epi.data.hub import ensure_hub_clone
    from prime_radiant.epi.submission.validate import SubmissionInvalidError, validate_submission

    hub_clone = ensure_hub_clone(Path(args.hub))
    frame = pd.read_csv(args.file, dtype={"location": str})
    frame["output_type_id"] = frame["output_type_id"].astype(float)
    frame["reference_date"] = pd.to_datetime(frame["reference_date"])
    frame["target_end_date"] = pd.to_datetime(frame["target_end_date"])
    try:
        validate_submission(
            frame,
            hub_clone / "hub-config" / "tasks.json",
            locations_csv=hub_clone / "auxiliary-data" / "locations.csv",
        )
    except SubmissionInvalidError as error:
        print(f"INVALID: {error}")
        return 1
    print(f"valid: {args.file}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="prime-radiant")
    subparsers = parser.add_subparsers(dest="namespace", required=True)
    epi = subparsers.add_parser("epi", help="FluSight epi pipeline")
    epi_sub = epi.add_subparsers(dest="command", required=True)

    forecast = epi_sub.add_parser("forecast", help="produce a weekly submission file (dry-run)")
    forecast.add_argument("--reference-date", default="auto")
    forecast.add_argument("--out", default="model-output")
    forecast.add_argument("--hub", default="data/hub")
    forecast.add_argument("--vintage-cache", default="data/vintage_cache")
    forecast.add_argument("--backtest-dir", default="data/backtest")
    forecast.set_defaults(func=_cmd_forecast)

    validate = epi_sub.add_parser("validate", help="validate a submission file against the hub")
    validate.add_argument("file")
    validate.add_argument("--hub", default="data/hub")
    validate.set_defaults(func=_cmd_validate)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
