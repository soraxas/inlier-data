help:
  just --list

update:
  uv run scripts/update_registry.py

# Build <name>.tar.zst; see PACKAGES in scripts/package_release.py.
package name source="":
  uv run python scripts/package_release.py "{{name}}" {{ if source == "" { "" } else { quote(source) } }}

publish-release artifact tag:
  uv run scripts/publish_release_asset.py "{{artifact}}" --tag "{{tag}}"

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
