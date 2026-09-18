from __future__ import annotations

import argparse
import os
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render video uniqueizer copies without Telegram.")
    parser.add_argument("input", type=Path, help="Input video file")
    parser.add_argument("--output", type=Path, default=Path("./output"), help="Output directory")
    parser.add_argument("--copies", type=int, default=1, help="Number of copies to render")
    parser.add_argument("--mode", choices=("standard", "satisfying"), default="standard")
    parser.add_argument("--asset-dir", type=Path, default=None, help="Directory with satisfying/background assets")
    parser.add_argument("--threads", type=int, default=2, help="FFmpeg threads per render")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.input.is_file():
        raise SystemExit(f"Input file does not exist: {args.input}")
    if args.copies < 1:
        raise SystemExit("--copies must be at least 1")
    if args.asset_dir is not None:
        os.environ["ASSET_DIR"] = str(args.asset_dir.resolve())

    from .processing import make_copy

    args.output.mkdir(parents=True, exist_ok=True)
    for index in range(args.copies):
        output = make_copy(str(args.input), args.output, index, threads=args.threads, mode=args.mode)
        print(output)


if __name__ == "__main__":
    main()
