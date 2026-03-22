#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Test per selection_model."""

import tempfile
import unittest
from pathlib import Path

from dump_folder.engine.selection_model import FileSystemSelectionModel


class SelectionModelTests(unittest.TestCase):
    def _build_tree(self, root):
        src = root / "src"
        src.mkdir()
        nested = src / "pkg"
        nested.mkdir()
        (src / "main.py").write_text("print('main')\n", encoding="utf-8")
        (nested / "mod.py").write_text("print('mod')\n", encoding="utf-8")
        (root / "README.md").write_text("# demo\n", encoding="utf-8")
        return src

    def test_tri_state_base(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            src = self._build_tree(root)
            model = FileSystemSelectionModel()
            src_id = model.add_root(src)

            self.assertEqual(model.get_node_check_state(src_id), "unchecked")
            model.set_subtree_included(src_id, True)
            self.assertEqual(model.get_node_check_state(src_id), "checked")

    def test_parent_selection_propagates_to_loaded_children(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            src = self._build_tree(root)
            model = FileSystemSelectionModel()
            src_id = model.add_root(src)
            child_ids = model.load_children(src_id)

            model.set_subtree_included(src_id, True)

            self.assertTrue(child_ids)
            for child_id in child_ids:
                self.assertEqual(model.get_node_check_state(child_id), "checked")

    def test_children_selection_marks_parent_indeterminate(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            src = self._build_tree(root)
            model = FileSystemSelectionModel()
            src_id = model.add_root(src)
            child_ids = model.load_children(src_id)
            file_id = next(child_id for child_id in child_ids if model.nodes[child_id].kind == "file")

            model.set_subtree_included(file_id, True)

            self.assertEqual(model.get_node_check_state(file_id), "checked")
            self.assertEqual(model.get_node_check_state(src_id), "indeterminate")

    def test_folder_include_with_child_excluded_stays_indeterminate(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            src = self._build_tree(root)
            model = FileSystemSelectionModel()
            src_id = model.add_root(src)
            child_ids = model.load_children(src_id)
            file_id = next(child_id for child_id in child_ids if model.nodes[child_id].kind == "file")

            model.set_subtree_included(src_id, True)
            model.set_node_excluded(file_id)

            normalized = model.build_normalized_selection()
            self.assertEqual(model.get_node_check_state(src_id), "indeterminate")
            self.assertIn(src_id, normalized.includes)
            self.assertIn(file_id, normalized.excludes)

    def test_normalization_removes_redundant_children(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            src = self._build_tree(root)
            model = FileSystemSelectionModel()
            src_id = model.add_root(src)
            child_ids = model.load_children(src_id)
            file_id = next(child_id for child_id in child_ids if model.nodes[child_id].kind == "file")

            model.set_subtree_included(file_id, True)
            model.set_subtree_included(src_id, True)

            normalized = model.build_normalized_selection()
            self.assertEqual(normalized.includes, [src_id])
            self.assertEqual(normalized.excludes, [])

    def test_restore_state_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            src = self._build_tree(root)
            model = FileSystemSelectionModel()
            src_id = model.add_root(src)
            child_ids = model.load_children(src_id)
            model.expand_node(src_id)
            model.set_subtree_included(src_id, True)
            model.set_node_excluded(child_ids[0])
            exported = model.export_state()

            restored = FileSystemSelectionModel()
            restored.restore_state(exported)

            self.assertIn(src_id, restored.root_ids)
            self.assertIn(src_id, restored.ui_state.expanded_ids)
            self.assertEqual(restored.build_normalized_selection().includes, [src_id])
            self.assertEqual(len(restored.build_normalized_selection().excludes), 1)

    def test_lazy_loading_loads_only_direct_children(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            src = self._build_tree(root)
            model = FileSystemSelectionModel()
            src_id = model.add_root(src)

            child_ids = model.load_children(src_id)

            self.assertTrue(child_ids)
            nested_dir_id = next(child_id for child_id in child_ids if model.nodes[child_id].kind == "directory")
            self.assertFalse(model.nodes[nested_dir_id].children_loaded)


if __name__ == "__main__":
    unittest.main()
