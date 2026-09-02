"""CLI auto-date selection: latest enumerated round <= live reference date whose
vintage passes the untouched guard."""

from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from prime_radiant.epi.cli import (
    _default_vintage_check,
    auto_reference_date,
    enumerated_reference_dates,
    shadow_reference_date,
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


class TestShadowReferenceDate:
    def test_returns_current_epiweek_saturday_when_vintage_usable(self) -> None:
        assert shadow_reference_date(date(2026, 9, 1), lambda d: True) == date(2026, 9, 5)

    def test_returns_none_when_vintage_guard_refuses(self) -> None:
        # off-season: hub truth stale -> guard refuses -> honest skip, never a forecast
        assert shadow_reference_date(date(2026, 9, 1), lambda d: False) is None

    def test_guard_is_asked_about_the_shadow_date_itself(self) -> None:
        asked: list[date] = []

        def check(candidate: date) -> bool:
            asked.append(candidate)
            return True

        shadow_reference_date(date(2026, 9, 1), check)
        assert asked == [date(2026, 9, 5)]


class TestForecastShadowWiring:
    def _wire(
        self, monkeypatch: pytest.MonkeyPatch, shadow_result: date | None
    ) -> dict[str, object]:
        import prime_radiant.epi.backtest.rolling as rolling_module
        import prime_radiant.epi.cli as cli_module
        import prime_radiant.epi.data.hub as hub_module
        import prime_radiant.epi.submission.write as write_module

        captured: dict[str, object] = {}
        monkeypatch.setattr(hub_module, "ensure_hub_clone", lambda path: Path(path))
        monkeypatch.setattr(
            cli_module, "shadow_reference_date", lambda today, check: shadow_result
        )

        def fake_run_origin(
            hub: Path, reference: date, backtest_dir: Path, cache: Path
        ) -> dict[str, str]:
            captured["reference"] = reference
            captured["backtest_dir"] = backtest_dir
            return {"ensemble": "FRAME"}

        monkeypatch.setattr(rolling_module, "run_origin", fake_run_origin)
        monkeypatch.setattr(
            write_module,
            "write_submission_csv",
            lambda frame, out, team, model: out / "f.csv",
        )
        return captured

    def test_shadow_wires_reference_and_scratches_backtest_under_out(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        from prime_radiant.epi.cli import main

        captured = self._wire(monkeypatch, date(2026, 9, 5))
        out = tmp_path / "shadow"
        assert main(["epi", "forecast", "--shadow", "--out", str(out)]) == 0
        assert captured["reference"] == date(2026, 9, 5)
        # shadow intermediates stay under --out, never the committed data/backtest
        assert captured["backtest_dir"] == out / "backtest"

    def test_shadow_skip_exits_3_and_never_forecasts(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from prime_radiant.epi.cli import main

        captured = self._wire(monkeypatch, None)
        assert main(["epi", "forecast", "--shadow", "--out", str(tmp_path)]) == 3
        assert captured == {}
        assert "SHADOW SKIP" in capsys.readouterr().out

    def test_shadow_conflicts_with_explicit_reference_date(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        from prime_radiant.epi.cli import main

        captured = self._wire(monkeypatch, date(2026, 9, 5))
        code = main(
            ["epi", "forecast", "--shadow", "--reference-date", "2026-09-05"]
        )
        assert code == 2
        assert captured == {}

    def test_explicit_backtest_dir_wins_in_shadow_mode(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        from prime_radiant.epi.cli import main

        captured = self._wire(monkeypatch, date(2026, 9, 5))
        code = main(
            [
                "epi",
                "forecast",
                "--shadow",
                "--out",
                str(tmp_path),
                "--backtest-dir",
                str(tmp_path / "bt"),
            ]
        )
        assert code == 0
        assert captured["backtest_dir"] == tmp_path / "bt"

    def test_default_backtest_dir_unchanged_without_shadow(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        from prime_radiant.epi.cli import main

        captured = self._wire(monkeypatch, None)
        code = main(
            ["epi", "forecast", "--reference-date", "2026-09-05", "--out", str(tmp_path)]
        )
        assert code == 0
        assert captured["backtest_dir"] == Path("data/backtest")


class TestValidateShadowWiring:
    def _submission_csv(self, tmp_path: Path) -> Path:
        path = tmp_path / "2026-09-05-JGracey-prime_radiant.csv"
        pd.DataFrame(
            {
                "reference_date": ["2026-09-05"],
                "target": ["wk inc flu hosp"],
                "horizon": [0],
                "target_end_date": ["2026-09-05"],
                "location": ["06"],
                "output_type": ["quantile"],
                "output_type_id": [0.5],
                "value": [1],
            }
        ).to_csv(path, index=False)
        return path

    def _wire(self, monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
        import prime_radiant.epi.data.hub as hub_module
        import prime_radiant.epi.submission.validate as validate_module

        captured: dict[str, object] = {}
        monkeypatch.setattr(hub_module, "ensure_hub_clone", lambda path: Path(path))

        def fake_validate(
            frame: pd.DataFrame,
            tasks_json_path: Path,
            locations_csv: Path | None = None,
            require_enumerated_round: bool = True,
        ) -> None:
            captured["require_enumerated_round"] = require_enumerated_round

        monkeypatch.setattr(validate_module, "validate_submission", fake_validate)
        return captured

    def test_round_membership_required_by_default(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        from prime_radiant.epi.cli import main

        captured = self._wire(monkeypatch)
        assert main(["epi", "validate", str(self._submission_csv(tmp_path))]) == 0
        assert captured["require_enumerated_round"] is True

    def test_shadow_flag_relaxes_only_round_membership(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        from prime_radiant.epi.cli import main

        captured = self._wire(monkeypatch)
        code = main(["epi", "validate", "--shadow", str(self._submission_csv(tmp_path))])
        assert code == 0
        assert captured["require_enumerated_round"] is False


class TestDefaultVintageCheck:
    def test_factory_returns_a_callable_guard(self, tmp_path: Path) -> None:
        # the closure body is clone-IO (integration-tested); the factory's
        # contract — a per-date callable — is locked here
        check = _default_vintage_check(tmp_path / "hub", tmp_path / "cache")
        assert callable(check)
