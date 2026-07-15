from __future__ import annotations

import ast
import re
import subprocess
from pathlib import Path
from typing import Dict


ROOT = Path(__file__).resolve().parent.parent
REGISTRY_FILE = ROOT / "inlier_data.py"
TESTDATA_DIR = ROOT / "testdata"


def _load_registry(source: str) -> Dict[str, str]:
    tree = ast.parse(source)
    registry_node = next(
        (
            node.value
            for node in tree.body
            if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == "REPO_REGISTRY" for target in node.targets)
        ),
        None,
    )

    if registry_node is None:
        raise RuntimeError("Could not find REPO_REGISTRY in inlier_data.py")

    return ast.literal_eval(registry_node)


def _render_registry_block(registry: Dict[str, str], indent: str) -> str:
    entry_indent = indent + "    "
    lines = [
        f'{entry_indent}"{name}": "{sha}",' for name, sha in sorted(registry.items())
    ]
    return "\n".join([f"{indent}REPO_REGISTRY = {{"] + lines + [f"{indent}}}"])


def _replace_registry_block(source: str, registry: Dict[str, str]) -> str:
    pattern = re.compile(r"(?ms)^(?P<indent>\s*)REPO_REGISTRY\s*=\s*\{.*?^\s*\}")
    match = pattern.search(source)
    if not match:
        raise RuntimeError("Could not locate registry block for replacement")

    indent = match.group("indent")
    replacement = _render_registry_block(registry, indent)
    return pattern.sub(replacement, source, count=1)


def _sha256sum(path: Path) -> str:
    output = subprocess.check_output(["sha256sum", str(path)], text=True)
    return output.strip().split()[0]


def main() -> None:
    source = REGISTRY_FILE.read_text()
    registry = _load_registry(source)

    added = {}
    for path in TESTDATA_DIR.iterdir():
        if not path.is_file():
            continue
        name = path.name
        if name in registry:
            continue
        added[name] = _sha256sum(path)
        registry[name] = added[name]

    if not added:
        print("No new testdata files to add.")
        return

    updated_source = _replace_registry_block(source, registry)
    REGISTRY_FILE.write_text(updated_source)

    for name, sha in added.items():
        print(f"Added {name}: {sha}")


if __name__ == "__main__":
    main()
