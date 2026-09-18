from __future__ import annotations

import json
import os
import random
import shutil
import subprocess
import uuid
from pathlib import Path


PROJECT_W = 1080
PROJECT_H = 1920
PANEL_W = 540
PANEL_H = 960
OUTPUT_TARGET_MB = 47.0
COLOR_CHAINS = [
    "eq=contrast=1.006:brightness=-0.0015:saturation=0.995",
    "eq=contrast=1.004:brightness=0.0012:saturation=1.006",
    "colorbalance=rs=0.004:gs=-0.002:bs=-0.003,eq=saturation=1.004",
    "colorbalance=rs=-0.003:gs=0.001:bs=0.004,eq=saturation=0.998",
]


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")


def probe(path: str) -> dict:
    r = _run(["ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams", "-show_format", path])
    if r.returncode != 0:
        raise RuntimeError(r.stderr[-500:])
    data = json.loads(r.stdout)
    video = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), None)
    audio = next((s for s in data.get("streams", []) if s.get("codec_type") == "audio"), None)
    if not video:
        raise RuntimeError("video stream not found")
    return {
        "w": int(video["width"]),
        "h": int(video["height"]),
        "duration": float(data.get("format", {}).get("duration", 0) or 0),
        "bitrate": int(data.get("format", {}).get("bit_rate", 0) or 0),
        "audio": audio is not None,
    }


def validate_output(path: str) -> None:
    info = probe(path)
    if info["w"] != PROJECT_W or info["h"] != PROJECT_H:
        raise RuntimeError(f"bad output size: {info['w']}x{info['h']}")
    if info["duration"] <= 0.2:
        raise RuntimeError("bad output duration")
    if os.path.getsize(path) > 49 * 1024 * 1024:
        raise RuntimeError("output exceeds 49 MB Telegram delivery target")


def metadata_args() -> list[str]:
    # Remove source metadata for privacy; do not invent a fake device identity.
    return ["-map_metadata", "-1", "-map_chapters", "-1", "-metadata", "encoder=", "-metadata", "comment=", "-dn"]


def asset_paths() -> list[Path]:
    for root in (Path(os.getenv("ASSET_DIR", "/opt/video-uniqueizer/assets")), Path("/app/assets"), Path("/data/assets")):
        paths = sorted((root / "curated_source_bank").glob("source_*.mp4"))
        if paths:
            return paths
        paths = sorted((root / "source_bank").glob("source_*.mp4"))
        if paths:
            return paths
        paths = sorted((root / "stock").glob("stock_*.mp4"))
        if paths:
            return paths
        paths = sorted(root.glob("satisfying_v3_*.mp4"))
        if not paths:
            paths = sorted(root.glob("satisfying_*.mp4"))
        if not paths:
            paths = sorted(root.glob("loop_*.mp4"))
        if paths:
            return paths
    raise RuntimeError("motion asset pack is missing")


def background_paths() -> list[Path]:
    for root in (Path(os.getenv("ASSET_DIR", "/opt/video-uniqueizer/assets")), Path("/app/assets"), Path("/data/assets")):
        paths = sorted(root.glob("satisfying_v3_*.mp4"))
        if not paths:
            paths = sorted(root.glob("satisfying_*.mp4"))
        if not paths:
            paths = sorted(root.glob("loop_*.mp4"))
        if paths:
            return paths
    raise RuntimeError("generated background pack is missing")


def _video_bitrate(duration: float) -> int:
    target_bits = OUTPUT_TARGET_MB * 1024 * 1024 * 8
    audio_bits = 192_000 * max(duration, 1.0)
    return max(900_000, min(8_000_000, int((target_bits - audio_bits) / max(duration, 1.0))))


def _render_standard(input_path: str, output_dir: Path, idx: int, threads: int, info: dict) -> Path:
    duration = max(0.3, info["duration"])
    out = output_dir / f"copy_{idx + 1:03d}_{uuid.uuid4().hex[:8]}.mp4"
    zoom = random.uniform(1.006, 1.018)
    crop_w, crop_h = int(PROJECT_W * zoom), int(PROJECT_H * zoom)
    vf = (
        f"scale={crop_w}:{crop_h}:force_original_aspect_ratio=increase:flags=lanczos,"
        f"crop={PROJECT_W}:{PROJECT_H}," + random.choice(COLOR_CHAINS) + ",setsar=1"
    )
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]
    if threads > 0:
        cmd += ["-threads", str(threads)]
    cmd += ["-i", input_path, "-vf", vf, "-map", "0:v:0"]
    if info["audio"]:
        cmd += ["-map", "0:a?", "-af", f"volume={random.uniform(0.997, 1.003):.4f}"]
    else:
        cmd += ["-an"]
    bitrate = _video_bitrate(duration)
    cmd += [
        "-t", f"{duration:.3f}", "-c:v", "libx264", "-preset", "fast",
        "-b:v", str(bitrate), "-maxrate", str(bitrate), "-bufsize", str(bitrate * 2),
        "-pix_fmt", "yuv420p", "-profile:v", "high", "-level", "4.2", "-g", "60",
        "-movflags", "+faststart",
    ]
    if info["audio"]:
        cmd += ["-c:a", "aac", "-b:a", "192k", "-ar", "48000"]
    cmd += metadata_args() + [str(out)]
    result = _run(cmd)
    if result.returncode != 0:
        raise RuntimeError(result.stderr[-1200:])
    validate_output(str(out))
    return out


def make_copy(input_path: str, output_dir: Path, idx: int, threads: int = 2, use_gpu: bool = False, mode: str = "standard") -> Path:
    info = probe(input_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    if mode != "satisfying":
        return _render_standard(input_path, output_dir, idx, threads, info)
    duration = max(0.3, info["duration"])
    out = output_dir / f"copy_{idx + 1:03d}_{uuid.uuid4().hex[:8]}.mp4"
    assets = asset_paths()
    loop_asset = random.choice(assets)
    backgrounds = background_paths()
    background_asset = random.choice(backgrounds)
    main_on_right = random.choice([True, False])
    main_x = PANEL_W if main_on_right else 0
    loop_x = 0 if main_on_right else PANEL_W
    main_chain = (
        f"scale={PANEL_W}:{PANEL_H}:force_original_aspect_ratio=increase:flags=lanczos,"
        f"crop={PANEL_W}:{PANEL_H}," + random.choice(COLOR_CHAINS) + ",setsar=1"
    )
    loop_flip = random.choice([False, True])
    loop_chain = (
        f"scale={PANEL_W}:{PANEL_H}:force_original_aspect_ratio=increase:flags=lanczos,"
        f"crop={PANEL_W}:{PANEL_H}"
        + (",hflip" if loop_flip else "")
        + ",setsar=1"
    )
    background_chain = "scale=1080:1920:force_original_aspect_ratio=increase:flags=lanczos,crop=1080:1920,setsar=1"
    filter_complex = (
        f"[0:v]{main_chain}[main];[1:v]{loop_chain}[loop];[2:v]{background_chain}[bg];"
        f"[bg][main]overlay={main_x}:480[tmp];[tmp][loop]overlay={loop_x}:480[vout]"
    )
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]
    if threads > 0:
        cmd += ["-threads", str(threads)]
    cmd += [
        "-i", input_path,
        "-stream_loop", "-1", "-i", str(loop_asset),
        "-stream_loop", "-1", "-i", str(background_asset),
        "-filter_complex", filter_complex,
        "-map", "[vout]",
    ]
    if info["audio"]:
        cmd += ["-map", "0:a?", "-af", f"volume={random.uniform(0.997, 1.003):.4f}"]
    else:
        cmd += ["-an"]
    bitrate = _video_bitrate(duration)
    cmd += [
        "-t", f"{duration:.3f}", "-c:v", "libx264", "-preset", "fast",
        "-b:v", str(bitrate), "-maxrate", str(bitrate), "-bufsize", str(bitrate * 2),
        "-pix_fmt", "yuv420p", "-profile:v", "high", "-level", "4.2", "-g", "60",
        "-movflags", "+faststart",
    ]
    if info["audio"]:
        cmd += ["-c:a", "aac", "-b:a", "192k", "-ar", "48000"]
    cmd += metadata_args() + [str(out)]
    result = _run(cmd)
    if result.returncode != 0:
        raise RuntimeError(result.stderr[-1200:])
    validate_output(str(out))
    return out


def cleanup_path(path: str | Path) -> None:
    shutil.rmtree(path, ignore_errors=True)
