"""CLI auto-date selection: latest enumerated round <= live reference date whose
vintage passes the untouched guard."""

from datetime import date
from pathlib import Path

import pytest

from prime_radiant.epi.cli import (
    _default_vintage_check,
    auto_reference_date,
    enumerated_reference_dates,
)

pytestmark = pytest.mark.unit

TASKS_JSON = Path(__file__).parent.parent / "fixtures" / "tasks.json"


class TestEnumeratedReferenceDates:
    def test_reads_the_hub_round_list(self) -> None:
        dates = enumerated_reference_dates(TASKS_JSON)
        assert dates[0] == date(2023, 10, 7)
        assert dates[-1] == date(2026, 5, 30)
        assert len(dates) == 89  # verified count


class TestAutoReferenceDate:
    def test_selects_latest_guard_passing_round(self) -> None:
        picked = auto_reference_date(
            TASKS_JSON,
            today=date(2026, 8, 31),
            vintage_check=lambda d: True,
        )
        assert picked == date(2026, 5, 30)  # clamp: latest round <= live ref date

    def test_walks_back_past_guard_failures(self) -> None:
        picked = auto_reference_date(
            TASKS_JSON,
            today=date(2026, 8, 31),
            vintage_check=lambda d: d < date(2026, 5, 1),
        )
        assert picked == date(2026, 4, 25)

    def test_clamp_prevents_future_round_overshoot(self) -> None:
        # mid-season: live reference date for a Wednesday 2026-01-07 is Saturday
        # 2026-01-10; enumerated rounds run months further — must not overshoot.
        picked = auto_reference_date(
            TASKS_JSON,
            today=date(2026, 1, 7),
            vintage_check=lambda d: True,
        )
        assert picked == date(2026, 1, 10)

    def test_raises_when_nothing_passes(self) -> None:
        with pytest.raises(LookupError, match="no enumerated round"):
            auto_reference_date(TASKS_JSON, today=date(2026, 8, 31), vintage_check=lambda d: False)


class TestBundleCommand:
    def test_wires_defaults_and_pinned_sha_into_build_bundle(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import prime_radiant.epi.serve.bundle as bundle_module
        from prime_radiant.epi.cli import main

        captured: dict[str, object] = {}

        def fake_build(**kwargs: object) -> Path:
            captured.update(kwargs)
            return Path("serve_data")

        monkeypatch.setattr(bundle_module, "build_bundle", fake_build)
        assert main(["epi", "bundle"]) == 0
        assert captured["backtest_dir"] == Path("data/backtest")
        assert captured["benchmark_cache"] == Path("data/benchmarks")
        assert captured["truth_parquet"] == Path(
            "data/vintage_cache/"
            f"{bundle_module.TRUTH_VINTAGE_SHA}--target-hospital-admissions.parquet"
        )
        assert captured["truth_vintage_sha"] == bundle_module.TRUTH_VINTAGE_SHA
        assert captured["reports_dir"] == Path("reports")
        assert captured["locations_csv"] == Path("data/hub/auxiliary-data/locations.csv")
        assert captured["out_dir"] == Path("serve_data")


class TestDefaultVintageCheck:
    def test_factory_returns_a_callable_guard(self, tmp_path: Path) -> None:
        # the closure body is clone-IO (integration-tested); the factory's
        # contract — a per-date callable — is locked here
        check = _default_vintage_check(tmp_path / "hub", tmp_path / "cache")
        assert callable(check)
