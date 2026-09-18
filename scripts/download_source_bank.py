from __future__ import annotations

import json
import re
import sys
import time
import urllib.request
from urllib.error import HTTPError, URLError
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


CATEGORY_PAGES = [
    "slime", "soap", "washing-hands", "sand", "bubbles", "paint",
    "liquid", "craft", "food", "cutting",
]
TARGET = 240
URL_RE = re.compile(r"https://assets\.mixkit\.co/videos/(\d+)/(\d+)-(360|720|1080)\.mp4")


def fetch(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "VideoUniqueizerSourceCollector/1.0"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                body = response.read().decode("utf-8", errors="replace")
            time.sleep(0.8)
            return body
        except (HTTPError, URLError):
            if attempt == 3:
                raise
            time.sleep(4 + attempt * 3)


def valid_video(path: Path) -> bool:
    import subprocess
    result = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type", "-of", "csv=p=0", str(path)], capture_output=True, text=True)
    return result.returncode == 0 and "video" in result.stdout


def download_one(item: tuple[int, str, str, str, str], target: Path) -> dict:
    index, category, video_id, url, license_name = item
    out = target / f"source_{index:03d}.mp4"
    if not out.exists() or not valid_video(out):
        request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; VideoUniqueizer/1.0)"})
        with urllib.request.urlopen(request, timeout=120) as response, out.open("wb") as stream:
            stream.write(response.read())
    if not valid_video(out):
        raise RuntimeError(f"invalid downloaded source: {url}")
    return {
        "index": index,
        "category": category,
        "video_id": video_id,
        "source_url": url,
        "license": license_name,
        "watermark": "none_claimed_by_source",
        "local_path": str(out),
    }


def main() -> None:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else "/opt/video-uniqueizer/assets")
    target = root / "source_bank"
    target.mkdir(parents=True, exist_ok=True)
    source_list = root / "source_urls.tsv"
    items: list[tuple[int, str, str, str, str]] = []
    if source_list.exists():
        for line in source_list.read_text(encoding="utf-8").splitlines():
            if not line.strip() or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) >= 4:
                category, video_id, url, license_name = parts[:4]
                items.append((len(items) + 1, category, video_id, url, license_name))
    else:
        candidates: dict[str, tuple[str, str, str]] = {}
        for category in CATEGORY_PAGES:
            for page in range(1, 11):
                try:
                    html = fetch(f"https://mixkit.co/free-stock-video/{category}/?page={page}")
                except (HTTPError, URLError):
                    continue
                by_id: dict[str, list[tuple[int, str]]] = {}
                for site_id, video_id, quality in URL_RE.findall(html):
                    by_id.setdefault(video_id, []).append((int(quality), f"https://assets.mixkit.co/videos/{site_id}/{video_id}-{quality}.mp4"))
                for video_id, options in by_id.items():
                    quality, url = max(options)
                    candidates.setdefault(video_id, (category, url, str(quality)))
                if len(candidates) >= TARGET:
                    break
            if len(candidates) >= TARGET:
                break
        selected = list(candidates.items())[:TARGET]
        items = [(index, category, video_id, url, "Mixkit License") for index, (video_id, (category, url, _quality)) in enumerate(selected, start=1)]
    manifest: list[dict] = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(download_one, item, target) for item in items]
        for future in as_completed(futures):
            manifest.append(future.result())
    manifest.sort(key=lambda row: row["index"])
    (root / "SOURCE_BANK_LICENSES.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"sources={len(manifest)}")


if __name__ == "__main__":
    main()
