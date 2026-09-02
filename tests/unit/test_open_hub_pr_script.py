"""scripts/open_hub_pr.sh against local fixture repos — the hub PR mechanics.

Boundary replay: a local bare "upstream" and bare "fork" stand in for GitHub,
and a stub `gh` on PATH captures the PR-create arguments. Real execution
against the live hub stays impossible until the season opens (stated gap in
NOTES/go-live-runbook.md); everything the script decides is proven here.
"""

import os
import subprocess
from datetime import date, timedelta
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

SCRIPT = Path(__file__).parents[2] / "scripts" / "open_hub_pr.sh"
MODEL_ID = "JGracey-prime_radiant"
# In-window relative to the real clock: the script's freshness guard compares
# the filename date against today (adversarial finding — a stale artifact
# must never reach the hub).
REF = (date.today() + timedelta(days=5)).isoformat()


def _git(*args: str, cwd: Path) -> str:
    result = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True)
    return result.stdout.strip()


class HubFixture:
    def __init__(self, tmp_path: Path, upstream_has_metadata: bool) -> None:
        self.tmp_path = tmp_path
        self.upstream = tmp_path / "upstream.git"
        self.fork = tmp_path / "fork.git"
        subprocess.run(["git", "init", "--bare", "-b", "main", str(self.upstream)], check=True)
        subprocess.run(["git", "init", "--bare", "-b", "main", str(self.fork)], check=True)

        seed = tmp_path / "seed"
        subprocess.run(["git", "clone", str(self.upstream), str(seed)], check=True)
        _git("checkout", "-b", "main", cwd=seed)
        (seed / "README.md").write_text("# FluSight hub fixture\n")
        if upstream_has_metadata:
            (seed / "model-metadata").mkdir()
            (seed / "model-metadata" / f"{MODEL_ID}.yml").write_text("upstream: original\n")
        _git("add", "-A", cwd=seed)
        _git(
            "-c",
            "user.name=Hub Maintainer",
            "-c",
            "user.email=hub@example.org",
            "commit",
            "-m",
            "seed",
            cwd=seed,
        )
        _git("push", "origin", "main", cwd=seed)

        self.submission = tmp_path / f"{REF}-{MODEL_ID}.csv"
        self.submission.write_text("reference_date,value\n2026-11-21,1\n")
        self.metadata = tmp_path / f"{MODEL_ID}.yml"
        self.metadata.write_text("ours: rendered\n")

        gh_bin = tmp_path / "bin"
        gh_bin.mkdir()
        self.gh_capture = tmp_path / "gh_capture.txt"
        gh_stub = gh_bin / "gh"
        gh_stub.write_text(
            "#!/usr/bin/env bash\n"
            'echo "$@" >> "$GH_CAPTURE"\n'
            'if [ "$1" = "pr" ] && [ "$2" = "list" ]; then\n'
            '  echo "${GH_PR_LIST_COUNT:-0}"\n'
            "fi\n"
        )
        gh_stub.chmod(0o755)
        self.path = f"{gh_bin}:{os.environ['PATH']}"

    def run(self, **extra_env: str) -> subprocess.CompletedProcess[str]:
        env = {
            "PATH": self.path,
            "HOME": os.environ.get("HOME", str(self.tmp_path)),
            "SUBMISSION_FILE": str(self.submission),
            "METADATA_FILE": str(self.metadata),
            "FORK_PUSH_URL": str(self.fork),
            "UPSTREAM_URL": str(self.upstream),
            "UPSTREAM_REPO": "cdcepi/FluSight-forecast-hub",
            "FORK_HEAD_OWNER": "JeremyGracey-AI",
            "WORK_DIR": str(self.tmp_path / "work"),
            "GH_CAPTURE": str(self.gh_capture),
            **extra_env,
        }
        return subprocess.run(["bash", str(SCRIPT)], env=env, capture_output=True, text=True)

    def fork_tree(self) -> str:
        return _git(
            "--git-dir",
            str(self.fork),
            "ls-tree",
            "-r",
            "--name-only",
            f"refs/heads/submit-{REF}",
            cwd=self.tmp_path,
        )


class TestOpenHubPr:
    def test_pushes_branch_with_forecast_and_bundled_metadata(self, tmp_path: Path) -> None:
        fixture = HubFixture(tmp_path, upstream_has_metadata=False)
        result = fixture.run()
        assert result.returncode == 0, result.stderr
        tree = fixture.fork_tree()
        assert f"model-output/{MODEL_ID}/{REF}-{MODEL_ID}.csv" in tree
        assert f"model-metadata/{MODEL_ID}.yml" in tree  # bundled: upstream lacked it
        author = _git(
            "--git-dir",
            str(fixture.fork),
            "log",
            "-1",
            "--format=%ae",
            f"refs/heads/submit-{REF}",
            cwd=tmp_path,
        )
        assert author == "jeremy.a.gracey@gmail.com"

    def test_does_not_touch_metadata_already_in_upstream(self, tmp_path: Path) -> None:
        fixture = HubFixture(tmp_path, upstream_has_metadata=True)
        result = fixture.run()
        assert result.returncode == 0, result.stderr
        content = _git(
            "--git-dir",
            str(fixture.fork),
            "show",
            f"refs/heads/submit-{REF}:model-metadata/{MODEL_ID}.yml",
            cwd=tmp_path,
        )
        assert content == "upstream: original"  # ours was NOT copied over it

    def test_pr_create_targets_upstream_main_from_fork_branch(self, tmp_path: Path) -> None:
        fixture = HubFixture(tmp_path, upstream_has_metadata=False)
        assert fixture.run().returncode == 0
        capture = fixture.gh_capture.read_text()
        assert "pr create" in capture
        assert "--repo cdcepi/FluSight-forecast-hub" in capture
        assert "--base main" in capture
        assert f"--head JeremyGracey-AI:submit-{REF}" in capture

    def test_dry_run_pushes_nothing_and_opens_nothing(self, tmp_path: Path) -> None:
        fixture = HubFixture(tmp_path, upstream_has_metadata=False)
        result = fixture.run(DRY_RUN="1")
        assert result.returncode == 0, result.stderr
        assert "DRY RUN" in result.stdout
        assert not fixture.gh_capture.exists()
        branches = _git("--git-dir", str(fixture.fork), "branch", "--list", cwd=tmp_path)
        assert "submit" not in branches

    def test_rejects_a_filename_that_is_not_a_dated_submission(self, tmp_path: Path) -> None:
        fixture = HubFixture(tmp_path, upstream_has_metadata=False)
        rogue = tmp_path / "notes.csv"
        rogue.write_text("x\n")
        result = fixture.run(SUBMISSION_FILE=str(rogue))
        assert result.returncode != 0
        assert "unexpected submission filename" in result.stderr

    def test_refuses_a_stale_reference_date(self, tmp_path: Path) -> None:
        # Adversarial finding: off-season, auto resolves to the LAST enumerated
        # round — months old — and it validates green. The script is the
        # structural freshness gate: a past reference date never reaches the hub.
        fixture = HubFixture(tmp_path, upstream_has_metadata=False)
        stale = tmp_path / f"2026-05-30-{MODEL_ID}.csv"
        stale.write_text("reference_date,value\n2026-05-30,1\n")
        result = fixture.run(SUBMISSION_FILE=str(stale))
        assert result.returncode == 65
        assert "refusing stale or far-future submission" in result.stderr
        assert not fixture.gh_capture.exists()

    def test_refuses_an_impossible_calendar_date(self, tmp_path: Path) -> None:
        # 2026-13-40 matches the format regex; the calendar check must kill it.
        fixture = HubFixture(tmp_path, upstream_has_metadata=False)
        rogue = tmp_path / f"2026-13-40-{MODEL_ID}.csv"
        rogue.write_text("x\n")
        result = fixture.run(SUBMISSION_FILE=str(rogue))
        assert result.returncode != 0
        assert "unexpected submission filename" in result.stderr

    def test_retry_same_week_reuses_workdir_and_updates_the_branch(self, tmp_path: Path) -> None:
        # Adversarial finding: a transient gh failure stranded submit-<ref> on
        # the fork and made every retry die non-fast-forward (and a reused
        # WORK_DIR died on the existing clone). Retries must be idempotent.
        fixture = HubFixture(tmp_path, upstream_has_metadata=False)
        assert fixture.run().returncode == 0
        second = fixture.run()  # same WORK_DIR, branch already on the fork
        assert second.returncode == 0, second.stderr
        assert fixture.gh_capture.read_text().count("pr create") == 2

    def test_skips_pr_create_when_pr_is_already_open(self, tmp_path: Path) -> None:
        fixture = HubFixture(tmp_path, upstream_has_metadata=False)
        result = fixture.run(GH_PR_LIST_COUNT="1")
        assert result.returncode == 0, result.stderr
        assert "already open" in result.stdout
        assert "pr create" not in fixture.gh_capture.read_text()
