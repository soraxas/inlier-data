# Dataset provenance and licenses

Dataset permissions are independent of this package's software license and the
licenses of renderers used to load them. Keep the authoritative dataset-specific
source, attribution, permission evidence and modification record here. Include
applicable attribution and license text in any subsequently published archive.

## Gaussian splat candidates

[gaussian_splats.json](../inlier_data/gaussian_splats.json) records pinned upstream
revisions, original-byte SHA-256 hashes, sizes and license evidence for three
candidate fixtures. It includes all 57 referenced files in the Playbot hierarchy,
not only its root manifest. It contains metadata only, with no model binaries.

| Candidate | Attribution | Evidence status | Release mirror |
| --- | --- | --- | --- |
| Apartment | Stephane Agullo | Conflicting/insufficient version-specific evidence | `gaussian-apartment-v1` |
| JunkShop SH3 | Original creator not yet established | Asset-specific permission unverified | `gaussian-junkshop-sh3-v1` |
| Playbot LOD | Stephane Agullo | Conflicting declarations | `gaussian-playbot-lod-v1` |

The pinned PlayCanvas examples credit Apartment and Playbot as CC BY 4.0, but
the linked author scene pages currently declare CC BY-NC 4.0. Apartment's linked
page also has a different current title/count. A development-site upload lists
Apartment as CC BY 4.0 but does not establish the original author's grant for
our exact version. Record both claims rather than guessing which applies.
This inventory does not determine whether an earlier valid grant exists or
has changed; establish the exact-version permission before promotion.

For JunkShop, the example file and renderer software license are identifiable,
but the reviewed sources do not establish the original scene creator or a
separate asset grant. A name matching a Blender sample is not sufficient
provenance for a reconstructed or transformed SOG file.

Evidence URLs, observation date and remaining questions are in each catalog
entry. Primary permission references:

- [Pinned Apartment example credit](https://github.com/playcanvas/engine/blob/46233e5bcd2ab17395f242341bc3be480188ec23/examples/src/examples/gaussian-splatting/editor.example.mjs),
  [linked author scene](https://superspl.at/scene/cdcec084).
- [Pinned Playbot example credit](https://github.com/playcanvas/engine/blob/46233e5bcd2ab17395f242341bc3be480188ec23/examples/src/examples/gaussian-splatting/lod-instances.example.mjs),
  [linked author scene](https://superspl.at/scene/ee6d8bc4).
- [Pinned JunkShop viewer reference](https://github.com/WilliamLiu-1997/Gaussian-Splat-Lite/blob/3cd506ae21cfaf842501a80b1c443af2799333b0/examples/viewer/viewer.js).

## Promotion to benchmark inputs

Each fixture's exact upstream bytes are mirrored as a GitHub Release asset so it
survives upstream moves. The archive extracts to a valid `--source` root and
carries a `LICENSE.md` linking the upstream source and license declarations; the
release notes repeat those links. Rebuild one with
`just package gaussian-<dataset-id>`; the bytes are reproducible. Mirroring does
not resolve the license evidence above.

1. Resolve the dataset's applicable license and exact-version attribution. Store
   its license identifier, full text or authoritative link, evidence, and any
   required notices. Permission to redistribute and suitability for the intended
   use must be established; recording a URL or hash alone does not establish it.
2. Preserve source bytes. For hierarchy archives preserve every relative path;
   retain the per-file manifest and validate referenced ranges. Include notices
   and record repackaging without implying geometry or textures were changed.
3. Build a deterministic archive where needed. Use an immutable version/tag,
   verify its SHA-256 and follow the existing release publisher. Do not invent
   download URLs for releases that have not been published.
4. Register the published artifact in `inlier_data/release_artifacts.json` through
   the publisher. That existing registry feeds Pooch. Candidate entries here are
   deliberately not imported into `REGISTRY`, `URLS`, or `TEST_DATA`.
5. Fetch and verify before a timed run; serve verified scene bytes to the viewer.
   Keep fixture download/unpacking outside render/load measurements. Pin cameras,
   render settings and dataset version in the benchmark consumer.

Consumer repositories should reference this catalog's revision and dataset ID,
not duplicate license decisions or copy models into Git. The catalog and offline
preparation module are installed package data; original model files are not.

## Prepare the local fixtures

From this repository, seed the cache with existing files or a complete hierarchy:

```sh
just gaussian prepare apartment-v1 --source /path/to/apartment.sog
just gaussian prepare junkshop-sh3-v1 --source /path/to/JunkShop-SH3.sog
just gaussian prepare playbot-lod-v1 --source /path/to/playbot
just gaussian verify playbot-lod-v1
just test
```

Without Just, use `uv run python -m inlier_data.gaussian` with the same arguments.
`--cache-root /path/to/cache` or `INLIER_DATA_DIR` overrides the OS cache base.
Each fixture lives under `gaussian/<catalog-version>/<dataset-id>/<input-hash>/`.
Changing any inventoried bytes creates a different identity and directory.
Repeated prepare/verify calls recheck every file and reuse a complete valid
cache without requiring the original source. Corrupt caches fail explicitly;
use a fresh cache base or remove the affected fixture directory before reseeding.

The command emits one JSON report on success and a nonzero exit on failure.
`fixture.json` is published only after complete validation and an atomic cache
directory rename. It records `entrypoint`, `root`, all file hashes, the catalog
hash, complete asset-set identity and unresolved license evidence. Bundle checks
cover ZIP CRC, metadata and referenced textures; hierarchy checks cover every
inventoried resource and leaf-range bounds. These are structural checks, not
production decoding, rendered correctness or measured performance.

Pass `entrypoint` to a native SOG runner or file-picker browser replay. For LOD,
serve `root` on localhost and load `entrypoint_relative` as the hierarchy URL;
use `asset_identity` as the whole-hierarchy identity. Preparing files belongs
outside the timed window. Keep captures and traces outside this repository.
