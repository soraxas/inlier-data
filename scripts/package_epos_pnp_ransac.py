#!/usr/bin/env python3
"""Build the image-free EPOS absolute-pose fixture used by RANSAC benchmarks."""

from __future__ import annotations

import argparse
import hashlib
import shutil
import subprocess
import tempfile
from pathlib import Path

SOURCE_DIR = "epos_corr_lmo"
ARCHIVE_ROOT = "epos-pnp-ransac-val"
MIN_CASES = 600


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
        help="Extracted RANSAC tutorial PnP archive root or epos_corr_lmo directory",
    )
    parser.add_argument(
        "--output", type=Path, default=Path("epos-pnp-ransac-val-v1.tar.zst")
    )
    args = parser.parse_args()

    if shutil.which("tar") is None or shutil.which("zstd") is None:
        raise SystemExit("Packaging requires both tar and zstd on PATH")

    source = args.source.resolve()
    source = source / SOURCE_DIR if (source / SOURCE_DIR).is_dir() else source
    if source.name != SOURCE_DIR or not source.is_dir():
        raise SystemExit(f"Expected an extracted {SOURCE_DIR} directory, got {source}")

    cases = sorted(source.glob("*.txt"))
    if len(cases) < MIN_CASES:
        raise SystemExit(f"Expected at least {MIN_CASES} PnP cases, found {len(cases)}")
    empty = [path for path in cases if path.stat().st_size == 0]
    if empty:
        raise SystemExit("Empty PnP cases:\n" + "\n".join(map(str, empty)))

    output = args.output.resolve()
    if output.suffixes[-2:] != [".tar", ".zst"]:
        raise SystemExit("Output must have a .tar.zst suffix")

    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="epos-pnp-ransac-", dir=output.parent) as temp:
        temp_path = Path(temp)
        staging = temp_path / ARCHIVE_ROOT / SOURCE_DIR
        staging.mkdir(parents=True)
        for case in cases:
            shutil.copyfile(case, staging / case.name)

        tar_path = temp_path / "fixture.tar"
        compressed_path = temp_path / output.name
        subprocess.run(["tar", "-C", temp_path, "-cf", tar_path, ARCHIVE_ROOT], check=True)
        subprocess.run(
            ["zstd", "-q", "-19", "-T0", "-f", tar_path, "-o", compressed_path],
            check=True,
        )
        subprocess.run(["zstd", "-q", "-t", compressed_path], check=True)
        compressed_path.replace(output)

    print(f"cases: {len(cases)}")
    print(f"archive: {output}")
    print(f"size_bytes: {output.stat().st_size}")
    print(f"sha256: {sha256(output)}")


if __name__ == "__main__":
    main()
