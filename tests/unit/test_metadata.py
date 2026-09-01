"""Model-metadata rendering, validated against the RECORDED hub schema."""

import json
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator

from prime_radiant.epi.submission.metadata import render_model_metadata

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
