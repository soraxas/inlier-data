# Dataset provenance and licenses

Dataset permissions are independent of this package's software license and the
licenses of renderers used to load them. Keep the authoritative dataset-specific
source, attribution, permission evidence and modification record here. Include
applicable attribution and license text in any subsequently published archive.

## Gaussian splat candidates

[gaussian-splats-v1.json](gaussian-splats-v1.json) records pinned upstream
revisions, original-byte SHA-256 hashes, sizes and license evidence for three
candidate fixtures. It includes all 57 referenced files in the Playbot hierarchy,
not only its root manifest. It contains metadata only, with no model binaries.

| Candidate | Attribution | Evidence status | Automatic fetch / release |
| --- | --- | --- | --- |
| Apartment | Stephane Agullo | Conflicting/insufficient version-specific evidence | Disabled |
| JunkShop SH3 | Original creator not yet established | Asset-specific permission unverified | Disabled |
| Playbot LOD | Stephane Agullo | Conflicting declarations | Disabled |

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
not duplicate license decisions or copy models into Git. The catalog is currently
repository documentation and is not distributed as installed package data.
