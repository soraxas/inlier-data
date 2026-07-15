#!/usr/bin/env python3
"""Build a compact, image-only PhotoTourism WebP archive for visual use."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ARCHIVE_ROOT = "phototourism-val-images-webp-q85"
SCENES = ("sacre_coeur", "st_peters_square")


def convert(source: Path, destination: Path, quality: int) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["cwebp", "-quiet", "-q", str(quality), source, "-o", destination],
        check=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="Extracted archive root or its val directory")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("phototourism-val-images-webp-q85-v1.tar.zst"),
    )
    parser.add_argument("--quality", type=int, default=85)
    parser.add_argument("--workers", type=int, default=min(os.cpu_count() or 1, 8))
    args = parser.parse_args()

    if not 0 <= args.quality <= 100:
        raise SystemExit("WebP quality must be in [0, 100]")
    if args.workers < 1:
        raise SystemExit("workers must be positive")
    if any(shutil.which(command) is None for command in ("cwebp", "tar", "zstd")):
        raise SystemExit("Packaging requires cwebp, tar, and zstd on PATH")

    source = args.source.resolve()
    source = source / "val" if (source / "val").is_dir() else source
    output = args.output.resolve()
    if output.suffixes[-2:] != [".tar", ".zst"]:
        raise SystemExit("Output must have a .tar.zst suffix")

    images = sorted(
        image
        for scene in SCENES
        for image in (source / scene / "images").glob("*.jpg")
    )
    if not images:
        raise SystemExit(f"No JPEG images found below {source}")

    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="phototourism-webp-", dir=output.parent) as temp:
        staging = Path(temp) / ARCHIVE_ROOT
        destinations = [
            staging / image.relative_to(source).with_suffix(".webp") for image in images
        ]
        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            futures = [
                executor.submit(convert, image, destination, args.quality)
                for image, destination in zip(images, destinations)
            ]
            for future in futures:
                future.result()

        tar_path = Path(temp) / "images.tar"
        compressed_path = Path(temp) / output.name
        subprocess.run(["tar", "-C", temp, "-cf", tar_path, ARCHIVE_ROOT], check=True)
        subprocess.run(
            ["zstd", "-q", "-19", "-T0", "-f", tar_path, "-o", compressed_path],
            check=True,
        )
        subprocess.run(["zstd", "-q", "-t", compressed_path], check=True)
        compressed_path.replace(output)

    print(f"images: {len(images)}")
    print(f"archive: {output}")
    print(f"size_bytes: {output.stat().st_size}")


if __name__ == "__main__":
    main()
