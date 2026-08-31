"""Vintage discipline: as_of(date) must never see data committed after that date.

These tests run against a synthetic git repo with commits at controlled dates, so
the invariant is proven offline — no network, no real hub clone.
"""

import subprocess
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from prime_radiant.epi.data.vintages import VintageNotFoundError, as_of, resolve_vintage

pytestmark = pytest.mark.contract

TARGET_REL = "target-data/target-hospital-admissions.csv"
# Second file committed in the SAME commits: real hub weekly commits touch up to
# 4 target-data files at once, so the cache must key on (sha, file), not sha alone.
ED_VISITS_REL = "target-data/target-ed-visits.csv"

# (commit datetime UTC, rows present in that vintage: (date, value))
VINTAGES = [
    (datetime(2025, 11, 5, 12, 0, tzinfo=UTC), [("2025-11-01", 10.0)]),
    (
        datetime(2025, 11, 12, 12, 0, tzinfo=UTC),
        [("2025-11-01", 11.0), ("2025-11-08", 20.0)],
    ),
    (
        datetime(2025, 11, 19, 12, 0, tzinfo=UTC),
        [("2025-11-01", 11.0), ("2025-11-08", 21.0), ("2025-11-15", 30.0)],
    ),
]


def _vintage_csv(rows: list[tuple[str, float]]) -> str:
    lines = ["date,location,location_name,value,weekly_rate"]
    lines += [f"{d},US,US,{v},{v / 100}" for d, v in rows]
    return "\n".join(lines) + "\n"


def _commit(repo: Path, stamp: str, message: str) -> None:
    env = {
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@t",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@t",
        "GIT_AUTHOR_DATE": stamp,
        "GIT_COMMITTER_DATE": stamp,
        "HOME": str(repo),
    }
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", message], check=True, env=env)


@pytest.fixture(scope="module")
def hub_repo(tmp_path_factory: pytest.TempPathFactory) -> Path:
    repo = tmp_path_factory.mktemp("fake-hub")
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
    (repo / "target-data").mkdir()
    for committed_at, rows in VINTAGES:
        (repo / TARGET_REL).write_text(_vintage_csv(rows))
        ed_rows = [(d, v * 7) for d, v in rows]  # distinct values, same shape
        (repo / ED_VISITS_REL).write_text(_vintage_csv(ed_rows))
        stamp = committed_at.isoformat()
        _commit(repo, stamp, f"weekly update {stamp}")
    return repo


class TestResolveVintage:
    def test_picks_latest_commit_at_or_before_date(self, hub_repo: Path) -> None:
        vintage = resolve_vintage(hub_repo, date(2025, 11, 13))
        assert vintage.committed_at.date() == date(2025, 11, 12)

    def test_commit_on_the_as_of_date_counts(self, hub_repo: Path) -> None:
        vintage = resolve_vintage(hub_repo, date(2025, 11, 12))
        assert vintage.committed_at.date() == date(2025, 11, 12)

    def test_raises_before_first_commit(self, hub_repo: Path) -> None:
        with pytest.raises(VintageNotFoundError):
            resolve_vintage(hub_repo, date(2025, 11, 1))


class TestAsOf:
    def test_returns_the_vintage_content_not_the_latest(
        self, hub_repo: Path, tmp_path: Path
    ) -> None:
        frame = as_of(hub_repo, date(2025, 11, 13), cache_dir=tmp_path)
        # the 2025-11-12 vintage: two rows, revised value 11.0, and NO 2025-11-15 row
        assert len(frame) == 2
        assert frame["value"].tolist() == [11.0, 20.0]
        assert str(frame["date"].max().date()) == "2025-11-08"

    def test_cache_round_trip(self, hub_repo: Path, tmp_path: Path) -> None:
        first = as_of(hub_repo, date(2025, 11, 20), cache_dir=tmp_path)
        cached_files = list(tmp_path.glob("*.parquet"))
        assert len(cached_files) == 1
        second = as_of(hub_repo, date(2025, 11, 20), cache_dir=tmp_path)
        assert first.equals(second)

    def test_cache_is_actually_read_back(self, hub_repo: Path, tmp_path: Path) -> None:
        # Adversarial review showed the old round-trip test passed even when the
        # read branch was deleted (recompute gives an identical frame). Poisoning
        # the cache file proves the second call really reads the parquet.
        import pandas as pd

        first = as_of(hub_repo, date(2025, 11, 20), cache_dir=tmp_path)
        cache_file = next(tmp_path.glob("*.parquet"))
        poisoned = first.assign(value=first["value"] * 1000)
        poisoned.to_parquet(cache_file)
        second = as_of(hub_repo, date(2025, 11, 20), cache_dir=tmp_path)
        pd.testing.assert_frame_equal(second, poisoned)

    def test_cache_key_distinguishes_target_files(self, hub_repo: Path, tmp_path: Path) -> None:
        # Both files were last touched by the SAME commit; a sha-only cache key
        # would silently serve hospital admissions when asked for ed visits.
        admissions = as_of(hub_repo, date(2025, 11, 20), cache_dir=tmp_path)
        ed_visits = as_of(
            hub_repo, date(2025, 11, 20), cache_dir=tmp_path, target_file=ED_VISITS_REL
        )
        assert ed_visits["value"].tolist() == [v * 7 for v in admissions["value"].tolist()]

    def test_committed_at_is_utc_normalized(self, tmp_path_factory: pytest.TempPathFactory) -> None:
        # A commit stamped 2025-11-16T05:00+10:00 happened at 19:00 UTC on the
        # 15th. Without normalization, committed_at.date() reports the 16th and
        # the invariant below is violated (demonstrated by adversarial review).
        repo = tmp_path_factory.mktemp("offset-hub")
        subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
        (repo / "target-data").mkdir()
        (repo / TARGET_REL).write_text(_vintage_csv([("2025-11-08", 5.0)]))
        _commit(repo, "2025-11-16T05:00:00+10:00", "positive-offset commit")

        vintage = resolve_vintage(repo, date(2025, 11, 15))
        assert vintage.committed_at.tzinfo == UTC
        assert vintage.committed_at.date() == date(2025, 11, 15)

    @settings(max_examples=40, deadline=None)
    @given(
        # Starts BEFORE the first commit so the VintageNotFoundError branch is
        # exercised, and stays dense around the commit dates where a wrong
        # vintage is actually detectable.
        as_of_date=st.dates(min_value=date(2025, 11, 1), max_value=date(2025, 11, 30)),
    )
    def test_nothing_returned_postdates_the_as_of_date(
        self, hub_repo: Path, as_of_date: date
    ) -> None:
        try:
            vintage = resolve_vintage(hub_repo, as_of_date)
        except VintageNotFoundError:
            assert as_of_date < date(2025, 11, 5)
            return
        frame = as_of(hub_repo, as_of_date, cache_dir=None)
        assert vintage.committed_at.date() <= as_of_date
        assert frame["date"].max().date() <= as_of_date
