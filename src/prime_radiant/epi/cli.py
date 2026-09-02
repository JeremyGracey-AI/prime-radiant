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


SHADOW_SKIP_EXIT = 3  # honest off-season skip; CI turns it into a green run with a notice


def shadow_reference_date(today: date, vintage_check: Callable[[date], bool]) -> date | None:
    """Current epiweek's Saturday if its vintage passes the guard, else None.

    Shadow mode never relaxes the vintage guard: while the hub's truth data is
    off-season stale this returns None (honest skip), and it self-arms the week
    the hub resumes publishing."""
    reference = reference_date_for(today)
    return reference if vintage_check(reference) else None


def _default_vintage_check(hub_clone: Path, vintage_cache: Path) -> Callable[[date], bool]:
    def check(candidate: date) -> bool:
        import prime_radiant.epi.backtest.rolling as rolling

        try:
            rolling.resolve_usable_vintage(hub_clone, candidate, vintage_cache)
        except rolling.NoUsableVintageError:
            # the honest miss ONLY — KeyError/IndexError (LookupError subclasses)
            # from hub-side schema drift propagate and fail the run red, never
            # masquerading as an off-season skip (adversarial finding)
            return False
        return True

    return check


def _cmd_forecast(args: argparse.Namespace) -> int:  # pragma: no cover — integration-tested
    from prime_radiant.epi.backtest.rolling import run_origin
    from prime_radiant.epi.data.hub import ensure_hub_clone, update_hub_clone
    from prime_radiant.epi.submission.metadata import MODEL_ABBR, TEAM_ABBR
    from prime_radiant.epi.submission.write import write_submission_csv

    if args.shadow and args.reference_date != "auto":
        print("--shadow selects the current week itself; drop --reference-date")
        return 2

    hub_clone = ensure_hub_clone(Path(args.hub))
    vintage_cache = Path(args.vintage_cache)
    tasks_json = hub_clone / "hub-config" / "tasks.json"

    if args.shadow:
        # A persistent local clone must see the hub wake up: ensure_hub_clone
        # never fetches, so without this a local shadow run would evaluate a
        # frozen snapshot and skip forever (adversarial finding). CI clones
        # fresh each run; the extra pull there is a harmless no-op.
        update_hub_clone(hub_clone)
        shadow = shadow_reference_date(
            date.today(), _default_vintage_check(hub_clone, vintage_cache)
        )
        if shadow is None:
            print(
                "SHADOW SKIP: no usable vintage for the current week "
                "(hub truth data stale — off-season)"
            )
            return SHADOW_SKIP_EXIT
        reference = shadow
    elif args.reference_date == "auto":
        reference = auto_reference_date(
            tasks_json, date.today(), _default_vintage_check(hub_clone, vintage_cache)
        )
    else:
        reference = date.fromisoformat(args.reference_date)

    # Shadow intermediates scratch under --out; the committed data/backtest
    # stays reserved for enumerated-round runs.
    backtest_dir = (
        Path(args.backtest_dir)
        if args.backtest_dir is not None
        else (Path(args.out) / "backtest" if args.shadow else Path("data/backtest"))
    )
    frames = run_origin(hub_clone, reference, backtest_dir, vintage_cache)
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
            require_enumerated_round=not args.shadow,
        )
    except SubmissionInvalidError as error:
        print(f"INVALID: {error}")
        return 1
    print(f"valid: {args.file}")
    return 0


def _cmd_bundle(args: argparse.Namespace) -> int:
    from prime_radiant.epi.serve import bundle

    truth_parquet = (
        Path(args.vintage_cache) / f"{bundle.TRUTH_VINTAGE_SHA}--target-hospital-admissions.parquet"
    )
    out = bundle.build_bundle(
        backtest_dir=Path(args.backtest_dir),
        benchmark_cache=Path(args.benchmarks),
        truth_parquet=truth_parquet,
        truth_vintage_sha=bundle.TRUTH_VINTAGE_SHA,
        reports_dir=Path(args.reports),
        locations_csv=Path(args.hub) / "auxiliary-data" / "locations.csv",
        out_dir=Path(args.out),
    )
    print(f"bundle written to {out}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="prime-radiant")
    subparsers = parser.add_subparsers(dest="namespace", required=True)
    epi = subparsers.add_parser("epi", help="FluSight epi pipeline")
    epi_sub = epi.add_subparsers(dest="command", required=True)

    forecast = epi_sub.add_parser("forecast", help="produce a weekly submission file (dry-run)")
    forecast.add_argument("--reference-date", default="auto")
    forecast.add_argument(
        "--shadow",
        action="store_true",
        help="forecast the CURRENT week even if tasks.json does not enumerate it "
        "(off-season baseline); exits 3 when the vintage guard refuses",
    )
    forecast.add_argument("--out", default="model-output")
    forecast.add_argument("--hub", default="data/hub")
    forecast.add_argument("--vintage-cache", default="data/vintage_cache")
    forecast.add_argument(
        "--backtest-dir",
        default=None,
        help="parquet cache dir (default data/backtest; shadow runs default to <out>/backtest)",
    )
    forecast.set_defaults(func=_cmd_forecast)

    validate = epi_sub.add_parser("validate", help="validate a submission file against the hub")
    validate.add_argument("file")
    validate.add_argument(
        "--shadow",
        action="store_true",
        help="skip only the round-membership check (shadow files target "
        "not-yet-enumerated rounds); every other hub-contract check still runs",
    )
    validate.add_argument("--hub", default="data/hub")
    validate.set_defaults(func=_cmd_validate)

    bundle = epi_sub.add_parser("bundle", help="build the dashboard serve bundle (offline)")
    bundle.add_argument("--backtest-dir", default="data/backtest")
    bundle.add_argument("--benchmarks", default="data/benchmarks")
    bundle.add_argument("--vintage-cache", default="data/vintage_cache")
    bundle.add_argument("--reports", default="reports")
    bundle.add_argument("--hub", default="data/hub")
    bundle.add_argument("--out", default="serve_data")
    bundle.set_defaults(func=_cmd_bundle)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
