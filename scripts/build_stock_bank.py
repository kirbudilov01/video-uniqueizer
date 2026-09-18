from __future__ import annotations

import json
import subprocess
import sys
import urllib.request
from pathlib import Path


SOURCES = [
    ("slime", "https://assets.mixkit.co/videos/47332/47332-1080.mp4"),
    ("slime", "https://assets.mixkit.co/videos/47335/47335-1080.mp4"),
    ("slime", "https://assets.mixkit.co/videos/47334/47334-1080.mp4"),
    ("slime", "https://assets.mixkit.co/videos/47330/47330-1080.mp4"),
    ("slime", "https://assets.mixkit.co/videos/47333/47333-1080.mp4"),
    ("soap", "https://assets.mixkit.co/videos/33705/33705-720.mp4"),
    ("soap", "https://assets.mixkit.co/videos/44818/44818-1080.mp4"),
    ("soap", "https://assets.mixkit.co/videos/47585/47585-720.mp4"),
    ("soap", "https://assets.mixkit.co/videos/47832/47832-720.mp4"),
    ("soap", "https://assets.mixkit.co/videos/44829/44829-1080.mp4"),
    ("hands", "https://assets.mixkit.co/videos/33096/33096-720.mp4"),
    ("hands", "https://assets.mixkit.co/videos/33789/33789-720.mp4"),
    ("hands", "https://assets.mixkit.co/videos/18199/18199-1080.mp4"),
    ("hands", "https://assets.mixkit.co/videos/22089/22089-720.mp4"),
]


def run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")


def duration(path: Path) -> float:
    result = run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)])
    return max(1.0, float(result.stdout.strip() or "1"))


def valid_video(path: Path) -> bool:
    result = run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type", "-of", "csv=p=0", str(path)])
    return result.returncode == 0 and "video" in result.stdout


def main() -> None:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else "/opt/video-uniqueizer/assets")
    source_dir = root / "stock_sources"
    stock_dir = root / "stock"
    source_dir.mkdir(parents=True, exist_ok=True)
    stock_dir.mkdir(parents=True, exist_ok=True)
    manifest = []
    local_sources = []

    for index, (category, url) in enumerate(SOURCES, start=1):
        source = source_dir / f"source_{index:02d}.mp4"
        if not source.exists():
            urllib.request.urlretrieve(url, source)
        if not valid_video(source):
            raise RuntimeError(f"downloaded source is not a valid video: {url}")
        local_sources.append((category, source, url))
        manifest.append({"category": category, "source_url": url, "license": "Mixkit License", "local_path": str(source)})

    # Build 240 short variants from real stock clips. The source remains human-shot;
    # variants only change crop, segment, mirror and gentle color treatment.
    for index in range(1, 241):
        category, source, url = local_sources[(index - 1) % len(local_sources)]
        out = stock_dir / f"stock_{index:03d}.mp4"
        if out.exists() and valid_video(out):
            continue
        if out.exists():
            out.unlink()
        source_duration = duration(source)
        max_start = max(0.0, source_duration - 4.5)
        start = (index * 0.73) % max_start if max_start else 0.0
        mirror = index % 2
        saturation = 0.94 + (index % 7) * 0.018
        mirror_filter = "hflip," if mirror else ""
        vf = (
            "scale=540:960:force_original_aspect_ratio=increase:flags=lanczos,crop=540:960,"
            f"{mirror_filter}eq=contrast=1.02:saturation={saturation:.3f},setsar=1"
        )
        result = run([
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-ss", f"{start:.3f}", "-i", str(source), "-t", "4.5", "-vf", vf,
            "-an", "-r", "30", "-c:v", "libx264", "-preset", "veryfast",
            "-crf", "22", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out),
        ])
        if result.returncode != 0:
            raise RuntimeError(result.stderr[-1000:])
        if not valid_video(out):
            raise RuntimeError(f"generated stock asset is invalid: {out}")
        manifest.append({"asset": str(out), "source_url": url, "license": "Mixkit License", "category": category, "watermark": "none_claimed_by_source"})

    (root / "STOCK_BANK_LICENSES.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"sources={len(local_sources)} variants=240")


if __name__ == "__main__":
    main()
