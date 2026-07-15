# Inlier Data

Large benchmark archives are GitHub Release assets, never Git blobs. After a
download completes, publish and register it with Pooch:

```bash
just publish-release RANSAC-Tutorial-Data-ValOnly.tar phototourism-val-v1
```

The command rejects unfinished `.aria2` downloads and files larger than 2 GiB,
uploads to the named release, and records the release URL and SHA256 in
`release_artifacts.json`.
