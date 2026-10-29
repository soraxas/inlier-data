"""Check that the Pooch registries agree with testdata/ and release metadata.

Runs offline: release assets are validated by shape, not downloaded.
"""

from __future__ import annotations

import ast
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REGISTRY_FILE = ROOT / "inlier_data" / "__init__.py"
RELEASE_FILE = ROOT / "inlier_data" / "release_artifacts.json"
TESTDATA_DIR = ROOT / "testdata"
GAUSSIAN_CATALOG = ROOT / "inlier_data" / "gaussian_splats.json"
RELEASE_URL = (
    "https://github.com/soraxas/inlier-data/releases/download/{release}/{name}"
)
SHA256_RE = re.compile(r"[0-9a-f]{64}")


def _repo_registry() -> dict[str, str]:
    tree = ast.parse(REGISTRY_FILE.read_text())
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "REPO_REGISTRY"
            for target in node.targets
        ):
            return ast.literal_eval(node.value)
    raise RuntimeError(f"REPO_REGISTRY not found in {REGISTRY_FILE}")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _check_repo_registry(errors: list[str]) -> set[str]:
    registry = _repo_registry()
    files = {path.name: path for path in TESTDATA_DIR.iterdir() if path.is_file()}

    for name in sorted(files.keys() - registry.keys()):
        errors.append(f"testdata/{name} is not in REPO_REGISTRY (run `just update`)")
    for name in sorted(registry.keys() - files.keys()):
        errors.append(f"REPO_REGISTRY lists {name}, but testdata/{name} is missing")
    for name in sorted(files.keys() & registry.keys()):
        actual = _sha256(files[name])
        if actual != registry[name]:
            errors.append(
                f"testdata/{name} hash {actual} does not match REPO_REGISTRY "
                f"{registry[name]}"
            )
    return set(registry)


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    keys = [key for key, _ in pairs]
    duplicates = sorted({key for key in keys if keys.count(key) > 1})
    if duplicates:
        raise ValueError(f"duplicate keys: {', '.join(duplicates)}")
    return dict(pairs)


def _check_release_registry(errors: list[str], repo_names: set[str]) -> None:
    try:
        artifacts = json.loads(
            RELEASE_FILE.read_text(), object_pairs_hook=_reject_duplicate_keys
        )
    except ValueError as error:
        errors.append(f"{RELEASE_FILE.name}: {error}")
        return

    if not isinstance(artifacts, dict):
        errors.append(f"{RELEASE_FILE.name}: top level must be an object")
        return
    # The publisher writes this exact form; anything else is a hand edit.
    if (
        RELEASE_FILE.read_text()
        != json.dumps(artifacts, indent=2, sort_keys=True) + "\n"
    ):
        errors.append(
            f"{RELEASE_FILE.name} is not in the publisher's sorted, 2-space form"
        )

    from package_release import PACKAGES

    for name in artifacts:
        if name.removesuffix(".tar.zst") not in PACKAGES:
            errors.append(
                f"{name} has no PACKAGES entry in scripts/package_release.py, "
                "so it cannot be rebuilt"
            )
    catalog = json.loads(GAUSSIAN_CATALOG.read_text())
    for dataset_id, dataset in catalog["datasets"].items():
        artifact = dataset.get("release_artifact")
        if artifact is not None and artifact not in artifacts:
            errors.append(
                f"{GAUSSIAN_CATALOG.name}[{dataset_id!r}].release_artifact "
                f"{artifact} is not registered"
            )

    for name, artifact in artifacts.items():
        where = f"{RELEASE_FILE.name}[{name!r}]"
        if not isinstance(artifact, dict) or set(artifact) != {
            "release",
            "sha256",
            "url",
        }:
            errors.append(f"{where} must have exactly release, sha256 and url")
            continue
        if not SHA256_RE.fullmatch(str(artifact["sha256"])):
            errors.append(f"{where}.sha256 is not a lowercase SHA-256 hex digest")
        expected_url = RELEASE_URL.format(release=artifact["release"], name=name)
        if artifact["url"] != expected_url:
            errors.append(
                f"{where}.url is {artifact['url']!r}, expected {expected_url!r}"
            )
        if name in repo_names:
            errors.append(f"{where} is also in REPO_REGISTRY")


def main() -> int:
    errors: list[str] = []
    repo_names = _check_repo_registry(errors)
    _check_release_registry(errors, repo_names)
    for error in errors:
        print(error, file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
