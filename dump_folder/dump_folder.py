#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import datetime

"""
Dump ricorsivo di una directory in un singolo file testuale.

- Ordine deterministico dei file
- Esclusione directory configurabile
- File binari sostituiti da placeholder
- Output pensato per consumo automatico (machine-oriented)
"""


# ======================================================================================================================
# CONFIG
# ======================================================================================================================
# fmt: off
class DumpConfig:
    OUTPUT_NAME = "dump.txt"
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


def is_binary(path, config=DumpConfig):
    return os.path.splitext(path)[1].lower() not in config.TEXT_EXTENSIONS


def collect_files(base_dir, config=DumpConfig):
    """
    Raccoglie ricorsivamente i file sotto base_dir.
    - Esclude le directory definite in config.EXCLUDED_DIRS
    - Esclude il file con nome (config.OUTPUT_NAME) generalmente 'dump.txt'
    - Restituisce una lista di path ordinata in modo deterministico
    """
    collected = []

    for root, dirs, files in os.walk(base_dir):
        # Modifica dirs in-place per impedire a os.walk di entrare nelle directory escluse
        dirs[:] = sorted(d for d in dirs if d not in config.EXCLUDED_DIRS)

        for fname in sorted(files):
            if fname == config.OUTPUT_NAME:
                continue
            if fname in config.EXCLUDED_FILES:
                continue
            collected.append(os.path.join(root, fname))

    return collected


def write_file_dump(out, file_path, base_dir, config=DumpConfig):
    # Normalizzazione path per output cross-platform
    rel_path = os.path.relpath(file_path, start=base_dir).replace("\\", "/")

    out.write("\n" + config.SEPARATOR + "\n")
    out.write(f"# FILE: {rel_path}\n")
    out.write(config.SEPARATOR + "\n\n")

    if is_binary(file_path, config):
        out.write(f"[BINARIO NON INCLUSO: {os.path.basename(file_path)}]\n\n")
        return

    try:
        with open(file_path, "r", encoding="utf-8", errors="strict") as f:
            out.write(f.read().rstrip() + "\n\n")
    except Exception as e:
        out.write(f"[ERRORE LETTURA FILE]\n{repr(e)}\n\n")


# ======================================================================================================================
# CORE
# ======================================================================================================================


def dump_folder(source_dir, config=DumpConfig):
    source_dir = os.path.abspath(source_dir)

    if not os.path.isdir(source_dir):
        raise ValueError(f"Directory non valida: {source_dir}")

    output_path = os.path.join(source_dir, config.OUTPUT_NAME)
    files = collect_files(source_dir, config)
    timestamp = datetime.datetime.now().isoformat(timespec="seconds")

    with open(output_path, "w", encoding="utf-8", errors="strict") as out:
        out.write(config.SEPARATOR + "\n")
        out.write(f"# DUMP GENERATO IL: {timestamp}\n")
        out.write(f"# DIRECTORY: {source_dir}\n")
        out.write(config.SEPARATOR + "\n\n")

        for file_path in files:
            write_file_dump(out, file_path, source_dir, config)

    print(f"[OK] Dump creato: {output_path}")


# ======================================================================================================================
# CLI
# ======================================================================================================================

if __name__ == "__main__":
    folder = sys.argv[1] if len(sys.argv) > 1 else "."
    dump_folder(folder)
