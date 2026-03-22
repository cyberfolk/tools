const fs = require("fs/promises");
const path = require("path");
const { normalizePath, isSameOrChild } = require("./selection-model");

const FORMAT_EXTENSIONS = {
  txt: ".txt",
  md: ".md",
  html: ".html",
};

const SEPARATOR = "=".repeat(60);
const EXCLUDED_DIRS = new Set([".git", ".venv", "venv", "node_modules", "__pycache__", ".idea", ".vscode", "scratch"]);
const EXCLUDED_FILES = new Set([".gitignore", ".gitmodules", ".gitattributes"]);
const TEXT_EXTENSIONS = new Set([
  ".txt", ".md", ".py", ".json", ".yaml", ".yml", ".xml", ".html", ".css",
  ".js", ".ts", ".ini", ".cfg", ".csv", ".sql", ".rst", ".sh",
]);
const LARGE_FILE_WARNING_BYTES = 2 * 1024 * 1024;

function humanSize(size) {
  if (size <= 0) {
    return "0 B";
  }
  const units = ["B", "KB", "MB", "GB", "TB"];
  let value = Number(size);
  for (const unit of units) {
    if (value < 1024 || unit === units[units.length - 1]) {
      return unit === "B" ? `${Math.trunc(value)} B` : `${value.toFixed(1)} ${unit}`;
    }
    value /= 1024;
  }
  return `${Math.trunc(size)} B`;
}

async function pathExists(targetPath) {
  try {
    await fs.access(targetPath);
    return true;
  } catch {
    return false;
  }
}

async function statOrNull(targetPath, useLstat = false) {
  try {
    return useLstat ? await fs.lstat(targetPath) : await fs.stat(targetPath);
  } catch {
    return null;
  }
}

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

async function isBinary(filePath) {
  return !TEXT_EXTENSIONS.has(path.extname(filePath).toLowerCase());
}

async function readTextFile(filePath) {
  const content = await fs.readFile(filePath, "utf8");
  return content.replace(/\s+$/u, "");
}

function getCodeFenceLanguage(filePath) {
  const ext = path.extname(filePath).toLowerCase();
  const mapping = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".json": "json",
    ".md": "md",
    ".html": "html",
    ".css": "css",
    ".xml": "xml",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".sql": "sql",
    ".sh": "bash",
    ".rst": "rst",
    ".ini": "ini",
    ".cfg": "ini",
    ".txt": "text",
    ".csv": "csv",
  };
  return mapping[ext] || "";
}

function displayPath(filePath, selectedRoots) {
  const resolvedFile = path.resolve(filePath);
  const matchingRoots = selectedRoots.filter((root) => resolvedFile === root || resolvedFile.startsWith(`${root}${path.sep}`));
  if (!matchingRoots.length) {
    return normalizePath(resolvedFile);
  }
  const bestRoot = matchingRoots.sort((left, right) => right.length - left.length)[0];
  if (resolvedFile === bestRoot) {
    return normalizePath(path.basename(bestRoot));
  }
  return normalizePath(path.join(path.basename(bestRoot), path.relative(bestRoot, resolvedFile)));
}

async function walkDirectory(rootPath, visitor, onError) {
  let entries;
  try {
    entries = await fs.readdir(rootPath, { withFileTypes: true });
  } catch (error) {
    onError?.(error, rootPath);
    return;
  }

  entries.sort((left, right) => {
    const leftDir = left.isDirectory() ? 0 : 1;
    const rightDir = right.isDirectory() ? 0 : 1;
    if (leftDir !== rightDir) {
      return leftDir - rightDir;
    }
    return left.name.localeCompare(right.name, undefined, { sensitivity: "base" });
  });

  for (const entry of entries) {
    await visitor(entry, path.join(rootPath, entry.name));
  }
}

async function collectManifestFromSelection(selection, outputPath = "", format = "txt") {
  const normalizedSelection = {
    includes: Array.isArray(selection?.includes) ? selection.includes.map((item) => path.resolve(item)) : [],
    excludes: Array.isArray(selection?.excludes) ? selection.excludes.map((item) => normalizePath(item)) : [],
  };

  const outputExtension = FORMAT_EXTENSIONS[format] || ".txt";
  const resolvedOutput = outputPath
    ? path.join(path.parse(path.resolve(outputPath)).dir, `${path.parse(path.resolve(outputPath)).name}${outputExtension}`)
    : null;

  const seenFiles = new Set();
  const seenDirectories = new Set();
  const files = [];
  const directories = [];
  const warnings = [];
  let estimatedSize = 0;

  const isExcluded = (targetPath) => normalizedSelection.excludes.some((excluded) => isSameOrChild(targetPath, excluded));

  async function registerFile(filePath) {
    const resolved = path.resolve(filePath);
    const normalized = normalizePath(resolved);
    if (seenFiles.has(normalized) || isExcluded(normalized)) {
      return;
    }
    if (resolvedOutput && normalizePath(resolvedOutput) === normalized) {
      return;
    }
    if (EXCLUDED_FILES.has(path.basename(resolved)) && !normalizedSelection.includes.includes(resolved)) {
      return;
    }

    const stat = await statOrNull(resolved);
    const size = stat?.size || 0;
    if (!stat) {
      warnings.push(`Lettura metadata fallita per ${normalized}`);
    }
    if (size > LARGE_FILE_WARNING_BYTES) {
      warnings.push(`File grande rilevato: ${normalized} (${size} bytes)`);
    }

    seenFiles.add(normalized);
    files.push(normalized);
    estimatedSize += size;
  }

  async function visitPath(targetPath, explicitlyIncluded = false) {
    const rawPath = path.resolve(targetPath);
    const normalized = normalizePath(rawPath);
    if (!(await pathExists(rawPath))) {
      warnings.push(`Percorso non trovato: ${normalized}`);
      return;
    }
    if (isExcluded(normalized)) {
      return;
    }

    const baseName = path.basename(rawPath);
    if (!explicitlyIncluded && (EXCLUDED_DIRS.has(baseName) || EXCLUDED_FILES.has(baseName))) {
      return;
    }

    const lstat = await statOrNull(rawPath, true);
    if (!lstat) {
      warnings.push(`Accesso negato o fallito su ${normalized}`);
      return;
    }
    if (lstat.isSymbolicLink()) {
      warnings.push(`Symlink ignorato: ${normalized}`);
      return;
    }

    const stat = await statOrNull(rawPath);
    if (!stat) {
      warnings.push(`Accesso negato o fallito su ${normalized}`);
      return;
    }

    if (stat.isFile()) {
      await registerFile(rawPath);
      return;
    }

    if (!stat.isDirectory()) {
      return;
    }

    if (!seenDirectories.has(normalized)) {
      seenDirectories.add(normalized);
      directories.push(normalized);
    }

    await walkDirectory(
      rawPath,
      async (entry, entryPath) => {
        const entryNormalized = normalizePath(entryPath);
        const explicitChildInclude = normalizedSelection.includes.includes(path.resolve(entryPath));
        if (isExcluded(entryNormalized)) {
          return;
        }
        if (entry.isDirectory()) {
          if (EXCLUDED_DIRS.has(entry.name) && !explicitChildInclude) {
            return;
          }
          await visitPath(entryPath, explicitChildInclude);
          return;
        }
        if (EXCLUDED_FILES.has(entry.name) && !explicitChildInclude) {
          return;
        }
        await registerFile(entryPath);
      },
      (error, failedPath) => {
        warnings.push(`Accesso negato o fallito su ${normalizePath(failedPath)}: ${error.message}`);
      },
    );
  }

  const orderedIncludes = [...normalizedSelection.includes].sort((left, right) =>
    normalizePath(left).localeCompare(normalizePath(right), undefined, { sensitivity: "base" }),
  );
  for (const includePath of orderedIncludes) {
    await visitPath(includePath, true);
  }

  files.sort((left, right) => left.localeCompare(right, undefined, { sensitivity: "base" }));
  directories.sort((left, right) => left.localeCompare(right, undefined, { sensitivity: "base" }));

  return {
    files,
    directories,
    estimatedSize,
    estimatedSizeLabel: humanSize(estimatedSize),
    warnings: [...new Set(warnings)].sort(),
  };
}

async function renderTxt(files, selectedRoots) {
  let output = `${SEPARATOR}\n# DUMP GENERATO IL: ${new Date().toISOString().slice(0, 19)}\n# SORGENTI:\n`;
  for (const source of selectedRoots) {
    output += `# - ${normalizePath(source)}\n`;
  }
  output += `${SEPARATOR}\n\n`;

  for (const filePath of files) {
    output += `\n${SEPARATOR}\n# FILE: ${displayPath(filePath, selectedRoots)}\n${SEPARATOR}\n\n`;
    if (await isBinary(filePath)) {
      output += `[BINARIO NON INCLUSO: ${path.basename(filePath)}]\n\n`;
      continue;
    }
    try {
      output += `${await readTextFile(filePath)}\n\n`;
    } catch (error) {
      output += `[ERRORE LETTURA FILE]\n${String(error)}\n\n`;
    }
  }
  return output;
}

async function renderMd(files, selectedRoots) {
  let output = "# Dump selezione\n\n";
  output += `Generato il: \`${new Date().toISOString().slice(0, 19)}\`\n\n`;
  output += "## Sorgenti\n";
  for (const source of selectedRoots) {
    output += `- \`${normalizePath(source)}\`\n`;
  }
  output += "\n---\n";

  for (const filePath of files) {
    output += `\n## \`${displayPath(filePath, selectedRoots)}\`\n\n`;
    if (await isBinary(filePath)) {
      output += `\`[BINARIO NON INCLUSO: ${path.basename(filePath)}]\`\n\n`;
      continue;
    }
    try {
      output += `\`\`\`${getCodeFenceLanguage(filePath)}\n${await readTextFile(filePath)}\n\`\`\`\n\n`;
    } catch (error) {
      output += `\`\`\`text\n[ERRORE LETTURA FILE]\n${String(error)}\n\`\`\`\n\n`;
    }
  }

  return output;
}

async function renderHtml(files, selectedRoots) {
  let output = "<!doctype html>\n<html lang=\"it\">\n<head>\n<meta charset=\"utf-8\">\n<title>Dump selezione</title>\n";
  output += "<style>body{font-family:Arial,sans-serif;margin:24px;line-height:1.4;}details{border:1px solid #ccc;border-radius:6px;padding:8px 12px;margin-bottom:12px;background:#fafafa;}summary{cursor:pointer;font-weight:bold;}pre{background:#f4f4f4;padding:12px;border-radius:4px;overflow-x:auto;white-space:pre-wrap;word-break:break-word;}.binary{color:#7a5c00;font-style:italic;margin-top:8px;}.error{color:#a40000;font-weight:bold;margin-top:8px;}</style>\n";
  output += "</head>\n<body>\n<h1>Dump selezione</h1>\n";
  output += `<div><strong>Generato il:</strong> ${escapeHtml(new Date().toISOString().slice(0, 19))}</div>`;
  output += "<div><strong>Sorgenti:</strong></div><ul>";
  for (const source of selectedRoots) {
    output += `<li>${escapeHtml(normalizePath(source))}</li>`;
  }
  output += "</ul>\n";

  for (const filePath of files) {
    output += `<details>\n<summary>${escapeHtml(displayPath(filePath, selectedRoots))}</summary>\n`;
    if (await isBinary(filePath)) {
      output += `<div class="binary">[BINARIO NON INCLUSO: ${escapeHtml(path.basename(filePath))}]</div>\n</details>\n`;
      continue;
    }
    try {
      output += `<pre><code>${escapeHtml(await readTextFile(filePath))}</code></pre>\n`;
    } catch (error) {
      output += `<div class="error">[ERRORE LETTURA FILE]</div>\n<pre><code>${escapeHtml(String(error))}</code></pre>\n`;
    }
    output += "</details>\n";
  }

  output += "</body>\n</html>\n";
  return output;
}

async function generateDump(selection, outputPath, format = "txt") {
  if (!selection?.includes?.length) {
    throw new Error("Seleziona almeno un file o una cartella nel tree.");
  }
  if (!outputPath) {
    throw new Error("Seleziona il file di output.");
  }

  const normalizedFormat = String(format || "txt").toLowerCase().trim();
  if (!FORMAT_EXTENSIONS[normalizedFormat]) {
    throw new Error(`Formato non valido: ${normalizedFormat}. Formati supportati: ${Object.keys(FORMAT_EXTENSIONS).join(", ")}`);
  }

  const parsedOutput = path.parse(path.resolve(outputPath));
  const finalOutput = path.join(parsedOutput.dir, `${parsedOutput.name}${FORMAT_EXTENSIONS[normalizedFormat]}`);
  const manifest = await collectManifestFromSelection(selection, finalOutput, normalizedFormat);
  if (!manifest.files.length) {
    throw new Error("Nessun file valido trovato nella selezione.");
  }

  const selectedRoots = selection.includes.map((item) => path.resolve(item));
  const rendered =
    normalizedFormat === "txt"
      ? await renderTxt(manifest.files, selectedRoots)
      : normalizedFormat === "md"
        ? await renderMd(manifest.files, selectedRoots)
        : await renderHtml(manifest.files, selectedRoots);

  await fs.mkdir(path.dirname(finalOutput), { recursive: true });
  await fs.writeFile(finalOutput, rendered, "utf8");
  return finalOutput;
}

module.exports = {
  collectManifestFromSelection,
  FORMAT_EXTENSIONS,
  generateDump,
  humanSize,
};
