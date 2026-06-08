"""
PySTA Premium Dark Theme
========================
A next-level dark theme for the PySTA GUI — PyQt6-native, pixel-perfect,
and tuned for the demands of a professional EDA/STA application.

Features:
  • Full PyQt6 compatibility (no deprecated AA_ attributes)
  • Expanded colour palette with semantic tokens
  • Richer widget coverage: Dock, ToolBar, Dial, Slider, Frame, Wizard …
  • Micro-detail polish: focus rings, press-depth, disabled states, alternating rows
  • Timing-domain colour helpers (slack, criticality, clock/data path)
  • Static utility methods for building custom widgets consistently
  • Zero external dependencies — pure PyQt6
"""

from __future__ import annotations

from PyQt6.QtCore    import Qt
from PyQt6.QtGui     import QColor, QFont, QLinearGradient, QBrush, QPalette, QIcon, QPixmap, QPainter
from PyQt6.QtWidgets import QApplication, QGraphicsDropShadowEffect, QWidget


# ──────────────────────────────────────────────────────────────────────────────
#  Colour Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _rgba(r: int, g: int, b: int, a: int = 255) -> QColor:
    """Convenience: build a QColor from RGBA components."""
    c = QColor(r, g, b)
    c.setAlpha(a)
    return c


def _hex(color: QColor) -> str:
    """Return '#RRGGBB' string from QColor."""
    return color.name()


def _hexA(color: QColor) -> str:
    """Return 'rgba(r,g,b,a)' string from QColor (alpha-aware)."""
    return f"rgba({color.red()},{color.green()},{color.blue()},{color.alpha()})"


# ──────────────────────────────────────────────────────────────────────────────
#  DarkTheme
# ──────────────────────────────────────────────────────────────────────────────

class DarkTheme:
    """
    Premium dark theme for PySTA.

    Usage
    -----
    Call once at startup, after QApplication is created::

        from Src.gui.dark_theme import DarkTheme
        DarkTheme.apply_theme(QApplication.instance())

    Individual colours are available via the :attr:`COLORS` dict.
    Utility factory methods help build consistent custom widgets.
    """

    # ── Typography ────────────────────────────────────────────────────────────
    FONT_FAMILY  = "'Segoe UI', 'Inter', 'Roboto', 'Microsoft YaHei', sans-serif"
    FONT_MONO    = "'Cascadia Code', 'Fira Code', 'Consolas', 'Courier New', monospace"
    FONT_SIZE    = 10       # pt  — base body size
    FONT_SIZE_SM =  9       # pt  — secondary / status bar
    FONT_SIZE_LG = 12       # pt  — section headings
    FONT_SIZE_XL = 15       # pt  — dialog / panel titles

    # ── Colour Palette ────────────────────────────────────────────────────────
    COLORS: dict[str, QColor] = {

        # ── Background layers (z-order: dark → base → card → light → overlay)
        'bg_void'       : QColor( 8,   8,  10),   # deepest well
        'bg_dark'       : QColor(12,  12,  15),   # panel / editor base
        'bg_base'       : QColor(18,  18,  22),   # main window background
        'bg_card'       : QColor(24,  24,  30),   # card / group box fill
        'bg_light'      : QColor(32,  32,  38),   # elevated surface
        'bg_overlay'    : _rgba(20,  20,  24, 230), # semi-transparent overlay

        # Legacy aliases kept for backward-compat with existing call-sites
        'background'      : QColor(18,  18,  22),
        'background_light': QColor(32,  32,  38),
        'background_dark' : QColor(12,  12,  15),
        'background_card' : QColor(24,  24,  30),

        # ── Foreground / text
        'fg_primary'    : QColor(228, 228, 238),   # primary body text
        'fg_secondary'  : QColor(180, 180, 195),   # secondary / captions
        'fg_muted'      : QColor(120, 120, 135),   # placeholders, hints
        'fg_disabled'   : QColor( 72,  72,  82),   # disabled labels
        'fg_on_accent'  : QColor(255, 255, 255),   # text on coloured buttons

        # Legacy aliases
        'foreground'         : QColor(228, 228, 238),
        'foreground_light'   : QColor(180, 180, 195),
        'foreground_muted'   : QColor(120, 120, 135),
        'foreground_disabled': QColor( 72,  72,  82),

        # ── Primary accent — Windows-blue
        'accent'              : QColor(  0, 122, 204),
        'accent_hover'        : QColor( 30, 145, 225),
        'accent_pressed'      : QColor(  0,  95, 175),
        'accent_subtle'       : _rgba(  0, 122, 204,  35),   # tinted bg
        'accent_light'        : QColor( 90, 175, 245),
        'accent_dark'         : QColor(  0,  75, 150),

        # ── Secondary accent — violet / purple (used for path / secondary panels)
        'secondary'           : QColor(120,  85, 210),
        'secondary_hover'     : QColor(148, 112, 238),
        'secondary_pressed'   : QColor( 90,  60, 175),
        'secondary_subtle'    : _rgba(120,  85, 210,  35),
        'secondary_light'     : QColor(165, 135, 248),
        'secondary_dark'      : QColor( 88,  55, 170),

        # ── Status — success / green
        'success'        : QColor( 38, 168,  80),
        'success_hover'  : QColor( 60, 195, 105),
        'success_subtle' : _rgba( 38, 168,  80,  30),
        'success_light'  : QColor( 80, 200, 120),

        # ── Status — warning / amber
        'warning'        : QColor(224, 148,  28),
        'warning_hover'  : QColor(248, 175,  55),
        'warning_subtle' : _rgba(224, 148,  28,  30),
        'warning_light'  : QColor(248, 190,  80),

        # ── Status — error / red
        'error'          : QColor(208,  60,  60),
        'error_hover'    : QColor(235,  90,  90),
        'error_subtle'   : _rgba(208,  60,  60,  30),
        'error_light'    : QColor(240, 105, 105),

        # ── Status — info / teal-cyan
        'info'           : QColor(  0, 155, 210),
        'info_subtle'    : _rgba(  0, 155, 210,  30),
        'info_light'     : QColor( 60, 190, 235),

        # ── Borders
        'border'         : QColor( 44,  44,  52),
        'border_light'   : QColor( 62,  62,  72),
        'border_focus'   : QColor(  0, 122, 204),
        'border_error'   : QColor(208,  60,  60),

        # ── Surface buttons
        'btn_bg'         : QColor( 36,  36,  44),
        'btn_hover'      : QColor( 48,  48,  58),
        'btn_pressed'    : QColor( 26,  26,  32),
        'btn_primary'    : QColor(  0, 100, 192),
        'btn_primary_hv' : QColor(  0, 122, 212),
        'btn_primary_pr' : QColor(  0,  78, 165),

        # Legacy button aliases
        'button'               : QColor( 36,  36,  44),
        'button_hover'         : QColor( 48,  48,  58),
        'button_pressed'       : QColor( 26,  26,  32),
        'button_primary'       : QColor(  0, 100, 192),
        'button_primary_hover' : QColor(  0, 122, 212),
        'button_primary_pressed':QColor(  0,  78, 165),

        # ── Selection
        'selection'      : QColor(  0, 100, 192),
        'selection_bg'   : _rgba(  0, 100, 192,  55),
        'selection_text' : QColor(255, 255, 255),
        'highlight'      : QColor(  0, 122, 204),
        'highlight_muted': _rgba(  0,  80, 140,  60),

        # ── Timing / EDA domain colours ───────────────────────────────────────
        # Slack coloring
        'slack_positive'    : QColor( 55, 175,  90),
        'slack_positive_bg' : _rgba( 38, 168,  80,  28),
        'slack_negative'    : QColor(215,  70,  70),
        'slack_negative_bg' : _rgba(208,  60,  60,  28),
        'slack_marginal'    : QColor(224, 148,  28),
        'slack_marginal_bg' : _rgba(200, 130,  20,  28),
        'slack_zero'        : QColor(120, 120, 135),

        # Path / arc types
        'clock_path'        : QColor(130, 192, 255),   # cool blue
        'data_path'         : QColor(165, 220, 168),   # soft green
        'path_critical'     : QColor(255, 125, 125),   # warm red
        'path_near_critical': QColor(250, 185,  70),   # amber
        'path_safe'         : QColor( 80, 200, 130),   # mint green

        # Criticality gradient anchors (use interpolate_criticality())
        'crit_low'          : QColor( 55, 175,  90),
        'crit_medium'       : QColor(224, 148,  28),
        'crit_high'         : QColor(208,  60,  60),

        # ── Graph / chart specific
        'chart_grid'        : QColor( 44,  44,  52),
        'chart_axis'        : QColor( 80,  80,  92),
        'chart_line_1'      : QColor(  0, 122, 204),
        'chart_line_2'      : QColor(120,  85, 210),
        'chart_line_3'      : QColor( 38, 168,  80),
        'chart_fill_1'      : _rgba(  0, 122, 204,  40),
        'chart_fill_2'      : _rgba(120,  85, 210,  40),
    }

    # ── Geometry / Spacing constants ──────────────────────────────────────────
    RADIUS_SM   =  4   # px — small radius (badges, tags)
    RADIUS_MD   =  6   # px — normal widgets
    RADIUS_LG   =  8   # px — panels, group boxes
    RADIUS_XL   = 12   # px — dialogs, cards
    BORDER_W    =  1   # px — standard border
    BORDER_W_FX =  2   # px — focus / active border

    # ──────────────────────────────────────────────────────────────────────────
    #  Palette
    # ──────────────────────────────────────────────────────────────────────────

    @staticmethod
    def get_palette() -> QPalette:
        """Return a fully configured QPalette for dark mode."""
        C  = DarkTheme.COLORS
        p  = QPalette()
        sr = p.setColor  # shorthand

        # Window surface
        sr(QPalette.ColorRole.Window,         C['bg_base'])
        sr(QPalette.ColorRole.WindowText,     C['fg_primary'])

        # Input / list base
        sr(QPalette.ColorRole.Base,           C['bg_dark'])
        sr(QPalette.ColorRole.AlternateBase,  C['bg_light'])

        # Tooltips
        sr(QPalette.ColorRole.ToolTipBase,    C['bg_light'])
        sr(QPalette.ColorRole.ToolTipText,    C['fg_primary'])

        # Text
        sr(QPalette.ColorRole.Text,           C['fg_primary'])
        sr(QPalette.ColorRole.PlaceholderText,C['fg_muted'])
        sr(QPalette.ColorRole.BrightText,     C['fg_secondary'])

        # Buttons
        sr(QPalette.ColorRole.Button,         C['btn_bg'])
        sr(QPalette.ColorRole.ButtonText,     C['fg_primary'])

        # Links
        sr(QPalette.ColorRole.Link,           C['accent'])
        sr(QPalette.ColorRole.LinkVisited,    C['secondary'])

        # Highlight / selection
        sr(QPalette.ColorRole.Highlight,      C['selection'])
        sr(QPalette.ColorRole.HighlightedText,C['selection_text'])

        # Shadow / mid tones
        sr(QPalette.ColorRole.Shadow,         C['bg_void'])
        sr(QPalette.ColorRole.Mid,            C['bg_card'])
        sr(QPalette.ColorRole.Midlight,       C['bg_light'])
        sr(QPalette.ColorRole.Dark,           C['bg_dark'])
        sr(QPalette.ColorRole.Light,          C['bg_overlay'])

        # ── Disabled group
        D  = QPalette.ColorGroup.Disabled
        for role in (
            QPalette.ColorRole.WindowText,
            QPalette.ColorRole.Text,
            QPalette.ColorRole.ButtonText,
        ):
            sr(D, role, C['fg_disabled'])

        sr(D, QPalette.ColorRole.Highlight,       C['bg_light'])
        sr(D, QPalette.ColorRole.HighlightedText, C['fg_disabled'])
        sr(D, QPalette.ColorRole.Button,          C['bg_card'])
        sr(D, QPalette.ColorRole.Base,            C['bg_dark'])

        return p

    # ──────────────────────────────────────────────────────────────────────────
    #  Master Stylesheet
    # ──────────────────────────────────────────────────────────────────────────

    @staticmethod
    def get_stylesheet() -> str:
        """Return the complete application stylesheet."""
        c = DarkTheme.COLORS          # colour map shorthand
        r = DarkTheme                  # constants shorthand

        # Pull frequently-used values into locals for readability
        bg          = _hex(c['bg_base'])
        bg_dark     = _hex(c['bg_dark'])
        bg_card     = _hex(c['bg_card'])
        bg_light    = _hex(c['bg_light'])
        bg_void     = _hex(c['bg_void'])

        fg          = _hex(c['fg_primary'])
        fg_sec      = _hex(c['fg_secondary'])
        fg_muted    = _hex(c['fg_muted'])
        fg_dis      = _hex(c['fg_disabled'])
        fg_accent   = _hex(c['fg_on_accent'])

        acc         = _hex(c['accent'])
        acc_hv      = _hex(c['accent_hover'])
        acc_pr      = _hex(c['accent_pressed'])
        acc_sub     = _hexA(c['accent_subtle'])

        sec         = _hex(c['secondary'])

        ok          = _hex(c['success'])
        ok_hv       = _hex(c['success_hover'])
        ok_sub      = _hexA(c['success_subtle'])

        warn        = _hex(c['warning'])
        warn_hv     = _hex(c['warning_hover'])
        warn_sub    = _hexA(c['warning_subtle'])

        err         = _hex(c['error'])
        err_hv      = _hex(c['error_hover'])
        err_sub     = _hexA(c['error_subtle'])

        info        = _hex(c['info'])
        info_sub    = _hexA(c['info_subtle'])

        bd          = _hex(c['border'])
        bd_lt       = _hex(c['border_light'])
        bd_fx       = _hex(c['border_focus'])
        bd_err      = _hex(c['border_error'])

        btn_bg      = _hex(c['btn_bg'])
        btn_hv      = _hex(c['btn_hover'])
        btn_pr      = _hex(c['btn_pressed'])
        btn_pri     = _hex(c['btn_primary'])
        btn_pri_hv  = _hex(c['btn_primary_hv'])
        btn_pri_pr  = _hex(c['btn_primary_pr'])

        sel         = _hex(c['selection'])
        sel_bg      = _hexA(c['selection_bg'])
        sel_txt     = _hex(c['selection_text'])

        ff          = r.FONT_FAMILY
        fm          = r.FONT_MONO
        fs          = r.FONT_SIZE
        fs_sm       = r.FONT_SIZE_SM
        fs_lg       = r.FONT_SIZE_LG
        fs_xl       = r.FONT_SIZE_XL
        rm          = r.RADIUS_MD
        rl          = r.RADIUS_LG
        rsl         = r.RADIUS_SM

        # ── Domain colours
        slk_pos     = _hex(c['slack_positive'])
        slk_pos_bg  = _hexA(c['slack_positive_bg'])
        slk_neg     = _hex(c['slack_negative'])
        slk_neg_bg  = _hexA(c['slack_negative_bg'])
        slk_mrg     = _hex(c['slack_marginal'])
        slk_mrg_bg  = _hexA(c['slack_marginal_bg'])
        clk_path    = _hex(c['clock_path'])
        dat_path    = _hex(c['data_path'])
        crit_path   = _hex(c['path_critical'])

        return f"""
/* ═══════════════════════════════════════════════════════════════════════════
   PySTA Premium Dark Theme  ·  PyQt6-native  ·  do not edit directly
   ═══════════════════════════════════════════════════════════════════════════ */

/* ── Global reset & base ──────────────────────────────────────────────── */
* {{
    font-family : {ff};
    font-size   : {fs}pt;
    outline     : none;
}}

QMainWindow, QDialog, QWidget {{
    background-color : {bg};
    color            : {fg};
}}

/* ── Frame / generic containers ──────────────────────────────────────── */
QFrame {{
    background-color : {bg};
    border           : none;
}}

QFrame[frameShape="4"],    /* HLine */
QFrame[frameShape="5"] {{  /* VLine */
    background-color : {bd};
    border           : none;
    max-height       : 1px;
    max-width        : 1px;
}}

/* ── Menu bar ────────────────────────────────────────────────────────── */
QMenuBar {{
    background-color : {bg_dark};
    color            : {fg_sec};
    border-bottom    : 1px solid {bd};
    padding          : 2px 4px;
    spacing          : 2px;
    font-weight      : 500;
}}

QMenuBar::item {{
    padding       : 5px 12px;
    border-radius : {rsl}px;
}}

QMenuBar::item:selected,
QMenuBar::item:hover {{
    background-color : {sel_bg};
    color            : {fg};
}}

QMenuBar::item:pressed {{
    background-color : {sel};
    color            : {sel_txt};
}}

/* ── Dropdown menu ───────────────────────────────────────────────────── */
QMenu {{
    background-color : {bg_light};
    color            : {fg};
    border           : 1px solid {bd_lt};
    border-radius    : {rm}px;
    padding          : 4px 2px;
}}

QMenu::item {{
    padding          : 7px 28px 7px 20px;
    border-radius    : {rsl}px;
    margin           : 1px 4px;
}}

QMenu::item:selected {{
    background-color : {sel};
    color            : {sel_txt};
}}

QMenu::icon {{
    margin-left : 8px;
}}

QMenu::separator {{
    height           : 1px;
    background-color : {bd};
    margin           : 5px 8px;
}}

QMenu::indicator {{
    width  : 14px;
    height : 14px;
    left   : 8px;
}}

/* ── Toolbar ─────────────────────────────────────────────────────────── */
QToolBar {{
    background-color : {bg_dark};
    border-bottom    : 1px solid {bd};
    padding          : 2px 4px;
    spacing          : 4px;
}}

QToolBar::separator {{
    width            : 1px;
    background-color : {bd};
    margin           : 4px 6px;
}}

QToolButton {{
    background-color : transparent;
    color            : {fg_sec};
    border           : 1px solid transparent;
    padding          : 5px 8px;
    border-radius    : {rsl}px;
    font-weight      : 500;
}}

QToolButton:hover {{
    background-color : {btn_hv};
    border-color     : {bd};
    color            : {fg};
}}

QToolButton:pressed {{
    background-color : {btn_pr};
    border-color     : {bd_lt};
}}

QToolButton:checked {{
    background-color : {acc_sub};
    border-color     : {acc};
    color            : {acc};
}}

QToolButton::menu-button {{
    border-left      : 1px solid {bd};
    width            : 16px;
    border-top-right-radius    : {rsl}px;
    border-bottom-right-radius : {rsl}px;
}}

/* ── Status bar ──────────────────────────────────────────────────────── */
QStatusBar {{
    background-color : {bg_dark};
    color            : {fg_muted};
    border-top       : 1px solid {bd};
    padding          : 2px 6px;
    font-size        : {fs_sm}pt;
}}

QStatusBar::item {{
    border        : none;
    padding       : 0 6px;
    border-radius : {rsl}px;
}}

QStatusBar QLabel {{
    color         : {fg_muted};
    font-size     : {fs_sm}pt;
    padding       : 0 4px;
}}

/* ── Dock widgets ────────────────────────────────────────────────────── */
QDockWidget {{
    color            : {fg_sec};
    titlebar-close-icon  : none;
    titlebar-normal-icon : none;
}}

QDockWidget::title {{
    background-color : {bg_dark};
    padding          : 6px 10px;
    border-bottom    : 1px solid {bd};
    font-weight      : 600;
    font-size        : {fs_sm}pt;
    letter-spacing   : 0.4px;
    text-transform   : uppercase;
}}

QDockWidget::close-button,
QDockWidget::float-button {{
    background-color : transparent;
    border           : none;
    padding          : 2px;
    border-radius    : {rsl}px;
}}

QDockWidget::close-button:hover,
QDockWidget::float-button:hover {{
    background-color : {btn_hv};
}}

/* ── Tab widget ──────────────────────────────────────────────────────── */
QTabWidget::pane {{
    border           : 1px solid {bd};
    background-color : {bg};
    border-radius    : 0 {rm}px {rm}px {rm}px;
    top              : -1px;
}}

QTabBar {{
    qproperty-drawBase : 0;
}}

QTabBar::tab {{
    background-color             : {bg_card};
    color                        : {fg_muted};
    padding                      : 8px 18px;
    margin-right                 : 2px;
    border                       : 1px solid {bd};
    border-bottom                : none;
    border-top-left-radius       : {rm}px;
    border-top-right-radius      : {rm}px;
    font-weight                  : 500;
    min-width                    : 80px;
}}

QTabBar::tab:selected {{
    background-color  : {bg};
    color             : {acc};
    border-color      : {bd};
    border-bottom     : 2px solid {acc};
    font-weight       : 600;
}}

QTabBar::tab:hover:!selected {{
    background-color  : {sel_bg};
    color             : {fg};
    border-color      : {bd_lt};
}}

QTabBar::tab:disabled {{
    color             : {fg_dis};
}}

QTabBar::close-button {{
    border-radius : 2px;
    padding       : 1px;
}}

QTabBar::close-button:hover {{
    background-color : {err_sub};
}}

/* ── Splitter ────────────────────────────────────────────────────────── */
QSplitter::handle {{
    background-color : {bd};
}}

QSplitter::handle:horizontal {{
    width  : 2px;
}}

QSplitter::handle:vertical {{
    height : 2px;
}}

QSplitter::handle:hover {{
    background-color : {acc};
}}

QSplitter::handle:pressed {{
    background-color : {acc_pr};
}}

/* ── Group box ───────────────────────────────────────────────────────── */
QGroupBox {{
    color            : {fg_sec};
    border           : 1px solid {bd};
    border-radius    : {rl}px;
    margin-top       : 14px;
    padding-top      : 18px;
    padding-left     : 8px;
    padding-right    : 8px;
    font-weight      : 600;
    font-size        : {fs_sm}pt;
    background-color : {bg_card};
}}

QGroupBox::title {{
    subcontrol-origin  : margin;
    subcontrol-position: top left;
    left               : 14px;
    padding            : 1px 8px;
    color              : {acc};
    background-color   : {bg_card};
    border-radius      : 3px;
    font-size          : {fs_sm}pt;
}}

/* ── Buttons ─────────────────────────────────────────────────────────── */
QPushButton {{
    background-color : {btn_bg};
    color            : {fg};
    border           : 1px solid {bd};
    padding          : 7px 18px;
    border-radius    : {rm}px;
    font-weight      : 500;
    min-width        : 84px;
}}

QPushButton:hover {{
    background-color : {btn_hv};
    border-color     : {bd_lt};
    color            : {fg};
}}

QPushButton:pressed {{
    background-color : {btn_pr};
    border-color     : {bd_lt};
    padding          : 8px 17px 6px 19px;
}}

QPushButton:disabled {{
    background-color : {bg_card};
    color            : {fg_dis};
    border-color     : {bd};
}}

QPushButton:default {{
    border-color     : {acc};
}}

/* Primary (call-to-action) */
QPushButton#primary {{
    background-color : {btn_pri};
    color            : {fg_accent};
    border           : none;
    font-weight      : 600;
}}

QPushButton#primary:hover {{
    background-color : {btn_pri_hv};
}}

QPushButton#primary:pressed {{
    background-color : {btn_pri_pr};
}}

QPushButton#primary:disabled {{
    background-color : {bg_card};
    color            : {fg_dis};
}}

/* Semantic variants */
QPushButton#success {{
    background-color : {ok};
    color            : {fg_accent};
    border           : none;
    font-weight      : 600;
}}

QPushButton#success:hover  {{ background-color : {ok_hv}; }}

QPushButton#warning {{
    background-color : {warn};
    color            : {fg_accent};
    border           : none;
    font-weight      : 600;
}}

QPushButton#warning:hover  {{ background-color : {warn_hv}; }}

QPushButton#danger {{
    background-color : {err};
    color            : {fg_accent};
    border           : none;
    font-weight      : 600;
}}

QPushButton#danger:hover   {{ background-color : {err_hv}; }}

/* Flat / ghost button */
QPushButton#flat, QPushButton#ghost {{
    background-color : transparent;
    border           : none;
    color            : {fg_sec};
    min-width        : 0;
}}

QPushButton#flat:hover, QPushButton#ghost:hover {{
    background-color : {btn_hv};
    color            : {fg};
}}

/* Icon-only button */
QPushButton#icon_btn {{
    background-color : transparent;
    border           : none;
    padding          : 5px;
    min-width        : 28px;
    border-radius    : {rsl}px;
}}

QPushButton#icon_btn:hover {{
    background-color : {btn_hv};
}}

/* ── Input fields ────────────────────────────────────────────────────── */
QLineEdit,
QTextEdit,
QPlainTextEdit {{
    background-color          : {bg_dark};
    color                     : {fg};
    border                    : 1px solid {bd};
    padding                   : 7px 10px;
    border-radius             : {rm}px;
    selection-background-color: {sel};
    selection-color           : {sel_txt};
}}

QLineEdit:hover,
QTextEdit:hover,
QPlainTextEdit:hover {{
    border-color : {bd_lt};
}}

QLineEdit:focus,
QTextEdit:focus,
QPlainTextEdit:focus {{
    border        : 2px solid {bd_fx};
    padding       : 6px 9px;
    background-color : {bg_void};
}}

QLineEdit:disabled,
QTextEdit:disabled,
QPlainTextEdit:disabled {{
    background-color : {bg_card};
    color            : {fg_dis};
    border-color     : {bd};
}}

QLineEdit[readOnly="true"],
QTextEdit[readOnly="true"],
QPlainTextEdit[readOnly="true"] {{
    background-color : {bg_card};
    color            : {fg_sec};
    border-color     : {bd};
}}

/* Monospace variant — for code / timing reports */
QTextEdit#mono, QPlainTextEdit#mono {{
    font-family : {fm};
    font-size   : {fs_sm}pt;
    line-height : 1.5;
}}

/* ── Combo box ───────────────────────────────────────────────────────── */
QComboBox {{
    background-color : {bg_dark};
    color            : {fg};
    border           : 1px solid {bd};
    padding          : 6px 12px;
    border-radius    : {rm}px;
    min-width        : 120px;
}}

QComboBox:hover {{
    border-color     : {bd_lt};
}}

QComboBox:focus {{
    border           : 2px solid {bd_fx};
    padding          : 5px 11px;
}}

QComboBox:disabled {{
    background-color : {bg_card};
    color            : {fg_dis};
    border-color     : {bd};
}}

QComboBox::drop-down {{
    subcontrol-origin    : padding;
    subcontrol-position  : center right;
    width                : 26px;
    border-left          : 1px solid {bd};
    border-top-right-radius    : {rm}px;
    border-bottom-right-radius : {rm}px;
}}

QComboBox::down-arrow {{
    width  : 10px;
    height : 10px;
}}

QComboBox QAbstractItemView {{
    background-color          : {bg_dark};
    color                     : {fg};
    selection-background-color: {sel};
    selection-color           : {sel_txt};
    border                    : 1px solid {bd_lt};
    border-radius             : {rm}px;
    outline                   : none;
    padding                   : 4px;
}}

QComboBox QAbstractItemView::item {{
    padding       : 6px 12px;
    border-radius : {rsl}px;
    min-height    : 26px;
}}

/* ── Spin boxes ──────────────────────────────────────────────────────── */
QSpinBox, QDoubleSpinBox {{
    background-color : {bg_dark};
    color            : {fg};
    border           : 1px solid {bd};
    padding          : 6px 8px;
    border-radius    : {rm}px;
}}

QSpinBox:hover, QDoubleSpinBox:hover {{
    border-color : {bd_lt};
}}

QSpinBox:focus, QDoubleSpinBox:focus {{
    border : 2px solid {bd_fx};
    padding: 5px 7px;
}}

QSpinBox::up-button, QDoubleSpinBox::up-button {{
    subcontrol-origin   : border;
    subcontrol-position : top right;
    width               : 22px;
    border-left         : 1px solid {bd};
    border-top-right-radius : {rm}px;
    background-color    : {btn_bg};
}}

QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover {{
    background-color : {btn_hv};
}}

QSpinBox::down-button, QDoubleSpinBox::down-button {{
    subcontrol-origin   : border;
    subcontrol-position : bottom right;
    width               : 22px;
    border-left         : 1px solid {bd};
    border-bottom-right-radius : {rm}px;
    background-color    : {btn_bg};
}}

QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {{
    background-color : {btn_hv};
}}

/* ── Check box ───────────────────────────────────────────────────────── */
QCheckBox {{
    color   : {fg};
    spacing : 8px;
}}

QCheckBox:disabled {{
    color : {fg_dis};
}}

QCheckBox::indicator {{
    width            : 18px;
    height           : 18px;
    border           : 2px solid {bd};
    border-radius    : {rsl}px;
    background-color : {bg_dark};
}}

QCheckBox::indicator:hover {{
    border-color : {acc};
    background-color : {acc_sub};
}}

QCheckBox::indicator:checked {{
    background-color : {acc};
    border-color     : {acc};
    /* inner check mark is rendered natively via Fusion */
}}

QCheckBox::indicator:checked:hover {{
    background-color : {acc_hv};
    border-color     : {acc_hv};
}}

QCheckBox::indicator:indeterminate {{
    background-color : {sec};
    border-color     : {sec};
}}

QCheckBox::indicator:disabled {{
    background-color : {bg_card};
    border-color     : {bd};
}}

/* ── Radio button ────────────────────────────────────────────────────── */
QRadioButton {{
    color   : {fg};
    spacing : 8px;
}}

QRadioButton:disabled {{
    color : {fg_dis};
}}

QRadioButton::indicator {{
    width            : 18px;
    height           : 18px;
    border           : 2px solid {bd};
    border-radius    : 9px;
    background-color : {bg_dark};
}}

QRadioButton::indicator:hover {{
    border-color     : {acc};
    background-color : {acc_sub};
}}

QRadioButton::indicator:checked {{
    background-color : {acc};
    border-color     : {acc};
}}

QRadioButton::indicator:disabled {{
    background-color : {bg_card};
    border-color     : {bd};
}}

/* ── Slider ──────────────────────────────────────────────────────────── */
QSlider::groove:horizontal {{
    height           : 4px;
    background-color : {bg_light};
    border-radius    : 2px;
    margin           : 0 4px;
}}

QSlider::sub-page:horizontal {{
    background-color : {acc};
    border-radius    : 2px;
}}

QSlider::handle:horizontal {{
    background-color : {acc};
    border           : 2px solid {acc_hv};
    width            : 16px;
    height           : 16px;
    margin           : -6px -4px;
    border-radius    : 8px;
}}

QSlider::handle:horizontal:hover {{
    background-color : {acc_hv};
    width            : 18px;
    height           : 18px;
    margin           : -7px -5px;
}}

QSlider::handle:horizontal:disabled {{
    background-color : {fg_dis};
    border-color     : {bd};
}}

QSlider::groove:vertical {{
    width            : 4px;
    background-color : {bg_light};
    border-radius    : 2px;
    margin           : 4px 0;
}}

QSlider::sub-page:vertical {{
    background-color : {acc};
    border-radius    : 2px;
}}

QSlider::handle:vertical {{
    background-color : {acc};
    border           : 2px solid {acc_hv};
    width            : 16px;
    height           : 16px;
    margin           : -4px -6px;
    border-radius    : 8px;
}}

/* ── Table view ──────────────────────────────────────────────────────── */
QTableView {{
    background-color          : {bg_dark};
    color                     : {fg};
    border                    : 1px solid {bd};
    border-radius             : {rm}px;
    gridline-color            : {bd};
    selection-background-color: {sel};
    selection-color           : {sel_txt};
    alternate-background-color: {bg_card};
}}

QTableView::item {{
    padding       : 7px 10px;
    border-bottom : 1px solid {bd};
}}

QTableView::item:selected {{
    background-color : {sel};
    color            : {sel_txt};
}}

QTableView::item:hover:!selected {{
    background-color : {sel_bg};
}}

QTableView::item:focus {{
    border : 1px solid {bd_fx};
}}

QTableCornerButton::section {{
    background-color : {bg_light};
    border           : 1px solid {bd};
}}

/* ── Tree view ───────────────────────────────────────────────────────── */
QTreeView {{
    background-color          : {bg_dark};
    color                     : {fg};
    border                    : 1px solid {bd};
    border-radius             : {rm}px;
    alternate-background-color: {bg_card};
    selection-background-color: {sel};
    selection-color           : {sel_txt};
}}

QTreeView::item {{
    padding       : 5px 8px;
    border-radius : {rsl}px;
}}

QTreeView::item:hover:!selected {{
    background-color : {sel_bg};
}}

QTreeView::item:selected {{
    background-color : {sel};
    color            : {sel_txt};
}}

QTreeView::branch {{
    background-color : {bg_dark};
}}

QTreeView::branch:has-children:!has-siblings:closed,
QTreeView::branch:closed:has-children:has-siblings {{
    border-image : none;
}}

QTreeView::branch:open:has-children:!has-siblings,
QTreeView::branch:open:has-children:has-siblings {{
    border-image : none;
}}

/* ── Header view (tables & trees) ────────────────────────────────────── */
QHeaderView {{
    background-color : {bg_light};
    border           : none;
}}

QHeaderView::section {{
    background-color : {bg_light};
    color            : {fg_sec};
    padding          : 8px 12px;
    border           : none;
    border-right     : 1px solid {bd};
    border-bottom    : 2px solid {acc};
    font-weight      : 600;
    font-size        : {fs_sm}pt;
    letter-spacing   : 0.3px;
}}

QHeaderView::section:first {{
    border-top-left-radius : {rm}px;
}}

QHeaderView::section:last {{
    border-top-right-radius : {rm}px;
    border-right : none;
}}

QHeaderView::section:hover {{
    background-color : {btn_hv};
    color            : {fg};
}}

QHeaderView::section:checked {{
    background-color : {acc_sub};
    color            : {acc};
}}

QHeaderView::down-arrow,
QHeaderView::up-arrow {{
    width  : 10px;
    height : 10px;
    margin-right : 4px;
}}

/* ── List widget ─────────────────────────────────────────────────────── */
QListWidget {{
    background-color          : {bg_dark};
    color                     : {fg};
    border                    : 1px solid {bd};
    border-radius             : {rm}px;
    alternate-background-color: {bg_card};
    selection-background-color: {sel};
    selection-color           : {sel_txt};
}}

QListWidget::item {{
    padding          : 7px 14px;
    border-radius    : {rsl}px;
    margin           : 1px 2px;
}}

QListWidget::item:hover:!selected {{
    background-color : {sel_bg};
}}

QListWidget::item:selected {{
    background-color : {sel};
    color            : {sel_txt};
}}

/* ── Scroll bars ─────────────────────────────────────────────────────── */
QScrollBar:vertical {{
    background-color : transparent;
    width            : 10px;
    margin           : 0;
}}

QScrollBar::handle:vertical {{
    background-color : {btn_bg};
    min-height       : 32px;
    border-radius    : 5px;
    margin           : 2px 2px 2px 1px;
}}

QScrollBar::handle:vertical:hover {{
    background-color : {bd_lt};
}}

QScrollBar::handle:vertical:pressed {{
    background-color : {acc};
}}

QScrollBar:horizontal {{
    background-color : transparent;
    height           : 10px;
    margin           : 0;
}}

QScrollBar::handle:horizontal {{
    background-color : {btn_bg};
    min-width        : 32px;
    border-radius    : 5px;
    margin           : 1px 2px 2px 2px;
}}

QScrollBar::handle:horizontal:hover {{
    background-color : {bd_lt};
}}

QScrollBar::handle:horizontal:pressed {{
    background-color : {acc};
}}

QScrollBar::add-line,
QScrollBar::sub-line,
QScrollBar::add-page,
QScrollBar::sub-page {{
    background : none;
    border     : none;
}}

/* ── Progress bar ────────────────────────────────────────────────────── */
QProgressBar {{
    border           : 1px solid {bd};
    border-radius    : {rm}px;
    text-align       : center;
    color            : {fg};
    background-color : {bg_dark};
    font-weight      : 600;
    font-size        : {fs_sm}pt;
    min-height       : 18px;
}}

QProgressBar::chunk {{
    background-color : {acc};
    border-radius    : {rm}px;
}}

QProgressBar[value="100"]::chunk {{
    background-color : {ok};
}}

/* ── Tooltips ────────────────────────────────────────────────────────── */
QToolTip {{
    background-color : {bg_light};
    color            : {fg};
    border           : 1px solid {bd_lt};
    border-radius    : {rsl}px;
    padding          : 6px 10px;
    font-size        : {fs_sm}pt;
    opacity          : 240;
}}

/* ── Labels ──────────────────────────────────────────────────────────── */
QLabel {{
    color            : {fg};
    background-color : transparent;
}}

QLabel#title {{
    font-size        : {fs_xl}pt;
    font-weight      : 700;
    color            : {fg};
    letter-spacing   : -0.3px;
}}

QLabel#subtitle {{
    font-size        : {fs_lg}pt;
    font-weight      : 600;
    color            : {acc};
    letter-spacing   : 0.1px;
}}

QLabel#caption {{
    font-size        : {fs_sm}pt;
    color            : {fg_muted};
}}

QLabel#section_header {{
    font-size        : {fs_sm}pt;
    font-weight      : 700;
    color            : {fg_sec};
    letter-spacing   : 0.8px;
    text-transform   : uppercase;
    padding          : 2px 0;
    border-bottom    : 1px solid {bd};
}}

QLabel#info    {{ color : {info};  font-style : italic; }}
QLabel#warning {{ color : {warn};  font-weight : 600;   }}
QLabel#error   {{ color : {err};   font-weight : 600;   }}
QLabel#success {{ color : {ok};    font-weight : 600;   }}
QLabel#accent  {{ color : {acc};   font-weight : 600;   }}
QLabel#muted   {{ color : {fg_muted};                   }}

/* Badge labels */
QLabel#badge_primary  {{ background-color : {acc};  color : {fg_accent}; border-radius : {rsl}px; padding : 2px 8px; font-size : {fs_sm}pt; font-weight : 600; }}
QLabel#badge_success  {{ background-color : {ok};   color : {fg_accent}; border-radius : {rsl}px; padding : 2px 8px; font-size : {fs_sm}pt; font-weight : 600; }}
QLabel#badge_warning  {{ background-color : {warn}; color : {fg_accent}; border-radius : {rsl}px; padding : 2px 8px; font-size : {fs_sm}pt; font-weight : 600; }}
QLabel#badge_error    {{ background-color : {err};  color : {fg_accent}; border-radius : {rsl}px; padding : 2px 8px; font-size : {fs_sm}pt; font-weight : 600; }}

/* ── Timing / EDA domain cell colouring ─────────────────────────────── */
QTableView QLabel#slack_positive,
QTreeView  QLabel#slack_positive {{
    color            : {slk_pos};
    background-color : {slk_pos_bg};
    font-weight      : 700;
    padding          : 2px 6px;
    border-radius    : {rsl}px;
}}

QTableView QLabel#slack_negative,
QTreeView  QLabel#slack_negative {{
    color            : {slk_neg};
    background-color : {slk_neg_bg};
    font-weight      : 700;
    padding          : 2px 6px;
    border-radius    : {rsl}px;
}}

QTableView QLabel#slack_marginal,
QTreeView  QLabel#slack_marginal {{
    color            : {slk_mrg};
    background-color : {slk_mrg_bg};
    font-weight      : 700;
    padding          : 2px 6px;
    border-radius    : {rsl}px;
}}

/* Inline class selectors (used by custom delegates) */
.slack-positive {{
    color            : {slk_pos};
    background-color : {slk_pos_bg};
    font-weight      : 700;
}}

.slack-negative {{
    color            : {slk_neg};
    background-color : {slk_neg_bg};
    font-weight      : 700;
}}

.slack-marginal {{
    color            : {slk_mrg};
    background-color : {slk_mrg_bg};
    font-weight      : 700;
}}

.clock-path {{
    color       : {clk_path};
    font-weight : 600;
}}

.data-path {{
    color       : {dat_path};
    font-weight : 600;
}}

.critical-path {{
    color       : {crit_path};
    font-weight : 700;
}}

/* ── Scroll area ─────────────────────────────────────────────────────── */
QScrollArea {{
    background-color : {bg};
    border           : none;
}}

QScrollArea > QWidget > QWidget {{
    background-color : {bg};
}}

/* ── Wizard pages ────────────────────────────────────────────────────── */
QWizard {{
    background-color : {bg};
}}

QWizardPage {{
    background-color : {bg};
}}

/* ── Message box ─────────────────────────────────────────────────────── */
QMessageBox {{
    background-color : {bg_card};
    border-radius    : {rl}px;
}}

QMessageBox QLabel {{
    color            : {fg};
    min-width        : 300px;
}}

/* ── Input dialog ────────────────────────────────────────────────────── */
QInputDialog {{
    background-color : {bg_card};
}}

/* ── File dialog ─────────────────────────────────────────────────────── */
QFileDialog {{
    background-color : {bg};
    color            : {fg};
}}

QFileDialog QTreeView,
QFileDialog QListView {{
    background-color : {bg_dark};
    border           : 1px solid {bd};
    border-radius    : {rm}px;
}}

/* ── Color dialog ────────────────────────────────────────────────────── */
QColorDialog {{
    background-color : {bg};
}}

/* ── Font dialog ─────────────────────────────────────────────────────── */
QFontDialog {{
    background-color : {bg};
}}

/* ═══════════════════════════════════════════════════════════════════════ */
"""

    # ──────────────────────────────────────────────────────────────────────────
    #  Theme Application
    # ──────────────────────────────────────────────────────────────────────────

    @staticmethod
    def apply_theme(app: QApplication) -> None:
        """
        Apply the premium dark theme to a QApplication instance.

        This method is PyQt6-compatible — it does not use any deprecated
        ``AA_EnableHighDpiScaling`` attribute (removed in PyQt6 ≥ 6.0).

        Parameters
        ----------
        app : QApplication
            The running application instance.
        """
        if app is None:
            return

        # Fusion gives us a consistent cross-platform baseline
        app.setStyle("Fusion")

        # Apply colour palette first, then stylesheet overrides
        app.setPalette(DarkTheme.get_palette())
        app.setStyleSheet(DarkTheme.get_stylesheet())

        # High-DPI: in PyQt6 this is on by default — no attribute needed.
        # AA_EnableHighDpiScaling was removed in PyQt6; calling it raises
        # AttributeError, so we deliberately omit it.

    # ──────────────────────────────────────────────────────────────────────────
    #  Utility Factories
    # ──────────────────────────────────────────────────────────────────────────

    @staticmethod
    def get_gradient(
        start_color: QColor,
        end_color:   QColor,
        horizontal:  bool = True,
    ) -> QBrush:
        """Return a QBrush with a linear gradient between two colours."""
        grad = QLinearGradient(0, 0, 1 if horizontal else 0, 0 if horizontal else 1)
        grad.setCoordinateMode(QLinearGradient.CoordinateMode.ObjectBoundingMode)
        grad.setColorAt(0.0, start_color)
        grad.setColorAt(1.0, end_color)
        return QBrush(grad)

    @staticmethod
    def make_shadow(
        widget:     QWidget,
        radius:     int   = 18,
        x_offset:   float = 0.0,
        y_offset:   float = 4.0,
        color:      QColor | None = None,
    ) -> QGraphicsDropShadowEffect:
        """
        Attach and return a drop-shadow effect on *widget*.

        Parameters
        ----------
        widget    : target widget
        radius    : blur radius in pixels
        x_offset  : horizontal shadow offset
        y_offset  : vertical shadow offset
        color     : shadow colour (default: semi-transparent black)
        """
        shadow = QGraphicsDropShadowEffect(widget)
        shadow.setBlurRadius(radius)
        shadow.setXOffset(x_offset)
        shadow.setYOffset(y_offset)
        shadow.setColor(color or _rgba(0, 0, 0, 160))
        widget.setGraphicsEffect(shadow)
        return shadow

    @staticmethod
    def get_font(
        size:   int  = 0,
        bold:   bool = False,
        italic: bool = False,
        mono:   bool = False,
    ) -> QFont:
        """
        Return a themed QFont.

        Parameters
        ----------
        size   : point size (0 = default body size)
        bold   : set bold weight
        italic : set italic style
        mono   : use monospace family instead of sans-serif
        """
        family = "Cascadia Code" if mono else "Segoe UI"
        font   = QFont(family, size or DarkTheme.FONT_SIZE)
        font.setBold(bold)
        font.setItalic(italic)
        if mono:
            font.setFixedPitch(True)
        return font

    @staticmethod
    def interpolate_criticality(ratio: float) -> QColor:
        """
        Return a colour on the green → amber → red spectrum.

        Parameters
        ----------
        ratio : float in [0.0, 1.0]
                0.0 = safe (green), 0.5 = marginal (amber), 1.0 = critical (red)
        """
        ratio = max(0.0, min(1.0, ratio))
        C = DarkTheme.COLORS
        if ratio <= 0.5:
            t = ratio * 2.0
            a, b = C['crit_low'], C['crit_medium']
        else:
            t = (ratio - 0.5) * 2.0
            a, b = C['crit_medium'], C['crit_high']

        r = int(a.red()   + t * (b.red()   - a.red()))
        g = int(a.green() + t * (b.green() - a.green()))
        bl= int(a.blue()  + t * (b.blue()  - a.blue()))
        return QColor(r, g, bl)

    @staticmethod
    def slack_color(slack_ns: float, wns_ns: float = -1.0) -> QColor:
        """
        Return the appropriate slack colour for a timing path.

        Parameters
        ----------
        slack_ns : slack value in nanoseconds
        wns_ns   : worst negative slack in the design (used for normalisation)
        """
        C = DarkTheme.COLORS
        if slack_ns > 0.0:
            return C['slack_positive']
        if slack_ns == 0.0:
            return C['slack_zero']
        if wns_ns < 0.0 and wns_ns != 0.0:
            ratio = min(1.0, slack_ns / wns_ns)
            return DarkTheme.interpolate_criticality(ratio)
        return C['slack_negative']

    @staticmethod
    def color(name: str) -> QColor:
        """Look up a named colour, raising KeyError with a helpful message."""
        try:
            return DarkTheme.COLORS[name]
        except KeyError:
            available = ", ".join(sorted(DarkTheme.COLORS.keys()))
            raise KeyError(
                f"Unknown theme colour '{name}'.\n"
                f"Available keys: {available}"
            ) from None

    @staticmethod
    def hex(name: str) -> str:
        """Return the '#RRGGBB' string for a named theme colour."""
        return _hex(DarkTheme.color(name))