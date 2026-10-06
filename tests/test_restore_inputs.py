"""Owned tiny archive fixtures only; no science or native library execution.

Set PCS_RESTORE_FIXTURE_PARENT to keep every new fixture under a private path.
Fixtures are deliberately retained, never deleted by this test.
"""
from pathlib import Path
import ast
import os
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import restore_inputs as loader


class RestoreTests(unittest.TestCase):
    def setUp(self):
        parent = os.environ.get("PCS_RESTORE_FIXTURE_PARENT")
        if parent:
            Path(parent).mkdir(parents=True, exist_ok=True)
        self.base = Path(tempfile.mkdtemp(prefix="owned-restore-", dir=parent))
        self.destination = self.base / "destination"
        self.destination.mkdir()
        self.archive = self.base / "fixture.zip"
        self.payloads = {"cases/owned.json": b'{"owned":1}\n',
                         "results/owned.jsonl": b'{"result":2}\r\n'}
        self.manifest = patch.dict(loader.MEMBERS,
                                   {n: len(b) for n,b in self.payloads.items()}, clear=True)
        self.manifest.start()
        self.addCleanup(self.manifest.stop)  # restores a Python dict, deletes no file.

    def make_zip(self, extra=(), link=False, compression=zipfile.ZIP_LZMA):
        with zipfile.ZipFile(self.archive, "x") as archive:
            for name, data in [*self.payloads.items(), *extra]:
                info = zipfile.ZipInfo(name, date_time=(1980,1,1,0,0,0))
                info.create_system = 3
                info.compress_type = compression
                info.external_attr = ((stat.S_IFLNK if link else stat.S_IFREG) | 0o644) << 16
                archive.writestr(info, data)

    def assert_no_materialized_data(self):
        self.assertFalse((self.destination / "cases/owned.json").exists())
        self.assertFalse((self.destination / "results/owned.jsonl").exists())

    def test_restore_exact_bytes_and_idempotence(self):
        self.make_zip()
        first = loader.restore_inputs(self.destination, self.archive)
        self.assertEqual(first["restored_files"], 2)
        times = {}
        for name, data in self.payloads.items():
            target = self.destination / name
            self.assertEqual(target.read_bytes(), data)
            times[name] = target.stat().st_mtime_ns
        second = loader.restore_inputs(self.destination, self.archive)
        self.assertEqual(second["restored_files"], 0)
        self.assertEqual(second["existing_files_byte_equal"], 2)
        self.assertEqual(times, {n:(self.destination/n).stat().st_mtime_ns for n in times})

    def test_same_size_existing_mismatch_blocks_every_write(self):
        self.make_zip()
        existing = self.destination / "results/owned.jsonl"
        existing.parent.mkdir()
        wrong = b"x" * len(self.payloads["results/owned.jsonl"])
        existing.write_bytes(wrong)
        with self.assertRaisesRegex(ValueError, "existing file differs"):
            loader.restore_inputs(self.destination, self.archive)
        self.assertEqual(existing.read_bytes(), wrong)
        self.assertFalse((self.destination/"cases").exists())

    def test_existing_directory_is_not_a_file(self):
        self.make_zip()
        (self.destination/"cases/owned.json").mkdir(parents=True)
        with self.assertRaisesRegex(ValueError, "ordinary file"):
            loader.restore_inputs(self.destination, self.archive)
        self.assertFalse((self.destination/"results").exists())

    def test_non_directory_parent_refused(self):
        self.make_zip()
        (self.destination/"cases").write_bytes(b"sentinel")
        with self.assertRaisesRegex(ValueError, "ordinary directory"):
            loader.restore_inputs(self.destination, self.archive)
        self.assertEqual((self.destination/"cases").read_bytes(), b"sentinel")
        self.assertFalse((self.destination/"results").exists())

    def test_path_traversal_member_refused(self):
        self.make_zip(extra=[("../owned.txt", b"owned")])
        with self.assertRaises(ValueError):
            loader.restore_inputs(self.destination, self.archive)
        self.assert_no_materialized_data()
        self.assertFalse((self.base/"owned.txt").exists())

    def test_duplicate_member_refused(self):
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            self.make_zip(extra=[("cases/owned.json", self.payloads["cases/owned.json"])])
        with self.assertRaisesRegex(ValueError, "duplicate"):
            loader.restore_inputs(self.destination, self.archive)
        self.assert_no_materialized_data()

    def test_size_manifest_mismatch_refused(self):
        self.make_zip()
        loader.MEMBERS["results/owned.jsonl"] += 1
        with self.assertRaisesRegex(ValueError, "size mismatch"):
            loader.restore_inputs(self.destination, self.archive)
        self.assert_no_materialized_data()

    def test_symlink_member_refused(self):
        self.make_zip(link=True)
        with self.assertRaisesRegex(ValueError, "type/compression/size"):
            loader.restore_inputs(self.destination, self.archive)
        self.assert_no_materialized_data()

    def test_existing_symlink_refused(self):
        self.make_zip()
        outside = self.base/"outside"
        outside.mkdir()
        try:
            (self.destination/"cases").symlink_to(outside, target_is_directory=True)
        except OSError as error:
            self.skipTest(f"OS symlink creation unavailable: {error}")
        with self.assertRaisesRegex(ValueError, "ordinary directory"):
            loader.restore_inputs(self.destination, self.archive)
        self.assertEqual(list(outside.iterdir()), [])

    def test_compressed_size_limit_refused(self):
        self.make_zip()
        with patch.object(loader, "MAX_ARCHIVE_BYTES", 1):
            with self.assertRaisesRegex(ValueError, "exceeds 12 MB"):
                loader.restore_inputs(self.destination, self.archive)
        self.assert_no_materialized_data()

    def test_uncompressed_size_limit_refused(self):
        self.make_zip()
        with patch.object(loader, "MAX_TOTAL_BYTES", 1):
            with self.assertRaisesRegex(ValueError, "uncompressed"):
                loader.restore_inputs(self.destination, self.archive)
        self.assert_no_materialized_data()

    def test_decoder_dictionary_limit_refused(self):
        self.make_zip()
        with patch.object(loader, "MAX_DICTIONARY_BYTES", 1):
            with self.assertRaisesRegex(ValueError, "dictionary limit"):
                loader.restore_inputs(self.destination, self.archive)
        self.assert_no_materialized_data()

    def test_wrong_compression_refused(self):
        self.make_zip(compression=zipfile.ZIP_STORED)
        with self.assertRaisesRegex(ValueError, "compression"):
            loader.restore_inputs(self.destination, self.archive)
        self.assert_no_materialized_data()

    def test_bootstrap_precedes_snapshot_and_children(self):
        tree = ast.parse((ROOT/"scripts/reproduce.py").read_text(encoding="utf-8"))
        main = next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=="main")
        calls = {n.func.id:n.lineno for n in ast.walk(main)
                 if isinstance(n,ast.Call) and isinstance(n.func,ast.Name)
                 and n.func.id in {"restore_inputs","snapshot","run"}}
        self.assertLess(calls["restore_inputs"], min(n.lineno for n in ast.walk(main)
                        if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=="snapshot"))
        self.assertLess(calls["restore_inputs"], calls["run"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
