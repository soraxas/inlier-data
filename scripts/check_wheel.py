"""Build a clean sdist and wheel, then check the installed package imports."""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REQUIRED_FILES = {"inlier_data/__init__.py", "inlier_data/release_artifacts.json"}
IMPORT_CHECK = (
    "import inlier_data; "
    "assert inlier_data.RELEASE_ARTIFACTS, 'release_artifacts.json is empty'; "
    "assert set(inlier_data.URLS) <= set(inlier_data.REGISTRY)"
)


def main() -> int:
    # Stale setuptools output can mask package-data that a clean build omits.
    shutil.rmtree(ROOT / "build", ignore_errors=True)
    for egg_info in ROOT.glob("*.egg-info"):
        shutil.rmtree(egg_info)

    with tempfile.TemporaryDirectory(prefix="inlier-data-wheel-") as out_dir:
        # Plain `uv build` builds the wheel from the sdist, which is stricter.
        subprocess.run(
            ["uv", "build", "--quiet", "--out-dir", out_dir], cwd=ROOT, check=True
        )
        wheels = list(Path(out_dir).glob("*.whl"))
        if len(wheels) != 1:
            print(f"expected one wheel, found {wheels}", file=sys.stderr)
            return 1

        with zipfile.ZipFile(wheels[0]) as wheel:
            missing = REQUIRED_FILES - set(wheel.namelist())
        if missing:
            print(f"{wheels[0].name} is missing {sorted(missing)}", file=sys.stderr)
            return 1

        subprocess.run(
            [
                "uv",
                "run",
                "--quiet",
                "--isolated",
                "--no-project",
                "--with",
                str(wheels[0]),
                "python",
                "-c",
                IMPORT_CHECK,
            ],
            cwd=out_dir,
            check=True,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
