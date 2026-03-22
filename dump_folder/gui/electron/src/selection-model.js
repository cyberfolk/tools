(function (globalObject) {
  const pathSeparatorPattern = /\\/g;

  function normalizePath(value) {
    const normalized = String(value).replace(pathSeparatorPattern, "/");
    if (/^[A-Za-z]:\//.test(normalized)) {
      return normalized.replace(/\/+/g, "/");
    }
    return normalized.replace(/\/+/g, "/");
  }

  function pathDepth(value) {
    return normalizePath(value).split("/").length;
  }

  function isSameOrChild(value, candidateParent) {
    const normalizedValue = normalizePath(value);
    const normalizedParent = normalizePath(candidateParent);
    return normalizedValue === normalizedParent || normalizedValue.startsWith(`${normalizedParent}/`);
  }

  class FileSystemSelectionModel {
    constructor() {
      this.nodes = new Map();
      this.rootIds = [];
      this.expandedIds = new Set();
      this.focusedId = null;
      this.includeRules = new Set();
      this.excludeRules = new Set();
    }

    reset() {
      this.nodes.clear();
      this.rootIds = [];
      this.expandedIds.clear();
      this.focusedId = null;
      this.includeRules.clear();
      this.excludeRules.clear();
    }

    addRoot(node) {
      this.reset();
      this.storeNode(node);
      this.rootIds = [node.id];
    }

    storeNode(node) {
      this.nodes.set(node.id, {
        ...node,
        childrenIds: Array.isArray(node.childrenIds) ? [...node.childrenIds] : [],
      });
    }

    storeChildren(parentId, children) {
      const parent = this.nodes.get(parentId);
      if (!parent) {
        return;
      }
      parent.childrenLoaded = true;
      parent.childrenIds = children.map((child) => child.id);
      parent.hasChildren = children.length > 0;
      this.nodes.set(parentId, parent);

      for (const child of children) {
        this.storeNode(child);
      }
    }

    setFocus(nodeId) {
      this.focusedId = nodeId ? normalizePath(nodeId) : null;
    }

    expandNode(nodeId) {
      this.expandedIds.add(normalizePath(nodeId));
    }

    collapseNode(nodeId) {
      this.expandedIds.delete(normalizePath(nodeId));
    }

    clearSelection() {
      this.includeRules.clear();
      this.excludeRules.clear();
    }

    removeDescendantRules(nodeId) {
      const normalizedId = normalizePath(nodeId);
      this.includeRules = new Set(
        [...this.includeRules].filter((rule) => !(rule !== normalizedId && isSameOrChild(rule, normalizedId))),
      );
      this.excludeRules = new Set(
        [...this.excludeRules].filter((rule) => !(rule !== normalizedId && isSameOrChild(rule, normalizedId))),
      );
    }

    setSubtreeIncluded(nodeId, included) {
      const normalizedId = normalizePath(nodeId);
      this.removeDescendantRules(normalizedId);
      this.includeRules.delete(normalizedId);
      this.excludeRules.delete(normalizedId);
      if (included) {
        this.includeRules.add(normalizedId);
      } else {
        this.excludeRules.add(normalizedId);
      }
      this.simplifyRules();
    }

    isEffectivelyIncluded(nodeId, includeRules = this.includeRules, excludeRules = this.excludeRules) {
      const normalizedId = normalizePath(nodeId);
      let winningDepth = -1;
      let winningState = false;

      for (const rulePath of includeRules) {
        if (isSameOrChild(normalizedId, rulePath)) {
          const depth = pathDepth(rulePath);
          if (depth > winningDepth) {
            winningDepth = depth;
            winningState = true;
          }
        }
      }

      for (const rulePath of excludeRules) {
        if (isSameOrChild(normalizedId, rulePath)) {
          const depth = pathDepth(rulePath);
          if (depth > winningDepth) {
            winningDepth = depth;
            winningState = false;
          }
        }
      }

      return winningState;
    }

    hasDescendantRule(nodeId) {
      const normalizedId = normalizePath(nodeId);
      for (const rule of [...this.includeRules, ...this.excludeRules]) {
        if (rule !== normalizedId && isSameOrChild(rule, normalizedId)) {
          return true;
        }
      }
      return false;
    }

    getNodeCheckState(nodeId) {
      const normalizedId = normalizePath(nodeId);
      if (this.hasDescendantRule(normalizedId)) {
        return "indeterminate";
      }
      return this.isEffectivelyIncluded(normalizedId) ? "checked" : "unchecked";
    }

    pruneRulesOutsideRoots() {
      if (!this.rootIds.length) {
        this.includeRules.clear();
        this.excludeRules.clear();
        return;
      }

      const belongsToRoots = (rule) => this.rootIds.some((rootId) => isSameOrChild(rule, rootId));
      this.includeRules = new Set([...this.includeRules].filter(belongsToRoots));
      this.excludeRules = new Set([...this.excludeRules].filter(belongsToRoots));
    }

    simplifyRules() {
      const includeRules = new Set(this.includeRules);
      const excludeRules = new Set(this.excludeRules);

      this.includeRules = new Set(
        [...includeRules].filter((rule) => {
          const nextIncludes = new Set([...includeRules].filter((candidate) => candidate !== rule));
          return !this.isEffectivelyIncluded(rule, nextIncludes, excludeRules);
        }),
      );

      const normalizedIncludes = new Set(this.includeRules);
      this.excludeRules = new Set(
        [...excludeRules].filter((rule) => {
          const nextExcludes = new Set([...excludeRules].filter((candidate) => candidate !== rule));
          return this.isEffectivelyIncluded(rule, normalizedIncludes, nextExcludes);
        }),
      );

      const overlap = [...this.includeRules].filter((rule) => this.excludeRules.has(rule));
      for (const rule of overlap) {
        this.includeRules.delete(rule);
        this.excludeRules.delete(rule);
      }

      this.pruneRulesOutsideRoots();
    }

    buildNormalizedSelection() {
      this.simplifyRules();
      const compareRules = (left, right) =>
        pathDepth(left) - pathDepth(right) || left.localeCompare(right, undefined, { sensitivity: "base" });
      return {
        includes: [...this.includeRules].sort(compareRules),
        excludes: [...this.excludeRules].sort(compareRules),
      };
    }

    exportState() {
      const normalized = this.buildNormalizedSelection();
      return {
        roots: [...this.rootIds],
        expandedIds: [...this.expandedIds].sort(),
        focusedId: this.focusedId,
        includeRules: normalized.includes,
        excludeRules: normalized.excludes,
      };
    }

    restoreState(data) {
      this.reset();
      if (!data || typeof data !== "object") {
        return;
      }
      this.rootIds = Array.isArray(data.roots) ? data.roots.map(normalizePath) : [];
      this.expandedIds = new Set(Array.isArray(data.expandedIds) ? data.expandedIds.map(normalizePath) : []);
      this.focusedId = data.focusedId ? normalizePath(data.focusedId) : null;
      this.includeRules = new Set(Array.isArray(data.includeRules) ? data.includeRules.map(normalizePath) : []);
      this.excludeRules = new Set(Array.isArray(data.excludeRules) ? data.excludeRules.map(normalizePath) : []);
      this.pruneRulesOutsideRoots();
      this.simplifyRules();
    }
  }

  globalObject.DumpBuilderSelectionModel = {
    FileSystemSelectionModel,
    isSameOrChild,
    normalizePath,
    pathDepth,
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = globalObject.DumpBuilderSelectionModel;
  }
})(typeof window !== "undefined" ? window : globalThis);
