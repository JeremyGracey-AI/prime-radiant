# /// script
# requires-python = ">=3.11"
# dependencies = ["playwright>=1.45"]  # inline metadata: keeps playwright out of uv.lock
# ///
# pyright: reportMissingImports=false
"""Record the Sentinel season replay as an MP4 for LinkedIn / social.

Usage (from repo root, one-time browser install first):
    uv run --with playwright playwright install chromium
    uv run scripts/record_sentinel.py

Output: reports/sentinel-replay.mp4 (1920x1080, H.264, LinkedIn-safe).
Requires ffmpeg on PATH for the WebM -> MP4 step (`brew install ffmpeg`).
"""

import shutil
import subprocess
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright

PAGE_URL = "https://jeremygracey.ai/prime-radiant/sentinel/"
SIZE = {"width": 1920, "height": 1080}
REPLAY_TIMEOUT_MS = 180_000  # full 28-round season clock, with headroom
HOLD_MS = 5_000  # linger on the score card so the last frame reads
OUT_PATH = Path(__file__).resolve().parents[1] / "reports" / "sentinel-replay.mp4"


def record_webm(video_dir: Path) -> Path:
    """Play the replay start to finish in headless Chromium; return the WebM path."""
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(
            viewport=SIZE, record_video_dir=str(video_dir), record_video_size=SIZE
        )
        page = ctx.new_page()
        page.goto(PAGE_URL, wait_until="networkidle")
        page.locator("#hero").scroll_into_view_if_needed()
        page.click("#btn-play")
        # The page flips #endcard to .show when the season clock runs out.
        page.wait_for_selector("#endcard.show", timeout=REPLAY_TIMEOUT_MS)
        page.wait_for_timeout(HOLD_MS)
        ctx.close()
        browser.close()
    videos = list(video_dir.glob("*.webm"))
    assert len(videos) == 1, f"expected one recording, got {videos}"
    return videos[0]


def to_mp4(webm: Path, out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["ffmpeg", "-y", "-i", str(webm), "-c:v", "libx264", "-pix_fmt", "yuv420p"]
    subprocess.run([*cmd, "-movflags", "+faststart", str(out)], check=True)


def main() -> None:
    assert shutil.which("ffmpeg"), "ffmpeg not on PATH: brew install ffmpeg"
    with tempfile.TemporaryDirectory() as tmp:
        to_mp4(record_webm(Path(tmp)), OUT_PATH)
    print(f"wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
