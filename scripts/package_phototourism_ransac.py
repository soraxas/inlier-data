#!/usr/bin/env python3
"""Build the image-free PhotoTourism fixture used by RANSAC benchmarks."""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

SCENES = ("sacre_coeur", "st_peters_square")
FILES = ("matches.h5", "match_conf.h5", "Fgt.h5", "Egt.h5", "K1_K2.h5", "R.h5", "T.h5")
ARCHIVE_ROOT = "phototourism-ransac-val"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "source",
        type=Path,
        help="Extracted archive root or its val directory",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("phototourism-ransac-val-v1.tar.zst"),
    )
    args = parser.parse_args()

    if shutil.which("tar") is None or shutil.which("zstd") is None:
        raise SystemExit("Packaging requires both tar and zstd on PATH")

    source = args.source.resolve()
    source = source / "val" if (source / "val").is_dir() else source
    output = args.output.resolve()
    if output.suffixes[-2:] != [".tar", ".zst"]:
        raise SystemExit("Output must have a .tar.zst suffix")

    expected = [source / scene / filename for scene in SCENES for filename in FILES]
    missing = [path for path in expected if not path.is_file()]
    if missing:
        raise SystemExit("Missing required inputs:\n" + "\n".join(map(str, missing)))

    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="phototourism-ransac-", dir=output.parent) as temp:
        staging = Path(temp) / ARCHIVE_ROOT
        for source_path in expected:
            relative = source_path.relative_to(source)
            destination = staging / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            os.link(source_path, destination)

        tar_path = Path(temp) / "fixture.tar"
        compressed_path = Path(temp) / output.name
        subprocess.run(
            ["tar", "-C", temp, "-cf", tar_path, ARCHIVE_ROOT], check=True
        )
        subprocess.run(
            ["zstd", "-q", "-19", "-T0", "-f", tar_path, "-o", compressed_path],
            check=True,
        )
        subprocess.run(["zstd", "-q", "-t", compressed_path], check=True)
        compressed_path.replace(output)

    print(f"archive: {output}")
    print(f"size_bytes: {output.stat().st_size}")
    print(f"sha256: {sha256(output)}")


if __name__ == "__main__":
    main()
