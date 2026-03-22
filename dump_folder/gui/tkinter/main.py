#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Entrypoint GUI per dump_folder."""

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[3]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

try:
    from .gui import run_app
except ImportError:  # pragma: no cover - supporto avvio come script
    from dump_folder.gui.tkinter.gui import run_app


if __name__ == "__main__":
    run_app()
