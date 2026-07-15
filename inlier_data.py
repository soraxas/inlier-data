import json
from pathlib import Path

import pooch

repo_name = "inlier-data"

version = "0.0.1+0.dev"

RELEASE_ARTIFACTS = json.loads(
    Path(__file__).with_name("release_artifacts.json").read_text()
)

STATIC_REGISTRY = {
    "homography_sacre_coeur_a.jpg": "8eaa0be84ce6a9e126f06811726683e17a7a9c9fe880c99fc2006fbb40bd65b9",
    "homography_sacre_coeur_b.jpg": "4f52d9dcdb3ba9d8cf025025fb1be3f8f8d1ba0e0d84ab7eeb271215589ca608",
    "pose6dscene.K": "e6102143e171fe20349b50aa4c39ea0f7bb3f7517b6c950c6528a1ee9df5a880",
    "pose6dscene_gt.txt": "6e0fcc4c1f6f285a94ef525377ca3cb7b5f5add46a909c075a1a7250ba0447de",
    "pose6dscene_points.txt": "db55eb905928a857608b8f3fd643da0098689824cb448805bb087ef7735314eb",
    "rigid_pose_example_gt.txt": "3bf6f0aee7bc5027ef1168bf1089b2db80ec5c73c4a609ad86662b45836a5f6a",
    "rigid_pose_example_points.txt": "5e3939b84ab2c2cafbdc08aa6ae7bdcfeb5d0f0f28b0b6ec5a9e473bd2d8ac0a",
}

TEST_DATA = pooch.create(
    path=pooch.os_cache(repo_name),
    base_url="https://github.com/soraxas/inlier-data/raw/{version}/testdata/",
    # Pooches are versioned so that you can use multiple versions of a
    # package simultaneously. Use PEP440 compliant version number. The
    # version will be appended to the path.
    version=version,
    # If a version as a "+XX.XXXXX" suffix, we'll assume that this is a dev
    # version and replace the version with this string.
    version_dev="main",
    # An environment variable that overwrites the path.
    env="INLIER_DATA_DIR",
    # The cache file registry. A dictionary with all files managed by this
    # pooch. Keys are the file names (relative to *base_url*) and values
    # are their respective SHA256 hashes. Files will be downloaded
    # automatically when needed (see fetch_gravity_data).
    registry={**STATIC_REGISTRY, **{name: artifact["sha256"] for name, artifact in RELEASE_ARTIFACTS.items()}},
    urls={name: artifact["url"] for name, artifact in RELEASE_ARTIFACTS.items()},
)
