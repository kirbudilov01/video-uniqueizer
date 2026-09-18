from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path


def probe(path: Path) -> tuple[int, int, float, int]:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration,size:stream=width,height", "-of", "json", str(path)],
        capture_output=True,
        text=True,
        check=True,
    )
    data = json.loads(result.stdout)
    video = next(stream for stream in data["streams"] if "width" in stream)
    fmt = data["format"]
    return int(video["width"]), int(video["height"]), float(fmt["duration"]), int(fmt["size"])


def main() -> None:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else "/opt/video-uniqueizer/assets")
    source = root / "source_bank"
    curated = root / "curated_source_bank"
    curated.mkdir(parents=True, exist_ok=True)
    for old in curated.glob("source_*.mp4"):
        old.unlink()
    manifest = []
    for path in sorted(source.glob("source_*.mp4")):
        try:
            width, height, duration, size = probe(path)
        except (OSError, subprocess.CalledProcessError, StopIteration, KeyError, ValueError):
            continue
        if min(width, height) < 720 or not 5 <= duration <= 60 or size < 1_000_000:
            continue
        shutil.copy2(path, curated / path.name)
        manifest.append({"file": path.name, "width": width, "height": height, "duration": round(duration, 3), "size": size})
    (root / "CURATED_SOURCE_BANK.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"curated={len(manifest)} total={len(list(source.glob('source_*.mp4')))}")


if __name__ == "__main__":
    main()
