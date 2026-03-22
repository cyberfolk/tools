const fs = require("fs/promises");
const path = require("path");

function normalizePath(value) {
  return path.resolve(String(value)).replace(/\\/g, "/");
}

async function inspectPath(targetPath, parentId = null) {
  const resolved = path.resolve(targetPath);
  let stat;
  try {
    stat = await fs.lstat(resolved);
  } catch {
    throw new Error(`Percorso non valido: ${resolved}`);
  }

  const isSymlink = stat.isSymbolicLink();
  const isDirectory = !isSymlink && stat.isDirectory();
  let hasChildren = false;
  if (isDirectory) {
    try {
      const children = await fs.readdir(resolved);
      hasChildren = children.length > 0;
    } catch {
      hasChildren = false;
    }
  }

  return {
    id: normalizePath(resolved),
    path: normalizePath(resolved),
    name: path.basename(resolved) || normalizePath(resolved),
    kind: isSymlink ? "symlink" : isDirectory ? "directory" : "file",
    parentId: parentId ? normalizePath(parentId) : null,
    hasChildren,
    childrenLoaded: false,
    childrenIds: [],
    size: typeof stat.size === "number" ? stat.size : null,
    error: null,
  };
}

async function listDirectory(targetPath) {
  const resolved = path.resolve(targetPath);
  const entries = await fs.readdir(resolved, { withFileTypes: true });
  entries.sort((left, right) => {
    const leftDir = left.isDirectory() ? 0 : 1;
    const rightDir = right.isDirectory() ? 0 : 1;
    if (leftDir !== rightDir) {
      return leftDir - rightDir;
    }
    return left.name.localeCompare(right.name, undefined, { sensitivity: "base" });
  });

  const children = [];
  for (const entry of entries) {
    children.push(await inspectPath(path.join(resolved, entry.name), resolved));
  }
  return children;
}

module.exports = {
  inspectPath,
  listDirectory,
  normalizePath,
};
