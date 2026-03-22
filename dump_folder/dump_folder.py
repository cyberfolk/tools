#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""CLI storica per dump_folder, ora basata su dump_engine."""

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

try:
    from dump_folder.engine.dump_engine import dump_folder
except ImportError:  # pragma: no cover - supporto avvio come script
    from dump_folder.engine.dump_engine import dump_folder


if __name__ == "__main__":
    folder = sys.argv[1] if len(sys.argv) > 1 else "."
    output_format = sys.argv[2] if len(sys.argv) > 2 else "txt"
    output_path = dump_folder(folder, output_format)
    print(f"[OK] Dump creato: {output_path}")
