"""Model-metadata rendering, validated against the RECORDED hub schema."""

import json
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator

from prime_radiant.epi.submission.metadata import render_model_metadata, write_model_metadata

pytestmark = pytest.mark.unit

SCHEMA = Path(__file__).parent.parent / "fixtures" / "model-metadata-schema.json"


class TestRenderModelMetadata:
    def test_validates_against_the_hub_schema(self) -> None:
        rendered = render_model_metadata()
        parsed = yaml.safe_load(rendered)
        schema = json.loads(SCHEMA.read_text())
        errors = list(Draft202012Validator(schema).iter_errors(parsed))
        assert errors == [], [e.message for e in errors]

    def test_identity_fields(self) -> None:
        parsed = yaml.safe_load(render_model_metadata())
        assert parsed["team_abbr"] == "JGracey"
        assert parsed["model_abbr"] == "prime_radiant"
        assert parsed["license"] == "CC-BY-4.0"
        assert parsed["designated_model"] is True
        assert parsed["model_contributors"][0]["email"] == "jeremy.a.gracey@gmail.com"

    def test_methods_within_hub_length_cap(self) -> None:
        parsed = yaml.safe_load(render_model_metadata())
        assert len(parsed["methods"]) <= 200  # schema maxLength

    def test_mentions_claude_code(self) -> None:
        # House rule: agentic-coding references name Claude Code explicitly.
        assert "Claude Code" in yaml.safe_load(render_model_metadata())["methods_long"]


class TestCleanroomFallback:
    def test_missing_pyproject_falls_back_to_canonical_identity(self, tmp_path: Path) -> None:
        # cleanroom wheel installs have no pyproject nearby — the metadata must
        # still render with the canonical repo URL and a real version string
        parsed = yaml.safe_load(render_model_metadata(tmp_path / "absent.toml"))
        assert parsed["repo_url"] == "https://github.com/JeremyGracey-AI/prime-radiant"
        assert parsed["model_version"] == "0.1.0"

    def test_malformed_pyproject_takes_the_same_fallback(self, tmp_path: Path) -> None:
        broken = tmp_path / "pyproject.toml"
        broken.write_text('[project]\nname = "x"\n')  # no version, no urls
        parsed = yaml.safe_load(render_model_metadata(broken))
        assert parsed["repo_url"] == "https://github.com/JeremyGracey-AI/prime-radiant"
        assert parsed["model_version"] == "0.1.0"

    def test_real_pyproject_wins_over_the_fallback(self, tmp_path: Path) -> None:
        custom = tmp_path / "pyproject.toml"
        custom.write_text(
            '[project]\nversion = "9.9.9"\n[project.urls]\nRepository = "https://example.test/repo"\n'
        )
        parsed = yaml.safe_load(render_model_metadata(custom))
        assert parsed["model_version"] == "9.9.9"
        assert parsed["repo_url"] == "https://example.test/repo"


class TestWriteModelMetadata:
    def test_writes_the_hub_named_file_that_round_trips(self, tmp_path: Path) -> None:
        out = write_model_metadata(tmp_path / "nested" / "model-metadata")
        assert out.name == "JGracey-prime_radiant.yml"
        assert out.read_text() == render_model_metadata()
        assert yaml.safe_load(out.read_text())["team_abbr"] == "JGracey"
