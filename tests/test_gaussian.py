"""Exercise offline fixture preparation with real local files and archives."""

import hashlib
import importlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


class GaussianFixtureTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(
            importlib.util.find_spec("inlier_data.gaussian"),
            "The Gaussian fixture preparation module is not implemented",
        )
        self.fixtures = importlib.import_module("inlier_data.gaussian")
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "source"
        self.source.mkdir()
        self.cache = self.root / "cache"
        self.catalog = self.root / "catalog.json"

    def write_catalog(self, files, format="sog-v2-bundle"):
        entries = []
        for name in files:
            data = (self.source / name).read_bytes()
            entries.append(
                {
                    "path": name,
                    "bytes": len(data),
                    "sha256": hashlib.sha256(data).hexdigest(),
                    "url": "https://invalid.example/never-request/" + name,
                }
            )
        value = {
            "schema_version": 1,
            "catalog_version": "test-v1",
            "datasets": {
                "test-v1": {
                    "title": "Test",
                    "format": format,
                    "splat_count": 2,
                    "source": {"revision": "a" * 40},
                    "license": {
                        "status": "unverified",
                        "automatic_fetch_enabled": False,
                        "release_publication_enabled": False,
                    },
                    "files": entries,
                }
            },
        }
        self.catalog.write_text(json.dumps(value))
        return value

    def bundle(self, missing_texture=False):
        meta = {"version": 2, "count": 2}
        for key in ("means", "quats", "scales", "sh0"):
            meta[key] = {"files": [key + ".webp"]}
        with zipfile.ZipFile(self.source / "scene.sog", "w") as archive:
            archive.writestr("meta.json", json.dumps(meta))
            for key in ("means", "quats", "scales", "sh0"):
                if not missing_texture or key != "means":
                    archive.writestr(key + ".webp", b"RIFF\x04\x00\x00\x00WEBP")
        self.write_catalog(["scene.sog"])

    def prepare(self, source=None):
        return self.fixtures.prepare(
            "test-v1",
            source=source if source is not None else self.source,
            cache_root=self.cache,
            catalog_path=self.catalog,
        )

    def test_local_bundle_is_copied_and_manifest_retains_permission_scope(self):
        self.bundle()
        result = self.prepare(source=self.source / "scene.sog")
        self.assertEqual(
            Path(result["entrypoint"]).read_bytes(),
            (self.source / "scene.sog").read_bytes(),
        )
        self.assertEqual(result["license"]["status"], "unverified")
        self.assertFalse(result["license"]["release_publication_enabled"])
        self.assertEqual(result["dataset_id"], "test-v1")
        self.assertRegex(result["asset_identity"], r"^sha256:[a-f0-9]{64}$")
        self.assertTrue((Path(result["root"]) / "fixture.json").is_file())

    def test_verified_cache_is_reusable_without_source_or_network(self):
        self.bundle()
        result = self.prepare()
        (self.source / "scene.sog").unlink()
        again = self.fixtures.prepare(
            "test-v1", cache_root=self.cache, catalog_path=self.catalog
        )
        self.assertEqual(again["asset_identity"], result["asset_identity"])
        self.assertEqual(again["entrypoint"], result["entrypoint"])

    def test_wrong_local_bytes_do_not_publish_success_manifest(self):
        self.bundle()
        path = self.source / "scene.sog"
        payload = path.read_bytes()
        path.write_bytes(payload[:-1] + bytes([payload[-1] ^ 1]))
        with self.assertRaisesRegex(ValueError, "SHA256"):
            self.prepare()
        self.assertEqual(list(self.cache.rglob("fixture.json")), [])

    def test_corrupt_cache_fails_verification_instead_of_redownloading(self):
        self.bundle()
        result = self.prepare()
        path = Path(result["entrypoint"])
        path.write_bytes(b"x" * path.stat().st_size)
        with self.assertRaisesRegex(ValueError, "SHA256"):
            self.fixtures.verify(
                "test-v1", cache_root=self.cache, catalog_path=self.catalog
            )

    def test_missing_source_does_not_attempt_download(self):
        self.bundle()
        with self.assertRaisesRegex(ValueError, "[Ll]ocal source"):
            self.fixtures.prepare(
                "test-v1", cache_root=self.cache, catalog_path=self.catalog
            )
        self.assertEqual(list(self.cache.rglob("fixture.json")), [])

    def test_archive_with_missing_referenced_texture_is_rejected(self):
        self.bundle(missing_texture=True)
        with self.assertRaisesRegex(ValueError, "(referenced|missing|Missing)"):
            self.prepare()
        self.assertEqual(list(self.cache.rglob("fixture.json")), [])

    def hierarchy(self, bad_range=False, missing_catalog_file=False):
        chunk = self.source / "chunk"
        chunk.mkdir()
        meta = {"version": 2, "count": 2}
        for key in ("means", "quats", "scales", "sh0"):
            meta[key] = {"files": [key + ".webp"]}
            (chunk / (key + ".webp")).write_bytes(b"RIFF\x04\x00\x00\x00WEBP")
        (chunk / "meta.json").write_text(json.dumps(meta))
        lod = {
            "lodLevels": 1,
            "environment": None,
            "filenames": ["chunk/meta.json"],
            "tree": {
                "lods": {"0": {"file": 0, "offset": 0, "count": 3 if bad_range else 2}}
            },
        }
        (self.source / "lod-meta.json").write_text(json.dumps(lod))
        files = [
            "lod-meta.json",
            "chunk/meta.json",
            "chunk/means.webp",
            "chunk/quats.webp",
            "chunk/scales.webp",
            "chunk/sh0.webp",
        ]
        if missing_catalog_file:
            files.remove("chunk/means.webp")
        self.write_catalog(files, "sog-v2-hierarchy")

    def test_complete_hierarchy_preserves_paths_and_byte_identity(self):
        self.hierarchy()
        result = self.prepare()
        self.assertEqual(Path(result["entrypoint"]).name, "lod-meta.json")
        self.assertEqual(result["validation"]["referenced_files"], 6)
        self.assertEqual(result["validation"]["leaf_ranges"], 1)
        self.assertTrue((Path(result["root"]) / "chunk/means.webp").is_file())

    def test_out_of_bounds_lod_range_is_rejected(self):
        self.hierarchy(bad_range=True)
        with self.assertRaisesRegex(ValueError, "range"):
            self.prepare()
        self.assertEqual(list(self.cache.rglob("fixture.json")), [])

    def test_uninventoried_child_cannot_hide_behind_valid_root_hash(self):
        self.hierarchy(missing_catalog_file=True)
        with self.assertRaisesRegex(ValueError, "(catalog|inventor|referenced)"):
            self.prepare()

    def test_catalog_path_traversal_is_rejected_before_any_copy(self):
        self.bundle()
        value = json.loads(self.catalog.read_text())
        value["datasets"]["test-v1"]["files"][0]["path"] = "../escaped.sog"
        self.catalog.write_text(json.dumps(value))
        with self.assertRaisesRegex(ValueError, "path"):
            self.prepare()
        self.assertFalse((self.root / "escaped.sog").exists())

    def test_changed_catalog_bytes_have_a_distinct_cache_identity(self):
        self.bundle()
        before = self.prepare()
        with zipfile.ZipFile(self.source / "scene.sog", "a") as archive:
            archive.writestr("note.txt", "new fixture version")
        self.write_catalog(["scene.sog"])
        after = self.prepare()
        self.assertNotEqual(before["root"], after["root"])
        self.assertNotEqual(before["asset_identity"], after["asset_identity"])
        self.assertTrue(Path(before["entrypoint"]).is_file())

    def test_cli_failure_has_nonzero_exit_and_no_success_json(self):
        self.bundle()
        run = subprocess.run(
            [
                sys.executable,
                "-m",
                "inlier_data.gaussian",
                "prepare",
                "test-v1",
                "--catalog",
                str(self.catalog),
                "--cache-root",
                str(self.cache),
            ],
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(run.returncode, 0)
        self.assertEqual(run.stdout, "")
        self.assertIn("source", run.stderr.lower())


if __name__ == "__main__":
    unittest.main()
