#!/usr/bin/env python3
"""Mirror a pinned Gaussian splat fixture into a deterministic release archive.

Fetches the catalog's exact upstream bytes (or reads them from --source), checks
hashes and SOG structure, then writes <archive-root>/ containing the fixture
files at their catalog paths plus LICENSE.md linking to the upstream source and
license. The extracted root is a valid `inlier_data.gaussian prepare --source`.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from inlier_data import gaussian  # noqa: E402


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _add(archive: tarfile.TarFile, name: str, data: bytes) -> None:
    # Fixed metadata so identical inputs always produce identical archives.
    info = tarfile.TarInfo(name)
    info.size = len(data)
    info.mode = 0o644
    info.mtime = 0
    info.uid = info.gid = 0
    info.uname = info.gname = ""
    archive.addfile(info, io.BytesIO(data))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset_id")
    parser.add_argument(
        "--source", type=Path, help="Local copy of the files (default: download)"
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    if shutil.which("zstd") is None:
        raise SystemExit("Packaging requires zstd on PATH")

    catalog = json.loads(gaussian.CATALOG.read_text())
    dataset = catalog["datasets"].get(args.dataset_id)
    if dataset is None:
        raise SystemExit(f"Unknown Gaussian dataset: {args.dataset_id}")
    archive_root = f"gaussian-{args.dataset_id}"
    output = (args.output or Path(f"{archive_root}.tar.zst")).resolve()
    if output.suffixes[-2:] != [".tar", ".zst"]:
        raise SystemExit("Output must have a .tar.zst suffix")

    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=f"{archive_root}-", dir=output.parent
    ) as temp:
        temp_path = Path(temp)
        staging = temp_path / archive_root
        for entry in dataset["files"]:
            target = gaussian._inside(staging, entry["path"])
            target.parent.mkdir(parents=True, exist_ok=True)
            if args.source is not None:
                shutil.copyfile(gaussian._inside(args.source, entry["path"]), target)
            else:
                with urllib.request.urlopen(entry["url"]) as response:
                    target.write_bytes(response.read())
        # Same integrity and structure checks the consumer runs on prepare.
        gaussian._bytes(staging, dataset)
        gaussian._structure(staging, dataset)

        source = dataset["source"]
        license_lines = [
            f"# {dataset['title']}",
            "",
            "Unmodified mirror of the upstream files, kept so fixtures survive",
            "upstream moves. Use is governed by the upstream license, not this",
            "repository.",
            "",
            f"- Source: {source['repository']}/tree/{source['revision']}/{source['path']}",
            f"- Author: {dataset['license'].get('author') or 'unknown'}",
            "- License:",
            *(
                f"  - {item['declaration']}: {item['url']}"
                for item in dataset["license"]["evidence"]
            ),
            "",
        ]
        tar_path = temp_path / "fixture.tar"
        with tarfile.open(tar_path, "w", format=tarfile.PAX_FORMAT) as archive:
            _add(
                archive,
                f"{archive_root}/LICENSE.md",
                "\n".join(license_lines).encode(),
            )
            for entry in sorted(dataset["files"], key=lambda row: row["path"]):
                path = gaussian._inside(staging, entry["path"])
                _add(archive, f"{archive_root}/{entry['path']}", path.read_bytes())

        compressed_path = temp_path / output.name
        subprocess.run(
            ["zstd", "-q", "-19", "-f", tar_path, "-o", compressed_path], check=True
        )
        subprocess.run(["zstd", "-q", "-t", compressed_path], check=True)
        compressed_path.replace(output)

    print(f"files: {len(dataset['files'])}")
    print(f"archive: {output}")
    print(f"size_bytes: {output.stat().st_size}")
    print(f"sha256: {sha256(output)}")


if __name__ == "__main__":
    main()
