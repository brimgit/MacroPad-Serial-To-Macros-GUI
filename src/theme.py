_DARK = {
    'BG': '#0d1117', 'BG_CARD': '#161c2a', 'BG_ELEVATED': '#1c2438',
    'BG_HOVER': '#222d42', 'SIDEBAR_BG': '#090e1a',
    'ACCENT': '#06b6d4', 'ACCENT_DIM': '#0891b2', 'ACCENT_HOVER': '#22d3ee', 'ACCENT_GLOW': '#06b6d418',
    'SUCCESS': '#10b981', 'WARNING': '#f59e0b', 'DANGER': '#ef4444',
    'TEXT': '#f1f5f9', 'TEXT_MUTED': '#94a3b8', 'TEXT_DIM': '#4b5675',
    'BORDER': '#1e2a3a', 'BORDER_LIGHT': '#283548',
}
_LIGHT = {
    'BG': '#e8eaed', 'BG_CARD': '#f1f3f5', 'BG_ELEVATED': '#e0e3e8',
    'BG_HOVER': '#d4d8de', 'SIDEBAR_BG': '#e8eaed',
    'ACCENT': '#0284c7', 'ACCENT_DIM': '#0369a1', 'ACCENT_HOVER': '#0ea5e9', 'ACCENT_GLOW': '#0284c718',
    'SUCCESS': '#16a34a', 'WARNING': '#d97706', 'DANGER': '#dc2626',
    'TEXT': '#111827', 'TEXT_MUTED': '#4b5563', 'TEXT_DIM': '#9ca3af',
    'BORDER': '#d1d5db', 'BORDER_LIGHT': '#c4c8cf',
}

_mode = 'dark'

BG           = _DARK['BG']
BG_CARD      = _DARK['BG_CARD']
BG_ELEVATED  = _DARK['BG_ELEVATED']
BG_HOVER     = _DARK['BG_HOVER']
SIDEBAR_BG   = _DARK['SIDEBAR_BG']
ACCENT       = _DARK['ACCENT']
ACCENT_DIM   = _DARK['ACCENT_DIM']
ACCENT_HOVER = _DARK['ACCENT_HOVER']
ACCENT_GLOW  = _DARK['ACCENT_GLOW']
SUCCESS      = _DARK['SUCCESS']
WARNING      = _DARK['WARNING']
DANGER       = _DARK['DANGER']
TEXT         = _DARK['TEXT']
TEXT_MUTED   = _DARK['TEXT_MUTED']
TEXT_DIM     = _DARK['TEXT_DIM']
BORDER       = _DARK['BORDER']
BORDER_LIGHT = _DARK['BORDER_LIGHT']


def set_mode(mode):
    global _mode
    global BG, BG_CARD, BG_ELEVATED, BG_HOVER, SIDEBAR_BG
    global ACCENT, ACCENT_DIM, ACCENT_HOVER, ACCENT_GLOW
    global SUCCESS, WARNING, DANGER
    global TEXT, TEXT_MUTED, TEXT_DIM
    global BORDER, BORDER_LIGHT

    _mode = mode
    palette = _DARK if mode == 'dark' else _LIGHT

    BG           = palette['BG']
    BG_CARD      = palette['BG_CARD']
    BG_ELEVATED  = palette['BG_ELEVATED']
    BG_HOVER     = palette['BG_HOVER']
    SIDEBAR_BG   = palette['SIDEBAR_BG']
    ACCENT       = palette['ACCENT']
    ACCENT_DIM   = palette['ACCENT_DIM']
    ACCENT_HOVER = palette['ACCENT_HOVER']
    ACCENT_GLOW  = palette['ACCENT_GLOW']
    SUCCESS      = palette['SUCCESS']
    WARNING      = palette['WARNING']
    DANGER       = palette['DANGER']
    TEXT         = palette['TEXT']
    TEXT_MUTED   = palette['TEXT_MUTED']
    TEXT_DIM     = palette['TEXT_DIM']
    BORDER       = palette['BORDER']
    BORDER_LIGHT = palette['BORDER_LIGHT']


def get_mode():
    return _mode


def build_stylesheet():
    return f"""
* {{
    font-family: 'Segoe UI Variable', 'Segoe UI', 'Inter', Arial, sans-serif;
}}
QMainWindow {{
    background-color: {BG};
}}
QWidget {{
    background-color: {BG};
    color: {TEXT};
    font-size: 13px;
}}
QLabel {{
    background: transparent;
    color: {TEXT};
}}
QFrame {{
    background-color: {BG_CARD};
    border: none;
}}

/* ── Buttons ────────────────────────────────── */
QPushButton {{
    background-color: {BG_ELEVATED};
    color: {TEXT_MUTED};
    border: 1px solid {BORDER_LIGHT};
    border-radius: 8px;
    padding: 8px 18px;
    font-size: 13px;
    font-weight: 500;
}}
QPushButton:hover {{
    background-color: {BG_HOVER};
    border-color: {ACCENT};
    color: {TEXT};
}}
QPushButton:pressed {{
    background-color: {ACCENT_DIM};
    color: white;
    border-color: {ACCENT_DIM};
}}
QPushButton:disabled {{
    color: {TEXT_DIM};
    border-color: {BORDER};
    background-color: {BG_CARD};
}}

/* ── ComboBox ───────────────────────────────── */
QComboBox {{
    background-color: {BG_ELEVATED};
    color: {TEXT};
    border: 1px solid {BORDER_LIGHT};
    border-radius: 8px;
    padding: 7px 36px 7px 12px;
    min-width: 100px;
    selection-background-color: {ACCENT};
    selection-color: #000;
}}
QComboBox:hover {{
    border-color: {ACCENT};
    background-color: {BG_HOVER};
}}
QComboBox:focus {{
    border-color: {ACCENT};
}}
QComboBox::drop-down {{
    border: none;
    width: 30px;
    subcontrol-origin: padding;
    subcontrol-position: right center;
}}
QComboBox::down-arrow {{
    image: none;
    width: 0;
    height: 0;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {TEXT_DIM};
    margin-right: 10px;
}}
QComboBox QAbstractItemView {{
    background-color: {BG_CARD};
    border: 1px solid {BORDER_LIGHT};
    border-radius: 10px;
    padding: 4px;
    selection-background-color: {ACCENT};
    selection-color: #000;
    outline: none;
}}
QComboBox QAbstractItemView::item {{
    padding: 7px 12px;
    border-radius: 6px;
    min-height: 28px;
    color: {TEXT};
    background-color: transparent;
}}
QComboBox QAbstractItemView::item:hover {{
    background-color: {BG_ELEVATED};
}}
QComboBox QAbstractItemView::item:selected {{
    background-color: {ACCENT};
    color: #000;
}}

/* ── LineEdit ───────────────────────────────── */
QLineEdit {{
    background-color: {BG_ELEVATED};
    color: {TEXT};
    border: 1px solid {BORDER_LIGHT};
    border-radius: 8px;
    padding: 7px 12px;
    selection-background-color: {ACCENT};
}}
QLineEdit:focus {{
    border-color: {ACCENT};
}}

/* ── TextEdit ───────────────────────────────── */
QTextEdit {{
    background-color: {BG};
    color: {TEXT_MUTED};
    border: 1px solid {BORDER};
    border-radius: 10px;
    padding: 10px;
    font-family: 'Cascadia Code', 'Consolas', monospace;
    font-size: 12px;
    line-height: 1.5;
}}

/* ── Sliders ────────────────────────────────── */
QSlider::groove:horizontal {{
    background: {BG_ELEVATED};
    height: 5px;
    border-radius: 3px;
}}
QSlider::handle:horizontal {{
    background: {ACCENT};
    border: 2px solid {BG};
    width: 16px;
    height: 16px;
    margin: -6px 0;
    border-radius: 8px;
}}
QSlider::sub-page:horizontal {{
    background: {ACCENT};
    border-radius: 3px;
}}

/* ── Scrollbars ─────────────────────────────── */
QScrollBar:vertical {{
    background: transparent;
    width: 6px;
    margin: 2px 0;
}}
QScrollBar::handle:vertical {{
    background: {BORDER_LIGHT};
    border-radius: 3px;
    min-height: 32px;
}}
QScrollBar::handle:vertical:hover {{
    background: {TEXT_DIM};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
    background: none;
}}
QScrollBar:horizontal {{
    background: transparent;
    height: 6px;
    margin: 0 2px;
}}
QScrollBar::handle:horizontal {{
    background: {BORDER_LIGHT};
    border-radius: 3px;
    min-width: 32px;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
    background: none;
}}

/* ── CheckBox ───────────────────────────────── */
QCheckBox {{
    color: {TEXT};
    spacing: 8px;
}}
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border-radius: 4px;
    border: 1px solid {BORDER_LIGHT};
    background: {BG_ELEVATED};
}}
QCheckBox::indicator:checked {{
    background: {ACCENT};
    border-color: {ACCENT};
}}

/* ── ListWidget ─────────────────────────────── */
QListWidget {{
    background: {BG_CARD};
    border: 1px solid {BORDER};
    border-radius: 10px;
    color: {TEXT};
    font-size: 12px;
    padding: 4px;
}}
QListWidget::item {{ padding: 4px 8px; border-radius: 6px; }}
QListWidget::item:hover {{ background: {BG_ELEVATED}; }}
QListWidget::item:selected {{ background: {ACCENT}22; color: {ACCENT}; }}

/* ── ScrollArea ─────────────────────────────── */
QScrollArea {{ background: transparent; border: none; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}

/* ── Dialog ─────────────────────────────────── */
QDialog {{
    background-color: {BG};
}}

/* ── Tooltip ────────────────────────────────── */
QToolTip {{
    background-color: {BG_CARD};
    color: {TEXT};
    border: 1px solid {BORDER_LIGHT};
    border-radius: 6px;
    padding: 5px 8px;
    font-size: 12px;
}}

/* ── GroupBox ───────────────────────────────── */
QGroupBox {{
    background-color: transparent;
    border: 1px solid {BORDER};
    border-radius: 10px;
    margin-top: 16px;
    padding-top: 8px;
    color: {TEXT_MUTED};
    font-size: 11px;
    font-weight: 600;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 14px;
    top: -7px;
    padding: 0 6px;
    background-color: {BG_CARD};
    color: {TEXT_MUTED};
    font-size: 10px;
    letter-spacing: 1.5px;
    text-transform: uppercase;
}}
"""


# Initialize dark mode and build the initial stylesheet
set_mode('dark')
STYLESHEET = build_stylesheet()
