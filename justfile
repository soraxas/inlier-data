help:
  just --list

update:
  uv run scripts/update_registry.py

publish-release artifact tag:
  uv run scripts/publish_release_asset.py "{{artifact}}" --tag "{{tag}}"

package-phototourism source="RANSAC-Tutorial-Data-ValOnly" output="phototourism-ransac-val-v1.tar.zst":
  uv run scripts/package_phototourism_ransac.py "{{source}}" --output "{{output}}"

package-phototourism-webp source="RANSAC-Tutorial-Data-ValOnly" output="phototourism-val-images-webp-q85-v1.tar.zst":
  uv run scripts/package_phototourism_webp_images.py "{{source}}" --output "{{output}}"

package-homography source="homography.tar.gz" output="homography-ransac-val-v1.tar.zst":
  uv run scripts/package_homography_ransac.py "{{source}}" --output "{{output}}"

package-epos-pnp source="RANSAC-Tutorial-Data-PnP" output="epos-pnp-ransac-val-v1.tar.zst":
  uv run scripts/package_epos_pnp_ransac.py "{{source}}" --output "{{output}}"

check:
  prek run --all-files

check-releases:
  uv run --no-project python scripts/check_release_assets.py

# Offline preparation from a local SOG file or complete hierarchy directory.
[positional-arguments]
gaussian *args:
  uv run python -m inlier_data.gaussian "$@"

test-gaussian:
  uv run python -m unittest discover -s tests -p 'test_gaussian.py' -v

package-gaussian dataset:
  uv run python scripts/package_gaussian_splats.py "{{dataset}}"
