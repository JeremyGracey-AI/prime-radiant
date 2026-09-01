"""Honesty checks for the Phase G workflows (ci, release, publish, docs, ai-use).

Same discipline as test_workflow_honesty / test_space_deploy_honesty: exact
assertions on gates, SHA pins everywhere, minimal permissions with every write
explicit and justified. yaml parses the `on:` key as boolean True.
"""

import re
from pathlib import Path

import pytest
import yaml

pytestmark = pytest.mark.unit

WORKFLOWS = Path(__file__).parents[2] / ".github" / "workflows"
NEW = ["ci.yml", "release.yml", "publish.yml", "docs.yml", "ai-use.yml"]


def _load(name: str) -> dict:
    return yaml.safe_load((WORKFLOWS / name).read_text())


@pytest.mark.parametrize("name", NEW)
class TestEveryNewWorkflow:
    def test_every_action_is_sha_pinned(self, name: str) -> None:
        uses = re.findall(r"uses:\s*(\S+)", (WORKFLOWS / name).read_text())
        assert uses, f"{name}: no actions found — parsing broke"
        for entry in uses:
            _, _, ref = entry.partition("@")
            assert re.fullmatch(r"[0-9a-f]{40}", ref), f"{name}: not SHA-pinned: {entry}"

    def test_top_level_permissions_are_read_only(self, name: str) -> None:
        assert _load(name)["permissions"] == {"contents": "read"}

    def test_timeouts_present_on_every_job(self, name: str) -> None:
        for job_name, job in _load(name)["jobs"].items():
            assert "timeout-minutes" in job, f"{name}:{job_name} lacks timeout-minutes"

    def test_no_expression_interpolation_in_run_blocks(self, name: str) -> None:
        for job in _load(name)["jobs"].values():
            for step in job.get("steps", []):
                if "run" in step:
                    assert "${{" not in step["run"], f"{name}: {step.get('name', 'unnamed')}"

    def test_checkouts_never_persist_credentials(self, name: str) -> None:
        for job in _load(name)["jobs"].values():
            for step in job.get("steps", []):
                if str(step.get("uses", "")).startswith("actions/checkout@"):
                    assert step["with"]["persist-credentials"] is False, name

    def test_no_cron_trigger(self, name: str) -> None:
        assert "schedule" not in _load(name)[True], name


class TestCiWorkflow:
    def test_matrix_covers_supported_pythons(self) -> None:
        matrix = _load("ci.yml")["jobs"]["test"]["strategy"]["matrix"]
        assert matrix["python-version"] == ["3.11", "3.12", "3.13"]

    def test_gate_commands_match_the_makefile(self) -> None:
        runs = "\n".join(step.get("run", "") for step in _load("ci.yml")["jobs"]["test"]["steps"])
        assert "ruff check ." in runs
        assert "ruff format --check ." in runs
        assert 'python -c "import gradio"' in runs  # stub-warm before pyright
        assert "--cov-fail-under=85" in runs
        assert '-m "not integration"' in runs

    def test_codecov_upload_is_public_gated_oidc_single_leg(self) -> None:
        steps = _load("ci.yml")["jobs"]["test"]["steps"]
        codecov = [s for s in steps if str(s.get("uses", "")).startswith("codecov/")]
        assert len(codecov) == 1
        assert codecov[0]["if"] == (
            "matrix.python-version == '3.12' && github.event.repository.private == false"
        )
        assert codecov[0]["with"]["use_oidc"] is True
        # OIDC needs id-token on the job; nothing beyond read+id-token allowed
        assert _load("ci.yml")["jobs"]["test"]["permissions"] == {
            "contents": "read",
            "id-token": "write",
        }

    def test_cleanroom_wheel_job_smokes_the_console_script(self) -> None:
        job = _load("ci.yml")["jobs"]["wheel"]
        assert job["needs"] == "test"
        runs = "\n".join(step.get("run", "") for step in job["steps"])
        assert "uv build" in runs
        assert "prime-radiant --help" in runs

    def test_docker_job_builds_and_smokes(self) -> None:
        runs = "\n".join(step.get("run", "") for step in _load("ci.yml")["jobs"]["docker"]["steps"])
        assert "docker build" in runs
        assert "docker run --rm" in runs

    def test_docs_build_is_strict(self) -> None:
        runs = "\n".join(
            step.get("run", "") for step in _load("ci.yml")["jobs"]["docs-build"]["steps"]
        )
        assert "mkdocs build --strict" in runs


class TestReleaseWorkflow:
    def test_manual_dispatch_is_the_only_trigger(self) -> None:
        assert list(_load("release.yml")[True].keys()) == ["workflow_dispatch"]

    def test_contents_write_only_on_the_release_job(self) -> None:
        # the ONE write permission in this repo's workflows: psr pushes the
        # release commit + tag, and only behind a manual dispatch
        jobs = _load("release.yml")["jobs"]
        assert jobs["release"]["permissions"] == {"contents": "write"}

    def test_psr_runs_the_verified_version_via_uvx(self) -> None:
        runs = "\n".join(
            step.get("run", "") for step in _load("release.yml")["jobs"]["release"]["steps"]
        )
        assert "python-semantic-release==10.6.2" in runs

    def test_noop_input_defaults_to_dry_run(self) -> None:
        inputs = _load("release.yml")[True]["workflow_dispatch"]["inputs"]
        assert inputs["noop"]["default"] is True


class TestPublishWorkflow:
    def test_triggers_are_version_tags_and_manual_dispatch(self) -> None:
        # GITHUB_TOKEN-pushed tags never fire push events (recursion guard), so
        # a psr release needs the manual dispatch path
        triggers = _load("publish.yml")[True]
        assert set(triggers.keys()) == {"push", "workflow_dispatch"}
        assert triggers["push"] == {"tags": ["v*"]}

    def test_build_runs_twine_check(self) -> None:
        runs = "\n".join(
            step.get("run", "") for step in _load("publish.yml")["jobs"]["build"]["steps"]
        )
        assert "twine check" in runs

    def test_publish_job_is_trusted_publishing_shaped(self) -> None:
        job = _load("publish.yml")["jobs"]["publish"]
        assert job["needs"] == "build"
        assert job["environment"]["name"] == "pypi"
        assert job["permissions"] == {"id-token": "write"}
        uses = [str(step.get("uses", "")) for step in job["steps"]]
        assert any(entry.startswith("pypa/gh-action-pypi-publish@") for entry in uses)
        assert not any(entry.startswith("actions/checkout@") for entry in uses)


class TestDocsWorkflow:
    def test_deploy_is_gated_on_the_public_flip(self) -> None:
        job = _load("docs.yml")["jobs"]["deploy"]
        assert job["if"] == "github.event.repository.private == false"
        assert job["needs"] == "build"
        assert job["permissions"] == {"pages": "write", "id-token": "write"}
        assert job["environment"]["name"] == "github-pages"


class TestAiUseWorkflow:
    def test_check_is_pinned_to_the_verified_sha(self) -> None:
        steps = _load("ai-use.yml")["jobs"]["check"]["steps"]
        uses = [str(step.get("uses", "")) for step in steps]
        assert "JeremyGracey-AI/ai-use/check@eadf1067e62c2e209b926df8e4115a702ef13ee8" in uses
