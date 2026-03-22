#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Test automatici per dump_engine."""

import tempfile
import unittest
from pathlib import Path

from dump_folder.engine.dump_engine import collect_files_from_inputs, collect_manifest_from_selection, generate_dump
from dump_folder.engine.selection_model import NormalizedSelection


class DumpEngineTests(unittest.TestCase):
    def test_collect_files_deduplicates_and_excludes_common_dirs(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            project = root / "project"
            project.mkdir()
            included = project / "app.py"
            included.write_text("print('ok')\n", encoding="utf-8")

            excluded_dir = project / ".git"
            excluded_dir.mkdir()
            (excluded_dir / "config").write_text("secret\n", encoding="utf-8")

            pycache_dir = project / "__pycache__"
            pycache_dir.mkdir()
            (pycache_dir / "app.cpython-312.pyc").write_bytes(b"\x00\x01")

            files = collect_files_from_inputs([project, included])

            self.assertEqual(files, [included.resolve()])

    def test_generate_dump_adds_expected_extension(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            source = root / "notes.txt"
            source.write_text("hello\n", encoding="utf-8")

            output = generate_dump([source], root / "result", "md")

            self.assertEqual(Path(output).suffix, ".md")
            self.assertTrue(Path(output).exists())

    def test_generate_dump_skips_output_file_inside_selected_folder(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            source_dir = root / "project"
            source_dir.mkdir()
            (source_dir / "alpha.txt").write_text("A\n", encoding="utf-8")

            output = source_dir / "dump.txt"
            generate_dump([source_dir], output, "txt")

            content = output.read_text(encoding="utf-8")
            self.assertIn("# FILE: project/alpha.txt", content)
            self.assertEqual(content.count("# FILE: project/dump.txt"), 0)

    def test_generate_dump_marks_binary_files_with_placeholder(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            binary_file = root / "image.bin"
            binary_file.write_bytes(b"\x00\xff\x10")
            output = root / "dump.txt"

            generate_dump([binary_file], output, "txt")

            content = output.read_text(encoding="utf-8")
            self.assertIn("[BINARIO NON INCLUSO: image.bin]", content)

    def test_generate_dump_handles_mixed_file_and_folder_inputs(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            folder = root / "src"
            folder.mkdir()
            nested = folder / "main.py"
            nested.write_text("print('nested')\n", encoding="utf-8")
            single = root / "README.md"
            single.write_text("# demo\n", encoding="utf-8")
            output = root / "bundle.html"

            generate_dump([single, folder], output, "html")

            content = output.read_text(encoding="utf-8")
            self.assertIn("README.md", content)
            self.assertIn("src/main.py", content)

    def test_collect_manifest_applies_exclude_override_without_duplicates(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            source_dir = root / "project"
            source_dir.mkdir()
            keep_file = source_dir / "keep.py"
            keep_file.write_text("print('keep')\n", encoding="utf-8")
            skip_file = source_dir / "skip.py"
            skip_file.write_text("print('skip')\n", encoding="utf-8")

            selection = NormalizedSelection(
                includes=[str(source_dir.resolve())],
                excludes=[str(skip_file.resolve())],
            )

            manifest = collect_manifest_from_selection(selection)

            self.assertEqual(manifest.files, [keep_file.resolve()])
            self.assertEqual(manifest.directories, [source_dir.resolve()])

    def test_collect_manifest_counts_nested_directories(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            source_dir = root / "project"
            nested_dir = source_dir / "pkg"
            deeper_dir = nested_dir / "data"
            deeper_dir.mkdir(parents=True)
            (deeper_dir / "keep.py").write_text("print('keep')\n", encoding="utf-8")

            selection = NormalizedSelection(
                includes=[str(source_dir.resolve())],
                excludes=[],
            )

            manifest = collect_manifest_from_selection(selection)

            self.assertEqual(
                manifest.directories,
                [source_dir.resolve(), nested_dir.resolve(), deeper_dir.resolve()],
            )

    def test_generate_dump_accepts_normalized_selection(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            source_dir = root / "project"
            source_dir.mkdir()
            keep_file = source_dir / "keep.py"
            keep_file.write_text("print('keep')\n", encoding="utf-8")
            skip_file = source_dir / "skip.py"
            skip_file.write_text("print('skip')\n", encoding="utf-8")
            output = root / "bundle.txt"

            selection = NormalizedSelection(
                includes=[str(source_dir.resolve())],
                excludes=[str(skip_file.resolve())],
            )
            generate_dump(selection, output, "txt")

            content = output.read_text(encoding="utf-8")
            self.assertIn("keep.py", content)
            self.assertNotIn("skip.py", content)


if __name__ == "__main__":
    unittest.main()
