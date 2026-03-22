#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Interfaccia Tkinter per il generatore di dump."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import sys
import threading
import traceback
import tkinter as tk
from tkinter import filedialog, font as tkfont, messagebox, ttk

ROOT_DIR = Path(__file__).resolve().parents[3]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

LOG_DIR = ROOT_DIR / "dump_folder" / "logs"
LOG_FILE = LOG_DIR / "tkinter.log"

try:
    from ...engine.dump_engine import DumpConfig, collect_manifest_from_selection, estimate_output_size, generate_dump
    from ...engine.selection_model import FileSystemSelectionModel, path_depth
except ImportError:  # pragma: no cover - supporto avvio come script
    from dump_folder.engine.dump_engine import DumpConfig, collect_manifest_from_selection, estimate_output_size, generate_dump
    from dump_folder.engine.selection_model import FileSystemSelectionModel, path_depth


def configure_logging():
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("dump_folder.tkinter")
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    logger.propagate = False
    return logger


LOGGER = configure_logging()


def install_global_exception_logging():
    def log_unhandled(exc_type, exc_value, exc_traceback):
        LOGGER.critical(
            "Eccezione non gestita",
            exc_info=(exc_type, exc_value, exc_traceback),
        )
        sys.__excepthook__(exc_type, exc_value, exc_traceback)

    sys.excepthook = log_unhandled

    if hasattr(threading, "excepthook"):
        def log_thread_exception(args):
            LOGGER.critical(
                "Eccezione non gestita in thread %s",
                args.thread.name if args.thread else "unknown",
                exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
            )

        threading.excepthook = log_thread_exception


def human_size(size):
    if size <= 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    value = float(size)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024
    return f"{int(size)} B"


class DumpApp:
    FORMAT_EXTENSIONS = {"txt": ".txt", "md": ".md", "html": ".html"}
    SETTINGS_FILE = Path.home() / ".dump_builder_settings.json"
    DUMMY_SUFFIX = "::__dummy__"

    COLORS = {
        "bg": "#f3efe7",
        "surface": "#fffaf2",
        "surface_alt": "#f7f1e8",
        "border": "#d8ccbd",
        "text": "#1c1814",
        "muted": "#6d645a",
        "accent": "#b5532d",
        "accent_soft": "#f4d7ca",
        "success": "#2f6b51",
        "success_soft": "#d7eadf",
        "error": "#8c2f2f",
        "error_soft": "#f3d9d9",
        "selected_row": "#dcebdc",
        "partial_row": "#f3e5b8",
        "partial_mark": "#b1841a",
        "unchecked_border": "#c9bcac",
    }

    def __init__(self, root):
        self.root = root
        self.root.title("Dump Builder")
        self.root.minsize(1160, 700)
        self.root.report_callback_exception = self._report_callback_exception

        LOGGER.info("Avvio GUI Tkinter")

        self.model = FileSystemSelectionModel()
        self.is_generating = False
        self.last_directory = str(Path.cwd())
        self.status_tone = "neutral"
        self.summary_after_id = None
        self.summary_request_id = 0
        self.preview_limit = 14

        self.format_var = tk.StringVar(value="txt")
        self.output_var = tk.StringVar()
        self.root_path_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Pronto per creare un nuovo dump")
        self.count_var = tk.StringVar(value="0 file / 0 cartelle")
        self.file_count_var = tk.StringVar(value="0")
        self.directory_count_var = tk.StringVar(value="0")
        self.size_var = tk.StringVar(value="0 B")
        self.output_size_var = tk.StringVar(value="0 B")
        self.state_images = {}

        self._configure_styles()
        self._build_state_images()
        self._build_layout()
        self._load_preferences()
        self._schedule_summary_refresh()

        self.format_var.trace_add("write", self._on_format_changed)
        self.output_var.trace_add("write", self._on_output_changed)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def _configure_styles(self):
        self.root.configure(bg=self.COLORS["bg"])

        title_font = tkfont.nametofont("TkDefaultFont").copy()
        title_font.configure(family="Segoe UI Semibold", size=22)
        subtitle_font = tkfont.nametofont("TkDefaultFont").copy()
        subtitle_font.configure(family="Segoe UI", size=10)
        body_font = tkfont.nametofont("TkDefaultFont").copy()
        body_font.configure(family="Segoe UI", size=10)
        strong_font = tkfont.nametofont("TkDefaultFont").copy()
        strong_font.configure(family="Segoe UI Semibold", size=10)
        metric_font = tkfont.nametofont("TkDefaultFont").copy()
        metric_font.configure(family="Segoe UI Semibold", size=16)

        self.fonts = {
            "title": title_font,
            "subtitle": subtitle_font,
            "body": body_font,
            "strong": strong_font,
            "metric": metric_font,
        }

        style = ttk.Style()
        style.theme_use("clam")

        style.configure(".", font=body_font)
        style.configure("App.TFrame", background=self.COLORS["bg"])
        style.configure("Card.TFrame", background=self.COLORS["surface"], relief="flat")
        style.configure("CardAlt.TFrame", background=self.COLORS["surface_alt"], relief="flat")
        style.configure("HeaderTitle.TLabel", background=self.COLORS["bg"], foreground=self.COLORS["text"], font=title_font)
        style.configure("HeaderSub.TLabel", background=self.COLORS["bg"], foreground=self.COLORS["muted"], font=subtitle_font)
        style.configure("CardTitle.TLabel", background=self.COLORS["surface"], foreground=self.COLORS["text"], font=strong_font)
        style.configure("CardText.TLabel", background=self.COLORS["surface"], foreground=self.COLORS["muted"], font=body_font)
        style.configure("Metric.TLabel", background=self.COLORS["surface"], foreground=self.COLORS["text"], font=metric_font)
        style.configure("Pill.TLabel", background=self.COLORS["accent_soft"], foreground=self.COLORS["accent"], font=strong_font, padding=(10, 4))
        style.configure("Hint.TLabel", background=self.COLORS["surface_alt"], foreground=self.COLORS["muted"], font=body_font)
        style.configure("Field.TLabel", background=self.COLORS["surface_alt"], foreground=self.COLORS["text"], font=strong_font)
        style.configure("Primary.TButton", background=self.COLORS["accent"], foreground="#ffffff", borderwidth=0, focusthickness=0, padding=(14, 10))
        style.map("Primary.TButton", background=[("active", "#9e4826"), ("disabled", "#d7b4a7")], foreground=[("disabled", "#fff8f3")])
        style.configure("Secondary.TButton", background=self.COLORS["surface_alt"], foreground=self.COLORS["text"], bordercolor=self.COLORS["border"], padding=(12, 9))
        style.map("Secondary.TButton", background=[("active", "#efe5d8"), ("disabled", "#f2ece4")], foreground=[("disabled", "#a59a8d")])
        style.configure("Ghost.TButton", background=self.COLORS["surface"], foreground=self.COLORS["muted"], bordercolor=self.COLORS["border"], padding=(10, 8))
        style.map("Ghost.TButton", background=[("active", "#f7f1e8"), ("disabled", "#faf6f0")], foreground=[("disabled", "#b1a89e")])
        style.configure("App.Treeview", background=self.COLORS["surface"], fieldbackground=self.COLORS["surface"], foreground=self.COLORS["text"], bordercolor=self.COLORS["border"], lightcolor=self.COLORS["border"], darkcolor=self.COLORS["border"], rowheight=30)
        style.map("App.Treeview", background=[("selected", self.COLORS["surface"])], foreground=[("selected", self.COLORS["text"])])
        style.configure("App.Treeview.Heading", background=self.COLORS["surface_alt"], foreground=self.COLORS["muted"], font=strong_font, relief="flat", padding=(8, 8))
        style.configure("App.Horizontal.TProgressbar", troughcolor=self.COLORS["surface_alt"], background=self.COLORS["accent"], bordercolor=self.COLORS["surface_alt"], lightcolor=self.COLORS["accent"], darkcolor=self.COLORS["accent"])
        style.configure("App.TEntry", fieldbackground=self.COLORS["surface"], bordercolor=self.COLORS["border"], lightcolor=self.COLORS["border"], darkcolor=self.COLORS["border"], padding=8)
        style.configure("App.TRadiobutton", background=self.COLORS["surface_alt"], foreground=self.COLORS["text"], padding=(8, 6))

    def _build_state_images(self):
        self.state_images = {
            "unchecked": self._draw_state_image(fill="#fffaf2", border=self.COLORS["unchecked_border"], mark=None),
            "checked": self._draw_state_image(fill=self.COLORS["success"], border=self.COLORS["success"], mark="check"),
            "indeterminate": self._draw_state_image(fill=self.COLORS["partial_mark"], border=self.COLORS["partial_mark"], mark="dash"),
        }

    def _draw_state_image(self, fill, border, mark=None):
        image = tk.PhotoImage(width=18, height=18)
        image.put(fill, to=(2, 2, 16, 16))
        image.put(border, to=(2, 2, 16, 3))
        image.put(border, to=(2, 15, 16, 16))
        image.put(border, to=(2, 2, 3, 16))
        image.put(border, to=(15, 2, 16, 16))
        if mark == "check":
            check_color = "#fffaf2"
            for x, y in ((5, 9), (6, 10), (7, 11), (8, 10), (9, 9), (10, 8), (11, 7), (12, 6)):
                image.put(check_color, to=(x, y, x + 1, y + 1))
            image.put(check_color, to=(4, 8, 5, 9))
            image.put(check_color, to=(5, 9, 6, 10))
        elif mark == "dash":
            image.put("#fff7e8", to=(4, 8, 14, 10))
        return image

    def _build_layout(self):
        self.container = ttk.Frame(self.root, style="App.TFrame", padding=20)
        self.container.grid(row=0, column=0, sticky="nsew")

        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        self.container.columnconfigure(0, weight=1)
        self.container.rowconfigure(1, weight=1)

        self._build_header()
        self._build_main_content()

    def _build_header(self):
        header = ttk.Frame(self.container, style="App.TFrame")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 18))
        header.columnconfigure(0, weight=1)
        header.columnconfigure(1, weight=0)

        ttk.Label(header, text="Dump Builder", style="HeaderTitle.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            header,
            text="Scegli una root di lavoro, naviga il tree e seleziona con checkbox tri-state cosa dumpare.",
            style="HeaderSub.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(6, 0))

    def _build_main_content(self):
        main = ttk.Frame(self.container, style="App.TFrame")
        main.grid(row=1, column=0, sticky="nsew")
        main.columnconfigure(0, weight=1, uniform="main_split")
        main.columnconfigure(1, weight=1, uniform="main_split")
        main.rowconfigure(0, weight=1)

        self._build_selection_panel(main)
        self._build_export_panel(main)

    def _build_selection_panel(self, parent):
        panel = self._create_card(parent, row=0, column=0, padding=18, sticky="nsew", style="Card.TFrame")
        panel.columnconfigure(0, weight=1)
        panel.rowconfigure(0, weight=1)

        list_frame = ttk.Frame(panel, style="Card.TFrame")
        list_frame.grid(row=0, column=0, sticky="nsew")
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)

        self.tree = ttk.Treeview(list_frame, show="tree", selectmode="browse", style="App.Treeview")
        self.tree.heading("#0", text="Nome")
        self.tree.column("#0", width=640, stretch=True)
        self.tree.grid(row=0, column=0, sticky="nsew")
        self.tree.bind("<Button-1>", self._on_tree_click)
        self.tree.bind("<<TreeviewOpen>>", self._on_tree_open)
        self.tree.bind("<<TreeviewClose>>", self._on_tree_close)
        self.tree.bind("<Double-1>", self.open_selected_path)

        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.tree.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.tag_configure("checked", background=self.COLORS["selected_row"])
        self.tree.tag_configure("indeterminate", background=self.COLORS["partial_row"])

    def _build_export_panel(self, parent):
        panel = self._create_card(parent, row=0, column=1, padding=18, sticky="nsew", style="CardAlt.TFrame")
        panel.columnconfigure(0, weight=1)
        stats = self._create_card(panel, row=0, column=0, padding=14, sticky="ew", style="Card.TFrame", padx=0)
        for column in range(4):
            stats.columnconfigure(column, weight=1)
        ttk.Label(stats, text="File", style="CardText.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(stats, text="Cartelle", style="CardText.TLabel").grid(row=0, column=1, sticky="w")
        ttk.Label(stats, text="Dimensione", style="CardText.TLabel").grid(row=0, column=2, sticky="w")
        ttk.Label(stats, text="Output stimato", style="CardText.TLabel").grid(row=0, column=3, sticky="w")
        ttk.Label(stats, textvariable=self.file_count_var, style="Metric.TLabel").grid(row=1, column=0, sticky="w")
        ttk.Label(stats, textvariable=self.directory_count_var, style="Metric.TLabel").grid(row=1, column=1, sticky="w")
        ttk.Label(stats, textvariable=self.size_var, style="Metric.TLabel").grid(row=1, column=2, sticky="w")
        ttk.Label(stats, textvariable=self.output_size_var, style="Metric.TLabel").grid(row=1, column=3, sticky="w")

        status_card = self._create_card(panel, row=1, column=0, padding=14, sticky="ew", style="Card.TFrame", padx=0)
        status_card.grid_configure(pady=(16, 0))
        status_card.columnconfigure(0, weight=0)
        status_card.columnconfigure(1, weight=1)
        self.status_badge = ttk.Label(status_card, text="Stato", style="Pill.TLabel")
        self.status_badge.grid(row=0, column=0, sticky="nw", padx=(0, 16))
        self.status_label = ttk.Label(status_card, textvariable=self.status_var, style="CardText.TLabel", wraplength=420, justify="left")
        self.status_label.grid(row=0, column=1, sticky="w")

        ttk.Label(panel, text="File di output", style="Field.TLabel").grid(row=2, column=0, sticky="w", pady=(18, 0))
        output_row = ttk.Frame(panel, style="CardAlt.TFrame")
        output_row.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        output_row.columnconfigure(0, weight=1)

        self.output_entry = ttk.Entry(output_row, textvariable=self.output_var, style="App.TEntry")
        self.output_entry.grid(row=0, column=0, sticky="ew")
        self.output_button = ttk.Button(output_row, text="Sfoglia", command=self.select_output, style="Secondary.TButton")
        self.output_button.grid(row=0, column=1, sticky="e", padx=(10, 0))

        ttk.Label(panel, text="Root di lavoro", style="Field.TLabel").grid(row=4, column=0, sticky="w", pady=(18, 0))
        root_row = ttk.Frame(panel, style="CardAlt.TFrame")
        root_row.grid(row=5, column=0, sticky="ew", pady=(10, 0))
        root_row.columnconfigure(0, weight=1)

        self.root_path_entry = ttk.Entry(root_row, textvariable=self.root_path_var, style="App.TEntry")
        self.root_path_entry.grid(row=0, column=0, sticky="ew")
        self.root_path_entry.configure(state="readonly")
        self.choose_root_button = ttk.Button(root_row, text="Sfoglia", command=self.choose_root, style="Secondary.TButton")
        self.choose_root_button.grid(row=0, column=1, sticky="e", padx=(10, 0))

        format_card = self._create_card(panel, row=6, column=0, padding=14, sticky="ew", style="Card.TFrame", padx=0)
        format_card.grid_configure(pady=(28, 0))
        format_card.columnconfigure(0, weight=1)
        ttk.Label(format_card, text="Formato", style="CardTitle.TLabel").grid(row=0, column=0, sticky="w")
        radios = ttk.Frame(format_card, style="Card.TFrame")
        radios.grid(row=1, column=0, sticky="w", pady=(10, 0))
        for index, fmt in enumerate(("txt", "md", "html")):
            ttk.Radiobutton(radios, text=fmt.upper(), value=fmt, variable=self.format_var, style="App.TRadiobutton").grid(row=0, column=index, sticky="w", padx=(0, 8))

        self.generate_button = ttk.Button(panel, text="Genera dump", command=self.generate, style="Primary.TButton")
        self.generate_button.grid(row=7, column=0, sticky="ew", pady=(18, 0))

        self.progress = ttk.Progressbar(panel, mode="indeterminate", style="App.Horizontal.TProgressbar")
        self.progress.grid(row=8, column=0, sticky="ew", pady=(14, 0))
        self.progress.grid_remove()

    def _create_card(self, parent, row=0, column=0, padding=12, sticky="nsew", style="Card.TFrame", padx=None):
        frame = ttk.Frame(parent, style=style, padding=padding)
        resolved_padx = (0, 16) if column == 0 else (0, 0)
        if padx is not None:
            resolved_padx = padx
        frame.grid(row=row, column=column, sticky=sticky, padx=resolved_padx)
        return frame

    def _set_status(self, message, tone="neutral"):
        self.status_var.set(message)
        self.status_tone = tone
        LOGGER.info("Status update: tone=%s message=%s", tone, message)
        if tone == "success":
            style_name = "StatusSuccess.TLabel"
            background = self.COLORS["success_soft"]
            foreground = self.COLORS["success"]
            badge_text = "Completato"
        elif tone == "error":
            style_name = "StatusError.TLabel"
            background = self.COLORS["error_soft"]
            foreground = self.COLORS["error"]
            badge_text = "Errore"
        elif tone == "working":
            style_name = "StatusWorking.TLabel"
            background = self.COLORS["accent_soft"]
            foreground = self.COLORS["accent"]
            badge_text = "In corso"
        else:
            style_name = "StatusNeutral.TLabel"
            background = self.COLORS["surface_alt"]
            foreground = self.COLORS["muted"]
            badge_text = "Stato"

        style = ttk.Style()
        style.configure(style_name, background=background, foreground=foreground, font=self.fonts["strong"], padding=(10, 4))
        self.status_badge.configure(style=style_name, text=badge_text)

    def _set_busy_state(self, is_busy):
        self.is_generating = is_busy
        state = tk.DISABLED if is_busy else tk.NORMAL
        self.choose_root_button.configure(state=state)
        self.output_button.configure(state=state)
        self.output_entry.configure(state="disabled" if is_busy else "normal")
        self.generate_button.configure(state=state)

        if is_busy:
            self.progress.grid()
            self.progress.start(10)
        else:
            self.progress.stop()
            self.progress.grid_remove()

    def _dummy_id(self, node_id):
        return f"{node_id}{self.DUMMY_SUFFIX}"

    def _is_dummy_id(self, item_id):
        return item_id.endswith(self.DUMMY_SUFFIX)

    def _insert_or_update_node(self, node_id, parent_id=""):
        node = self.model.nodes[node_id]
        state = self.model.get_node_check_state(node_id)
        tags = (state,) if state in {"checked", "indeterminate"} else ()
        if self.tree.exists(node_id):
            self.tree.item(node_id, text=node.name, image=self.state_images[state], tags=tags)
        else:
            self.tree.insert(
                parent_id,
                tk.END,
                iid=node_id,
                text=node.name,
                image=self.state_images[state],
                tags=tags,
                open=node_id in self.model.ui_state.expanded_ids,
            )
        self._sync_tree_children(node_id)

    def _sync_tree_children(self, node_id):
        if self._is_dummy_id(node_id) or not self.tree.exists(node_id):
            return
        node = self.model.nodes[node_id]
        for child_id in list(self.tree.get_children(node_id)):
            self.tree.delete(child_id)

        if node.kind != "directory":
            return
        if node.children_loaded:
            for child_id in node.children_ids:
                self._insert_or_update_node(child_id, parent_id=node_id)
        elif node.has_children:
            self.tree.insert(node_id, tk.END, iid=self._dummy_id(node_id), text="Carica...")

    def _refresh_branch(self, node_id, refresh_loaded_descendants=False):
        current_id = node_id
        while current_id:
            if current_id in self.model.nodes and self.tree.exists(current_id):
                self._insert_or_update_node(current_id, parent_id=self.model.nodes[current_id].parent_id or "")
            current_id = self.model.nodes[current_id].parent_id if current_id in self.model.nodes else None

        if refresh_loaded_descendants:
            self._refresh_loaded_descendants(node_id)

    def _refresh_loaded_descendants(self, node_id):
        if node_id not in self.model.nodes:
            return
        node = self.model.nodes[node_id]
        if node.children_loaded:
            for child_id in node.children_ids:
                if self.tree.exists(child_id):
                    self._insert_or_update_node(child_id, parent_id=node_id)
                    self._refresh_loaded_descendants(child_id)

    def _rebuild_tree(self):
        for item_id in self.tree.get_children():
            self.tree.delete(item_id)

        for root_id in self.model.root_ids:
            self._insert_or_update_node(root_id)

        for expanded_id in sorted(self.model.ui_state.expanded_ids, key=lambda item: (path_depth(item), item.lower())):
            if expanded_id in self.model.nodes and self.tree.exists(expanded_id):
                if self.model.nodes[expanded_id].kind == "directory":
                    self.model.load_children(expanded_id)
                    self._sync_tree_children(expanded_id)
                self.tree.item(expanded_id, open=True)

        if self.model.ui_state.focused_id and self.tree.exists(self.model.ui_state.focused_id):
            self.tree.focus(self.model.ui_state.focused_id)

    def _schedule_summary_refresh(self):
        if self.summary_after_id:
            self.root.after_cancel(self.summary_after_id)
        self.summary_after_id = self.root.after(120, self._start_summary_refresh)

    def _start_summary_refresh(self):
        self.summary_after_id = None
        selection = self.model.build_normalized_selection()
        if not selection.includes:
            LOGGER.info("Summary refresh skipped: empty selection")
            self._apply_empty_summary()
            return

        self.summary_request_id += 1
        request_id = self.summary_request_id
        output_value = self.output_var.get().strip()
        selected_format = self.format_var.get().upper()
        LOGGER.info(
            "Summary refresh queued: request_id=%s includes=%s excludes=%s",
            request_id,
            len(selection.includes),
            len(selection.excludes),
        )
        worker = threading.Thread(
            target=self._run_summary_refresh,
            args=(request_id, selection, output_value, selected_format),
            daemon=True,
            name=f"summary-refresh-{request_id}",
        )
        worker.start()

    def _apply_empty_summary(self):
        self.count_var.set("0 file / 0 cartelle")
        self.file_count_var.set("0")
        self.directory_count_var.set("0")
        self.size_var.set("0 B")
        self.output_size_var.set("0 B")
        self._suggest_output_path()

    def _run_summary_refresh(self, request_id, selection, output_value, selected_format):
        LOGGER.info("Summary refresh started: request_id=%s", request_id)
        try:
            manifest = collect_manifest_from_selection(selection, config=DumpConfig)
            manifest.estimated_output_size = estimate_output_size(
                manifest.files,
                selection.includes,
                output_format=selected_format.lower(),
                config=DumpConfig,
            )
        except Exception as exc:  # pragma: no cover - background logging
            LOGGER.error("Summary refresh failed: request_id=%s error=%s", request_id, exc, exc_info=True)
            self.root.after(0, self._on_summary_refresh_error, request_id, str(exc))
            return

        result = {
            "selection": selection,
            "manifest": manifest,
            "output_value": output_value,
            "selected_format": selected_format,
        }
        self.root.after(0, self._apply_summary_result, request_id, result)

    def _apply_summary_result(self, request_id, result):
        if request_id != self.summary_request_id:
            LOGGER.info("Summary refresh discarded: stale request_id=%s latest=%s", request_id, self.summary_request_id)
            return

        selection = result["selection"]
        manifest = result["manifest"]
        file_count = len(manifest.files)
        directory_count = len(manifest.directories)
        self.count_var.set(f"{file_count} file / {directory_count} cartelle")
        self.file_count_var.set(str(file_count))
        self.directory_count_var.set(str(directory_count))
        self.size_var.set(human_size(manifest.estimated_size))
        self.output_size_var.set(human_size(manifest.estimated_output_size))

        self._suggest_output_path()
        LOGGER.info(
            "Summary refresh completed: request_id=%s files=%s directories=%s warnings=%s",
            request_id,
            file_count,
            directory_count,
            len(manifest.warnings),
        )

    def _on_summary_refresh_error(self, request_id, error_message):
        if request_id != self.summary_request_id:
            return
        LOGGER.error("Summary refresh UI error: request_id=%s error=%s", request_id, error_message)

    def _load_preferences(self):
        if not self.SETTINGS_FILE.exists():
            return

        try:
            settings = json.loads(self.SETTINGS_FILE.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self._set_status("Preferenze non leggibili, uso i valori predefiniti", tone="error")
            return

        saved_format = settings.get("format")
        if saved_format in self.FORMAT_EXTENSIONS:
            self.format_var.set(saved_format)
        saved_output = settings.get("output_path", "").strip()
        if saved_output:
            self.output_var.set(saved_output)
        saved_directory = settings.get("last_directory", "").strip()
        if saved_directory:
            self.last_directory = saved_directory
        geometry = settings.get("window_geometry", "").strip()
        if geometry:
            self.root.geometry(geometry)

        tree_state = settings.get("tree_state")
        if isinstance(tree_state, dict):
            self.model.restore_state(tree_state)
            self._rebuild_tree()
            self._update_root_path_var()

        self._set_status("Preferenze caricate", tone="neutral")

    def _save_preferences(self):
        settings = {
            "format": self.format_var.get(),
            "output_path": self.output_var.get().strip(),
            "last_directory": self.last_directory,
            "window_geometry": self.root.geometry(),
            "tree_state": self.model.export_state(),
        }
        try:
            self.SETTINGS_FILE.write_text(json.dumps(settings, ensure_ascii=True, indent=2), encoding="utf-8")
        except OSError:
            self._set_status("Impossibile salvare le preferenze", tone="error")

    def _suggest_output_path(self):
        if self.output_var.get().strip() or not self.model.root_ids:
            return
        first_root = Path(self.model.root_ids[0])
        base_dir = first_root.parent if first_root.is_file() else first_root
        self.output_var.set(str((base_dir / f"dump{self.FORMAT_EXTENSIONS[self.format_var.get()]}").resolve()))

    def _replace_output_extension(self):
        output_value = self.output_var.get().strip()
        if not output_value:
            return
        output_path = Path(output_value)
        desired_suffix = self.FORMAT_EXTENSIONS[self.format_var.get()]
        if output_path.suffix.lower() != desired_suffix:
            self.output_var.set(str(output_path.with_suffix(desired_suffix)))

    def _update_root_path_var(self):
        self.root_path_var.set(self.model.root_ids[0] if self.model.root_ids else "")

    def _on_format_changed(self, *_args):
        self._replace_output_extension()
        self._schedule_summary_refresh()
        self._save_preferences()

    def _on_output_changed(self, *_args):
        self._schedule_summary_refresh()
        self._save_preferences()

    def _focused_node_id(self):
        selection = self.tree.selection()
        if selection:
            return selection[0]
        focus = self.tree.focus()
        return focus if focus and not self._is_dummy_id(focus) else None

    def _on_tree_click(self, event):
        LOGGER.info("Tree click: x=%s y=%s state=%s", event.x, event.y, event.state)
        item_id = self.tree.identify_row(event.y)
        if not item_id or self._is_dummy_id(item_id):
            return None
        region = self.tree.identify("region", event.x, event.y)
        if region in {"tree", "cell"}:
            if event.state & 0x0004:
                self.tree.focus(item_id)
                self.tree.selection_remove(self.tree.selection())
                self.model.set_focus(item_id)
                self._save_preferences()
                self.open_selected_path()
                return "break"

            if region == "tree":
                element = self.tree.identify_element(event.x, event.y)
                if "indicator" in element:
                    return None

            self.tree.focus(item_id)
            self.tree.selection_remove(self.tree.selection())
            self.model.set_focus(item_id)
            LOGGER.info("Tree click focus set: item_id=%s", item_id)
            current_state = self.model.get_node_check_state(item_id)
            LOGGER.info("Tree click current state: item_id=%s state=%s", item_id, current_state)
            if current_state == "checked":
                self.model.set_subtree_included(item_id, False)
            else:
                self.model.set_subtree_included(item_id, True)
            LOGGER.info("Tree click selection updated: item_id=%s", item_id)
            self._refresh_branch(item_id, refresh_loaded_descendants=False)
            LOGGER.info("Tree click branch refreshed: item_id=%s", item_id)
            self._schedule_summary_refresh()
            LOGGER.info("Tree click summary refresh scheduled: item_id=%s", item_id)
            self._save_preferences()
            LOGGER.info("Tree click preferences saved: item_id=%s", item_id)
            return "break"
        return None

    def _on_tree_open(self, _event):
        node_id = self.tree.focus()
        if not node_id or self._is_dummy_id(node_id) or node_id not in self.model.nodes:
            return
        self.model.expand_node(node_id)
        self._sync_tree_children(node_id)
        self._refresh_branch(node_id, refresh_loaded_descendants=True)
        self._save_preferences()

    def _on_tree_close(self, _event):
        node_id = self.tree.focus()
        if not node_id or self._is_dummy_id(node_id):
            return
        self.model.collapse_node(node_id)
        self._save_preferences()

    def _add_root_path(self, path):
        if self.model.root_ids:
            self.model = FileSystemSelectionModel()
            self._rebuild_tree()

        try:
            node_id = self.model.add_root(path)
        except ValueError as exc:
            self._set_status(str(exc), tone="error")
            return

        self._insert_or_update_node(node_id)
        self._update_root_path_var()
        current_path = Path(node_id)
        self.last_directory = str(current_path.parent if current_path.is_file() else current_path)
        self._schedule_summary_refresh()
        self._save_preferences()
        self._set_status(f"Root impostata: {node_id}", tone="success")

    def choose_root(self):
        path = filedialog.askdirectory(title="Seleziona root di lavoro", initialdir=self.last_directory)
        if path:
            self._add_root_path(path)

    def open_selected_path(self, _event=None):
        node_id = self._focused_node_id()
        if not node_id or node_id not in self.model.nodes:
            self._set_status("Seleziona un elemento da aprire", tone="neutral")
            return

        path = Path(self.model.nodes[node_id].path)
        self.last_directory = str(path.parent if path.is_file() else path)
        try:
            os.startfile(str(path))
        except AttributeError:
            messagebox.showinfo("Percorso selezionato", str(path))
        except OSError as exc:
            messagebox.showerror("Errore", f"Impossibile aprire il percorso:\n{exc}")
            self._set_status("Impossibile aprire il percorso selezionato", tone="error")
            return

        self._save_preferences()
        self._set_status(f"Percorso aperto: {path}", tone="success")

    def select_output(self):
        selected_format = self.format_var.get()
        default_ext = self.FORMAT_EXTENSIONS.get(selected_format, ".txt")
        initial_path = self.output_var.get().strip()
        initial_dir = self.last_directory
        initial_file = f"dump{default_ext}"
        if initial_path:
            output_path = Path(initial_path)
            initial_dir = str(output_path.parent)
            initial_file = output_path.name

        file_path = filedialog.asksaveasfilename(
            title="Seleziona output",
            defaultextension=default_ext,
            initialdir=initial_dir,
            initialfile=initial_file,
            filetypes=[("Text", "*.txt"), ("Markdown", "*.md"), ("HTML", "*.html")],
        )
        if file_path:
            self.output_var.set(file_path)
            self.last_directory = str(Path(file_path).parent)
            self._replace_output_extension()
            self._save_preferences()
            self._set_status(f"Output selezionato: {self.output_var.get()}", tone="success")

    def generate(self):
        if self.is_generating:
            return

        selection = self.model.build_normalized_selection()
        if not selection.includes:
            messagebox.showerror("Errore", "Seleziona almeno un file o una cartella nel tree.")
            self._set_status("Manca la selezione da esportare", tone="error")
            return

        output_path = self.output_var.get().strip()
        if not output_path:
            messagebox.showerror("Errore", "Seleziona il file di output.")
            self._set_status("Manca il file di output", tone="error")
            return

        self._set_busy_state(True)
        self._set_status(
            f"Generazione in corso con {len(selection.includes)} include rule e {len(selection.excludes)} exclude rule...",
            tone="working",
        )

        worker = threading.Thread(target=self._run_generate_dump, args=(selection, output_path, self.format_var.get()), daemon=True)
        worker.start()

    def _run_generate_dump(self, selection, output_path, output_format):
        try:
            final_output = generate_dump(selection, output_path, output_format)
        except Exception as exc:  # pragma: no cover - threading + UI callback
            self.root.after(0, self._on_generation_error, str(exc))
            return
        self.root.after(0, self._on_generation_success, final_output)

    def _on_generation_success(self, final_output):
        self._set_busy_state(False)
        self.output_var.set(final_output)
        self.last_directory = str(Path(final_output).parent)
        self._schedule_summary_refresh()
        self._save_preferences()
        self._set_status(f"Dump creato con successo: {final_output}", tone="success")
        messagebox.showinfo("Completato", f"Dump creato con successo:\n{final_output}")

    def _on_generation_error(self, error_message):
        self._set_busy_state(False)
        self._set_status("Errore durante la generazione del dump", tone="error")
        LOGGER.error("Errore durante la generazione del dump: %s", error_message)
        messagebox.showerror("Errore", error_message)

    def on_close(self):
        LOGGER.info("Chiusura GUI Tkinter")
        self._save_preferences()
        self.root.destroy()

    def _report_callback_exception(self, exc_type, exc_value, exc_traceback):
        LOGGER.error(
            "Eccezione in callback Tkinter",
            exc_info=(exc_type, exc_value, exc_traceback),
        )
        trace_text = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        messagebox.showerror(
            "Errore interno",
            f"Si e verificato un errore interno.\n\nLog: {LOG_FILE}\n\n{trace_text[-1200:]}",
        )


def run_app():
    install_global_exception_logging()
    root = tk.Tk()
    root.geometry("1220x760")
    DumpApp(root)
    root.mainloop()
