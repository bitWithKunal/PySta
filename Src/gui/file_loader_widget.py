"""
Compact, polished file loader widget with clean dark-theme UI.
Supports multiple file selection with validation and background loading.
"""

import os
from pathlib import Path
from typing import Optional, Dict, List, Any

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                             QLabel, QFileDialog, QProgressBar, QMessageBox,
                             QFrame, QScrollArea, QSizePolicy)
from PyQt6.QtCore import pyqtSignal, Qt, QThread, QSize
from PyQt6.QtGui import QFont, QIcon, QPalette, QColor

from Src.utils.logger import get_logger
from Src.utils.file_utils import FileUtils
from Src.liberty_parser.liberty_parser import LibertyParser
from Src.verilog_parser.verilog_parser import VerilogParser
from Src.sdc_parser.sdc_parser import SDCParser

logger = get_logger(__name__)

# ── Design tokens ────────────────────────────────────────────────────────────
CLR_BG          = "#16161e"
CLR_SURFACE     = "#1e1e28"
CLR_CARD        = "#23232f"
CLR_BORDER      = "#2e2e3e"
CLR_BORDER_LO   = "#28283a"
CLR_TEXT        = "#d4d4e8"
CLR_TEXT_DIM    = "#6e6e8e"
CLR_ACCENT      = "#7c6af5"       # indigo-violet
CLR_ACCENT_HI   = "#9d8fff"
CLR_ACCENT_LO   = "#5b50cc"
CLR_GREEN       = "#4ec994"
CLR_RED         = "#f07178"
CLR_YELLOW      = "#ffc96b"

FILE_TYPES = {
    "liberty": {"label": "Liberty",  "ext": ".lib",  "icon": "◈",  "color": CLR_ACCENT},
    "verilog": {"label": "Verilog",  "ext": ".v",    "icon": "◉",  "color": CLR_GREEN},
    "sdc":     {"label": "SDC",      "ext": ".sdc",  "icon": "◆",  "color": CLR_YELLOW},
}

BASE_STYLE = f"""
    * {{ font-family: 'JetBrains Mono', 'Cascadia Code', 'Fira Code', monospace; }}

    QWidget {{ background-color: {CLR_BG}; color: {CLR_TEXT}; }}

    QScrollArea {{ border: none; background: transparent; }}
    QScrollBar:vertical {{
        background: {CLR_SURFACE}; width: 6px; margin: 0;
    }}
    QScrollBar::handle:vertical {{
        background: {CLR_BORDER}; border-radius: 3px; min-height: 20px;
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}

    QToolTip {{
        background-color: {CLR_CARD}; color: {CLR_TEXT};
        border: 1px solid {CLR_BORDER}; border-radius: 4px;
        padding: 4px 8px; font-size: 10px;
    }}
"""

# ─────────────────────────────────────────────────────────────────────────────


def _btn_style(bg: str, fg: str, bg_hover: str, fg_hover: str = None,
               border: str = "none", radius: int = 5) -> str:
    if fg_hover is None:
        fg_hover = fg
    return f"""
        QPushButton {{
            background-color: {bg}; color: {fg};
            border: {border}; border-radius: {radius}px;
            padding: 0px 10px; font-size: 11px; font-weight: 600;
        }}
        QPushButton:hover  {{ background-color: {bg_hover}; color: {fg_hover}; }}
        QPushButton:pressed {{ background-color: {bg}; }}
        QPushButton:disabled {{ background-color: {CLR_SURFACE}; color: {CLR_TEXT_DIM}; }}
    """


class _Divider(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.HLine)
        self.setFixedHeight(1)
        self.setStyleSheet(f"background-color: {CLR_BORDER_LO}; border: none;")


class _Badge(QLabel):
    """Pill-shaped count badge."""
    def __init__(self, text="0", parent=None):
        super().__init__(text, parent)
        self._update()

    def set_count(self, n: int):
        self.setText(str(n))
        self._update()

    def _update(self):
        n = int(self.text())
        color = CLR_ACCENT if n > 0 else CLR_TEXT_DIM
        self.setStyleSheet(f"""
            QLabel {{
                background-color: {CLR_SURFACE};
                color: {color};
                border: 1px solid {CLR_BORDER};
                border-radius: 9px;
                padding: 0px 7px;
                font-size: 10px; font-weight: 700;
                min-width: 18px; max-height: 18px;
            }}
        """)


class _FileRow(QWidget):
    """Single compact file row with name + remove button."""
    removed = pyqtSignal(str)   # emits file_path

    def __init__(self, file_path: str, accent_color: str, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self._build(file_path, accent_color)

    def _build(self, file_path: str, accent: str):
        name = Path(file_path).name
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 3, 6, 3)
        layout.setSpacing(6)

        dot = QLabel("·")
        dot.setStyleSheet(f"color: {accent}; font-size: 14px; font-weight: 900;")
        dot.setFixedWidth(10)
        layout.addWidget(dot)

        lbl = QLabel(name)
        lbl.setStyleSheet(f"color: {CLR_TEXT}; font-size: 11px;")
        lbl.setToolTip(file_path)
        lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout.addWidget(lbl)

        rm = QPushButton("✕")
        rm.setFixedSize(18, 18)
        rm.setCursor(Qt.CursorShape.PointingHandCursor)
        rm.setToolTip("Remove file")
        rm.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {CLR_TEXT_DIM};
                border: none; font-size: 10px; font-weight: 700;
                border-radius: 9px; padding: 0;
            }}
            QPushButton:hover {{ color: {CLR_RED}; background: {CLR_SURFACE}; }}
        """)
        rm.clicked.connect(lambda: self.removed.emit(self.file_path))
        layout.addWidget(rm)

        self.setStyleSheet(f"""
            QWidget {{ background: transparent; border-radius: 4px; }}
            QWidget:hover {{ background: {CLR_SURFACE}; }}
        """)
        self.setFixedHeight(26)


# ─────────────────────────────────────────────────────────────────────────────

class _FileSection(QWidget):
    """Compact card for one file type."""
    browse_clicked  = pyqtSignal(str)
    file_removed    = pyqtSignal(str, str)   # file_type, path

    def __init__(self, file_type: str, parent=None):
        super().__init__(parent)
        self.file_type = file_type
        meta = FILE_TYPES[file_type]
        self._accent = meta["color"]
        self._rows: Dict[str, _FileRow] = {}
        self._build(meta)

    def _build(self, meta: dict):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {CLR_CARD};
                border: 1px solid {CLR_BORDER};
                border-radius: 8px;
            }}
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)

        # ── Header row ──────────────────────────────────────────────────────
        header = QWidget()
        header.setFixedHeight(36)
        header.setStyleSheet("background: transparent;")
        h = QHBoxLayout(header)
        h.setContentsMargins(10, 0, 8, 0)
        h.setSpacing(7)

        icon_lbl = QLabel(meta["icon"])
        icon_lbl.setStyleSheet(f"color: {self._accent}; font-size: 13px;")
        h.addWidget(icon_lbl)

        title = QLabel(meta["label"])
        title.setStyleSheet(f"color: {CLR_TEXT}; font-size: 12px; font-weight: 700;")
        h.addWidget(title)

        ext_lbl = QLabel(meta["ext"])
        ext_lbl.setStyleSheet(f"color: {CLR_TEXT_DIM}; font-size: 10px;")
        h.addWidget(ext_lbl)

        h.addStretch()

        self._badge = _Badge("0")
        h.addWidget(self._badge)

        browse_btn = QPushButton("+ Add")
        browse_btn.setFixedHeight(24)
        browse_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        browse_btn.setStyleSheet(_btn_style(
            CLR_SURFACE, self._accent, CLR_BORDER,
            border=f"1px solid {CLR_BORDER}", radius=5
        ))
        browse_btn.clicked.connect(lambda: self.browse_clicked.emit(self.file_type))
        h.addWidget(browse_btn)

        card_layout.addWidget(header)

        # ── Divider ─────────────────────────────────────────────────────────
        card_layout.addWidget(_Divider())

        # ── File list (collapsible scroll) ──────────────────────────────────
        self._list_area = QScrollArea()
        self._list_area.setWidgetResizable(True)
        self._list_area.setFrameShape(QFrame.Shape.NoFrame)
        self._list_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._list_area.setStyleSheet("background: transparent;")

        self._list_widget = QWidget()
        self._list_widget.setStyleSheet("background: transparent;")
        self._list_layout = QVBoxLayout(self._list_widget)
        self._list_layout.setContentsMargins(4, 4, 4, 4)
        self._list_layout.setSpacing(1)
        self._list_layout.addStretch()

        self._list_area.setWidget(self._list_widget)
        self._list_area.setVisible(False)

        card_layout.addWidget(self._list_area)

        root.addWidget(card)

    # ── Public interface ─────────────────────────────────────────────────────

    def add_file(self, file_path: str):
        row = _FileRow(file_path, self._accent)
        row.removed.connect(lambda p: self._on_remove(p))
        # insert before the stretch
        self._list_layout.insertWidget(self._list_layout.count() - 1, row)
        self._rows[file_path] = row
        self._sync_list_area()
        self._badge.set_count(len(self._rows))

    def remove_file(self, file_path: str):
        row = self._rows.pop(file_path, None)
        if row:
            row.deleteLater()
        self._sync_list_area()
        self._badge.set_count(len(self._rows))

    def clear(self):
        for row in self._rows.values():
            row.deleteLater()
        self._rows.clear()
        self._sync_list_area()
        self._badge.set_count(0)

    # ── Private helpers ──────────────────────────────────────────────────────

    def _on_remove(self, file_path: str):
        self.remove_file(file_path)
        self.file_removed.emit(self.file_type, file_path)

    def _sync_list_area(self):
        has_files = bool(self._rows)
        self._list_area.setVisible(has_files)
        if has_files:
            n = min(len(self._rows), 4)
            self._list_area.setFixedHeight(n * 28 + 10)


# ─────────────────────────────────────────────────────────────────────────────

class FileLoaderThread(QThread):
    """Background thread for file loading."""
    progress       = pyqtSignal(int)
    status         = pyqtSignal(str)
    file_processed = pyqtSignal(str, bool)
    finished       = pyqtSignal(dict)
    error          = pyqtSignal(str)

    def __init__(self, lib_files: List[str], verilog_files: List[str], sdc_files: List[str]):
        super().__init__()
        self.lib_files     = lib_files
        self.verilog_files = verilog_files
        self.sdc_files     = sdc_files
        self.results: Dict[str, Any] = {}

    def run(self):
        try:
            total = len(self.lib_files) + len(self.verilog_files) + len(self.sdc_files)
            done  = 0

            def tick(path, ok):
                nonlocal done
                self.file_processed.emit(path, ok)
                done += 1
                self.progress.emit(int(done * 100 / total))

            # Liberty
            if self.lib_files:
                self.status.emit("Parsing Liberty libraries…")
                parser = LibertyParser()
                for f in self.lib_files:
                    try:
                        self.status.emit(f"  {Path(f).name}")
                        parser.parse_file(f)
                        tick(f, True)
                    except Exception as e:
                        logger.error(f"Liberty parse failed [{f}]: {e}")
                        tick(f, False)
                self.results['cell_library'] = (
                    parser.parse_files(self.lib_files) if len(self.lib_files) > 1
                    else parser.library
                )

            # Verilog
            if self.verilog_files:
                self.status.emit("Parsing Verilog netlists…")
                parser = VerilogParser()
                for f in self.verilog_files:
                    try:
                        self.status.emit(f"  {Path(f).name}")
                        parser.parse_file(f)
                        tick(f, True)
                    except Exception as e:
                        logger.error(f"Verilog parse failed [{f}]: {e}")
                        tick(f, False)
                resolver = parser.module_resolver
                self.status.emit("Building hierarchy…")
                if hasattr(resolver, '_find_top_module'):
                    top = resolver._find_top_module()
                    if top:
                        resolver.build_hierarchy(top)
                self.results['module_resolver'] = resolver

            # SDC
            if self.sdc_files:
                self.status.emit("Parsing SDC constraints…")
                parser = SDCParser()
                clocks = exceptions = None
                for f in self.sdc_files:
                    try:
                        self.status.emit(f"  {Path(f).name}")
                        c, ex = parser.parse_file(f)
                        if clocks is None:
                            clocks, exceptions = c, ex
                        else:
                            for clk in c.get_all_clocks():
                                if not clocks.get_clock_by_name(clk.name):
                                    clocks.add_clock(clk)
                            for exc in ex.exceptions:
                                exceptions.add_exception(exc)
                        tick(f, True)
                    except Exception as e:
                        logger.error(f"SDC parse failed [{f}]: {e}")
                        tick(f, False)
                self.results['clock_constraints'] = clocks
                self.results['exception_manager'] = exceptions

            self.status.emit("Done")
            self.progress.emit(100)
            self.finished.emit(self.results)

        except Exception as e:
            logger.error(f"Loader thread error: {e}", exc_info=True)
            self.error.emit(str(e))


# ─────────────────────────────────────────────────────────────────────────────

class FileLoaderWidget(QWidget):
    """Compact, polished design-file loader widget."""

    files_loaded  = pyqtSignal(dict)
    file_selected = pyqtSignal(str, str)
    file_removed  = pyqtSignal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_files: Dict[str, List[str]] = {k: [] for k in FILE_TYPES}
        self._loader: Optional[FileLoaderThread] = None
        self.setStyleSheet(BASE_STYLE)
        self._build_ui()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        # Title bar
        root.addWidget(self._make_title_bar())

        # File sections
        self._sections: Dict[str, _FileSection] = {}
        for ft in FILE_TYPES:
            sec = _FileSection(ft)
            sec.browse_clicked.connect(self._browse)
            sec.file_removed.connect(self._on_section_removed)
            self._sections[ft] = sec
            root.addWidget(sec)

        # Progress row (hidden until loading)
        self._prog_frame = self._make_progress_row()
        self._prog_frame.setVisible(False)
        root.addWidget(self._prog_frame)

        # Action buttons
        root.addWidget(self._make_action_row())

        root.addStretch()

    def _make_title_bar(self) -> QWidget:
        bar = QWidget()
        bar.setFixedHeight(32)
        bar.setStyleSheet("background: transparent;")
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(2, 0, 2, 0)
        lay.setSpacing(8)

        icon = QLabel("⬡")
        icon.setStyleSheet(f"color: {CLR_ACCENT}; font-size: 16px;")
        lay.addWidget(icon)

        title = QLabel("Design File Loader")
        title.setStyleSheet(f"color: {CLR_TEXT}; font-size: 13px; font-weight: 700;")
        lay.addWidget(title)

        lay.addStretch()

        self._status_dot  = QLabel("●")
        self._status_dot.setStyleSheet(f"color: {CLR_TEXT_DIM}; font-size: 10px;")
        lay.addWidget(self._status_dot)

        self._status_lbl = QLabel("Ready")
        self._status_lbl.setStyleSheet(f"color: {CLR_TEXT_DIM}; font-size: 11px;")
        lay.addWidget(self._status_lbl)

        return bar

    def _make_progress_row(self) -> QWidget:
        frame = QWidget()
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(0, 4, 0, 0)
        lay.setSpacing(4)

        self._prog_label = QLabel("")
        self._prog_label.setStyleSheet(f"color: {CLR_TEXT_DIM}; font-size: 10px;")
        lay.addWidget(self._prog_label)

        self._progress = QProgressBar()
        self._progress.setFixedHeight(4)
        self._progress.setTextVisible(False)
        self._progress.setStyleSheet(f"""
            QProgressBar {{
                background-color: {CLR_SURFACE};
                border: none; border-radius: 2px;
            }}
            QProgressBar::chunk {{
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 {CLR_ACCENT_LO}, stop:1 {CLR_ACCENT_HI}
                );
                border-radius: 2px;
            }}
        """)
        lay.addWidget(self._progress)
        return frame

    def _make_action_row(self) -> QWidget:
        bar = QWidget()
        bar.setStyleSheet("background: transparent;")
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(0, 4, 0, 0)
        lay.setSpacing(8)

        self._clear_btn = QPushButton("Clear All")
        self._clear_btn.setFixedHeight(32)
        self._clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._clear_btn.setStyleSheet(_btn_style(
            CLR_SURFACE, CLR_TEXT_DIM, CLR_CARD,
            border=f"1px solid {CLR_BORDER}", radius=6
        ))
        self._clear_btn.clicked.connect(self.clear_all)
        lay.addWidget(self._clear_btn)

        lay.addStretch()

        self._load_btn = QPushButton("Load Files →")
        self._load_btn.setFixedHeight(32)
        self._load_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._load_btn.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 {CLR_ACCENT_LO}, stop:1 {CLR_ACCENT}
                );
                color: white; border: none; border-radius: 6px;
                padding: 0 18px; font-size: 12px; font-weight: 700;
                letter-spacing: 0.3px;
            }}
            QPushButton:hover {{
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 {CLR_ACCENT}, stop:1 {CLR_ACCENT_HI}
                );
            }}
            QPushButton:pressed  {{ padding: 1px 18px 0 18px; }}
            QPushButton:disabled {{
                background: {CLR_SURFACE}; color: {CLR_TEXT_DIM};
            }}
        """)
        self._load_btn.clicked.connect(self.load_files)
        lay.addWidget(self._load_btn)

        return bar

    # ── Slots ────────────────────────────────────────────────────────────────

    def _browse(self, file_type: str):
        meta = FILE_TYPES[file_type]
        ext  = meta["ext"]
        start = str(Path.home())
        if self.current_files[file_type]:
            start = str(Path(self.current_files[file_type][-1]).parent)

        paths, _ = QFileDialog.getOpenFileNames(
            self,
            f"Select {meta['label']} files",
            start,
            f"{meta['label']} Files (*{ext});;All Files (*)"
        )
        for p in paths:
            self._add_file(file_type, p)

    def _add_file(self, file_type: str, file_path: str):
        expected = FILE_TYPES[file_type]["ext"]
        if Path(file_path).suffix.lower() != expected:
            QMessageBox.warning(self, "Wrong file type",
                                f"Expected a {expected} file, got: {Path(file_path).name}")
            return
        if file_path in self.current_files[file_type]:
            return  # silently skip duplicates

        self.current_files[file_type].append(file_path)
        self._sections[file_type].add_file(file_path)
        self.file_selected.emit(file_type, file_path)
        self._set_status("Ready", CLR_TEXT_DIM)

    def _on_section_removed(self, file_type: str, file_path: str):
        if file_path in self.current_files[file_type]:
            self.current_files[file_type].remove(file_path)
        self.file_removed.emit(file_type, file_path)

    # ── Public API ───────────────────────────────────────────────────────────

    def add_file(self, file_type: str, file_path: str):
        """Programmatic file addition."""
        self._add_file(file_type, file_path)

    def clear_files(self, file_type: str):
        self.current_files[file_type].clear()
        self._sections[file_type].clear()

    def clear_all(self):
        for ft in FILE_TYPES:
            self.clear_files(ft)
        self._set_status("Ready", CLR_TEXT_DIM)

    def validate_files(self) -> bool:
        missing = [FILE_TYPES[ft]["label"]
                   for ft in FILE_TYPES if not self.current_files[ft]]
        if missing:
            QMessageBox.warning(self, "Missing files",
                                "Please add:\n  • " + "\n  • ".join(missing))
            return False
        return True

    def load_files(self):
        if not self.validate_files():
            return
        self._set_ui_enabled(False)
        self._prog_frame.setVisible(True)
        self._progress.setValue(0)
        self._set_status("Loading…", CLR_ACCENT)

        self._loader = FileLoaderThread(
            self.current_files['liberty'],
            self.current_files['verilog'],
            self.current_files['sdc'],
        )
        self._loader.progress.connect(self._progress.setValue)
        self._loader.status.connect(self._prog_label.setText)
        self._loader.file_processed.connect(self._on_file_processed)
        self._loader.finished.connect(self._on_finished)
        self._loader.error.connect(self._on_error)
        self._loader.start()

    def get_loaded_data(self) -> dict:
        return self._loader.results if self._loader else {}

    def get_file_summary(self) -> Dict[str, Any]:
        return {
            ft: {
                "count": len(files),
                "files": files,
                "total_size": sum(
                    Path(f).stat().st_size for f in files if Path(f).exists()
                ),
            }
            for ft, files in self.current_files.items() if files
        }

    # ── Thread callbacks ─────────────────────────────────────────────────────

    def _on_file_processed(self, path: str, ok: bool):
        if not ok:
            logger.warning(f"Failed: {path}")

    def _on_finished(self, results: dict):
        self._prog_frame.setVisible(False)
        self._set_ui_enabled(True)
        self._set_status("Loaded ✓", CLR_GREEN)
        self.files_loaded.emit(results)

        parts = []
        if results.get('cell_library'):
            parts.append(f"{len(results['cell_library'].cells)} cells")
        if results.get('module_resolver'):
            parts.append(f"{len(results['module_resolver'].modules)} modules")
        if results.get('clock_constraints'):
            parts.append(f"{len(results['clock_constraints'].clocks)} clocks")

        QMessageBox.information(self, "Load complete",
                                "Loaded:\n  • " + "\n  • ".join(parts) if parts
                                else "All files loaded.")
        logger.info("All files loaded successfully.")

    def _on_error(self, msg: str):
        self._prog_frame.setVisible(False)
        self._set_ui_enabled(True)
        self._set_status("Error", CLR_RED)
        QMessageBox.critical(self, "Load error", f"Failed to load files:\n\n{msg}")
        logger.error(f"Load error: {msg}")

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _set_status(self, text: str, color: str):
        self._status_lbl.setText(text)
        self._status_lbl.setStyleSheet(f"color: {color}; font-size: 11px;")
        self._status_dot.setStyleSheet(f"color: {color}; font-size: 10px;")

    def _set_ui_enabled(self, on: bool):
        for w in (self._load_btn, self._clear_btn):
            w.setEnabled(on)
        for sec in self._sections.values():
            sec.setEnabled(on)