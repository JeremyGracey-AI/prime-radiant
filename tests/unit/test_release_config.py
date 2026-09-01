"""Release-automation config: the actor-prefix strip that makes psr parse this
repo's history, and the no-requirements*.txt release-hygiene assertion.

The full psr parse (subclass + version compute) is exercised by the
integration-marked `uvx python-semantic-release --noop` test — psr cannot live
in the project env (its tomlkit floor conflicts with gradio's cap), so the
offline suite covers the pure prefix logic the subclass defers to.
"""

import importlib.util
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).parents[2]


def _load_strip():
    spec = importlib.util.spec_from_file_location("psr_parser", REPO_ROOT / "psr_parser.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.strip_actor_prefix


class TestActorPrefixStrip:
    def test_strips_the_claude_prefix(self) -> None:
        strip = _load_strip()
        assert strip("[claude] feat(epi): add thing") == "feat(epi): add thing"

    def test_plain_conventional_commits_pass_through(self) -> None:
        strip = _load_strip()
        assert strip("fix(scope): plain human commit") == "fix(scope): plain human commit"

    def test_strips_exactly_one_prefix(self) -> None:
        strip = _load_strip()
        assert strip("[claude] [claude] feat: x") == "[claude] feat: x"

    def test_tolerates_dotted_and_dashed_actors(self) -> None:
        strip = _load_strip()
        assert strip("[a.m-b_a] docs: y") == "docs: y"

    def test_prefix_only_matches_at_start(self) -> None:
        strip = _load_strip()
        assert strip("feat: mention [claude] mid-subject") == "feat: mention [claude] mid-subject"

    def test_multiline_bodies_keep_their_body(self) -> None:
        strip = _load_strip()
        assert strip("[claude] feat: x\n\nbody line") == "feat: x\n\nbody line"


class TestReleaseHygiene:
    def test_no_requirements_txt_is_tracked(self) -> None:
        # The Space's requirements.txt is GENERATED in CI (space-deploy stage
        # job); the git TREE must never carry one — pyproject/uv.lock are the
        # single source of dependency truth. Asserted over git ls-files, never
        # the working directory (CI staging legitimately writes one).
        tracked = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "ls-files"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.splitlines()
        offenders = [path for path in tracked if Path(path).name.lower().startswith("requirements")]
        assert offenders == []

    def test_flip_blocker_files_are_tracked(self) -> None:
        # LICENSE deletion survived every gate (surviving mutant k): a public
        # repo without it is all-rights-reserved and the wheel silently drops
        # its license file. Lock all the release-grade files.
        tracked = set(
            subprocess.run(
                ["git", "-C", str(REPO_ROOT), "ls-files"],
                check=True,
                capture_output=True,
                text=True,
            ).stdout.splitlines()
        )
        for required in (
            "LICENSE",
            "CITATION.cff",
            "AI-USE.md",
            "CHANGELOG.md",
            "CONTRIBUTING.md",
            "docs/model-card.md",
        ):
            assert required in tracked, required

    def test_sdist_is_scoped_to_the_package(self) -> None:
        # default hatchling sdists ship the whole working tree (NOTES, handoff
        # briefs, serve_data) to PyPI — the sdist target must stay scoped
        # (adversarial finding)
        pyproject = (REPO_ROOT / "pyproject.toml").read_text()
        assert "[tool.hatch.build.targets.sdist]" in pyproject
        assert "only-include" in pyproject
