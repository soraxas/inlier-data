# Inlier Data

Large benchmark archives are GitHub Release assets, never Git blobs. After a
download completes, publish and register it with Pooch:

```bash
just publish-release RANSAC-Tutorial-Data-ValOnly.tar phototourism-val-v1
```

The command rejects unfinished `.aria2` downloads and files larger than 2 GiB,
uploads to the named release, and records the release URL and SHA256 in
`inlier_data/release_artifacts.json`.

## PhotoTourism RANSAC fixture

The RANSAC benchmark consumes cached correspondences and ground truth, not the
source images. Build its image-free fixture from the extracted validation data:

```bash
just package-phototourism
just publish-release phototourism-ransac-val-v1.tar.zst phototourism-ransac-val-v1
```

The archive contains `matches.h5`, `match_conf.h5`, fundamental/essential
ground truth, calibration, and relative pose for both validation scenes. It
intentionally excludes JPEGs: image recompression or feature re-extraction
would make benchmark results incomparable.

## PhotoTourism WebP images

For visual inspection only, build and publish a separate lossy WebP archive:

```bash
just package-phototourism-webp
just publish-release phototourism-val-images-webp-q85-v1.tar.zst phototourism-val-images-webp-q85-v1
```

This is deliberately not a benchmark input. Lossless WebP preserves JPEG
decoded pixels but measured 41.67% larger than the original JPEG sample;
quality-85 WebP measured 78.35% smaller.

## Homography RANSAC fixture

Build the image-free HPatchesSeq and EVD validation fixture directly from the
RANSAC tutorial archive:

```bash
just package-homography /path/to/homography.tar.gz
just publish-release homography-ransac-val-v1.tar.zst homography-ransac-val-v1
```

## EPOS PnP validation fixture

The EPOS 2D--3D correspondence files from the RANSAC Tutorial PnP archive are
small enough to ship in full and do not require images. Build and publish the
canonical archive from the extracted source tree:

```bash
just package-epos-pnp /path/to/extracted/RANSAC-Tutorial-Data-PnP
just publish-release epos-pnp-ransac-val-v1.tar.zst epos-pnp-ransac-val-v1
```

The archive contains the complete `epos_corr_lmo` set; benchmark code selects a
deterministic, stratified subset for each CI scope.

It contains only cached correspondence, confidence, and ground-truth
homography HDF5 files. The PPM images and test split are intentionally
excluded because estimating an `inlier` model needs no image decoding or
feature extraction.
