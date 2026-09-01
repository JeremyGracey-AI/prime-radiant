"""Render model-metadata/<team>-<model>.yml for hub registration.

Field set and constraints verified against the hub's model-metadata-schema.json
(recorded as a test fixture): 13 required fields, additionalProperties false,
team/model abbr <=16 chars of [A-Za-z0-9_+] (we stay <=15 alnum+underscore per
the stricter README prose), license from the schema enum, methods <=200 chars.

designated_model=true makes the model eligible for CDC's ensemble (max two per
team) — flip to false before the registration PR for a soft launch. The
registration PR itself is a go-live action and is never opened by automation.
"""

import tomllib
from pathlib import Path

import yaml

TEAM_ABBR = "JGracey"
MODEL_ABBR = "prime_radiant"

_METHODS = (
    "Pooled LightGBM quantile regression on 4th-root transformed admission rates "
    "with lag/seasonal features, ensembled with a replica of FluSight-baseline."
)

_METHODS_LONG = (
    "One LightGBM booster per quantile level (23), trained jointly across all "
    "locations with horizon as a feature, predicting the change in 4th-root "
    "per-100k admission rates; per-location scale/center statistics are fitted "
    "per forecast origin from as-of data only. Post-processing sorts quantiles "
    "in transformed space, inverts, clips at zero, and rounds at the submission "
    "boundary. Forecasts are ensembled (per-quantile median) with a validated "
    "replica of FluSight-baseline (cross-validated to relative WIS 0.99999 on "
    "fingerprint-matched vintages). Backtested rolling-origin on hub git-history "
    "vintages across 2023-24, 2024-25 and 2025-26 with leakage invariants "
    "enforced as property tests. Development was agent-assisted using Claude "
    "Code, with every phase adversarially verified by independent refuter "
    "agents; the full methodology and honest league tables (wins and losses) "
    "are published in the repository."
)


def render_model_metadata(pyproject_path: Path | None = None) -> str:
    if pyproject_path is None:
        # parents[4] IS the repo root (submission->epi->prime_radiant->src->root);
        # the old .parent overshoot made this read dead code (adversarial finding).
        pyproject_path = Path(__file__).parents[4] / "pyproject.toml"
    try:
        project = tomllib.loads(pyproject_path.read_text())["project"]
        repo_url = project["urls"]["Repository"]
        version = project["version"]
    except (OSError, KeyError):  # cleanroom installs have no pyproject nearby
        repo_url = "https://github.com/JeremyGracey-AI/prime-radiant"
        version = "0.1.0"

    payload = {
        "team_name": "Jeremy Gracey",
        "team_abbr": TEAM_ABBR,
        "model_name": "Prime Radiant GBQR",
        "model_abbr": MODEL_ABBR,
        "model_version": version,
        "model_contributors": [
            {
                "name": "Jeremy Gracey",
                "affiliation": "Independent",
                "email": "jeremy.a.gracey@gmail.com",
            }
        ],
        "website_url": repo_url,
        "repo_url": repo_url,
        "license": "CC-BY-4.0",
        "designated_model": True,
        "methods": _METHODS,
        "data_inputs": (
            "NHSN weekly confirmed influenza hospital admissions via the FluSight "
            "hub target data; hub auxiliary-data location populations."
        ),
        "methods_long": _METHODS_LONG,
        "ensemble_of_models": True,
        "ensemble_of_hub_models": False,
    }
    return yaml.safe_dump(payload, sort_keys=False, allow_unicode=True, width=88)


def write_model_metadata(out_dir: Path, pyproject_path: Path | None = None) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{TEAM_ABBR}-{MODEL_ABBR}.yml"
    path.write_text(render_model_metadata(pyproject_path))
    return path
