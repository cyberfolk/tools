#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import datetime
import html

"""
Dump ricorsivo di una directory in un singolo file.

Formati supportati:
- txt
- md
- html

Uso:
    dump_folder
    dump_folder .
    dump_folder . txt
    dump_folder . md
    dump_folder . html
"""


# ======================================================================================================================
# CONFIG
# ======================================================================================================================
# fmt: off
class DumpConfig:
    OUTPUT_NAMES = {
        "txt": "dump.txt",
        "md": "dump.md",
        "html": "dump.html",
    }

    SEPARATOR = "=" * 60

    EXCLUDED_DIRS = {
        ".git", ".venv", "venv", "node_modules",
        "__pycache__", ".idea", ".vscode", "scratch"
    }

    EXCLUDED_FILES = {
        ".gitignore", ".gitmodules", ".gitattributes"
    }

    TEXT_EXTENSIONS = {
        ".txt", ".md", ".py", ".json", ".yaml", ".yml",
        ".xml", ".html", ".css", ".js", ".ts",
        ".ini", ".cfg", ".csv", ".sql", ".rst",
    }
# fmt: on


# ======================================================================================================================
# UTILS
# ======================================================================================================================
def normalize_rel_path(file_path, base_dir):
    return os.path.relpath(file_path, start=base_dir).replace("\\", "/")


def is_binary(path, config=DumpConfig):
    return os.path.splitext(path)[1].lower() not in config.TEXT_EXTENSIONS


def collect_files(base_dir, output_name_to_skip=None, config=DumpConfig):
    """
    Raccoglie ricorsivamente i file sotto base_dir.
    - Esclude le directory definite in config.EXCLUDED_DIRS
    - Esclude il file di output corrente
    - Restituisce una lista di path ordinata in modo deterministico
    """
    collected = []

    for root, dirs, files in os.walk(base_dir):
        dirs[:] = sorted(d for d in dirs if d not in config.EXCLUDED_DIRS)

        for fname in sorted(files):
            if output_name_to_skip and fname == output_name_to_skip:
                continue
            if fname in config.EXCLUDED_FILES:
                continue
            collected.append(os.path.join(root, fname))

    return collected


def read_text_file(file_path):
    with open(file_path, "r", encoding="utf-8", errors="strict") as f:
        return f.read().rstrip()


def get_code_fence_language(file_path):
    ext = os.path.splitext(file_path)[1].lower()

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


def html_escape(text):
    return html.escape(text, quote=True)


# ======================================================================================================================
# WRITER TXT
# ======================================================================================================================
def write_txt_header(out, source_dir, timestamp, config=DumpConfig):
    out.write(config.SEPARATOR + "\n")
    out.write(f"# DUMP GENERATO IL: {timestamp}\n")
    out.write(f"# DIRECTORY: {source_dir}\n")
    out.write(config.SEPARATOR + "\n\n")


def write_txt_file_dump(out, file_path, base_dir, config=DumpConfig):
    rel_path = normalize_rel_path(file_path, base_dir)

    out.write("\n" + config.SEPARATOR + "\n")
    out.write(f"# FILE: {rel_path}\n")
    out.write(config.SEPARATOR + "\n\n")

    if is_binary(file_path, config):
        out.write(f"[BINARIO NON INCLUSO: {os.path.basename(file_path)}]\n\n")
        return

    try:
        out.write(read_text_file(file_path) + "\n\n")
    except Exception as e:
        out.write(f"[ERRORE LETTURA FILE]\n{repr(e)}\n\n")


# ======================================================================================================================
# WRITER MD
# ======================================================================================================================
def write_md_header(out, source_dir, timestamp, _config=DumpConfig):
    out.write(f"# Dump cartella `{source_dir}`\n\n")
    out.write(f"Generato il: `{timestamp}`\n\n")
    out.write("---\n")


def write_md_file_dump(out, file_path, base_dir, config=DumpConfig):
    rel_path = normalize_rel_path(file_path, base_dir)

    out.write(f"\n## `{rel_path}`\n\n")

    if is_binary(file_path, config):
        out.write(f"`[BINARIO NON INCLUSO: {os.path.basename(file_path)}]`\n\n")
        return

    try:
        content = read_text_file(file_path)
        lang = get_code_fence_language(file_path)
        out.write(f"```{lang}\n{content}\n```\n\n")
    except Exception as e:
        out.write(f"```text\n[ERRORE LETTURA FILE]\n{repr(e)}\n```\n\n")


# ======================================================================================================================
# WRITER HTML
# ======================================================================================================================
def write_html_header(out, source_dir, timestamp, _config=DumpConfig):
    out.write("""<!doctype html>
<html lang="it">
<head>
    <meta charset="utf-8">
    <title>Dump cartella</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 24px;
            line-height: 1.4;
        }
        h1 {
            margin-bottom: 8px;
        }
        .meta {
            color: #555;
            margin-bottom: 24px;
        }
        details {
            border: 1px solid #ccc;
            border-radius: 6px;
            padding: 8px 12px;
            margin-bottom: 12px;
            background: #fafafa;
        }
        summary {
            cursor: pointer;
            font-weight: bold;
        }
        pre {
            background: #f4f4f4;
            padding: 12px;
            border-radius: 4px;
            overflow-x: auto;
            white-space: pre-wrap;
            word-break: break-word;
        }
        .binary {
            color: #7a5c00;
            font-style: italic;
            margin-top: 8px;
        }
        .error {
            color: #a40000;
            font-weight: bold;
            margin-top: 8px;
        }
    </style>
</head>
<body>
""")
    out.write(f"<h1>Dump cartella</h1>\n")
    out.write(f"<div class='meta'><div><strong>Directory:</strong> {html_escape(source_dir)}</div>\n")
    out.write(f"<div><strong>Generato il:</strong> {html_escape(timestamp)}</div></div>\n")


def write_html_footer(out):
    out.write("</body>\n</html>\n")


def write_html_file_dump(out, file_path, base_dir, config=DumpConfig):
    rel_path = normalize_rel_path(file_path, base_dir)

    out.write(f"<details>\n<summary>{html_escape(rel_path)}</summary>\n")

    if is_binary(file_path, config):
        out.write(
            f"<div class='binary'>[BINARIO NON INCLUSO: {html_escape(os.path.basename(file_path))}]</div>\n"
        )
        out.write("</details>\n")
        return

    try:
        content = read_text_file(file_path)
        out.write(f"<pre><code>{html_escape(content)}</code></pre>\n")
    except Exception as e:
        out.write(f"<div class='error'>[ERRORE LETTURA FILE]</div>\n")
        out.write(f"<pre><code>{html_escape(repr(e))}</code></pre>\n")

    out.write("</details>\n")


# ======================================================================================================================
# CORE
# ======================================================================================================================
def dump_folder(source_dir, output_format="txt", config=DumpConfig):
    source_dir = os.path.abspath(source_dir)
    output_format = output_format.lower().strip()

    if output_format not in config.OUTPUT_NAMES:
        raise ValueError(
            f"Formato non valido: {output_format}. "
            f"Formati supportati: {', '.join(config.OUTPUT_NAMES)}"
        )

    if not os.path.isdir(source_dir):
        raise ValueError(f"Directory non valida: {source_dir}")

    output_name = config.OUTPUT_NAMES[output_format]
    output_path = os.path.join(source_dir, output_name)
    files = collect_files(source_dir, output_name_to_skip=output_name, config=config)
    timestamp = datetime.datetime.now().isoformat(timespec="seconds")

    with open(output_path, "w", encoding="utf-8", errors="strict") as out:
        if output_format == "txt":
            write_txt_header(out, source_dir, timestamp, config)
            for file_path in files:
                write_txt_file_dump(out, file_path, source_dir, config)

        elif output_format == "md":
            write_md_header(out, source_dir, timestamp, config)
            for file_path in files:
                write_md_file_dump(out, file_path, source_dir, config)

        elif output_format == "html":
            write_html_header(out, source_dir, timestamp, config)
            for file_path in files:
                write_html_file_dump(out, file_path, source_dir, config)
            write_html_footer(out)

    print(f"[OK] Dump creato: {output_path}")


# ======================================================================================================================
# CLI
# ======================================================================================================================
if __name__ == "__main__":
    folder = sys.argv[1] if len(sys.argv) > 1 else "."
    output_format = sys.argv[2] if len(sys.argv) > 2 else "txt"
    dump_folder(folder, output_format)