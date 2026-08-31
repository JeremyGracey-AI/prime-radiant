"""As-of-honest access to hub target-data via its git history.

The hub commits target-data weekly in season, so the commit graph IS the vintage
store. `as_of(repo, date)` resolves the last commit at or before end-of-day UTC on
that date and reads the file as it stood then — never the latest revision. This is
the tested leakage invariant behind every backtest.

Blobless clones fetch each historical blob from origin on first read, so results
are cached as parquet by commit sha (a sha's content never changes).
"""

import io
import subprocess
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path

import pandas as pd

from prime_radiant.epi.data.hub import TARGET_FILE, load_target_data


class VintageNotFoundError(LookupError):
    """No commit exists at or before the requested as-of date."""


@dataclass(frozen=True)
class Vintage:
    sha: str
    committed_at: datetime


def resolve_vintage(repo: Path, as_of_date: date, target_file: str = TARGET_FILE) -> Vintage:
    before = f"{as_of_date.isoformat()}T23:59:59+00:00"
    result = subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "rev-list",
            "-1",
            f"--before={before}",
            # first-parent = what a main-branch watcher could see on that date;
            # without it, PR-branch commits surface before their merge landed.
            "--first-parent",
            "--format=%H %cI",
            "--no-commit-header",
            "HEAD",
            "--",
            target_file,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    line = result.stdout.strip()
    if not line:
        raise VintageNotFoundError(f"no vintage of {target_file} at or before {as_of_date}")
    sha, committed_at = line.split(" ", 1)
    # Normalize to UTC: a positive-offset stamp (e.g. +10:00) can carry a LOCAL
    # calendar date after the as-of date even though the instant is within it,
    # which would break `committed_at.date() <= as_of_date` for consumers.
    committed_utc = datetime.fromisoformat(committed_at).astimezone(UTC)
    return Vintage(sha=sha, committed_at=committed_utc)


def as_of(
    repo: Path,
    as_of_date: date,
    cache_dir: Path | None = None,
    target_file: str = TARGET_FILE,
) -> pd.DataFrame:
    vintage = resolve_vintage(repo, as_of_date, target_file)
    # Key on (sha, file): real hub commits touch several target-data files at
    # once, and a sha-only key silently serves one file's frame for another.
    cache_name = f"{vintage.sha}--{Path(target_file).stem}.parquet"

    if cache_dir is not None:
        cache_path = cache_dir / cache_name
        if cache_path.exists():
            return pd.read_parquet(cache_path)

    result = subprocess.run(
        ["git", "-C", str(repo), "show", f"{vintage.sha}:{target_file}"],
        check=True,
        capture_output=True,
        text=True,
    )
    frame = _parse_target_csv(result.stdout)

    if cache_dir is not None:
        cache_dir.mkdir(parents=True, exist_ok=True)
        frame.to_parquet(cache_dir / cache_name)
    return frame


def _parse_target_csv(text: str) -> pd.DataFrame:
    tmp = io.StringIO(text)
    return load_target_data(tmp)  # type: ignore[arg-type]  # read_csv accepts buffers too
