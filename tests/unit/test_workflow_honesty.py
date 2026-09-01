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


@pytest.fixture(scope="module")
def workflow() -> dict:
    return yaml.safe_load(WORKFLOW.read_text())


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
        condition = workflow["jobs"]["live-submit"]["if"]
        assert "github.event_name == 'workflow_dispatch'" in condition

    def test_live_job_carries_all_three_gates(self, workflow: dict) -> None:
        condition = workflow["jobs"]["live-submit"]["if"]
        assert "inputs.live == true" in condition
        assert "vars.LIVE == '1'" in condition
        # secret gate lives at step level (secrets context unusable in job if:)
        steps = workflow["jobs"]["live-submit"]["steps"]
        assert all(step.get("if") == "env.HUB_PAT != ''" for step in steps)

    def test_live_pr_step_fails_loudly_rather_than_pretending(self, workflow: dict) -> None:
        pr_step = workflow["jobs"]["live-submit"]["steps"][-1]
        assert "exit 1" in pr_step["run"]  # unimplemented until go-live, and says so

    def test_dry_run_uploads_artifact_or_fails(self, workflow: dict) -> None:
        upload = workflow["jobs"]["dry-run"]["steps"][-1]
        assert upload["with"]["if-no-files-found"] == "error"
