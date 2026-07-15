help:
  just --list

update:
  uv run scripts/update_registry.py

publish-release artifact tag:
  uv run scripts/publish_release_asset.py "{{artifact}}" --tag "{{tag}}"

package-phototourism source="RANSAC-Tutorial-Data-ValOnly" output="phototourism-ransac-val-v1.tar.zst":
  uv run scripts/package_phototourism_ransac.py "{{source}}" --output "{{output}}"
