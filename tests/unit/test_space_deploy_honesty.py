"""space-deploy.yml honesty: the YAML must carry every structural gate it claims.

Same discipline as test_workflow_honesty (exact-conjunction assertions, not
substrings — the ||-mutant lesson). The deploy job's upload step is REAL, so the
gates are the only thing standing between a dispatch and an outward push:
manual dispatch + deploy input + SPACE_LIVE repo var + HF_TOKEN secret.
"""

import re
from pathlib import Path

import pytest
import yaml

pytestmark = pytest.mark.unit

WORKFLOW = Path(__file__).parents[2] / ".github" / "workflows" / "space-deploy.yml"


@pytest.fixture(scope="module")
def workflow() -> dict:
    return yaml.safe_load(WORKFLOW.read_text())


class TestSpaceDeployHonesty:
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

    def test_manual_dispatch_is_the_only_trigger(self, workflow: dict) -> None:
        # yaml parses the `on:` key as boolean True
        assert list(workflow[True].keys()) == ["workflow_dispatch"]

    def test_deploy_gate_is_the_exact_conjunction(self, workflow: dict) -> None:
        condition = workflow["jobs"]["deploy"]["if"]
        assert condition == (
            "github.event_name == 'workflow_dispatch' && inputs.deploy == true"
            " && vars.SPACE_LIVE == '1'"
        )
        assert "||" not in condition

    def test_every_deploy_step_requires_the_secret(self, workflow: dict) -> None:
        steps = workflow["jobs"]["deploy"]["steps"]
        assert steps, "deploy job has no steps"
        assert all(step.get("if") == "env.HF_TOKEN != ''" for step in steps)

    def test_deploy_pushes_only_the_staged_artifact(self, workflow: dict) -> None:
        # what gets uploaded is exactly what the stage job validated: the deploy
        # job downloads the artifact and never checks out the repo
        steps = workflow["jobs"]["deploy"]["steps"]
        uses = [step.get("uses", "") for step in steps]
        assert any(entry.startswith("actions/download-artifact@") for entry in uses)
        assert not any(entry.startswith("actions/checkout@") for entry in uses)

    def test_upload_targets_the_registered_space(self, workflow: dict) -> None:
        upload = workflow["jobs"]["deploy"]["steps"][-1]
        assert "jeremygracey-ai/prime-radiant" in upload["run"]
        assert "--repo-type" in upload["run"]

    def test_deploy_verifies_the_space_exists_before_uploading(self, workflow: dict) -> None:
        # `hf upload` silently CREATES a missing Space (create_repo exist_ok in
        # huggingface_hub cli/upload.py) — Space creation is a runbook-only
        # action, so the deploy job must refuse to run against a missing Space
        runs = [step.get("run", "") for step in workflow["jobs"]["deploy"]["steps"]]
        verify_index = next(i for i, run in enumerate(runs) if "repo_info" in run)
        upload_index = next(i for i, run in enumerate(runs) if "hf upload" in run)
        assert verify_index < upload_index

    def test_generated_requirements_never_pin_gradio(self, workflow: dict) -> None:
        # sdk_version in the README front-matter governs the Space's gradio;
        # a requirements pin would fight it
        staging = [
            step["run"]
            for step in workflow["jobs"]["stage"]["steps"]
            if "requirements.txt" in step.get("run", "")
        ]
        assert len(staging) == 1, "exactly one step may write the Space requirements.txt"
        all_stage_runs = "\n".join(
            step.get("run", "") for step in workflow["jobs"]["stage"]["steps"]
        )
        assert "gradio==" not in all_stage_runs

    def test_no_expression_interpolation_in_run_blocks(self, workflow: dict) -> None:
        for job in workflow["jobs"].values():
            for step in job.get("steps", []):
                if "run" in step:
                    assert "${{" not in step["run"], step.get("name", "unnamed step")

    def test_checkout_does_not_persist_credentials(self, workflow: dict) -> None:
        checkout = workflow["jobs"]["stage"]["steps"][0]
        assert checkout["with"]["persist-credentials"] is False

    def test_stage_uploads_artifact_or_fails(self, workflow: dict) -> None:
        upload = workflow["jobs"]["stage"]["steps"][-1]
        assert upload["with"]["if-no-files-found"] == "error"
