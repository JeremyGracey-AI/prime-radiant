"""Workflow-honesty checks: the YAML must carry every structural gate it claims.

Static checks only — the semantic proof (live job actually skipped) comes from a
real dispatched CI run, asserted in the phase's done condition.
"""

import re
from pathlib import Path

import pytest
import yaml

pytestmark = pytest.mark.unit

WORKFLOW = Path(__file__).parents[2] / ".github" / "workflows" / "weekly-forecast.yml"
WATCH = Path(__file__).parents[2] / ".github" / "workflows" / "hub-config-watch.yml"


@pytest.fixture(scope="module")
def workflow() -> dict:
    return yaml.safe_load(WORKFLOW.read_text())


@pytest.fixture(scope="module")
def watch() -> dict:
    return yaml.safe_load(WATCH.read_text())


class TestWorkflowHonesty:
    def test_every_action_is_sha_pinned(self, workflow: dict) -> None:
        uses = re.findall(r"uses:\s*(\S+)", WORKFLOW.read_text())
        assert uses, "no actions found — parsing broke"
        for entry in uses:
            _, _, ref = entry.partition("@")
            assert re.fullmatch(r"[0-9a-f]{40}", ref), f"not SHA-pinned: {entry}"

    def test_minimal_permissions_and_concurrency(self, workflow: dict) -> None:
        assert workflow["permissions"] == {"contents": "read"}
        assert workflow["concurrency"]["cancel-in-progress"] is False

    def test_timeouts_present_on_every_job(self, workflow: dict) -> None:
        for name, job in workflow["jobs"].items():
            assert "timeout-minutes" in job, f"job {name} lacks timeout-minutes"

    def test_cron_cannot_reach_the_live_job(self, workflow: dict) -> None:
        # EXACT conjunction, not substrings: a mutant appending
        # "|| github.event_name == 'schedule'" passed the old substring checks
        # under &&-over-|| precedence (adversarial finding).
        condition = workflow["jobs"]["live-submit"]["if"]
        assert condition == (
            "github.event_name == 'workflow_dispatch' && inputs.live == true && vars.LIVE == '1'"
        )
        assert "||" not in condition

    def test_live_job_carries_all_three_gates(self, workflow: dict) -> None:
        condition = workflow["jobs"]["live-submit"]["if"]
        assert "inputs.live == true" in condition
        assert "vars.LIVE == '1'" in condition
        # secret gate lives at step level (secrets context unusable in job if:)
        steps = workflow["jobs"]["live-submit"]["steps"]
        assert all(step.get("if") == "env.HUB_PAT != ''" for step in steps)

    def test_live_pr_step_runs_the_submission_script(self, workflow: dict) -> None:
        # The go-live stub (`exit 1`) is retired: the last step must delegate to
        # the tested script, and no live-submit step may still fail-by-design.
        steps = workflow["jobs"]["live-submit"]["steps"]
        assert "scripts/open_hub_pr.sh" in steps[-1]["run"]
        assert all("exit 1" not in step.get("run", "") for step in steps)

    def test_live_submit_downloads_the_validated_artifact(self, workflow: dict) -> None:
        # Separate runner: the dry-run's validated CSV + rendered metadata reach
        # live-submit only through the artifact — never a re-forecast.
        steps = workflow["jobs"]["live-submit"]["steps"]
        downloads = [s for s in steps if str(s.get("uses", "")).startswith("actions/download-artifact@")]
        assert len(downloads) == 1
        assert downloads[0]["with"]["name"] == "submission"

    def test_no_expression_interpolation_in_run_blocks(self, workflow: dict) -> None:
        # Script-injection hardening: workflow_dispatch inputs must reach shell
        # via env indirection, never direct ${{ }} interpolation in run:.
        for job in workflow["jobs"].values():
            for step in job.get("steps", []):
                if "run" in step:
                    assert "${{" not in step["run"], step.get("name", "unnamed step")

    def test_checkouts_never_persist_credentials(self, workflow: dict) -> None:
        # Every checkout in every job — the shadow job pushes via an explicit
        # token URL instead of persisted credentials.
        checkouts = [
            step
            for job in workflow["jobs"].values()
            for step in job.get("steps", [])
            if str(step.get("uses", "")).startswith("actions/checkout@")
        ]
        assert checkouts, "no checkout steps found — parsing broke"
        for checkout in checkouts:
            assert checkout["with"]["persist-credentials"] is False

    def test_dry_run_uploads_artifact_or_fails(self, workflow: dict) -> None:
        upload = workflow["jobs"]["dry-run"]["steps"][-1]
        assert upload["with"]["if-no-files-found"] == "error"

    def test_dry_run_artifact_carries_metadata_for_live_submit(self, workflow: dict) -> None:
        # live-submit bundles model-metadata into the first PR if the hub hasn't
        # merged it (hub precedent #2329) — the artifact must carry the yml.
        steps = workflow["jobs"]["dry-run"]["steps"]
        assert any("write_model_metadata" in step.get("run", "") for step in steps)
        upload = steps[-1]
        assert "model-output/*.yml" in upload["with"]["path"]
        assert "model-output/*.csv" in upload["with"]["path"]

    def test_job_permissions_are_allowlisted(self, workflow: dict) -> None:
        # Only the shadow job may write, and only repo contents (its weekly
        # baseline commit); any other job-level escalation fails loudly.
        allowed = {"shadow": {"contents": "write"}}
        for job_name, job in workflow["jobs"].items():
            if "permissions" in job:
                assert job["permissions"] == allowed[job_name], job_name


class TestShadowJob:
    def test_skip_exit_3_is_green_and_loud(self, workflow: dict) -> None:
        # Exit 3 = honest off-season skip: the run stays green but writes a
        # step-summary notice; any other nonzero exit still fails the job.
        forecast = workflow["jobs"]["shadow"]["steps"][4]
        assert "--shadow" in forecast["run"]
        assert forecast.get("id") == "shadow"
        assert '"$code" -eq 3' in forecast["run"]
        assert "GITHUB_STEP_SUMMARY" in forecast["run"]
        assert 'exit "$code"' in forecast["run"]

    def test_downstream_steps_are_gated_on_not_skipped(self, workflow: dict) -> None:
        steps = workflow["jobs"]["shadow"]["steps"]
        gated = [s for s in steps if "if" in s]
        assert len(gated) == 2  # validate + commit
        for step in gated:
            assert step["if"] == "steps.shadow.outputs.skipped == 'false'"

    def test_validation_relaxes_only_round_membership(self, workflow: dict) -> None:
        steps = workflow["jobs"]["shadow"]["steps"]
        validate = next(s for s in steps if "epi validate" in s.get("run", ""))
        assert "validate --shadow" in validate["run"]

    def test_commit_is_actor_prefixed_chore_with_house_identity(self, workflow: dict) -> None:
        # `chore` parses under psr (a `data` type would land as noise); the git
        # identity is the house identity, not github-actions[bot].
        steps = workflow["jobs"]["shadow"]["steps"]
        commit = next(s for s in steps if "git push" in s.get("run", ""))
        assert "[cron] chore(shadow):" in commit["run"]
        assert "jeremy.a.gracey@gmail.com" in commit["run"]

    def test_push_targets_own_master_via_env_indirected_token(self, workflow: dict) -> None:
        steps = workflow["jobs"]["shadow"]["steps"]
        commit = next(s for s in steps if "git push" in s.get("run", ""))
        assert "HEAD:master" in commit["run"]
        assert "x-access-token" in commit["run"]
        assert set(commit["env"]) == {"TOKEN", "REPO"}

    def test_rerun_with_unchanged_file_commits_nothing(self, workflow: dict) -> None:
        steps = workflow["jobs"]["shadow"]["steps"]
        commit = next(s for s in steps if "git push" in s.get("run", ""))
        assert "git diff --cached --quiet" in commit["run"]


class TestHubConfigWatch:
    """The season trigger: a daily check for rounds beyond the last known max,
    pinging via exactly one open issue. Fires the moment the 2026-27 config
    lands (precedent: Sep 12 2023, Sep 30 2024, Sep 5 2025)."""

    def test_daily_cron_and_manual_dispatch_only(self, watch: dict) -> None:
        assert set(watch[True].keys()) == {"schedule", "workflow_dispatch"}
        assert watch[True]["schedule"] == [{"cron": "23 13 * * *"}]

    def test_permissions_are_issues_write_only(self, watch: dict) -> None:
        assert watch["permissions"] == {"issues": "write"}
        for job in watch["jobs"].values():
            assert "permissions" not in job

    def test_uses_no_actions_at_all(self, watch: dict) -> None:
        # curl + python3 + gh, all runner-preinstalled: nothing to pin, no
        # checkout to harden, no third-party code in the loop.
        assert "uses:" not in WATCH.read_text()

    def test_no_expression_interpolation_in_run_blocks(self, watch: dict) -> None:
        for job in watch["jobs"].values():
            for step in job.get("steps", []):
                if "run" in step:
                    assert "${{" not in step["run"], step.get("name", "unnamed step")

    def test_timeout_present(self, watch: dict) -> None:
        for job in watch["jobs"].values():
            assert "timeout-minutes" in job

    def test_last_known_max_is_the_verified_season_end(self, watch: dict) -> None:
        env = watch["jobs"]["watch"]["env"]
        assert env["LAST_KNOWN_MAX"] == "2026-05-30"  # max enumerated date, verified live

    def test_issue_step_is_gated_and_idempotent(self, watch: dict) -> None:
        steps = watch["jobs"]["watch"]["steps"]
        issue = next(s for s in steps if "gh issue create" in s.get("run", ""))
        assert issue["if"] == "steps.check.outputs.new == 'true'"
        # exactly one open ping at a time: exact-title count check before create
        assert "gh issue list" in issue["run"]
        assert 'select(.title ==' in issue["run"]

    def test_detection_reads_the_live_hub_config(self, watch: dict) -> None:
        steps = watch["jobs"]["watch"]["steps"]
        check = next(s for s in steps if s.get("id") == "check")
        assert (
            "https://raw.githubusercontent.com/cdcepi/FluSight-forecast-hub/main/hub-config/tasks.json"
            in check["run"]
        )
        assert "curl -fsSL" in check["run"]  # -f: an HTTP error fails the run, never reads as "no news"
