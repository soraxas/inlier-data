# Inlier Data

Benchmark and test fixtures for `inlier` and `inlier-benchmarks`, served
through [Pooch](https://www.fatiando.org/pooch/). Small files live in
`testdata/`; large archives are GitHub Release assets, never Git blobs.

**[Release dashboard](https://cs.tinyiu.com/inlier-data/)** shows every
registered artifact, its latest release, size, downloads and digest status.

## Using the data

```python
from inlier_data import TEST_DATA

path = TEST_DATA.fetch("homography-ransac-val-v1.tar.zst")
```

`inlier_data.REGISTRY` and `inlier_data.URLS` are the complete Pooch inputs.
Set `INLIER_DATA_DIR` to override the cache location.

| Artifact | Contents |
| --- | --- |
| `phototourism-ransac-val-v1` | Cached correspondences and F/E/K/R/T ground truth for two validation scenes; no images |
| `phototourism-val-images-webp-q85-v1` | Quality-85 WebP images for visual inspection only, not a benchmark input |
| `homography-ransac-val-v1` | HPatchesSeq and EVD validation `matches.h5`, `match_conf.h5`, `Hgt.h5`; no images |
| `epos-pnp-ransac-val-v1` | The complete EPOS `epos_corr_lmo` 2D–3D correspondence set |
| `gaussian-apartment-v1`, `gaussian-junkshop-sh3-v1`, `gaussian-playbot-lod-v1` | Unmodified mirrors of upstream Gaussian splat scenes |

The benchmark fixtures exclude source images on purpose: recompression or
feature re-extraction would make results incomparable.

### Gaussian splat fixtures

Each Gaussian archive carries a `LICENSE.md` linking the upstream source and
license declarations, and the release notes repeat them. Their license evidence
is unresolved (see [the dataset catalog](datasets/README.md)); check it before
use or redistribution. Prepare a verified local fixture from an extracted
archive or upstream files:

```bash
just gaussian prepare playbot-lod-v1 --source /path/to/gaussian-playbot-lod-v1
```

See [fixture preparation](datasets/README.md#prepare-the-local-fixtures).

## Adding or updating data

Small deterministic files: add them to `testdata/` and run `just update` to
record their hashes in `REPO_REGISTRY`.

Large archives: add an entry to `PACKAGES` in `scripts/package_release.py`,
then build, publish and commit the registry update:

```bash
just package <name> [source]
just publish-release <name>.tar.zst <name>
```

The packager writes a reproducible `<name>.tar.zst`. The publisher rejects
unfinished `.aria2` downloads and files over 2 GiB, refuses to replace an
existing asset with different bytes, and records the URL, tag and SHA-256 in
`inlier_data/release_artifacts.json`. Use a new tag (`-v2`) for changed bytes.

## Checks

```bash
prek install       # once per clone; hooks then run on every commit
just check         # all hooks on the whole tree
just check-releases  # compare the registry with live GitHub Releases
just dashboard     # build site/index.html locally
```

Hooks lint and format with ruff, block dataset archives from Git, verify
`REPO_REGISTRY` against `testdata/` hashes, validate the release registry,
check `uv.lock`, run the Gaussian fixture tests, and build and import a clean
wheel. CI runs the same hooks plus the live release check on every push, pull
request and daily, and publishes the dashboard to GitHub Pages.
