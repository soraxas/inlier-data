help:
  just --list

update:
  uv run scripts/update_registry.py

publish-release artifact tag:
  uv run scripts/publish_release_asset.py "{{artifact}}" --tag "{{tag}}"
