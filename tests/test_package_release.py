"""Exercise the release packager on small synthetic sources."""

import contextlib
import hashlib
import io
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import package_release  # noqa: E402


def members(archive):
    """Return {name: bytes} for every file in a .tar.zst archive."""
    data = subprocess.run(
        ["zstd", "-dc", archive], check=True, capture_output=True
    ).stdout
    with tarfile.open(fileobj=io.BytesIO(data)) as tar:
        return {
            info.name: tar.extractfile(info).read() for info in tar if info.isfile()
        }


@unittest.skipIf(shutil.which("zstd") is None, "zstd is required")
class PackageReleaseTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.packages = dict(package_release.PACKAGES)
        self.addCleanup(
            lambda: (
                package_release.PACKAGES.clear(),
                package_release.PACKAGES.update(self.packages),
            )
        )

    def write(self, name, data=b"payload"):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def build(self, spec, source, name="fixture-v1"):
        package_release.PACKAGES[name] = spec
        output = (
            self.root / "out" / f"{name}-{len(list(self.root.glob('out/*')))}.tar.zst"
        )
        with contextlib.redirect_stdout(io.StringIO()):
            package_release.build(name, source, output)
        return output

    def test_exact_files_from_tar_gz_keep_relative_layout(self):
        self.write("src/data/a/val/x.h5", b"x")
        self.write("src/data/b/val/x.h5", b"y")
        self.write("src/data/a/test/x.h5", b"excluded")
        source = self.root / "source.tar.gz"
        with tarfile.open(source, "w:gz") as tar:
            tar.add(self.root / "src" / "data", arcname="data")
        spec = {
            "root": "fixture",
            "within": "data",
            "files": ["a/val/x.h5", "b/val/x.h5"],
        }

        self.assertEqual(
            members(self.build(spec, source)),
            {"fixture/a/val/x.h5": b"x", "fixture/b/val/x.h5": b"y"},
        )

    def test_missing_exact_file_fails(self):
        self.write("src/a.h5")
        spec = {"root": "fixture", "files": ["a.h5", "b.h5"]}
        with self.assertRaises(SystemExit):
            self.build(spec, self.root / "src")

    def test_glob_accepts_parent_or_directory_and_enforces_counts(self):
        for index in range(3):
            self.write(f"src/cases/{index}.txt", b"case")
        spec = {
            "root": "fixture",
            "glob": "cases/*.txt",
            "min_files": 3,
            "nonempty": True,
        }

        from_parent = members(self.build(spec, self.root / "src"))
        from_directory = members(self.build(spec, self.root / "src" / "cases"))
        self.assertEqual(from_parent, from_directory)
        self.assertEqual(len(from_parent), 3)

        with self.assertRaises(SystemExit):
            self.build({**spec, "min_files": 4}, self.root / "src")
        self.write("src/cases/empty.txt", b"")
        with self.assertRaises(SystemExit):
            self.build(spec, self.root / "src")

    def test_rebuilds_are_byte_identical(self):
        self.write("src/a.h5", b"a")
        self.write("src/b.h5", b"b")
        spec = {"root": "fixture", "files": ["b.h5", "a.h5"], "license": "# L\n"}
        first = self.build(spec, self.root / "src")
        (self.root / "src" / "a.h5").touch()  # mtime must not leak into the archive
        second = self.build(spec, self.root / "src")

        self.assertEqual(first.read_bytes(), second.read_bytes())
        self.assertEqual(
            list(members(first)),
            ["fixture/LICENSE.md", "fixture/a.h5", "fixture/b.h5"],
        )

    def test_mirror_requires_pinned_size_and_hash(self):
        data = b"scene bytes"
        self.write("src/scene.sog", data)
        entry = {
            "path": "scene.sog",
            "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
            "url": "https://invalid.example/scene.sog",
        }
        spec = {"root": "fixture", "mirror": [entry]}
        self.assertEqual(
            members(self.build(spec, self.root / "src")), {"fixture/scene.sog": data}
        )

        self.write("src/scene.sog", b"tampered!!!")
        with self.assertRaises(SystemExit):
            self.build(spec, self.root / "src")

    def test_registered_artifacts_all_have_specs(self):
        import json

        registry = json.loads(package_release.REGISTRY.read_text())
        for name in registry:
            self.assertIn(name[: -len(".tar.zst")], self.packages)


if __name__ == "__main__":
    unittest.main()
