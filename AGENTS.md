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

GitHub Release assets have a strict 2 GiB limit in this repository. Build a
deterministic archive below that limit, validate it, then publish it with:

```bash
just publish-release <archive.tar.zst> <immutable-release-tag>
```

The publisher rejects unfinished `.aria2` downloads, checks an existing
asset's SHA-256 before reusing it, creates the release when necessary, uploads
the asset, and records its browser download URL, hash, and release tag in
`inlier_data/release_artifacts.json`. Commit and push that registry update in
the same change; a release upload alone does not update consumers' registry.

Use a new immutable tag for changed bytes. Do not overwrite a release asset.

## PhotoTourism Fixtures

Build the image-free RANSAC fixture from extracted validation data:

```bash
just package-phototourism
just publish-release phototourism-ransac-val-v1.tar.zst phototourism-ransac-val-v1
```

It contains the two validation scenes' `matches.h5`, `match_conf.h5`, `Fgt.h5`,
`Egt.h5`, `K1_K2.h5`, `R.h5`, and `T.h5`. Keep that archive layout stable for
benchmark consumers.

Build the optional visual image archive separately:

```bash
just package-phototourism-webp
just publish-release phototourism-val-images-webp-q85-v1.tar.zst phototourism-val-images-webp-q85-v1
```

The WebP artifact contains only 3,683 quality-85 WebP images. Lossless WebP
preserves decoded RGB pixels but measured 41.67% larger than the JPEG sample;
quality-85 WebP measured 78.35% smaller. Do not use either recompressed image
set as a canonical feature-extraction input.

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
