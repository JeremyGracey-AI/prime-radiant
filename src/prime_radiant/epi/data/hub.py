"""FluSight hub access: blobless+sparse local clone and the target-data loader.

The full hub repo is ~620 MB (dominated by model-output history); a blobless clone
with sparse-checkout of just target-data/, hub-config/ and auxiliary-data/ stays
small while keeping the full commit graph locally — which is what vintages.py needs.
"""

import shutil
import subprocess
from pathlib import Path

import pandas as pd

from prime_radiant.epi.schemas import RawTargetSchema

HUB_URL = "https://github.com/cdcepi/FluSight-forecast-hub.git"
SPARSE_DIRS = ("target-data", "hub-config", "auxiliary-data")
TARGET_FILE = "target-data/target-hospital-admissions.csv"


def load_target_data(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path, dtype={"location": str})
    # Old-form vintages (2023-10-19 .. 2024-05-06, 32 commits) carry a leading
    # unnamed index column; the 5 real columns are identical. Drop it so the
    # 2023-24 season's vintages load.
    frame = frame.drop(columns=[c for c in frame.columns if c.startswith("Unnamed:")])
    frame["date"] = pd.to_datetime(frame["date"])
    frame = frame.sort_values(["location", "date"]).reset_index(drop=True)
    return RawTargetSchema.validate(frame)


def ensure_hub_clone(dest: Path, url: str = HUB_URL) -> Path:  # pragma: no cover — network;
    # exercised by the integration suite against the real hub, not in unit runs.
    if (dest / ".git").exists():
        return dest
    if shutil.which("git") is None:
        # container context: the image ships no git — fail loud and clean
        # instead of a raw subprocess FileNotFoundError after attempting a
        # network clone from a command named `validate`
        raise RuntimeError(
            f"no hub clone at {dest} and no `git` on PATH to create one — "
            "mount a data directory containing an existing hub clone "
            "(see the Dockerfile header)"
        )
    dest.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "clone", "--filter=blob:none", "--sparse", url, str(dest)],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(dest), "sparse-checkout", "set", *SPARSE_DIRS],
        check=True,
        capture_output=True,
    )
    return dest


def update_hub_clone(dest: Path) -> None:  # pragma: no cover — network; integration-tested.
    subprocess.run(["git", "-C", str(dest), "pull", "--ff-only"], check=True, capture_output=True)
