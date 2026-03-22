#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Modello dati per file tree, regole di selezione e normalizzazione."""

from __future__ import annotations

from dataclasses import dataclass, field
import os
from pathlib import Path
from typing import Callable


CheckState = str


def normalize_path(path):
    """Normalizza un path in stile POSIX con casefold stabile."""
    return str(Path(path).absolute()).replace("\\", "/")


def path_depth(path):
    return normalize_path(path).count("/")


def is_same_or_child(path, candidate_parent):
    path = normalize_path(path)
    candidate_parent = normalize_path(candidate_parent)
    return path == candidate_parent or path.startswith(candidate_parent + "/")


def is_direct_child(path, parent_path):
    path = normalize_path(path)
    parent_path = normalize_path(parent_path)
    if not path.startswith(parent_path + "/"):
        return False
    relative = path[len(parent_path) + 1 :]
    return "/" not in relative


@dataclass
class TreeNode:
    id: str
    path: str
    name: str
    kind: str
    parent_id: str | None
    has_children: bool
    children_loaded: bool = False
    children_ids: list[str] = field(default_factory=list)
    size: int | None = None
    error: str | None = None


@dataclass
class TreeUiState:
    expanded_ids: set[str] = field(default_factory=set)
    focused_id: str | None = None
    loading_ids: set[str] = field(default_factory=set)
    error_by_id: dict[str, str] = field(default_factory=dict)


@dataclass
class SelectionState:
    include_rules: set[str] = field(default_factory=set)
    exclude_rules: set[str] = field(default_factory=set)


@dataclass
class NormalizedSelection:
    includes: list[str]
    excludes: list[str]


class FileSystemSelectionModel:
    """Gestisce roots, lazy loading e regole include/exclude sul filesystem."""

    def __init__(self, scandir_fn: Callable[[Path], list[os.DirEntry]] | None = None):
        self.nodes: dict[str, TreeNode] = {}
        self.root_ids: list[str] = []
        self.ui_state = TreeUiState()
        self.selection_state = SelectionState()
        self._scandir_fn = scandir_fn

    def add_root(self, path):
        resolved = Path(path).absolute()
        if not resolved.exists():
            raise ValueError(f"Percorso non valido: {resolved}")

        node = self._build_node(resolved, parent_id=None)
        if node.id in self.nodes:
            return node.id

        self.nodes[node.id] = node
        self.root_ids.append(node.id)
        return node.id

    def remove_root(self, node_id):
        node_id = normalize_path(node_id)
        if node_id not in self.nodes:
            return

        subtree_ids = [candidate_id for candidate_id in list(self.nodes) if is_same_or_child(candidate_id, node_id)]
        for subtree_id in subtree_ids:
            self.nodes.pop(subtree_id, None)
            self.ui_state.expanded_ids.discard(subtree_id)
            self.ui_state.loading_ids.discard(subtree_id)
            self.ui_state.error_by_id.pop(subtree_id, None)
            self.selection_state.include_rules.discard(subtree_id)
            self.selection_state.exclude_rules.discard(subtree_id)

        self.root_ids = [root_id for root_id in self.root_ids if root_id != node_id]
        self.ui_state.focused_id = None if self.ui_state.focused_id == node_id else self.ui_state.focused_id
        self._prune_rules_outside_roots()

    def load_children(self, node_id):
        node_id = normalize_path(node_id)
        node = self.nodes[node_id]
        if node.kind != "directory" or node.children_loaded:
            return node.children_ids

        directory = Path(node.path)
        self.ui_state.loading_ids.add(node_id)
        try:
            entries = self._list_directory(directory)
        except OSError as exc:
            node.error = str(exc)
            self.ui_state.error_by_id[node_id] = str(exc)
            node.children_loaded = True
            node.children_ids = []
            self.ui_state.loading_ids.discard(node_id)
            return []

        child_ids = []
        for entry in entries:
            child_node = self._build_node(Path(entry.path), parent_id=node_id)
            self.nodes[child_node.id] = child_node
            child_ids.append(child_node.id)

        node.children_loaded = True
        node.children_ids = child_ids
        node.has_children = bool(child_ids)
        self.ui_state.loading_ids.discard(node_id)
        self.ui_state.error_by_id.pop(node_id, None)
        return child_ids

    def ensure_visible(self, node_id):
        node_id = normalize_path(node_id)
        if node_id in self.nodes:
            return True

        target_path = Path(node_id)
        for root_id in self.root_ids:
            root_path = Path(root_id)
            try:
                relative_parts = target_path.relative_to(root_path).parts
            except ValueError:
                continue

            current_id = root_id
            if not relative_parts:
                return True

            for part in relative_parts:
                self.load_children(current_id)
                children = self.nodes[current_id].children_ids
                next_id = None
                for child_id in children:
                    if Path(self.nodes[child_id].path).name == part:
                        next_id = child_id
                        break
                if next_id is None:
                    return False
                current_id = next_id

            return current_id == node_id

        return False

    def expand_node(self, node_id):
        node_id = normalize_path(node_id)
        if self.nodes[node_id].kind == "directory":
            self.load_children(node_id)
        self.ui_state.expanded_ids.add(node_id)

    def collapse_node(self, node_id):
        self.ui_state.expanded_ids.discard(normalize_path(node_id))

    def set_focus(self, node_id):
        self.ui_state.focused_id = normalize_path(node_id) if node_id else None

    def clear_selection(self):
        self.selection_state.include_rules.clear()
        self.selection_state.exclude_rules.clear()

    def set_subtree_included(self, node_id, included):
        node_id = normalize_path(node_id)
        self._remove_descendant_rules(node_id)
        self.selection_state.include_rules.discard(node_id)
        self.selection_state.exclude_rules.discard(node_id)
        if included:
            self.selection_state.include_rules.add(node_id)
        else:
            self.selection_state.exclude_rules.add(node_id)
        self._simplify_rules()

    def set_node_excluded(self, node_id):
        self.set_subtree_included(node_id, False)

    def toggle_node_included(self, node_id):
        state = self.get_node_check_state(node_id)
        self.set_subtree_included(node_id, state == "unchecked")

    def build_normalized_selection(self):
        self._simplify_rules()
        includes = sorted(self.selection_state.include_rules, key=lambda value: (path_depth(value), value.lower()))
        excludes = sorted(self.selection_state.exclude_rules, key=lambda value: (path_depth(value), value.lower()))
        return NormalizedSelection(includes=includes, excludes=excludes)

    def is_effectively_included(self, node_id, include_rules=None, exclude_rules=None):
        node_id = normalize_path(node_id)
        include_rules = include_rules if include_rules is not None else self.selection_state.include_rules
        exclude_rules = exclude_rules if exclude_rules is not None else self.selection_state.exclude_rules

        winning_depth = -1
        winning_state = False
        for rule_path in include_rules:
            if is_same_or_child(node_id, rule_path):
                depth = path_depth(rule_path)
                if depth > winning_depth:
                    winning_depth = depth
                    winning_state = True
        for rule_path in exclude_rules:
            if is_same_or_child(node_id, rule_path):
                depth = path_depth(rule_path)
                if depth > winning_depth:
                    winning_depth = depth
                    winning_state = False
        return winning_state

    def get_node_check_state(self, node_id):
        node_id = normalize_path(node_id)
        effective = self.is_effectively_included(node_id)
        descendant_rules = self._has_descendant_rule(node_id)
        if descendant_rules:
            return "indeterminate"
        return "checked" if effective else "unchecked"

    def export_state(self):
        normalized = self.build_normalized_selection()
        return {
            "roots": list(self.root_ids),
            "expanded_ids": sorted(self.ui_state.expanded_ids),
            "focused_id": self.ui_state.focused_id,
            "include_rules": normalized.includes,
            "exclude_rules": normalized.excludes,
        }

    def restore_state(self, data):
        self.nodes.clear()
        self.root_ids = []
        self.ui_state = TreeUiState()
        self.selection_state = SelectionState()

        for root_path in data.get("roots", []):
            try:
                self.add_root(root_path)
            except ValueError:
                continue

        self.selection_state.include_rules = {normalize_path(path) for path in data.get("include_rules", [])}
        self.selection_state.exclude_rules = {normalize_path(path) for path in data.get("exclude_rules", [])}
        self._prune_rules_outside_roots()
        self._simplify_rules()

        for expanded_id in data.get("expanded_ids", []):
            expanded_id = normalize_path(expanded_id)
            if self.ensure_visible(expanded_id):
                self.ui_state.expanded_ids.add(expanded_id)
        focused_id = data.get("focused_id")
        if focused_id and self.ensure_visible(focused_id):
            self.ui_state.focused_id = normalize_path(focused_id)

    def _list_directory(self, directory):
        if self._scandir_fn is not None:
            return self._scandir_fn(directory)

        with os.scandir(directory) as iterator:
            entries = list(iterator)

        def sort_key(entry):
            try:
                is_dir = entry.is_dir(follow_symlinks=False)
            except OSError:
                is_dir = False
            return (0 if is_dir else 1, entry.name.lower())

        return sorted(entries, key=sort_key)

    def _build_node(self, path, parent_id):
        resolved = Path(path).absolute()
        node_id = normalize_path(resolved)
        try:
            is_symlink = resolved.is_symlink()
        except OSError:
            is_symlink = False

        if is_symlink:
            kind = "symlink"
            has_children = False
        elif resolved.is_dir():
            kind = "directory"
            has_children = self._directory_has_children(resolved)
        else:
            kind = "file"
            has_children = False

        return TreeNode(
            id=node_id,
            path=node_id,
            name=resolved.name or node_id,
            kind=kind,
            parent_id=normalize_path(parent_id) if parent_id else None,
            has_children=has_children,
            size=self._safe_stat_size(resolved),
        )

    def _directory_has_children(self, directory):
        try:
            with os.scandir(directory) as iterator:
                next(iterator, None)
                return True
        except OSError:
            return False

    def _safe_stat_size(self, path):
        try:
            return path.stat().st_size
        except OSError:
            return None

    def _has_descendant_rule(self, node_id):
        for rule_path in self.selection_state.include_rules | self.selection_state.exclude_rules:
            if rule_path != node_id and is_same_or_child(rule_path, node_id):
                return True
        return False

    def _remove_descendant_rules(self, node_id):
        self.selection_state.include_rules = {
            rule_path
            for rule_path in self.selection_state.include_rules
            if not (rule_path != node_id and is_same_or_child(rule_path, node_id))
        }
        self.selection_state.exclude_rules = {
            rule_path
            for rule_path in self.selection_state.exclude_rules
            if not (rule_path != node_id and is_same_or_child(rule_path, node_id))
        }

    def _simplify_rules(self):
        include_rules = set(self.selection_state.include_rules)
        exclude_rules = set(self.selection_state.exclude_rules)

        self.selection_state.include_rules = {
            rule_path
            for rule_path in include_rules
            if not self.is_effectively_included(
                rule_path,
                include_rules=include_rules - {rule_path},
                exclude_rules=exclude_rules,
            )
        }
        include_rules = set(self.selection_state.include_rules)

        self.selection_state.exclude_rules = {
            rule_path
            for rule_path in exclude_rules
            if self.is_effectively_included(
                rule_path,
                include_rules=include_rules,
                exclude_rules=exclude_rules - {rule_path},
            )
        }

        overlap = self.selection_state.include_rules & self.selection_state.exclude_rules
        self.selection_state.include_rules -= overlap
        self.selection_state.exclude_rules -= overlap
        self._prune_rules_outside_roots()

    def _prune_rules_outside_roots(self):
        if not self.root_ids:
            self.selection_state.include_rules.clear()
            self.selection_state.exclude_rules.clear()
            return

        def belongs_to_roots(rule_path):
            return any(is_same_or_child(rule_path, root_id) for root_id in self.root_ids)

        self.selection_state.include_rules = {rule_path for rule_path in self.selection_state.include_rules if belongs_to_roots(rule_path)}
        self.selection_state.exclude_rules = {rule_path for rule_path in self.selection_state.exclude_rules if belongs_to_roots(rule_path)}
