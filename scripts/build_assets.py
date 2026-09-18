from __future__ import annotations

import subprocess
import sys
from pathlib import Path


PALETTE = [
    ("101828", "36BFFA", "F79009"),
    ("172554", "38BDF8", "A78BFA"),
    ("052E2B", "2DD4BF", "84CC16"),
    ("3B1028", "F472B6", "FB7185"),
    ("1C1917", "FBBF24", "F97316"),
    ("172554", "60A5FA", "22D3EE"),
    ("312E81", "C4B5FD", "F0ABFC"),
    ("083344", "67E8F9", "14B8A6"),
    ("3F1D0B", "FDBA74", "FACC15"),
    ("1E293B", "94A3B8", "E2E8F0"),
    ("3F0D12", "FB7185", "F43F5E"),
    ("052E16", "4ADE80", "A3E635"),
]

SATISFYING_PALETTE = [
    ("07111F", "00D4FF", "7C3AED"),
    ("120B24", "FF4ECD", "6D5DFB"),
    ("061A17", "00E5A8", "B8F500"),
    ("1B1005", "FF9F43", "FFE66D"),
    ("090D1F", "5EE7FF", "FF61D2"),
    ("1A0611", "FF3864", "FFB000"),
    ("071A2B", "3B82F6", "22D3EE"),
    ("100D23", "A78BFA", "F0ABFC"),
]


def make_loop(out: Path, base: str, accent: str, accent2: str, index: int) -> None:
    filter_graph = (
        f"drawbox=x='mod(t*{90 + index * 7},iw+220)-220':y='mod(t*{35 + index * 3},ih-260)':"
        f"w=260:h=260:color=0x{accent}@0.72:t=fill,"
        f"drawbox=x='iw-mod(t*{70 + index * 5},iw+320)':y='ih/2+sin(t*{0.8 + index * 0.04:.2f})*240':"
        f"w=320:h=320:color=0x{accent2}@0.52:t=fill,"
        "drawgrid=w=90:h=90:t=2:c=white@0.08,vignette=PI/5"
    )
    subprocess.run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i", f"color=c=0x{base}:s=540x960:r=30",
        "-t", "6", "-vf", filter_graph, "-c:v", "libx264", "-preset", "veryfast",
        "-pix_fmt", "yuv420p", "-an", "-movflags", "+faststart", str(out),
    ], check=True)


def make_satisfying(out: Path, base: str, accent: str, accent2: str, index: int) -> None:
    speed = 48 + index * 5
    wave = 0.55 + index * 0.07
    filter_graph = (
        f"drawbox=x='mod(t*{speed},iw+420)-420':y='ih/2+sin(t*{wave:.2f})*280':"
        f"w=420:h=420:color=0x{accent}@0.92:t=3,"
        f"drawbox=x='iw-mod(t*{speed + 31},iw+520)':y='ih/2+cos(t*{wave + 0.23:.2f})*330':"
        f"w=520:h=520:color=0x{accent2}@0.82:t=3,"
        f"drawbox=x='iw/2+sin(t*{wave + 0.41:.2f})*190-150':y='mod(t*{speed + 17},ih+300)-300':"
        f"w=300:h=300:color=white@0.72:t=2,"
        f"drawbox=x='mod(t*{speed + 19},iw-18)':y='mod(t*{speed + 11},ih-18)':w=9:h=9:color=0x{accent}@0.95:t=fill,"
        f"drawbox=x='iw-mod(t*{speed + 27},iw-24)':y='mod(t*{speed + 13},ih-24)':w=6:h=6:color=0x{accent2}@0.95:t=fill,"
        "drawgrid=w=72:h=72:t=1:c=white@0.09,eq=brightness=0.015:contrast=1.12:saturation=1.22,vignette=PI/5"
    )
    subprocess.run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i", f"color=c=0x{base}:s=540x960:r=30",
        "-t", "6", "-vf", filter_graph, "-c:v", "libx264", "-preset", "veryfast",
        "-pix_fmt", "yuv420p", "-an", "-movflags", "+faststart", str(out),
    ], check=True)


def main() -> None:
    target = Path(sys.argv[1] if len(sys.argv) > 1 else "assets")
    target.mkdir(parents=True, exist_ok=True)
    for index, colors in enumerate(PALETTE, start=1):
        out = target / f"loop_{index:02d}.mp4"
        if not out.exists():
            make_loop(out, *colors, index)
    for index in range(1, 241):
        colors = SATISFYING_PALETTE[(index - 1) % len(SATISFYING_PALETTE)]
        out = target / f"satisfying_v3_{index:03d}.mp4"
        if not out.exists():
            make_satisfying(out, *colors, index)
    (target / "README.txt").write_text(
        "Generated satisfying motion loops for Video Uniqueizer.\n"
        "Source: project-generated with FFmpeg; no third-party footage.\n"
        "The city footage pack is retained separately for editorial projects and is not used by this uniqueizer.\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
