"""Prepare byte-pinned local Gaussian fixtures in a verified Pooch cache."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

import pooch

CATALOG = Path(__file__).with_name("gaussian_splats.json")


def _relative(name):
    if not isinstance(name, str):
        raise ValueError("Fixture path must be a string")
    path = PurePosixPath(name)
    if (
        not name
        or path.is_absolute()
        or ".." in path.parts
        or "\\" in name
        or ":" in name
        or path.as_posix() != name
        or name == "."
    ):
        raise ValueError(f"Invalid fixture path: {name!r}")
    return path


def _inside(root, name):
    path = root / _relative(name)
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError as error:
        raise ValueError(f"Fixture path escapes its root: {name}") from error
    return path


def _selection(dataset_id, cache_root, catalog_path):
    catalog_bytes = Path(catalog_path).read_bytes()
    catalog = json.loads(catalog_bytes)
    if catalog.get("schema_version") != 1:
        raise ValueError("Unsupported Gaussian catalog schema")
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", dataset_id):
        raise ValueError("Invalid dataset ID")
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", catalog["catalog_version"]):
        raise ValueError("Invalid catalog version")
    if dataset_id not in catalog["datasets"]:
        raise ValueError(f"Unknown Gaussian dataset: {dataset_id}")
    dataset = catalog["datasets"][dataset_id]
    if dataset["format"] not in {"sog-v2-bundle", "sog-v2-hierarchy"}:
        raise ValueError("Unsupported Gaussian fixture format")
    entries = dataset["files"]
    if not entries:
        raise ValueError("Empty fixture inventory")
    names = set()
    for entry in entries:
        name = entry["path"]
        _relative(name)
        if name in names or name == "fixture.json":
            raise ValueError(f"Duplicate or reserved fixture path: {name}")
        names.add(name)
        if not re.fullmatch(r"[a-f0-9]{64}", entry["sha256"]):
            raise ValueError(f"Invalid SHA256 for {name}")
        if type(entry["bytes"]) is not int or entry["bytes"] <= 0:
            raise ValueError(f"Invalid byte size for {name}")
    identity_rows = sorted(
        ({key: entry[key] for key in ("path", "bytes", "sha256")} for entry in entries),
        key=lambda row: row["path"],
    )
    digest = hashlib.sha256(
        json.dumps(identity_rows, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    base = Path(
        cache_root or os.environ.get("INLIER_DATA_DIR") or pooch.os_cache("inlier-data")
    )
    cache = pooch.create(
        path=base / "gaussian" / catalog["catalog_version"] / dataset_id / digest,
        base_url="https://invalid.example/offline-only/",
        registry={entry["path"]: "sha256:" + entry["sha256"] for entry in entries},
        urls={entry["path"]: entry["url"] for entry in entries},
        allow_updates=False,
    )
    return catalog, dataset, cache, digest, hashlib.sha256(catalog_bytes).hexdigest()


def _count(meta):
    count = meta.get("count")
    if type(count) is not int or count < 0 or meta.get("version") != 2:
        raise ValueError("Expected SOG v2 metadata with a nonnegative count")
    return count


def _textures(meta):
    result = set()
    for key in ("means", "quats", "scales", "sh0", "shN"):
        if key == "shN" and key not in meta:
            continue
        files = meta.get(key, {}).get("files")
        if not isinstance(files, list) or not files:
            raise ValueError(f"Missing referenced SOG texture files: {key}")
        result.update(str(_relative(name)) for name in files)
    return result


def _bundle(path):
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ValueError("Duplicate SOG archive members")
        for name in names:
            _relative(name)
        if archive.testzip() is not None:
            raise ValueError("SOG archive CRC mismatch")
        if "meta.json" not in names:
            raise ValueError("Missing SOG metadata")
        meta = json.loads(archive.read("meta.json"))
        missing = _textures(meta) - set(names)
        if missing:
            raise ValueError(f"Missing referenced archive textures: {sorted(missing)}")
        return _count(meta)


def _structure(root, dataset):
    inventory = {entry["path"] for entry in dataset["files"]}
    if dataset["format"] == "sog-v2-bundle":
        if len(inventory) != 1:
            raise ValueError("A bundled fixture requires exactly one SOG file")
        entry = next(iter(inventory))
        count = _bundle(_inside(root, entry))
        if dataset.get("splat_count", count) != count:
            raise ValueError("SOG count differs from catalog")
        return entry, {"referenced_files": 1, "splat_count": count}

    entry = "lod-meta.json"
    lod = json.loads(_inside(root, entry).read_text())
    refs = {entry}
    counts = []
    for name in lod["filenames"]:
        meta_path = _inside(root, name)
        refs.add(name)
        meta = json.loads(meta_path.read_text())
        counts.append(_count(meta))
        refs.update(
            str(PurePosixPath(name).parent / texture) for texture in _textures(meta)
        )
    environment = lod.get("environment")
    if environment is not None:
        refs.add(str(_relative(environment)))
        if environment.endswith(".sog"):
            _bundle(_inside(root, environment))
        else:
            meta = json.loads(_inside(root, environment).read_text())
            _count(meta)
            refs.update(
                str(PurePosixPath(environment).parent / f) for f in _textures(meta)
            )
    if refs != inventory:
        raise ValueError(
            f"Referenced files differ from catalog inventory: {sorted(refs ^ inventory)}"
        )
    for name in refs:
        if name.endswith(".webp"):
            with _inside(root, name).open("rb") as source:
                header = source.read(12)
            if header[:4] != b"RIFF" or header[8:12] != b"WEBP":
                raise ValueError(f"Invalid referenced WebP header: {name}")
    ranges = 0
    nodes = [lod["tree"]]
    while nodes:
        node = nodes.pop()
        nodes.extend(node.get("children", []))
        for level, span in node.get("lods", {}).items():
            file, offset, count = (span[key] for key in ("file", "offset", "count"))
            if (
                not all(
                    type(value) is int and value >= 0 for value in (file, offset, count)
                )
                or file >= len(counts)
                or offset + count > counts[file]
                or not 0 <= int(level) < lod["lodLevels"]
            ):
                raise ValueError(f"Invalid hierarchy leaf range: {span}")
            ranges += 1
    if not ranges:
        raise ValueError("Hierarchy has no leaf ranges")
    if "range_count" in dataset and ranges != dataset["range_count"]:
        raise ValueError("Hierarchy range count differs from catalog")
    if (
        "chunk_splat_counts_in_manifest_order" in dataset
        and counts != dataset["chunk_splat_counts_in_manifest_order"]
    ):
        raise ValueError("Hierarchy source counts differ from catalog")
    return entry, {
        "referenced_files": len(refs),
        "leaf_ranges": ranges,
        "lod_levels": lod["lodLevels"],
    }


def _bytes(root, dataset):
    for entry in dataset["files"]:
        path = _inside(root, entry["path"])
        if not path.is_file():
            raise ValueError(f"Missing inventoried file: {entry['path']}")
        if path.stat().st_size != entry["bytes"]:
            raise ValueError(f"Fixture size mismatch: {entry['path']}")
        if pooch.file_hash(str(path)) != entry["sha256"]:
            raise ValueError(f"Fixture SHA256 hash mismatch: {entry['path']}")


def _offline_download(*_args, **_kwargs):
    raise ValueError("Automatic fixture download is disabled; provide a local source")


def _report(dataset_id, root, catalog, dataset, digest, catalog_hash):
    entry, validation = _structure(root, dataset)
    return {
        "schema": "inlier-gaussian-fixture/1",
        "dataset_id": dataset_id,
        "catalog_version": catalog["catalog_version"],
        "catalog_sha256": catalog_hash,
        "asset_identity": "sha256:" + digest,
        "format": dataset["format"],
        "source": dataset["source"],
        "license": dataset["license"],
        "root": str(root.resolve()),
        "entrypoint": str((root / entry).resolve()),
        "entrypoint_relative": entry,
        "files": dataset["files"],
        "validation": {
            **validation,
            "scope": "byte hashes and container/metadata structure; not production decode or rendered quality",
        },
    }


def verify(dataset_id, *, cache_root=None, catalog_path=CATALOG):
    """Revalidate every cached input without downloading or trusting saved paths."""
    catalog, dataset, cache, digest, catalog_hash = _selection(
        dataset_id, cache_root, catalog_path
    )
    root = Path(cache.path)
    _bytes(root, dataset)
    for entry in dataset["files"]:
        cache.fetch(entry["path"], downloader=_offline_download)
    report = _report(dataset_id, root, catalog, dataset, digest, catalog_hash)
    manifest = root / "fixture.json"
    if not manifest.is_file():
        raise ValueError(
            "Missing prepared fixture manifest; prepare from a local source"
        )
    saved = json.loads(manifest.read_text())
    if (
        saved.get("asset_identity") != report["asset_identity"]
        or saved.get("dataset_id") != dataset_id
    ):
        raise ValueError("Cached fixture manifest identity mismatch")
    return report


def prepare(dataset_id, *, source=None, cache_root=None, catalog_path=CATALOG):
    """Atomically seed a Pooch cache from explicit local bytes and return provenance."""
    catalog, dataset, cache, digest, catalog_hash = _selection(
        dataset_id, cache_root, catalog_path
    )
    root = Path(cache.path)
    if root.exists():
        return verify(dataset_id, cache_root=cache_root, catalog_path=catalog_path)
    if source is None:
        raise ValueError(
            "Local source required for an uncached fixture; automatic downloads are disabled"
        )
    source = Path(source).resolve()
    if source.is_file():
        if len(dataset["files"]) != 1 or source.name != dataset["files"][0]["path"]:
            raise ValueError("Local source file must match the catalog filename")
        source = source.parent
    _bytes(source, dataset)
    _structure(source, dataset)
    root.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".prepare-", dir=root.parent) as temporary:
        staged = Path(temporary) / "fixture"
        staged.mkdir()
        for entry in dataset["files"]:
            target = _inside(staged, entry["path"])
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(_inside(source, entry["path"]), target)
        _bytes(staged, dataset)
        _structure(staged, dataset)
        report = _report(dataset_id, staged, catalog, dataset, digest, catalog_hash)
        report["root"] = str(root.resolve())
        report["entrypoint"] = str((root / report["entrypoint_relative"]).resolve())
        (staged / "fixture.json").write_text(json.dumps(report, indent=2) + "\n")
        try:
            staged.rename(root)
        except FileExistsError:
            # A concurrent preparer may have published the same verified inputs.
            return verify(dataset_id, cache_root=cache_root, catalog_path=catalog_path)
    return verify(dataset_id, cache_root=cache_root, catalog_path=catalog_path)


def main():
    """Prepare or verify fixtures and emit one machine-readable result on success."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "verify"))
    parser.add_argument("dataset_id")
    parser.add_argument(
        "--source", type=Path, help="Existing SOG file or hierarchy root (no download)"
    )
    parser.add_argument("--cache-root", type=Path)
    parser.add_argument("--catalog", type=Path, default=CATALOG)
    args = parser.parse_args()
    try:
        options = {"cache_root": args.cache_root, "catalog_path": args.catalog}
        if args.command == "prepare":
            result = prepare(args.dataset_id, source=args.source, **options)
        else:
            if args.source is not None:
                raise ValueError("verify does not accept --source")
            result = verify(args.dataset_id, **options)
    except (ValueError, OSError, KeyError, TypeError, zipfile.BadZipFile) as error:
        parser.exit(1, f"Fixture preparation failed: {error}\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
