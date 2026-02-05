import pooch

repo_name = "inlier-data"

version = "0.0.1+0.dev"

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
    registry={
        "rigid_pose_example_gt.txt": "3bf6f0aee7bc5027ef1168bf1089b2db80ec5c73c4a609ad86662b45836a5f6a",
        "rigid_pose_example_points.txt": "5e3939b84ab2c2cafbdc08aa6ae7bdcfeb5d0f0f28b0b6ec5a9e473bd2d8ac0a",
    },
)
