#!/usr/bin/env python3
"""Build the image-free homography fixture used by RANSAC benchmarks."""

from __future__ import annotations

import argparse
import hashlib
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path

DATASETS = ("HPatchesSeq", "EVD")
FILES = ("matches.h5", "match_conf.h5", "Hgt.h5")
SOURCE_ROOT = "homography"
ARCHIVE_ROOT = "homography-ransac-val"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def expected_members() -> tuple[str, ...]:
    return tuple(
        f"{SOURCE_ROOT}/{dataset}/val/{filename}"
        for dataset in DATASETS
        for filename in FILES
    )


def extract_required_files(source: Path, destination: Path) -> None:
    members = expected_members()
    with tarfile.open(source, "r:gz") as archive:
        available = {member.name for member in archive.getmembers()}
        missing = sorted(set(members) - available)
        if missing:
            raise SystemExit("Missing required inputs:\n" + "\n".join(missing))

        for member_name in members:
            extracted = archive.extractfile(member_name)
            if extracted is None:
                raise SystemExit(f"Could not extract {member_name}")
            target = destination / Path(member_name).relative_to(SOURCE_ROOT)
            target.parent.mkdir(parents=True, exist_ok=True)
            with extracted, target.open("wb") as file:
                shutil.copyfileobj(extracted, file)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="RANSAC tutorial homography.tar.gz archive")
    parser.add_argument(
        "--output", type=Path, default=Path("homography-ransac-val-v1.tar.zst")
    )
    args = parser.parse_args()

    if shutil.which("tar") is None or shutil.which("zstd") is None:
        raise SystemExit("Packaging requires both tar and zstd on PATH")

    source = args.source.resolve()
    if not source.is_file():
        raise SystemExit(f"Source archive does not exist: {source}")
    output = args.output.resolve()
    if output.suffixes[-2:] != [".tar", ".zst"]:
        raise SystemExit("Output must have a .tar.zst suffix")

    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="homography-ransac-", dir=output.parent) as temp:
        temp_path = Path(temp)
        staging = temp_path / ARCHIVE_ROOT
        extract_required_files(source, staging)

        tar_path = temp_path / "fixture.tar"
        compressed_path = temp_path / output.name
        subprocess.run(["tar", "-C", temp, "-cf", tar_path, ARCHIVE_ROOT], check=True)
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
