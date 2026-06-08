"""
PySTA  —  Main Window
═════════════════════════════════════════════════════════════════════
Professional static timing analyzer GUI.

Design Language  →  "Precision Instrument"
  Inspired by Synopsys PrimeTime / Cadence Innovus / Mentor Questa.
  Dense information density, monochrome-dominant palette, razor-sharp
  grid alignment, deliberate use of accent colour only for state.

  Rules
  ─────
  • No emoji anywhere in the UI
  • All colours from DarkTheme — zero magic hex literals here
  • Every widget has explicit QSizePolicy — Qt never guesses
  • Sidebar wrapped in QScrollArea — nothing ever clips
  • Splitter ratio is proportional (deferred), never pixel-absolute
  • Status bar has no max-height cap
  • Toolbar uses ToolButtonTextBesideIcon + min-width — no clipping

  Visual Hierarchy
  ─────────────────
  1. Title bar  — slim, navy strip, product name left, version right
  2. Toolbar    — flat pill buttons, separator lines, muted text → accent on hover
  3. Sidebar    — section headers in CAPS, 1 px separator, scrollable
  4. Main panel — full-height tabs, dark content area, no white flash
  5. Status bar — 3 zones: message | log file | live clock
"""

from __future__ import annotations

import sys
import os
from pathlib import Path
from datetime import datetime
from typing import Optional

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QTabWidget, QStatusBar,
    QMenu, QToolBar, QMessageBox, QApplication,
    QProgressDialog, QLabel, QFrame,
    QSizePolicy, QScrollArea,
)
from PyQt6.QtCore  import Qt, QTimer, pyqtSignal, QThread, QSize
from PyQt6.QtGui   import QAction, QIcon, QFont, QScreen, QColor, QPalette

from Src.gui.dark_theme          import DarkTheme
from Src.gui.file_loader_widget  import FileLoaderWidget
from Src.gui.timing_panel        import TimingPanel
from Src.gui.options_panel       import OptionsPanel
from Src.gui.results_panel       import ResultsPanel

from Src.timing_graph.timing_graph_builder import TimingGraphBuilder
from Src.sta_engine.setup_analyzer         import SetupAnalyzer
from Src.sta_engine.hold_analyzer          import HoldAnalyzer
from Src.ocv_engine.ocv_analyzer           import OCVAnalyzer
from Src.si_engine.si_analyzer             import SIAnalyzer
from Src.report_engine.report_generator    import ReportGenerator

from Src.utils.logger       import get_logger, get_log_file
from Src.utils.config_loader import ConfigLoader, STAConfig

logger = get_logger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
#  DPI  helper
# ─────────────────────────────────────────────────────────────────────────────

def _dpi_scale(base_px: int) -> int:
    """Return *base_px* scaled to primary screen's device-pixel ratio."""
    screen: Optional[QScreen] = QApplication.primaryScreen()
    dpr = screen.devicePixelRatio() if screen else 1.0
    return max(base_px, int(base_px * dpr))


def _toolbar_icon_size() -> QSize:
    s = _dpi_scale(16)
    return QSize(s, s)


# ─────────────────────────────────────────────────────────────────────────────
#  Background worker
# ─────────────────────────────────────────────────────────────────────────────

class STAAnalysisThread(QThread):
    """Worker thread — runs the full STA pipeline off the UI thread."""

    progress = pyqtSignal(int)
    status   = pyqtSignal(str)
    stage    = pyqtSignal(str)
    finished = pyqtSignal(dict)
    error    = pyqtSignal(str)

    def __init__(self, data: dict, config: STAConfig):
        super().__init__()
        self.data    = data
        self.config  = config
        self.results: dict = {}

    def run(self):
        try:
            cell_lib   = self.data.get('cell_library')
            mod_res    = self.data.get('module_resolver')
            clk_cons   = self.data.get('clock_constraints')
            exc_mgr    = self.data.get('exception_manager')

            if not all([cell_lib, mod_res, clk_cons]):
                raise ValueError("Missing required data for analysis")

            # ── Timing graph
            self.stage.emit("Building timing graph")
            self.status.emit("Building timing graph...")
            self.progress.emit(10)
            gb = TimingGraphBuilder(cell_lib, mod_res)
            gb.build_graph(clk_cons, exc_mgr)
            self.results['graph_builder'] = gb
            self.progress.emit(25)

            # ── Optional engines
            self.stage.emit("Initializing engines")
            ocv = si = None
            if self.config.enable_ocv:
                self.status.emit("Initializing OCV derating...")
                ocv = OCVAnalyzer(cell_lib)
                ocv.set_derates(self.config.ocv_derate_data,
                                self.config.ocv_derate_clock,
                                self.config.ocv_derate_early,
                                self.config.ocv_derate_late)
                self.results['ocv_analyzer'] = ocv
            if self.config.enable_si:
                self.status.emit("Initializing SI analysis...")
                si = SIAnalyzer(cell_lib)
                si.set_coupling_threshold(self.config.si_aggressor_coupling_threshold)
                self.results['si_analyzer'] = si
            self.progress.emit(40)

            # ── Setup
            if self.config.enable_setup:
                self.stage.emit("Setup analysis")
                self.status.emit("Running setup timing analysis...")
                sa = SetupAnalyzer(gb.edge_manager, gb.delay_calculator,
                                   clk_cons, exc_mgr, ocv, si)
                self.results['setup_analyzer'] = sa
                self.results['setup_results']  = sa.analyze()
                self.progress.emit(65)

            # ── Hold
            if self.config.enable_hold:
                self.stage.emit("Hold analysis")
                self.status.emit("Running hold timing analysis...")
                ha = HoldAnalyzer(gb.edge_manager, gb.delay_calculator,
                                  clk_cons, exc_mgr, ocv, si)
                self.results['hold_analyzer'] = ha
                self.results['hold_results']  = ha.analyze()
                self.progress.emit(85)

            # ── Reports
            self.stage.emit("Generating reports")
            self.status.emit("Generating timing reports...")
            rg = ReportGenerator()
            self.results['report_paths'] = rg.generate_all_reports(self.results)

            self.progress.emit(100)
            self.stage.emit("Complete")
            self.status.emit("Analysis complete")
            self.finished.emit(self.results)

        except Exception as exc:
            logger.error(f"Analysis failed: {exc}", exc_info=True)
            self.error.emit(str(exc))


# ─────────────────────────────────────────────────────────────────────────────
#  Main Window
# ─────────────────────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    """
    PySTA primary application window.

    The window is divided into three horizontal bands:

        [ Menu bar ]
        [ Tool bar ]
        [ Title strip ]  ←── 1 px accent underline
        ┌──────────────────────────────────────────────────┐
        │  Left sidebar  │  Main content (tab widget)      │
        │  (QScrollArea) │                                  │
        └──────────────────────────────────────────────────┘
        [ Status bar ]
    """

    # ── Sidebar width constraints (px at 1× DPI)
    _SIDEBAR_MIN = 300
    _SIDEBAR_MAX = 460
    _SIDEBAR_RATIO = 0.26   # fraction of window width

    def __init__(self):
        super().__init__()

        self.config             = ConfigLoader.load_config()
        self.loaded_data:  dict = {}
        self.analysis_results:  dict = {}
        self.analysis_thread: Optional[STAAnalysisThread] = None
        self.progress_dialog:  Optional[QProgressDialog]  = None

        # Build in the correct order so forward references work
        self._build_central_widget()
        self._build_status_bar()
        self._build_menu_bar()
        self._build_toolbar()

        # Apply theme AFTER all widgets are constructed
        DarkTheme.apply_theme(QApplication.instance())

        # Apply window-level stylesheet over the theme
        self._apply_window_style()

        logger.info("PySTA main window ready")

    # ═════════════════════════════════════════════════════════════════════════
    #  Central widget
    # ═════════════════════════════════════════════════════════════════════════

    def _build_central_widget(self):
        self.setWindowTitle("PySTA  —  Static Timing Analyzer  1.0")
        self.setGeometry(80, 80, 1640, 980)
        self.setMinimumSize(1100, 700)

        icon_path = Path(__file__).parent.parent.parent / "Resources" / "icon.png"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        root = QWidget()
        root.setObjectName("rootWidget")
        self.setCentralWidget(root)

        root_lay = QVBoxLayout(root)
        root_lay.setContentsMargins(0, 0, 0, 0)
        root_lay.setSpacing(0)

        # Title strip
        root_lay.addWidget(self._make_title_strip())

        # 1 px accent underline
        accent_line = QFrame()
        accent_line.setObjectName("accentLine")
        accent_line.setFixedHeight(1)
        root_lay.addWidget(accent_line)

        # Workspace
        workspace = QWidget()
        workspace.setObjectName("workspace")
        ws_lay = QHBoxLayout(workspace)
        ws_lay.setContentsMargins(0, 0, 0, 0)
        ws_lay.setSpacing(0)

        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        self._splitter.setObjectName("mainSplitter")
        self._splitter.setHandleWidth(3)
        self._splitter.setChildrenCollapsible(False)
        self._splitter.addWidget(self._make_sidebar())
        self._splitter.addWidget(self._make_main_panel())

        ws_lay.addWidget(self._splitter)
        root_lay.addWidget(workspace, stretch=1)

        # Defer proportional split until the window has its real width
        QTimer.singleShot(0, self._restore_split)

    # ─────────────────────────────────────────────────────────────────────────
    #  Title strip
    # ─────────────────────────────────────────────────────────────────────────

    def _make_title_strip(self) -> QFrame:
        strip = QFrame()
        strip.setObjectName("titleStrip")
        strip.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        lay = QHBoxLayout(strip)
        lay.setContentsMargins(14, 0, 14, 0)
        lay.setSpacing(12)

        # Product wordmark
        wordmark = QLabel("PySTA")
        wordmark.setObjectName("wordmark")
        wordmark.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        lay.addWidget(wordmark)

        # Vertical divider
        divider = QFrame()
        divider.setObjectName("titleDivider")
        divider.setFrameShape(QFrame.Shape.VLine)
        divider.setFixedWidth(1)
        lay.addWidget(divider)

        # Subtitle
        subtitle = QLabel("Static Timing Analyzer")
        subtitle.setObjectName("titleSubtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        lay.addWidget(subtitle)

        lay.addStretch(1)

        # Build badge (right-aligned)
        build_lbl = QLabel("v1.0.0  |  Build 2026")
        build_lbl.setObjectName("buildBadge")
        build_lbl.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight)
        lay.addWidget(build_lbl)

        return strip

    # ─────────────────────────────────────────────────────────────────────────
    #  Sidebar  (scrollable)
    # ─────────────────────────────────────────────────────────────────────────

    def _make_sidebar(self) -> QScrollArea:
        """
        The entire sidebar is a QScrollArea.

        setWidgetResizable(True)           — inner content fills scroll width
        ScrollBarAlwaysOff (horizontal)    — never wrap vertically because of H overflow
        ScrollBarAsNeeded  (vertical)      — thin scrollbar when content is taller than view

        Nothing in the sidebar ever clips.
        """
        inner = QWidget()
        inner.setObjectName("sidebarContent")
        inner.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        lay = QVBoxLayout(inner)
        lay.setContentsMargins(8, 10, 8, 10)
        lay.setSpacing(16)

        # ── Section: Design Files
        lay.addWidget(self._section_header("DESIGN FILES"))
        self.file_loader = FileLoaderWidget()
        self.file_loader.files_loaded.connect(self.on_files_loaded)
        self.file_loader.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        lay.addWidget(self._section_card(self.file_loader))

        # ── Section: Analysis Configuration
        lay.addWidget(self._section_header("ANALYSIS CONFIGURATION"))
        self.options_panel = OptionsPanel()
        self.options_panel.config_changed.connect(self.on_config_changed)
        self.options_panel.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        lay.addWidget(self._section_card(self.options_panel))

        lay.addStretch(1)

        # ── Wrap in scroll area
        sa = QScrollArea()
        sa.setObjectName("sidebar")
        sa.setWidget(inner)
        sa.setWidgetResizable(True)
        sa.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        sa.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        sa.setFrameShape(QFrame.Shape.NoFrame)
        sa.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        sa.setMinimumWidth(self._SIDEBAR_MIN)
        sa.setMaximumWidth(self._SIDEBAR_MAX)
        return sa

    # ─────────────────────────────────────────────────────────────────────────
    #  Main panel
    # ─────────────────────────────────────────────────────────────────────────

    def _make_main_panel(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("mainPanel")
        panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        lay = QVBoxLayout(panel)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        self.tab_widget = QTabWidget()
        self.tab_widget.setObjectName("mainTabs")
        self.tab_widget.setDocumentMode(False)
        self.tab_widget.setElideMode(Qt.TextElideMode.ElideRight)
        self.tab_widget.setMovable(False)
        self.tab_widget.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.timing_panel  = TimingPanel()
        self.results_panel = ResultsPanel()

        self.tab_widget.addTab(self.timing_panel,  "Timing Analysis")
        self.tab_widget.addTab(self.results_panel, "Analysis Results")
        self.tab_widget.addTab(QWidget(),          "Path Details")
        self.tab_widget.addTab(QWidget(),          "Waveforms")
        self.tab_widget.addTab(QWidget(),          "Reports")

        lay.addWidget(self.tab_widget)
        return panel

    # ─────────────────────────────────────────────────────────────────────────
    #  Sidebar widget factories
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _section_header(text: str) -> QLabel:
        """All-caps section label — VS-Code / Cadence sidebar style."""
        lbl = QLabel(text)
        lbl.setObjectName("sectionHeader")
        lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        return lbl

    @staticmethod
    def _section_card(child: QWidget) -> QFrame:
        """Thin-bordered card wrapping a child widget."""
        card = QFrame()
        card.setObjectName("sectionCard")
        card.setFrameShape(QFrame.Shape.NoFrame)
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        lay = QVBoxLayout(card)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(child)
        return card

    def _restore_split(self):
        total = self._splitter.width() or 1640
        left  = int(total * self._SIDEBAR_RATIO)
        self._splitter.setSizes([left, total - left])

    # ═════════════════════════════════════════════════════════════════════════
    #  Status bar
    # ═════════════════════════════════════════════════════════════════════════

    def _build_status_bar(self):
        sb = QStatusBar()
        self.setStatusBar(sb)
        sb.setObjectName("appStatusBar")
        # No setMaximumHeight — auto-sized from content

        # Left: live message
        self.status_label = QLabel("Ready")
        self.status_label.setObjectName("sbMessage")
        sb.addWidget(self.status_label, stretch=1)

        # Permanent: log file
        sb.addPermanentWidget(self._vsep("sbVsep"))

        log_name = Path(get_log_file()).name
        self.log_label = QLabel(f"Log: {log_name}")
        self.log_label.setObjectName("sbInfo")
        sb.addPermanentWidget(self.log_label)

        # Permanent: clock
        sb.addPermanentWidget(self._vsep("sbVsep"))

        self.time_label = QLabel()
        self.time_label.setObjectName("sbInfo")
        sb.addPermanentWidget(self.time_label)
        self._tick()

        self._clock = QTimer(self)
        self._clock.timeout.connect(self._tick)
        self._clock.start(1000)

    def _tick(self):
        self.time_label.setText(f"  {datetime.now().strftime('%H:%M:%S')}  ")

    @staticmethod
    def _vsep(obj_name: str = "") -> QFrame:
        f = QFrame()
        if obj_name:
            f.setObjectName(obj_name)
        f.setFrameShape(QFrame.Shape.VLine)
        f.setFixedWidth(1)
        f.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        return f

    # ═════════════════════════════════════════════════════════════════════════
    #  Menu bar
    # ═════════════════════════════════════════════════════════════════════════

    def _build_menu_bar(self):
        mb = self.menuBar()
        mb.setNativeMenuBar(False)
        mb.setObjectName("appMenuBar")

        def act(label, sc=None, slot=None) -> QAction:
            a = QAction(label, self)
            if sc:   a.setShortcut(sc)
            if slot: a.triggered.connect(slot)
            return a

        # File
        fm = mb.addMenu("File")
        fm.addAction(act("Load Files...",        "Ctrl+L", self.file_loader.load_files))
        fm.addSeparator()
        fm.addAction(act("Import Configuration", "Ctrl+I"))
        fm.addAction(act("Export Configuration", "Ctrl+E"))
        fm.addSeparator()
        fm.addAction(act("Exit",                 "Ctrl+Q", self.close))

        # Analysis
        am = mb.addMenu("Analysis")
        am.addAction(act("Run Setup Analysis",   "Ctrl+R",       lambda: self.run_analysis('setup')))
        am.addAction(act("Run Hold Analysis",    "Ctrl+H",       lambda: self.run_analysis('hold')))
        am.addSeparator()
        am.addAction(act("Run All",              "Ctrl+Shift+R", self.run_analysis))
        am.addSeparator()
        am.addAction(act("Cancel Analysis",      "Ctrl+.",       self._cancel_analysis))

        # View
        vm = mb.addMenu("View")
        vm.addAction(act("Timing Graph",         "Ctrl+G",  self.timing_panel.show_timing_graph))
        vm.addAction(act("Critical Paths",       "Ctrl+P",  self.timing_panel.show_timing_paths))
        vm.addSeparator()
        vm.addAction(act("Clock Waveforms",      "Ctrl+W",  self.timing_panel.show_clock_waveforms))
        vm.addSeparator()
        vm.addAction(act("Timing Analysis",      None,      lambda: self.tab_widget.setCurrentIndex(0)))
        vm.addAction(act("Analysis Results",     None,      lambda: self.tab_widget.setCurrentIndex(1)))
        vm.addAction(act("Path Details",         None,      lambda: self.tab_widget.setCurrentIndex(2)))
        vm.addAction(act("Waveforms",            None,      lambda: self.tab_widget.setCurrentIndex(3)))
        vm.addAction(act("Reports",              None,      lambda: self.tab_widget.setCurrentIndex(4)))

        # Reports
        rm = mb.addMenu("Reports")
        rm.addAction(act("Generate All Reports", "Ctrl+Shift+G", self.generate_reports))
        rm.addAction(act("Open Reports Folder",  "Ctrl+Shift+O", self.open_reports_folder))
        rm.addSeparator()
        rm.addAction(act("Export to Excel",      None))
        rm.addAction(act("Export to CSV",        None))
        rm.addAction(act("Export to PDF",        None))

        # Tools
        tm = mb.addMenu("Tools")
        tm.addAction(act("Preferences...",       "Ctrl+,"))
        tm.addSeparator()
        tm.addAction(act("Constraint Editor",    None))
        tm.addAction(act("Liberty Browser",      None))
        tm.addAction(act("Schematic Viewer",     None))

        # Help
        hm = mb.addMenu("Help")
        hm.addAction(act("Documentation",        "F1"))
        hm.addAction(act("Keyboard Shortcuts",   "Ctrl+/"))
        hm.addSeparator()
        hm.addAction(act("Check for Updates",    None))
        hm.addSeparator()
        hm.addAction(act("About PySTA",          None,  self.show_about))

    # ═════════════════════════════════════════════════════════════════════════
    #  Toolbar
    # ═════════════════════════════════════════════════════════════════════════

    def _build_toolbar(self):
        """
        Single toolbar row.
        ToolButtonTextBesideIcon  → text right of icon, compact, never clips.
        Explicit min-width/height in stylesheet  → DPI-resilient.
        """
        tb = QToolBar("Main")
        tb.setObjectName("mainToolbar")
        tb.setMovable(False)
        tb.setFloatable(False)
        tb.setIconSize(_toolbar_icon_size())
        tb.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.addToolBar(tb)

        def btn(label: str, tip: str, slot=None, shortcut: str = "") -> QAction:
            a = QAction(label, self)
            a.setStatusTip(tip)
            if shortcut: a.setShortcut(shortcut)
            if slot:     a.triggered.connect(slot)
            tb.addAction(a)
            return a

        # File group
        btn("Load",    "Load design files (Ctrl+L)",       self.file_loader.load_files, "Ctrl+L")
        tb.addSeparator()

        # Analysis group
        self._run_action = btn("Run",     "Run full STA analysis (Ctrl+Shift+R)", self.run_analysis, "Ctrl+Shift+R")
        btn("Setup",   "Run setup analysis (Ctrl+R)",      lambda: self.run_analysis('setup'), "Ctrl+R")
        btn("Hold",    "Run hold analysis (Ctrl+H)",       lambda: self.run_analysis('hold'),  "Ctrl+H")
        tb.addSeparator()

        # View group
        btn("Graph",   "Show timing graph (Ctrl+G)",       self.timing_panel.show_timing_graph, "Ctrl+G")
        btn("Paths",   "Show critical paths (Ctrl+P)",     self.timing_panel.show_timing_paths, "Ctrl+P")
        btn("Clocks",  "Show clock waveforms (Ctrl+W)",    self.timing_panel.show_clock_waveforms, "Ctrl+W")
        tb.addSeparator()

        # Reports group
        btn("Report",  "Generate timing reports",          self.generate_reports)
        btn("Folder",  "Open reports folder",              self.open_reports_folder)

    # ═════════════════════════════════════════════════════════════════════════
    #  Window-level stylesheet
    # ═════════════════════════════════════════════════════════════════════════

    def _apply_window_style(self):
        """
        Window-specific stylesheet.

        Colour tokens come exclusively from DarkTheme.hex() —
        no hard-coded hex values anywhere in this method.

        Application-wide widget styles (inputs, buttons, tables, …)
        are handled by DarkTheme.get_stylesheet() which is applied in
        DarkTheme.apply_theme().  Here we only style named QObjects that
        belong to this window's layout.
        """
        C = DarkTheme.hex      # C('accent') → '#007acc'

        # ── Collect values used more than once
        bg       = C('bg_base')
        bg_dark  = C('bg_dark')
        bg_void  = C('bg_void')
        bg_card  = C('bg_card')
        bg_lt    = C('bg_light')
        fg       = C('fg_primary')
        fg2      = C('fg_secondary')
        fg_m     = C('fg_muted')
        fg_d     = C('fg_disabled')
        fg_w     = C('fg_on_accent')
        acc      = C('accent')
        acc_h    = C('accent_hover')
        acc_p    = C('accent_pressed')
        acc_s    = C('accent_subtle')
        sec      = C('secondary')
        ok       = C('success')
        err      = C('error')
        err_h    = C('error_hover')
        bd       = C('border')
        bd_l     = C('border_light')
        bd_f     = C('border_focus')
        btn_bg   = C('btn_bg')
        btn_h    = C('btn_hover')
        btn_p    = C('btn_pressed')
        btn_pri  = C('btn_primary')
        btn_ph   = C('btn_primary_hv')
        btn_pp   = C('btn_primary_pr')
        sel      = C('selection')
        sel_t    = C('selection_text')

        # Monospace font stack
        mono = "'Cascadia Code', 'Consolas', 'Courier New', monospace"
        sans = "'Segoe UI', 'Inter', 'Roboto', sans-serif"

        self.setStyleSheet(f"""

/* ═══════════════════════════════════════════════════════════════════
   PySTA  —  window-scoped stylesheet
   All application-wide styles come from DarkTheme.get_stylesheet()
   ═══════════════════════════════════════════════════════════════════ */

/* ── Root ──────────────────────────────────────────────────────── */
QWidget#rootWidget,
QWidget#workspace {{
    background-color : {bg_void};
}}

/* ── Title strip ───────────────────────────────────────────────── */
QFrame#titleStrip {{
    background-color : {bg_void};
    min-height       : 36px;
    max-height       : 42px;
    border-bottom    : 1px solid {bd};
}}

QLabel#wordmark {{
    font-family   : {sans};
    font-size     : 13pt;
    font-weight   : 800;
    color         : {acc};
    letter-spacing: 0.5px;
    padding-right : 2px;
}}

QFrame#titleDivider {{
    background-color : {bd_l};
    min-width        : 1px;
    max-width        : 1px;
    min-height       : 18px;
    max-height       : 18px;
    margin           : 0 4px;
}}

QLabel#titleSubtitle {{
    font-family  : {sans};
    font-size    : 9pt;
    font-weight  : 400;
    color        : {fg_m};
    letter-spacing: 0.2px;
}}

QLabel#buildBadge {{
    font-family  : {mono};
    font-size    : 8pt;
    color        : {fg_d};
    padding      : 0 4px;
}}

/* 1 px accent underline beneath title strip */
QFrame#accentLine {{
    background-color : {acc};
    border           : none;
}}

/* ── Sidebar scroll area ────────────────────────────────────────── */
QScrollArea#sidebar {{
    background-color : {bg_dark};
    border-right     : 1px solid {bd};
    border-top       : none;
    border-left      : none;
    border-bottom    : none;
}}

/* Everything inside the scroll area: same background */
QScrollArea#sidebar > QWidget > QWidget,
QWidget#sidebarContent {{
    background-color : {bg_dark};
}}

/* Ultra-thin sidebar scrollbar */
QScrollArea#sidebar QScrollBar:vertical {{
    background       : transparent;
    width            : 5px;
    border-radius    : 2px;
    margin           : 0;
}}

QScrollArea#sidebar QScrollBar::handle:vertical {{
    background       : {bd_l};
    border-radius    : 2px;
    min-height       : 28px;
}}

QScrollArea#sidebar QScrollBar::handle:vertical:hover {{
    background       : {acc};
}}

QScrollArea#sidebar QScrollBar::add-line,
QScrollArea#sidebar QScrollBar::sub-line,
QScrollArea#sidebar QScrollBar::add-page,
QScrollArea#sidebar QScrollBar::sub-page {{
    background : none;
    height     : 0;
    border     : none;
}}

/* ── Sidebar section headers ────────────────────────────────────── */
QLabel#sectionHeader {{
    font-family    : {sans};
    font-size      : 7.5pt;
    font-weight    : 800;
    color          : {fg_m};
    letter-spacing : 1.6px;
    padding        : 4px 2px 3px 2px;
    border-bottom  : 1px solid {bd};
    background     : transparent;
}}

/* ── Sidebar section cards ──────────────────────────────────────── */
QFrame#sectionCard {{
    background-color : {bg_card};
    border           : 1px solid {bd};
    border-radius    : 4px;
    margin           : 0;
}}

QFrame#sectionCard:hover {{
    border-color : {bd_l};
}}

/* ── Splitter handle ────────────────────────────────────────────── */
QSplitter#mainSplitter::handle {{
    background-color : {bd};
    width            : 3px;
}}

QSplitter#mainSplitter::handle:hover {{
    background-color : {acc};
}}

QSplitter#mainSplitter::handle:pressed {{
    background-color : {acc_h};
}}

/* ── Main panel background ──────────────────────────────────────── */
QWidget#mainPanel {{
    background-color : {bg_void};
}}

/* ── Tab widget ─────────────────────────────────────────────────── */
QTabWidget#mainTabs {{
    background-color : {bg_void};
}}

QTabWidget#mainTabs::pane {{
    background-color : {bg_card};
    border           : 1px solid {bd};
    border-top       : none;
    border-radius    : 0;
    margin-top       : 0;
}}

QTabWidget#mainTabs QTabBar {{
    background-color : {bg_void};
    border-bottom    : 1px solid {bd};
}}

QTabWidget#mainTabs QTabBar::tab {{
    background-color         : {bg_void};
    color                    : {fg_m};
    font-family              : {sans};
    font-size                : 9.5pt;
    font-weight              : 500;
    padding                  : 8px 20px;
    margin-right             : 0;
    border-right             : 1px solid {bd};
    border-top               : 2px solid transparent;
    border-bottom            : none;
    min-width                : 110px;
}}

QTabWidget#mainTabs QTabBar::tab:first {{
    border-left : 1px solid {bd};
}}

QTabWidget#mainTabs QTabBar::tab:selected {{
    background-color : {bg_card};
    color            : {fg};
    border-top-color : {acc};
    font-weight      : 600;
}}

QTabWidget#mainTabs QTabBar::tab:hover:!selected {{
    background-color : {bg_dark};
    color            : {fg2};
    border-top-color : {bd_l};
}}

QTabWidget#mainTabs QTabBar::tab:disabled {{
    color : {fg_d};
}}

/* Force dark bg on all tab page content — no white flash */
QTabWidget#mainTabs > QWidget {{
    background-color : {bg_card};
}}

/* ── Toolbar ─────────────────────────────────────────────────────── */
QToolBar#mainToolbar {{
    background-color : {bg_void};
    border-bottom    : 1px solid {bd};
    spacing          : 2px;
    padding          : 3px 10px;
}}

QToolBar#mainToolbar::separator {{
    width            : 1px;
    background-color : {bd};
    margin           : 5px 8px;
}}

/* Every toolbar button: generous min-width so text is NEVER clipped */
QToolBar#mainToolbar QToolButton {{
    background-color : transparent;
    color            : {fg2};
    border           : 1px solid transparent;
    border-radius    : 3px;
    padding          : 4px 14px;
    min-width        : 68px;
    min-height       : 26px;
    font-family      : {sans};
    font-size        : 9.5pt;
    font-weight      : 500;
}}

QToolBar#mainToolbar QToolButton:hover {{
    background-color : {btn_h};
    border-color     : {bd};
    color            : {fg};
}}

QToolBar#mainToolbar QToolButton:pressed {{
    background-color : {btn_p};
    border-color     : {bd_l};
    color            : {fg};
}}

QToolBar#mainToolbar QToolButton:checked {{
    background-color : {acc_s};
    border-color     : {acc};
    color            : {acc};
}}

/* Special: "Run" button gets a primary accent treatment */
QToolBar#mainToolbar QToolButton[text="Run"] {{
    background-color : {btn_pri};
    color            : {fg_w};
    border           : none;
    font-weight      : 700;
    min-width        : 72px;
}}

QToolBar#mainToolbar QToolButton[text="Run"]:hover {{
    background-color : {btn_ph};
}}

QToolBar#mainToolbar QToolButton[text="Run"]:pressed {{
    background-color : {btn_pp};
}}

/* ── Menu bar ─────────────────────────────────────────────────────── */
QMenuBar#appMenuBar {{
    background-color : {bg_void};
    color            : {fg2};
    border-bottom    : 1px solid {bd};
    padding          : 2px 4px;
    font-family      : {sans};
    font-size        : 9.5pt;
    font-weight      : 400;
    spacing          : 2px;
}}

QMenuBar#appMenuBar::item {{
    padding      : 5px 12px;
    border-radius: 2px;
    background   : transparent;
}}

QMenuBar#appMenuBar::item:selected,
QMenuBar#appMenuBar::item:hover {{
    background-color : {btn_h};
    color            : {fg};
}}

QMenuBar#appMenuBar::item:pressed {{
    background-color : {bg_dark};
    color            : {fg};
}}

QMenu {{
    background-color : {bg_lt};
    color            : {fg};
    border           : 1px solid {bd_l};
    border-radius    : 3px;
    padding          : 3px 0;
    font-family      : {sans};
    font-size        : 9.5pt;
}}

QMenu::item {{
    padding          : 6px 28px 6px 20px;
    border-radius    : 0;
    margin           : 0;
    min-width        : 180px;
}}

QMenu::item:selected {{
    background-color : {acc};
    color            : {fg_w};
}}

QMenu::item:disabled {{
    color            : {fg_d};
}}

QMenu::separator {{
    height           : 1px;
    background-color : {bd};
    margin           : 4px 0;
}}

QMenu::indicator {{
    width  : 12px;
    height : 12px;
    left   : 8px;
}}

/* ── Status bar ───────────────────────────────────────────────────── */
QStatusBar#appStatusBar {{
    background-color : {bg_void};
    border-top       : 1px solid {bd};
    /* NO max-height — sized from content */
}}

QStatusBar#appStatusBar QLabel {{
    font-family : {sans};
    font-size   : 8.5pt;
}}

QLabel#sbMessage {{
    color   : {fg2};
    padding : 3px 10px;
}}

QLabel#sbInfo {{
    color   : {fg_m};
    padding : 3px 8px;
    font-family : {mono};
    font-size   : 8pt;
}}

QFrame#sbVsep {{
    background   : {bd};
    min-width    : 1px;
    max-width    : 1px;
}}

/* ── Custom dialog styling ─────────────────────────────────────────── */
QMessageBox {{
    background-color : {bg_card};
    font-family      : {sans};
}}

QMessageBox QLabel {{
    color       : {fg};
    font-size   : 9.5pt;
    min-width   : 380px;
    line-height : 1.6;
}}

QMessageBox QPushButton {{
    background-color : {btn_bg};
    color            : {fg};
    border           : 1px solid {bd_l};
    padding          : 5px 18px;
    border-radius    : 3px;
    min-width        : 80px;
    font-size        : 9.5pt;
    font-weight      : 500;
}}

QMessageBox QPushButton:default {{
    background-color : {btn_pri};
    color            : {fg_w};
    border           : none;
    font-weight      : 700;
}}

QMessageBox QPushButton:hover {{
    background-color : {btn_h};
    border-color     : {acc};
    color            : {fg};
}}

QMessageBox QPushButton:default:hover {{
    background-color : {btn_ph};
    color            : {fg_w};
}}

/* ── Progress dialog ────────────────────────────────────────────────── */
QProgressDialog {{
    background-color : {bg_card};
    border           : 1px solid {bd_l};
    border-radius    : 4px;
    font-family      : {sans};
}}

QProgressDialog QLabel {{
    color      : {fg};
    padding    : 10px 12px 4px 12px;
    font-size  : 9.5pt;
    min-width  : 380px;
}}

QProgressDialog QProgressBar {{
    border           : 1px solid {bd};
    border-radius    : 2px;
    text-align       : center;
    color            : {fg};
    background-color : {bg_dark};
    min-height       : 16px;
    font-size        : 8.5pt;
    font-family      : {mono};
}}

QProgressDialog QProgressBar::chunk {{
    background-color : {acc};
    border-radius    : 1px;
}}

QProgressDialog QPushButton {{
    background-color : {btn_bg};
    color            : {fg2};
    border           : 1px solid {bd};
    padding          : 4px 14px;
    border-radius    : 3px;
    min-width        : 72px;
    font-size        : 9pt;
}}

QProgressDialog QPushButton:hover {{
    background-color : {err};
    color            : {fg_w};
    border-color     : {err};
}}

        """)

    # ═════════════════════════════════════════════════════════════════════════
    #  Event handlers
    # ═════════════════════════════════════════════════════════════════════════

    def on_files_loaded(self, data: dict):
        self.loaded_data = data
        self._set_status("Files loaded successfully", kind='ok')
        self.timing_panel.set_data(data)
        QTimer.singleShot(4000, lambda: self._set_status("Ready"))
        logger.info("Design files loaded")

    def on_config_changed(self, config: STAConfig):
        self.config = config
        ConfigLoader.save_config(config)
        self._set_status("Configuration updated")
        logger.debug("Configuration updated")

    def on_analysis_stage(self, stage: str):
        self._set_status(f"{stage}...")

    def on_analysis_complete(self, results: dict):
        self.analysis_results = results
        self.results_panel.set_results(results)
        self.tab_widget.setCurrentIndex(1)
        self._set_status("Analysis complete", kind='ok')
        self._show_analysis_summary(results)
        logger.info("Analysis complete")

    def on_analysis_error(self, msg: str):
        self._set_status("Analysis failed", kind='err')
        self._alert("Analysis Failed",
                    f"The analysis encountered an error:\n\n{msg}",
                    critical=True)
        logger.error(f"Analysis error: {msg}")

    # ═════════════════════════════════════════════════════════════════════════
    #  Action methods
    # ═════════════════════════════════════════════════════════════════════════

    def run_analysis(self, analysis_type: str = 'all'):
        if not self.loaded_data:
            self._alert("No Design Loaded",
                        "Load the Liberty, Verilog, and SDC files before running analysis.")
            return

        self.config = self.options_panel.get_config()

        # ── Progress dialog
        pd = QProgressDialog(self)
        pd.setWindowTitle("Running STA Analysis")
        pd.setLabelText("Initializing analysis engines...")
        pd.setCancelButtonText("Cancel")
        pd.setRange(0, 100)
        pd.setWindowModality(Qt.WindowModality.WindowModal)
        pd.setMinimumWidth(440)
        pd.setMinimumHeight(120)
        pd.setAutoClose(True)
        pd.setAutoReset(True)
        self.progress_dialog = pd

        # ── Worker thread
        self.analysis_thread = STAAnalysisThread(self.loaded_data, self.config)
        self.analysis_thread.progress.connect(pd.setValue)
        self.analysis_thread.status.connect(pd.setLabelText)
        self.analysis_thread.stage.connect(self.on_analysis_stage)
        self.analysis_thread.finished.connect(self.on_analysis_complete)
        self.analysis_thread.error.connect(self.on_analysis_error)
        pd.canceled.connect(self._cancel_analysis)

        self.analysis_thread.start()
        self._set_status(f"Running {analysis_type} analysis...")
        pd.exec()
        logger.info(f"STA analysis started ({analysis_type})")

    def _cancel_analysis(self):
        if self.analysis_thread and self.analysis_thread.isRunning():
            self.analysis_thread.terminate()
            self._set_status("Analysis cancelled")
            logger.info("Analysis cancelled by user")

    def generate_reports(self):
        if not self.analysis_results:
            self._alert("No Results", "Run analysis before generating reports.")
            return
        paths = ReportGenerator().generate_all_reports(self.analysis_results)
        lines = "\n".join(
            f"  {k.upper():<20}  {Path(v).name}"
            for k, v in paths.items()
        )
        self._alert("Reports Generated",
                    f"Reports saved to the Reports/ directory.\n\n"
                    f"{'─' * 52}\n{lines}\n{'─' * 52}")
        logger.info("Reports generated")

    def open_reports_folder(self):
        folder = Path("Reports")
        folder.mkdir(exist_ok=True)
        if sys.platform == 'win32':
            os.startfile(folder)
        elif sys.platform == 'darwin':
            os.system(f'open "{folder}"')
        else:
            os.system(f'xdg-open "{folder}"')

    def show_about(self):
        C = DarkTheme.hex
        sans = "'Segoe UI', sans-serif"
        mono = "'Cascadia Code', 'Consolas', monospace"
        html = f"""
        <div style='font-family:{sans};padding:8px 6px;'>
          <table border='0' cellspacing='0' cellpadding='0'
                 style='margin-bottom:12px;'>
            <tr>
              <td style='padding-right:14px;'>
                <span style='font-size:32px;font-weight:900;
                             color:{C("accent")};letter-spacing:-1px;'>PySTA</span>
              </td>
              <td style='vertical-align:middle;border-left:2px solid {C("border")};
                         padding-left:14px;'>
                <div style='color:{C("fg_secondary")};font-size:11px;
                            font-weight:600;'>Static Timing Analyzer</div>
                <div style='color:{C("fg_muted")};font-size:9px;
                            font-family:{mono};margin-top:2px;'>
                    Version 1.0.0  |  Build 2026</div>
              </td>
            </tr>
          </table>
          <hr style='border:none;border-top:1px solid {C("border")};margin:0 0 10px;'>
          <table border='0' cellspacing='0' cellpadding='0'
                 style='color:{C("fg_secondary")};font-size:9px;line-height:1.9;'>
            <tr><td style='color:{C("fg_muted")};padding-right:12px;
                           font-weight:700;font-size:8px;letter-spacing:0.8px;'>
                CAPABILITY</td>
                <td style='color:{C("fg_muted")};font-weight:700;font-size:8px;
                           letter-spacing:0.8px;'>STATUS</td></tr>
            <tr><td>Liberty (.lib) parsing</td>
                <td style='color:{C("success")};font-family:{mono};'>Active</td></tr>
            <tr><td>Verilog netlist parsing</td>
                <td style='color:{C("success")};font-family:{mono};'>Active</td></tr>
            <tr><td>SDC constraint support</td>
                <td style='color:{C("success")};font-family:{mono};'>Active</td></tr>
            <tr><td>Setup timing analysis</td>
                <td style='color:{C("success")};font-family:{mono};'>Active</td></tr>
            <tr><td>Hold timing analysis</td>
                <td style='color:{C("success")};font-family:{mono};'>Active</td></tr>
            <tr><td>OCV derating</td>
                <td style='color:{C("success")};font-family:{mono};'>Active</td></tr>
            <tr><td>Signal integrity estimation</td>
                <td style='color:{C("success")};font-family:{mono};'>Active</td></tr>
            <tr><td>EDA-style reports (RPT/Excel)</td>
                <td style='color:{C("success")};font-family:{mono};'>Active</td></tr>
          </table>
          <hr style='border:none;border-top:1px solid {C("border")};margin:10px 0 6px;'>
          <div style='color:{C("fg_disabled")};font-size:8px;font-family:{mono};'>
              Copyright 2024 PySTA Project.  All rights reserved.</div>
        </div>
        """
        box = QMessageBox(self)
        box.setWindowTitle("About PySTA")
        box.setTextFormat(Qt.TextFormat.RichText)
        box.setText(html)
        box.setIcon(QMessageBox.Icon.NoIcon)
        box.setStandardButtons(QMessageBox.StandardButton.Ok)
        box.exec()

    def closeEvent(self, event):
        box = QMessageBox(self)
        box.setWindowTitle("Confirm Exit")
        box.setText("Exit PySTA?")
        box.setInformativeText("Any unsaved analysis data will be lost.")
        box.setIcon(QMessageBox.Icon.Question)
        box.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        box.setDefaultButton(QMessageBox.StandardButton.No)
        if box.exec() == QMessageBox.StandardButton.Yes:
            logger.info("Application exiting")
            event.accept()
        else:
            event.ignore()

    # ═════════════════════════════════════════════════════════════════════════
    #  Private helpers
    # ═════════════════════════════════════════════════════════════════════════

    def _set_status(self, text: str, kind: str = ''):
        self.status_label.setText(f"  {text}")
        palette_map = {
            'ok':  DarkTheme.hex('success'),
            'err': DarkTheme.hex('error'),
        }
        colour = palette_map.get(kind, DarkTheme.hex('fg_secondary'))
        self.status_label.setStyleSheet(f"color: {colour};")

    def _show_analysis_summary(self, results: dict):
        s = results.get('setup_results', {})
        h = results.get('hold_results',  {})

        C    = DarkTheme.hex
        mono = "'Cascadia Code', 'Consolas', monospace"
        sans = "'Segoe UI', sans-serif"

        def _row(label, val, unit="ps", ok_positive=True):
            val_ps  = val * 1e12
            colour  = C('success') if (val_ps >= 0) == ok_positive else C('error')
            sign    = "+" if val_ps >= 0 else ""
            return (f"<tr>"
                    f"<td style='padding:2px 16px 2px 0;color:{C('fg_muted')};'>{label}</td>"
                    f"<td style='font-family:{mono};color:{colour};'>"
                    f"{sign}{val_ps:,.2f} {unit}</td>"
                    f"</tr>")

        def _viol(label, count):
            colour = C('success') if count == 0 else C('error')
            return (f"<tr>"
                    f"<td style='padding:2px 16px 2px 0;color:{C('fg_muted')};'>{label}</td>"
                    f"<td style='font-family:{mono};color:{colour};'>{count}</td>"
                    f"</tr>")

        html = f"""
        <div style='font-family:{sans};font-size:9.5pt;'>
          <div style='font-size:11pt;font-weight:700;color:{C('fg_primary')};
                      margin-bottom:10px;'>Timing Summary</div>
        """

        if s:
            html += f"""
          <div style='font-weight:700;color:{C('accent')};font-size:9pt;
                      letter-spacing:0.5px;margin-bottom:4px;'>SETUP TIMING</div>
          <table border='0' cellspacing='0' style='margin-bottom:12px;font-size:9pt;'>
            {_row("Worst Negative Slack", s.get('worst_slack', 0))}
            {_viol("Violations", s.get('violations', 0))}
            {_row("Total Negative Slack", s.get('tns', 0))}
          </table>
            """
        if h:
            html += f"""
          <div style='font-weight:700;color:{C('secondary')};font-size:9pt;
                      letter-spacing:0.5px;margin-bottom:4px;'>HOLD TIMING</div>
          <table border='0' cellspacing='0' style='font-size:9pt;'>
            {_row("Worst Negative Slack", h.get('worst_slack', 0))}
            {_viol("Violations", h.get('violations', 0))}
            {_row("Total Negative Slack", h.get('tns', 0))}
          </table>
            """

        html += f"""
          <hr style='border:none;border-top:1px solid {C('border')};margin:10px 0 6px;'>
          <div style='color:{C('fg_muted')};font-size:8pt;font-family:{mono};'>
              Reports saved  →  Reports/</div>
        </div>
        """

        box = QMessageBox(self)
        box.setWindowTitle("Analysis Complete")
        box.setTextFormat(Qt.TextFormat.RichText)
        box.setText(html)
        box.setIcon(QMessageBox.Icon.NoIcon)
        box.setStandardButtons(QMessageBox.StandardButton.Ok)
        box.exec()

    def _alert(self, title: str, message: str, critical: bool = False):
        box = QMessageBox(self)
        box.setWindowTitle(title)
        box.setText(message)
        box.setIcon(QMessageBox.Icon.Critical if critical
                    else QMessageBox.Icon.Information)
        box.setStandardButtons(QMessageBox.StandardButton.Ok)
        box.exec()