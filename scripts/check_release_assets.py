"""Check release_artifacts.json against the live GitHub Releases.

Every registered artifact must exist at its release with the recorded URL and
SHA-256, and every release asset must be registered. Set GITHUB_TOKEN to avoid
anonymous API rate limits.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request
from pathlib import Path

REPOSITORY = "soraxas/inlier-data"
MANIFEST_PATH = Path(__file__).parents[1] / "inlier_data" / "release_artifacts.json"


def _get(url: str) -> list[dict]:
    request = urllib.request.Request(
        url, headers={"Accept": "application/vnd.github+json"}
    )
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(request) as response:
        return json.load(response)


def _release_assets() -> dict[str, tuple[str, dict]]:
    assets = {}
    page = 1
    while True:
        releases = _get(
            f"https://api.github.com/repos/{REPOSITORY}/releases"
            f"?per_page=100&page={page}"
        )
        if not releases:
            return assets
        for release in releases:
            for asset in release["assets"]:
                assets[asset["browser_download_url"]] = (release["tag_name"], asset)
        page += 1


def main() -> int:
    manifest = json.loads(MANIFEST_PATH.read_text())
    assets = _release_assets()
    errors = []

    for name, artifact in sorted(manifest.items()):
        found = assets.pop(artifact["url"], None)
        if found is None:
            errors.append(f"{name}: no release asset at {artifact['url']}")
            continue
        tag, asset = found
        if tag != artifact["release"]:
            errors.append(
                f"{name}: asset is in release {tag}, not {artifact['release']}"
            )
        digest = asset.get("digest") or ""
        if digest != f"sha256:{artifact['sha256']}":
            errors.append(
                f"{name}: release digest {digest or '(none)'} does not match "
                f"sha256:{artifact['sha256']}"
            )

    for url, (tag, _) in sorted(assets.items()):
        errors.append(
            f"release {tag} asset {url} is not in {MANIFEST_PATH.name} "
            "(register it with `just publish-release`)"
        )

    for error in errors:
        print(error, file=sys.stderr)
    if not errors:
        print(f"{len(manifest)} release artifacts match GitHub Releases")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
