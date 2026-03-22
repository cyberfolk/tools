#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Core engine per generare dump testuali da file e cartelle."""

import datetime
import html
import os
from pathlib import Path

try:
    from .selection_model import NormalizedSelection, is_same_or_child, normalize_path
except ImportError:  # pragma: no cover - supporto avvio come script
    from dump_folder.engine.selection_model import NormalizedSelection, is_same_or_child, normalize_path


class DumpConfig:
    """Configurazione base per il dump."""

    OUTPUT_EXTENSIONS = {
        "txt": ".txt",
        "md": ".md",
        "html": ".html",
    }

    SEPARATOR = "=" * 60

    EXCLUDED_DIRS = {
        ".git",
        ".venv",
        "venv",
        "node_modules",
        "__pycache__",
        ".idea",
        ".vscode",
        "scratch",
    }

    EXCLUDED_FILES = {
        ".gitignore",
        ".gitmodules",
        ".gitattributes",
    }

    TEXT_EXTENSIONS = {
        ".txt",
        ".md",
        ".py",
        ".json",
        ".yaml",
        ".yml",
        ".xml",
        ".html",
        ".css",
        ".js",
        ".ts",
        ".ini",
        ".cfg",
        ".csv",
        ".sql",
        ".rst",
    }

    SYMLINK_POLICY = "ignore"
    LARGE_FILE_WARNING_BYTES = 2 * 1024 * 1024
    SKIP_LARGE_FILES = False

def is_binary(path, config=DumpConfig):
    return Path(path).suffix.lower() not in config.TEXT_EXTENSIONS


def read_text_file(file_path):
    with open(file_path, "r", encoding="utf-8", errors="strict") as file_obj:
        return file_obj.read().rstrip()


def html_escape(text):
    return html.escape(text, quote=True)


def get_code_fence_language(file_path):
    ext = Path(file_path).suffix.lower()

    mapping = {
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
    }
    return mapping.get(ext, "")


def collect_files_from_inputs(selected_paths, output_path=None, config=DumpConfig):
    """Espande file/cartelle selezionati in una lista di file ordinata e deduplicata."""
    output_path = Path(output_path).resolve() if output_path else None
    seen = set()
    collected = []

    for raw_path in selected_paths:
        path = Path(raw_path).resolve()

        if not path.exists():
            continue

        if path.is_file():
            if output_path and path == output_path:
                continue
            if path.name in config.EXCLUDED_FILES:
                continue
            if path not in seen:
                seen.add(path)
                collected.append(path)
            continue

        for root, dirs, files in os.walk(path):
            dirs[:] = sorted(d for d in dirs if d not in config.EXCLUDED_DIRS)
            for file_name in sorted(files):
                if file_name in config.EXCLUDED_FILES:
                    continue
                file_path = Path(root) / file_name
                resolved = file_path.resolve()
                if output_path and resolved == output_path:
                    continue
                if resolved not in seen:
                    seen.add(resolved)
                    collected.append(resolved)

    return sorted(collected, key=lambda item: normalize_path(str(item)).lower())


class DumpManifest:
    def __init__(self, files=None, directories=None, estimated_size=0, estimated_output_size=0, warnings=None):
        self.files = files or []
        self.directories = directories or []
        self.estimated_size = estimated_size
        self.estimated_output_size = estimated_output_size
        self.warnings = warnings or []


def _estimate_text_output_bytes(content):
    return len(content.encode("utf-8", errors="strict"))


def estimate_output_size(files, selected_paths, output_format="txt", config=DumpConfig):
    output_format = output_format.lower().strip()
    timestamp = datetime.datetime.now().isoformat(timespec="seconds")
    selected_paths = [Path(path).resolve() for path in selected_paths]

    if output_format == "txt":
        total = len((config.SEPARATOR + "\n").encode("utf-8"))
        total += len(f"# DUMP GENERATO IL: {timestamp}\n".encode("utf-8"))
        total += len("# SORGENTI:\n".encode("utf-8"))
        for source in selected_paths:
            total += len(f"# - {normalize_path(str(source))}\n".encode("utf-8"))
        total += len((config.SEPARATOR + "\n\n").encode("utf-8"))
    elif output_format == "md":
        total = len("# Dump selezione\n\n".encode("utf-8"))
        total += len(f"Generato il: `{timestamp}`\n\n".encode("utf-8"))
        total += len("## Sorgenti\n".encode("utf-8"))
        for source in selected_paths:
            total += len(f"- `{normalize_path(str(source))}`\n".encode("utf-8"))
        total += len("\n---\n".encode("utf-8"))
    else:
        html_header = """<!doctype html>
<html lang="it">
<head>
    <meta charset="utf-8">
    <title>Dump selezione</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 24px; line-height: 1.4; }
        h1 { margin-bottom: 8px; }
        .meta { color: #555; margin-bottom: 24px; }
        details {
            border: 1px solid #ccc; border-radius: 6px; padding: 8px 12px;
            margin-bottom: 12px; background: #fafafa;
        }
        summary { cursor: pointer; font-weight: bold; }
        pre {
            background: #f4f4f4; padding: 12px; border-radius: 4px;
            overflow-x: auto; white-space: pre-wrap; word-break: break-word;
        }
        .binary { color: #7a5c00; font-style: italic; margin-top: 8px; }
        .error { color: #a40000; font-weight: bold; margin-top: 8px; }
    </style>
</head>
<body>
"""
        total = len(html_header.encode("utf-8"))
        total += len("<h1>Dump selezione</h1>\n".encode("utf-8"))
        meta_start = f"<div class='meta'><div><strong>Generato il:</strong> {html_escape(timestamp)}</div>"
        total += len(meta_start.encode("utf-8"))
        total += len("<div><strong>Sorgenti:</strong></div><ul>".encode("utf-8"))
        for source in selected_paths:
            total += len(f"<li>{html_escape(normalize_path(str(source)))}</li>".encode("utf-8"))
        total += len("</ul></div>\n".encode("utf-8"))

    for file_path in files:
        display_path = _display_path(file_path, selected_paths)
        if output_format == "txt":
            total += len(("\n" + config.SEPARATOR + "\n").encode("utf-8"))
            total += len(f"# FILE: {display_path}\n".encode("utf-8"))
            total += len((config.SEPARATOR + "\n\n").encode("utf-8"))
            if is_binary(file_path, config):
                total += len(f"[BINARIO NON INCLUSO: {Path(file_path).name}]\n\n".encode("utf-8"))
            else:
                try:
                    total += _estimate_text_output_bytes(read_text_file(file_path) + "\n\n")
                except Exception as exc:  # pragma: no cover
                    total += len(f"[ERRORE LETTURA FILE]\n{repr(exc)}\n\n".encode("utf-8"))
        elif output_format == "md":
            total += len(f"\n## `{display_path}`\n\n".encode("utf-8"))
            if is_binary(file_path, config):
                total += len(f"`[BINARIO NON INCLUSO: {Path(file_path).name}]`\n\n".encode("utf-8"))
            else:
                try:
                    content = read_text_file(file_path)
                    lang = get_code_fence_language(file_path)
                    total += len(f"```{lang}\n".encode("utf-8"))
                    total += _estimate_text_output_bytes(content)
                    total += len("\n```\n\n".encode("utf-8"))
                except Exception as exc:  # pragma: no cover
                    total += len(f"```text\n[ERRORE LETTURA FILE]\n{repr(exc)}\n```\n\n".encode("utf-8"))
        else:
            total += len(f"<details>\n<summary>{html_escape(display_path)}</summary>\n".encode("utf-8"))
            if is_binary(file_path, config):
                total += len(f"<div class='binary'>[BINARIO NON INCLUSO: {html_escape(Path(file_path).name)}]</div>\n".encode("utf-8"))
                total += len("</details>\n".encode("utf-8"))
            else:
                try:
                    content = read_text_file(file_path)
                    total += len("<pre><code>".encode("utf-8"))
                    total += len(html_escape(content).encode("utf-8"))
                    total += len("</code></pre>\n</details>\n".encode("utf-8"))
                except Exception as exc:  # pragma: no cover
                    total += len("<div class='error'>[ERRORE LETTURA FILE]</div>\n".encode("utf-8"))
                    total += len(f"<pre><code>{html_escape(repr(exc))}</code></pre>\n</details>\n".encode("utf-8"))

    if output_format == "html":
        total += len("</body>\n</html>\n".encode("utf-8"))

    return total


def collect_manifest_from_selection(selection, output_path=None, config=DumpConfig):
    """Espande include/exclude in un manifest deterministico senza duplicati."""
    output_path = Path(output_path).resolve() if output_path else None
    seen_files = set()
    seen_directories = set()
    files = []
    directories = []
    warnings = []
    estimated_size = 0
    includes = [Path(path).absolute() for path in selection.includes]
    excludes = [normalize_path(str(Path(path).absolute())) for path in selection.excludes]

    def is_excluded(path):
        normalized = normalize_path(str(Path(path).absolute()))
        return any(is_same_or_child(normalized, excluded) for excluded in excludes)

    def should_skip_common(path, explicitly_included=False):
        if explicitly_included:
            return False
        if path.is_dir():
            return path.name in config.EXCLUDED_DIRS
        return path.name in config.EXCLUDED_FILES

    def register_file(file_path):
        nonlocal estimated_size
        resolved = Path(file_path).absolute()
        normalized = normalize_path(str(resolved))
        if normalized in seen_files or is_excluded(resolved):
            return
        if output_path and resolved == output_path:
            return
        if resolved.name in config.EXCLUDED_FILES and normalized not in selection.includes:
            return

        try:
            size = resolved.stat().st_size
        except OSError as exc:
            warnings.append(f"Lettura metadata fallita per {normalized}: {exc}")
            size = 0

        large_threshold = getattr(config, "LARGE_FILE_WARNING_BYTES", None)
        if large_threshold and size > large_threshold:
            warnings.append(f"File grande rilevato: {normalized} ({size} bytes)")
            if getattr(config, "SKIP_LARGE_FILES", False):
                return

        seen_files.add(normalized)
        files.append(resolved)
        estimated_size += size

    def register_directory(directory_path):
        resolved = Path(directory_path).absolute()
        normalized = normalize_path(str(resolved))
        if normalized in seen_directories or is_excluded(resolved):
            return
        seen_directories.add(normalized)
        directories.append(resolved)

    def handle_symlink(link_path):
        policy = getattr(config, "SYMLINK_POLICY", "ignore")
        normalized = normalize_path(str(Path(link_path).absolute()))
        if policy == "ignore":
            warnings.append(f"Symlink ignorato: {normalized}")
            return
        if policy == "treat-as-entry":
            warnings.append(f"Symlink incluso come entry speciale: {normalized}")
            register_file(link_path)
            return
        try:
            target = Path(link_path).resolve()
        except OSError as exc:
            warnings.append(f"Symlink non risolto {normalized}: {exc}")
            return
        warnings.append(f"Symlink seguito: {normalized}")
        visit_path(target, explicitly_included=True)

    def visit_path(path, explicitly_included=False):
        raw_path = Path(path).absolute()
        normalized = normalize_path(str(raw_path))
        resolved = raw_path.resolve()
        if not raw_path.exists():
            warnings.append(f"Percorso non trovato: {normalized}")
            return
        if is_excluded(raw_path):
            return
        if should_skip_common(raw_path, explicitly_included=explicitly_included):
            return
        if raw_path.is_symlink():
            handle_symlink(raw_path)
            return
        if resolved.is_file():
            register_file(resolved)
            return
        if resolved.is_dir():
            register_directory(resolved)

            def on_error(exc):
                failed_name = normalize_path(exc.filename) if getattr(exc, "filename", None) else normalized
                warnings.append(f"Accesso negato o fallito su {failed_name}: {exc}")

            for root, dir_names, file_names in os.walk(resolved, onerror=on_error, followlinks=False):
                current_root = Path(root).absolute()
                if is_excluded(current_root):
                    dir_names[:] = []
                    continue
                register_directory(current_root)

                pruned_dirs = []
                for dir_name in sorted(dir_names):
                    child_dir = current_root / dir_name
                    child_normalized = normalize_path(str(child_dir.absolute()))
                    explicit_child_include = child_normalized in selection.includes
                    if is_excluded(child_dir):
                        continue
                    if dir_name in config.EXCLUDED_DIRS and not explicit_child_include:
                        continue
                    pruned_dirs.append(dir_name)
                dir_names[:] = pruned_dirs

                for file_name in sorted(file_names):
                    file_path = current_root / file_name
                    explicit_file_include = normalize_path(str(file_path.absolute())) in selection.includes
                    if file_name in config.EXCLUDED_FILES and not explicit_file_include:
                        continue
                    register_file(file_path)

    for included_path in sorted(includes, key=lambda item: normalize_path(str(item)).lower()):
        visit_path(included_path, explicitly_included=True)

    files.sort(key=lambda item: normalize_path(str(item)).lower())
    directories.sort(key=lambda item: normalize_path(str(item)).lower())
    estimated_output_size = estimate_output_size(files, includes, output_format="txt", config=config)
    warnings = sorted(set(warnings))
    return DumpManifest(
        files=files,
        directories=directories,
        estimated_size=estimated_size,
        estimated_output_size=estimated_output_size,
        warnings=warnings,
    )


def _display_path(file_path, selected_roots):
    file_path = Path(file_path)
    matching_roots = [root for root in selected_roots if file_path == root or root in file_path.parents]

    if matching_roots:
        best_root = max(matching_roots, key=lambda root: len(str(root)))
        if file_path == best_root:
            return normalize_path(file_path.name)
        rel = file_path.relative_to(best_root)
        return normalize_path(f"{best_root.name}/{rel}")

    return normalize_path(str(file_path))


def write_txt_header(out, selected_paths, timestamp, config=DumpConfig):
    out.write(config.SEPARATOR + "\n")
    out.write(f"# DUMP GENERATO IL: {timestamp}\n")
    out.write("# SORGENTI:\n")
    for source in selected_paths:
        out.write(f"# - {normalize_path(str(source))}\n")
    out.write(config.SEPARATOR + "\n\n")


def write_txt_file_dump(out, file_path, display_path, config=DumpConfig):
    out.write("\n" + config.SEPARATOR + "\n")
    out.write(f"# FILE: {display_path}\n")
    out.write(config.SEPARATOR + "\n\n")

    if is_binary(file_path, config):
        out.write(f"[BINARIO NON INCLUSO: {Path(file_path).name}]\n\n")
        return

    try:
        out.write(read_text_file(file_path) + "\n\n")
    except Exception as exc:  # pragma: no cover - gestione errori runtime
        out.write(f"[ERRORE LETTURA FILE]\n{repr(exc)}\n\n")


def write_md_header(out, selected_paths, timestamp):
    out.write("# Dump selezione\n\n")
    out.write(f"Generato il: `{timestamp}`\n\n")
    out.write("## Sorgenti\n")
    for source in selected_paths:
        out.write(f"- `{normalize_path(str(source))}`\n")
    out.write("\n---\n")


def write_md_file_dump(out, file_path, display_path, config=DumpConfig):
    out.write(f"\n## `{display_path}`\n\n")

    if is_binary(file_path, config):
        out.write(f"`[BINARIO NON INCLUSO: {Path(file_path).name}]`\n\n")
        return

    try:
        content = read_text_file(file_path)
        lang = get_code_fence_language(file_path)
        out.write(f"```{lang}\n{content}\n```\n\n")
    except Exception as exc:  # pragma: no cover - gestione errori runtime
        out.write(f"```text\n[ERRORE LETTURA FILE]\n{repr(exc)}\n```\n\n")


def write_html_header(out, selected_paths, timestamp):
    out.write("""<!doctype html>
<html lang="it">
<head>
    <meta charset="utf-8">
    <title>Dump selezione</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 24px; line-height: 1.4; }
        h1 { margin-bottom: 8px; }
        .meta { color: #555; margin-bottom: 24px; }
        details {
            border: 1px solid #ccc; border-radius: 6px; padding: 8px 12px;
            margin-bottom: 12px; background: #fafafa;
        }
        summary { cursor: pointer; font-weight: bold; }
        pre {
            background: #f4f4f4; padding: 12px; border-radius: 4px;
            overflow-x: auto; white-space: pre-wrap; word-break: break-word;
        }
        .binary { color: #7a5c00; font-style: italic; margin-top: 8px; }
        .error { color: #a40000; font-weight: bold; margin-top: 8px; }
    </style>
</head>
<body>
""")
    out.write("<h1>Dump selezione</h1>\n")
    out.write(f"<div class='meta'><div><strong>Generato il:</strong> {html_escape(timestamp)}</div>")
    out.write("<div><strong>Sorgenti:</strong></div><ul>")
    for source in selected_paths:
        out.write(f"<li>{html_escape(normalize_path(str(source)))}</li>")
    out.write("</ul></div>\n")


def write_html_file_dump(out, file_path, display_path, config=DumpConfig):
    out.write(f"<details>\n<summary>{html_escape(display_path)}</summary>\n")

    if is_binary(file_path, config):
        out.write(f"<div class='binary'>[BINARIO NON INCLUSO: {html_escape(Path(file_path).name)}]</div>\n")
        out.write("</details>\n")
        return

    try:
        content = read_text_file(file_path)
        out.write(f"<pre><code>{html_escape(content)}</code></pre>\n")
    except Exception as exc:  # pragma: no cover - gestione errori runtime
        out.write("<div class='error'>[ERRORE LETTURA FILE]</div>\n")
        out.write(f"<pre><code>{html_escape(repr(exc))}</code></pre>\n")

    out.write("</details>\n")


def write_html_footer(out):
    out.write("</body>\n</html>\n")


def generate_dump(selected_paths, output_path, output_format="txt", config=DumpConfig):
    """Genera il dump in base agli elementi selezionati."""
    if not selected_paths:
        raise ValueError("Nessun file o cartella selezionato.")

    output_format = output_format.lower().strip()
    if output_format not in config.OUTPUT_EXTENSIONS:
        raise ValueError(
            f"Formato non valido: {output_format}. "
            f"Formati supportati: {', '.join(config.OUTPUT_EXTENSIONS)}"
        )

    output_path = Path(output_path).resolve()
    if output_path.suffix.lower() != config.OUTPUT_EXTENSIONS[output_format]:
        output_path = output_path.with_suffix(config.OUTPUT_EXTENSIONS[output_format])

    if isinstance(selected_paths, NormalizedSelection):
        selection = selected_paths
        normalized_inputs = [Path(path).resolve() for path in selection.includes]
        display_roots = [Path(path).resolve() for path in (selection.roots or selection.includes)]
        manifest = collect_manifest_from_selection(selection, output_path=output_path, config=config)
        files = manifest.files
    else:
        normalized_inputs = [Path(path).resolve() for path in selected_paths]
        display_roots = normalized_inputs
        files = collect_files_from_inputs(normalized_inputs, output_path=output_path, config=config)
    if not files:
        raise ValueError("Nessun file valido trovato nella selezione.")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.datetime.now().isoformat(timespec="seconds")

    with open(output_path, "w", encoding="utf-8", errors="strict") as out:
        if output_format == "txt":
            write_txt_header(out, normalized_inputs, timestamp, config)
            for file_path in files:
                write_txt_file_dump(out, file_path, _display_path(file_path, display_roots), config)
        elif output_format == "md":
            write_md_header(out, normalized_inputs, timestamp)
            for file_path in files:
                write_md_file_dump(out, file_path, _display_path(file_path, display_roots), config)
        else:
            write_html_header(out, normalized_inputs, timestamp)
            for file_path in files:
                write_html_file_dump(out, file_path, _display_path(file_path, display_roots), config)
            write_html_footer(out)

    return str(output_path)


def dump_folder(source_dir, output_format="txt", config=DumpConfig):
    """Compatibilità con la CLI storica: dump di una singola cartella."""
    source_dir = Path(source_dir).resolve()
    if not source_dir.is_dir():
        raise ValueError(f"Directory non valida: {source_dir}")

    extension = config.OUTPUT_EXTENSIONS.get(output_format.lower().strip())
    if not extension:
        raise ValueError(
            f"Formato non valido: {output_format}. "
            f"Formati supportati: {', '.join(config.OUTPUT_EXTENSIONS)}"
        )

    output_name = f"dump{extension}"
    output_path = source_dir / output_name
    return generate_dump([str(source_dir)], str(output_path), output_format=output_format, config=config)
