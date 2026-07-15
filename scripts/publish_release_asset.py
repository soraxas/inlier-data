#!/usr/bin/env python3
"""Publish a completed dataset archive as a GitHub Release asset and Pooch entry."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

MAX_RELEASE_ASSET_BYTES = 2 * 1024**3
MANIFEST_PATH = Path(__file__).parents[1] / "release_artifacts.json"


def command(*args: str) -> str:
    return subprocess.run(args, check=True, text=True, capture_output=True).stdout


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("artifact", type=Path)
    parser.add_argument("--tag", required=True, help="Immutable release tag")
    parser.add_argument("--name", help="Pooch filename; defaults to archive filename")
    parser.add_argument("--notes", default="Dataset archive managed by inlier-data.")
    args = parser.parse_args()

    artifact = args.artifact.resolve()
    if not artifact.is_file():
        raise SystemExit(f"Artifact does not exist: {artifact}")
    partial = artifact.with_name(f"{artifact.name}.aria2")
    if partial.exists():
        raise SystemExit(f"Artifact download is unfinished: {partial.name} exists")
    if artifact.stat().st_size > MAX_RELEASE_ASSET_BYTES:
        raise SystemExit(
            f"{artifact.name} exceeds the strict 2 GiB GitHub Release asset limit"
        )

    exists = subprocess.run(
        ["gh", "release", "view", args.tag], text=True, capture_output=True
    ).returncode == 0
    if not exists:
        command("gh", "release", "create", args.tag, "--title", args.tag, "--notes", args.notes)

    repository = command("gh", "repo", "view", "--json", "nameWithOwner", "--jq", ".nameWithOwner").strip()

    def release_assets() -> list[dict[str, str]]:
        release = json.loads(
            command("gh", "api", f"repos/{repository}/releases/tags/{args.tag}")
        )
        return release["assets"]

    assets = release_assets()
    asset = next((item for item in assets if item["name"] == artifact.name), None)
    local_sha256 = file_sha256(artifact)
    if asset is not None:
        remote_sha256 = asset.get("digest", "").removeprefix("sha256:")
        if remote_sha256 != local_sha256:
            raise SystemExit(
                f"Release asset {artifact.name} already exists with a different SHA256; use a new tag"
            )
    else:
        command("gh", "release", "upload", args.tag, str(artifact))
        asset = next((item for item in release_assets() if item["name"] == artifact.name), None)
        if asset is None:
            raise SystemExit(f"Release upload did not produce {artifact.name}")

    manifest = json.loads(MANIFEST_PATH.read_text())
    name = args.name or artifact.name
    manifest[name] = {
        "url": asset["browser_download_url"],
        "sha256": local_sha256,
        "release": args.tag,
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps({name: manifest[name]}, indent=2))


if __name__ == "__main__":
    main()
