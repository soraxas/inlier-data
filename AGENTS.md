# Inlier Data Repository

`inlier-data` owns heavyweight fixtures used by `inlier` and
`inlier-benchmarks`. Keep this repository's Git history source-only: never add
downloaded datasets, generated archives, images, point clouds, or other large
binary assets as Git blobs.

## Choosing Where Data Lives

- Keep small, deterministic files in `testdata/`. Run `just update` after
  adding them; it updates `REPO_REGISTRY` in `inlier_data/__init__.py`.
- Put large benchmark inputs in a GitHub Release asset and register them with
  Pooch. The publisher writes `inlier_data/release_artifacts.json`; do not add
  release assets manually to `REPO_REGISTRY`.
- Keep a benchmark's canonical inputs separate from visual or exploratory
  assets. For PhotoTourism, the canonical RANSAC fixture contains cached
  correspondences and ground truth HDF5 files only. The quality-85 WebP image
  archive is visual-only and must not be used to regenerate benchmark matches.

## Large Release Assets

GitHub Release assets have a strict 2 GiB limit in this repository. Every
archive is built by one packager, `scripts/package_release.py`: add the dataset
as an entry in its `PACKAGES` spec (files to select from a local directory or
`.tar.gz`, or a URL + SHA-256 inventory to mirror) rather than writing a new
script. It writes a reproducible `<name>.tar.zst` with fixed tar metadata. Keep
the package name equal to the release tag, then publish it with:

```bash
just package <name> [source]
just publish-release <name>.tar.zst <name>
```

Archives published before the unified packager (PhotoTourism, homography,
EPOS) were built with system `tar`; rebuilding them yields the same files but
different archive bytes, so a rebuild needs a new tag.

The publisher rejects unfinished `.aria2` downloads, checks an existing
asset's SHA-256 before reusing it, creates the release when necessary, uploads
the asset, and records its browser download URL, hash, and release tag in
`inlier_data/release_artifacts.json`. Commit and push that registry update in
the same change; a release upload alone does not update consumers' registry.

Use a new immutable tag for changed bytes. Do not overwrite a release asset.

## PhotoTourism Fixtures

Build the image-free RANSAC fixture from extracted validation data:

```bash
just package phototourism-ransac-val-v1
just publish-release phototourism-ransac-val-v1.tar.zst phototourism-ransac-val-v1
```

It contains the two validation scenes' `matches.h5`, `match_conf.h5`, `Fgt.h5`,
`Egt.h5`, `K1_K2.h5`, `R.h5`, and `T.h5`. Keep that archive layout stable for
benchmark consumers.

Build the optional visual image archive separately:

```bash
just package phototourism-val-images-webp-q85-v1
just publish-release phototourism-val-images-webp-q85-v1.tar.zst phototourism-val-images-webp-q85-v1
```

The WebP artifact contains only 3,683 quality-85 WebP images. Lossless WebP
preserves decoded RGB pixels but measured 41.67% larger than the JPEG sample;
quality-85 WebP measured 78.35% smaller. Do not use either recompressed image
set as a canonical feature-extraction input.

## Homography Fixtures

Build the image-free validation fixture from the RANSAC tutorial's
`homography.tar.gz` archive:

```bash
just package homography-ransac-val-v1 /path/to/homography.tar.gz
just publish-release homography-ransac-val-v1.tar.zst homography-ransac-val-v1
```

### EPOS absolute-pose correspondences

The RANSAC Tutorial PnP archive contains image-free EPOS 2D--3D correspondence
files. Package the complete `epos_corr_lmo` tree (currently 609 cases), rather
than a hand-picked subset: benchmark runners choose their deterministic sample
from this canonical archive.

```bash
just package epos-pnp-ransac-val-v1 /path/to/extracted/RANSAC-Tutorial-Data-PnP
just publish-release epos-pnp-ransac-val-v1.tar.zst epos-pnp-ransac-val-v1
```

The fixture deliberately retains only `HPatchesSeq` and `EVD` validation
`matches.h5`, `match_conf.h5`, and `Hgt.h5` files. The archive's PPM images
and test split are not required to evaluate an estimator from its precomputed
correspondences and ground-truth homographies. Keep this layout stable for
benchmark consumers:

```text
homography-ransac-val/
  HPatchesSeq/val/{matches.h5,match_conf.h5,Hgt.h5}
  EVD/val/{matches.h5,match_conf.h5,Hgt.h5}
```

## Python Distribution

`inlier_data` is a package because `release_artifacts.json` must be installed
alongside its Python code. `REGISTRY` and `URLS` are the complete Pooch inputs;
they are derived from repository data and release metadata respectively.

After changing packaging or the release registry, verify a clean wheel and an
installed import, not only an editable checkout:

```bash
rm -rf build inlier_data.egg-info /tmp/inlier-data-wheel
uv build --wheel --out-dir /tmp/inlier-data-wheel
unzip -l /tmp/inlier-data-wheel/*.whl
```

The wheel must include both `inlier_data/__init__.py` and
`inlier_data/release_artifacts.json`.
Gaussian fixture preparation additionally ships `inlier_data/gaussian.py` and
`inlier_data/gaussian_splats.json`; the installed wheel must load that catalog.
Models remain outside Git and package distributions. Candidate fixtures may be
prepared offline from explicit local inputs; that verifies integrity, not asset
permissions. Keep unresolved license evidence and disabled automatic acquisition
in the catalog. See [dataset provenance](datasets/README.md).

## Commit Checks

Hooks are managed by [prek](https://github.com/j178/prek). Run `prek install`
once per clone; `just check` runs every hook on the whole tree. On commit they
lint and format Python with ruff, reject dataset archives, verify
`REPO_REGISTRY` against `testdata/` hashes and the shape of
`release_artifacts.json`, check `uv.lock`, and, when packaging inputs change,
build a clean wheel and import it from an isolated install.

CI (`.github/workflows/ci.yml`) runs the same hooks plus
`just check-releases`, which compares `release_artifacts.json` with the live
GitHub Releases: every entry must exist with its recorded URL and SHA-256, and
every release asset must be registered. It also runs daily, because release
assets can change outside Git.

`just dashboard` writes `site/index.html`, a static overview of every
registered artifact. In the browser it loads the live registry, the Gaussian
catalog and the GitHub Releases API, and flags missing assets, digest
mismatches, newer unregistered versions and release assets missing from the
registry. `.github/workflows/dashboard.yml` publishes it to GitHub Pages.
