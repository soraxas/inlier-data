#!/usr/bin/env python3
"""Build a release archive for one dataset in PACKAGES.

Every package becomes a reproducible <name>.tar.zst whose single top-level
directory holds the selected files. A package selects files either from a
local source (a directory or a .tar.gz) or, for mirrors of upstream files,
from a URL + SHA-256 inventory that is downloaded and verified.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import shutil
import subprocess
import tarfile
import tempfile
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "inlier_data" / "release_artifacts.json"
GAUSSIAN_CATALOG = ROOT / "inlier_data" / "gaussian_splats.json"
PHOTOTOURISM_SCENES = ("sacre_coeur", "st_peters_square")

# Keys (all optional except root):
#   root        top-level directory inside the archive
#   source      default local source (directory or .tar.gz)
#   within      descend into this subdirectory of the source when it exists
#   files       exact paths that must all exist, relative to the source
#   glob        pattern relative to the source; with min_files and nonempty
#   webp        convert matched JPEGs to WebP at this quality
#   mirror      list of {path, bytes, sha256, url} to download and verify
#   license     markdown written as LICENSE.md at the archive root
PACKAGES: dict[str, dict] = {
    "phototourism-ransac-val-v1": {
        "root": "phototourism-ransac-val",
        "source": "RANSAC-Tutorial-Data-ValOnly",
        "within": "val",
        "files": [
            f"{scene}/{name}"
            for scene in PHOTOTOURISM_SCENES
            for name in (
                "matches.h5",
                "match_conf.h5",
                "Fgt.h5",
                "Egt.h5",
                "K1_K2.h5",
                "R.h5",
                "T.h5",
            )
        ],
    },
    "phototourism-val-images-webp-q85-v1": {
        "root": "phototourism-val-images-webp-q85",
        "source": "RANSAC-Tutorial-Data-ValOnly",
        "within": "val",
        "glob": "*/images/*.jpg",
        "min_files": 1,
        "webp": 85,
    },
    "homography-ransac-val-v1": {
        "root": "homography-ransac-val",
        "source": "homography.tar.gz",
        "within": "homography",
        "files": [
            f"{dataset}/val/{name}"
            for dataset in ("HPatchesSeq", "EVD")
            for name in ("matches.h5", "match_conf.h5", "Hgt.h5")
        ],
    },
    "epos-pnp-ransac-val-v1": {
        "root": "epos-pnp-ransac-val",
        "source": "RANSAC-Tutorial-Data-PnP",
        "glob": "epos_corr_lmo/*.txt",
        "min_files": 600,
        "nonempty": True,
    },
}


def _gaussian_packages() -> dict[str, dict]:
    catalog = json.loads(GAUSSIAN_CATALOG.read_text())
    packages = {}
    for dataset_id, dataset in catalog["datasets"].items():
        source, license = dataset["source"], dataset["license"]
        lines = [
            f"# {dataset['title']}",
            "",
            "Unmodified mirror of the upstream files, kept so fixtures survive",
            "upstream moves. Use is governed by the upstream license, not this",
            "repository.",
            "",
            f"- Source: {source['repository']}/tree/{source['revision']}/{source['path']}",
            f"- Author: {license.get('author') or 'unknown'}",
            "- License:",
            *(
                f"  - {item['declaration']}: {item['url']}"
                for item in license["evidence"]
            ),
            "",
        ]
        packages[f"gaussian-{dataset_id}"] = {
            "root": f"gaussian-{dataset_id}",
            "mirror": dataset["files"],
            "license": "\n".join(lines),
        }
    return packages


PACKAGES.update(_gaussian_packages())


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe(name: str) -> str:
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or not name:
        raise SystemExit(f"Unsafe archive path: {name!r}")
    return path.as_posix()


def _select(spec: dict, source: Path) -> dict[str, Path]:
    """Return {archive path: file} from the first candidate root that matches."""
    candidates = [source / spec["within"]] if "within" in spec else []
    candidates += [source, source.parent]
    for base in candidates:
        if not base.is_dir():
            continue
        if "files" in spec:
            selected = {name: base / name for name in spec["files"]}
            if all(path.is_file() for path in selected.values()):
                return selected
        else:
            matches = sorted(path for path in base.glob(spec["glob"]) if path.is_file())
            if len(matches) >= spec.get("min_files", 1):
                return {path.relative_to(base).as_posix(): path for path in matches}
    wanted = (
        spec.get("files") or f"{spec['glob']} (at least {spec.get('min_files', 1)})"
    )
    raise SystemExit(f"No candidate under {source} contains {wanted}")


def _mirror(spec: dict, source: Path | None, staging: Path) -> dict[str, Path]:
    selected = {}
    for entry in spec["mirror"]:
        name = _safe(entry["path"])
        target = staging / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if source is not None:
            shutil.copyfile(source / name, target)
        else:
            with urllib.request.urlopen(entry["url"]) as response, target.open(
                "wb"
            ) as file:
                shutil.copyfileobj(response, file)
        if target.stat().st_size != entry["bytes"] or sha256(target) != entry["sha256"]:
            raise SystemExit(f"{name} does not match its pinned size and SHA-256")
        selected[name] = target
    return selected


def _webp(selected: dict[str, Path], quality: int, staging: Path) -> dict[str, Path]:
    if shutil.which("cwebp") is None:
        raise SystemExit("WebP packaging requires cwebp on PATH")
    converted = {
        str(PurePosixPath(name).with_suffix(".webp")): (path, staging / name)
        for name, path in selected.items()
    }

    def convert(job: tuple[Path, Path]) -> None:
        source, target = job
        target = target.with_suffix(".webp")
        target.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["cwebp", "-quiet", "-q", str(quality), source, "-o", target], check=True
        )

    with ThreadPoolExecutor(max_workers=min(os.cpu_count() or 1, 8)) as executor:
        list(executor.map(convert, converted.values()))
    return {
        name: target.with_suffix(".webp") for name, (_, target) in converted.items()
    }


def _info(name: str, size: int) -> tarfile.TarInfo:
    # Fixed metadata so identical inputs always produce identical archives.
    info = tarfile.TarInfo(name)
    info.size = size
    info.mode = 0o644
    info.mtime = 0
    info.uid = info.gid = 0
    info.uname = info.gname = ""
    return info


def build(name: str, source: Path | None, output: Path) -> None:
    spec = PACKAGES[name]
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f"{name}-", dir=output.parent) as temp:
        temp_path = Path(temp)
        staging = temp_path / "staging"
        if "mirror" in spec:
            selected = _mirror(spec, source, staging)
        else:
            if source is None:
                source = Path(spec["source"])
            source = source.resolve()
            if source.is_file() and source.name.endswith((".tar.gz", ".tgz")):
                extracted = temp_path / "source"
                with tarfile.open(source, "r:gz") as archive:
                    archive.extractall(extracted, filter="data")
                source = extracted
            selected = _select(spec, source)
            if spec.get("nonempty"):
                empty = [
                    str(path) for path in selected.values() if not path.stat().st_size
                ]
                if empty:
                    raise SystemExit("Empty inputs:\n" + "\n".join(empty))
            if "webp" in spec:
                selected = _webp(selected, spec["webp"], staging)

        tar_path = temp_path / "archive.tar"
        with tarfile.open(tar_path, "w", format=tarfile.PAX_FORMAT) as archive:
            if "license" in spec:
                data = spec["license"].encode()
                archive.addfile(
                    _info(f"{spec['root']}/LICENSE.md", len(data)), io.BytesIO(data)
                )
            for member in sorted(selected):
                path = selected[member]
                with path.open("rb") as file:
                    archive.addfile(
                        _info(f"{spec['root']}/{_safe(member)}", path.stat().st_size),
                        file,
                    )

        compressed = temp_path / output.name
        subprocess.run(
            ["zstd", "-q", "-19", "-T0", "-f", tar_path, "-o", compressed], check=True
        )
        subprocess.run(["zstd", "-q", "-t", compressed], check=True)
        compressed.replace(output)

    print(f"files: {len(selected)}")
    print(f"archive: {output}")
    print(f"size_bytes: {output.stat().st_size}")
    print(f"sha256: {sha256(output)}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("name", choices=sorted(PACKAGES), metavar="name")
    parser.add_argument(
        "source", nargs="?", type=Path, help="Local source (default per package)"
    )
    parser.add_argument("--output", type=Path, help="Default: <name>.tar.zst")
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Rebuild into a temporary file and require the registered SHA-256",
    )
    args = parser.parse_args()
    if shutil.which("zstd") is None:
        raise SystemExit("Packaging requires zstd on PATH")
    if args.verify:
        registered = json.loads(REGISTRY.read_text()).get(f"{args.name}.tar.zst")
        if registered is None:
            raise SystemExit(f"{args.name}.tar.zst is not in {REGISTRY.name}")
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / f"{args.name}.tar.zst"
            build(args.name, args.source, output)
            actual = sha256(output)
        if actual != registered["sha256"]:
            raise SystemExit(
                f"Rebuilt {args.name} has SHA-256 {actual}, registered "
                f"{registered['sha256']}"
            )
        print(f"verified: rebuild matches registered {args.name}")
        return
    output = (args.output or Path(f"{args.name}.tar.zst")).resolve()
    if output.suffixes[-2:] != [".tar", ".zst"]:
        raise SystemExit("Output must have a .tar.zst suffix")
    build(args.name, args.source, output)


if __name__ == "__main__":
    main()
