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


def _write_vintage_csv(repo: Path, rows: list[tuple[str, float]]) -> None:
    lines = ["date,location,location_name,value,weekly_rate"]
    lines += [f"{d},US,US,{v},{v / 100}" for d, v in rows]
    target = repo / TARGET_REL
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(lines) + "\n")


@pytest.fixture(scope="module")
def hub_repo(tmp_path_factory: pytest.TempPathFactory) -> Path:
    repo = tmp_path_factory.mktemp("fake-hub")
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
    for committed_at, rows in VINTAGES:
        _write_vintage_csv(repo, rows)
        stamp = committed_at.isoformat()
        env = {
            "GIT_AUTHOR_NAME": "t",
            "GIT_AUTHOR_EMAIL": "t@t",
            "GIT_COMMITTER_NAME": "t",
            "GIT_COMMITTER_EMAIL": "t@t",
            "GIT_AUTHOR_DATE": stamp,
            "GIT_COMMITTER_DATE": stamp,
        }
        subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
        subprocess.run(
            ["git", "-C", str(repo), "commit", "-q", "-m", f"weekly update {stamp}"],
            check=True,
            env={**env, "HOME": str(repo)},
        )
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

    @settings(max_examples=25, deadline=None)
    @given(
        as_of_date=st.dates(min_value=date(2025, 11, 5), max_value=date(2026, 1, 31)),
    )
    def test_nothing_returned_postdates_the_as_of_date(
        self, hub_repo: Path, as_of_date: date
    ) -> None:
        vintage = resolve_vintage(hub_repo, as_of_date)
        frame = as_of(hub_repo, as_of_date, cache_dir=None)
        assert vintage.committed_at.date() <= as_of_date
        assert frame["date"].max().date() <= as_of_date
