"""Central theme palette helpers for the modern MultiScreenKiosk UI."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ThemePalette:
    """Color palette describing the modern kiosk look."""

    name: str
    background: str
    surface: str
    surface_alt: str
    surface_strong: str
    text_primary: str
    text_secondary: str
    text_muted: str
    border: str
    border_strong: str
    accent: str
    accent_hover: str
    accent_text: str
    accent_soft: str
    danger: str
    danger_hover: str
    danger_text: str
    nav_background: str
    nav_border: str
    nav_hover: str
    nav_active: str
    nav_text: str
    nav_text_inactive: str
    header_background: str
    header_border: str
    header_text: str
    badge_background: str
    badge_text: str
    badge_alt_background: str
    badge_alt_text: str
    placeholder_bg: str
    placeholder_text: str


LIGHT_PALETTE = ThemePalette(
    name="light",
    background="#f8fafc",
    surface="#ffffff",
    surface_alt="#f1f5f9",
    surface_strong="#e2e8f0",
    text_primary="#0f172a",
    text_secondary="#475569",
    text_muted="#94a3b8",
    border="#e2e8f0",
    border_strong="#cbd5e1",
    accent="#2563eb",
    accent_hover="#1d4ed8",
    accent_text="#f8fafc",
    accent_soft="rgba(37, 99, 235, 0.12)",
    danger="#ef4444",
    danger_hover="#dc2626",
    danger_text="#ffffff",
    nav_background="#ffffff",
    nav_border="#e2e8f0",
    nav_hover="rgba(37, 99, 235, 0.1)",
    nav_active="#dbeafe",
    nav_text="#0f172a",
    nav_text_inactive="#64748b",
    header_background="#ffffff",
    header_border="#e2e8f0",
    header_text="#0f172a",
    badge_background="rgba(37, 99, 235, 0.12)",
    badge_text="#1d4ed8",
    badge_alt_background="rgba(15, 23, 42, 0.08)",
    badge_alt_text="#0f172a",
    placeholder_bg="#e2e8f0",
    placeholder_text="#475569",
)


DARK_PALETTE = ThemePalette(
    name="dark",
    background="#0b1120",
    surface="#111827",
    surface_alt="#18223a",
    surface_strong="#1f2937",
    text_primary="#f8fafc",
    text_secondary="#cbd5f5",
    text_muted="#64748b",
    border="#1f2937",
    border_strong="#334155",
    accent="#6366f1",
    accent_hover="#4f46e5",
    accent_text="#f8fafc",
    accent_soft="rgba(99, 102, 241, 0.18)",
    danger="#f87171",
    danger_hover="#ef4444",
    danger_text="#0b1120",
    nav_background="#0f172a",
    nav_border="#1f2937",
    nav_hover="rgba(99, 102, 241, 0.18)",
    nav_active="#312e81",
    nav_text="#e2e8f0",
    nav_text_inactive="#94a3b8",
    header_background="#111827",
    header_border="#1f2937",
    header_text="#f8fafc",
    badge_background="rgba(99, 102, 241, 0.18)",
    badge_text="#c7d2fe",
    badge_alt_background="rgba(148, 163, 184, 0.16)",
    badge_alt_text="#f8fafc",
    placeholder_bg="#1f2937",
    placeholder_text="#94a3b8",
)


def get_palette(theme: str | None) -> ThemePalette:
    """Return the palette for *theme* (defaults to light)."""

    if str(theme or "").lower().startswith("dark"):
        return DARK_PALETTE
    return LIGHT_PALETTE


def build_application_stylesheet(palette: ThemePalette) -> str:
    """Generate the shared Qt stylesheet for the application widgets."""

    p = palette
    return f"""
    QWidget {{
        background-color: {p.background};
        color: {p.text_primary};
        font-family: 'Segoe UI', 'Inter', 'Noto Sans', 'Helvetica Neue', sans-serif;
        font-size: 14px;
    }}
    QDialog {{
        background-color: {p.surface};
    }}
    QFrame#NavigationPanel {{
        background-color: {p.nav_background};
        border-right: 1px solid {p.nav_border};
    }}
    QFrame#NavigationPanel[orientation="top"] {{
        border-right: none;
        border-bottom: 1px solid {p.nav_border};
    }}
    QLabel#NavCaption {{
        font-size: 12px;
        text-transform: uppercase;
        letter-spacing: 0.18em;
        color: {p.nav_text_inactive};
    }}
    QLabel#NavSubtitle {{
        font-size: 12px;
        color: {p.nav_text_inactive};
    }}
    QLabel#NavLogo {{
        background-color: {p.accent_soft};
        color: {p.accent};
        font-weight: 700;
        font-size: 18px;
        border-radius: 16px;
        min-width: 48px;
        min-height: 48px;
        max-width: 48px;
        max-height: 48px;
    }}
    QLabel#NavLogo[pixmap="true"] {{
        background: transparent;
        border-radius: 12px;
        padding: 0px;
    }}
    QListWidget#NavigationList {{
        background: transparent;
        border: none;
        outline: none;
    }}
    QListWidget#NavigationList::item {{
        margin: 4px 8px;
        padding: 10px 14px;
        border-radius: 12px;
        color: {p.nav_text_inactive};
    }}
    QListWidget#NavigationList::item:selected {{
        background: {p.nav_active};
        color: {p.nav_text};
    }}
    QListWidget#NavigationList::item:hover:!selected {{
        background: {p.nav_hover};
        color: {p.nav_text};
    }}
    QLabel#NavEmpty {{
        color: {p.nav_text_inactive};
        border: 1px dashed {p.nav_border};
        border-radius: 12px;
        padding: 16px;
    }}
    QToolButton, QPushButton {{
        background: {p.surface_alt};
        color: {p.text_primary};
        border: 1px solid {p.border};
        border-radius: 12px;
        padding: 8px 12px;
    }}
    QToolButton:hover, QPushButton:hover {{
        background: {p.surface_strong};
        border-color: {p.border_strong};
    }}
    QToolButton:pressed, QPushButton:pressed {{
        background: {p.surface_alt};
    }}
    QToolButton[accent="true"], QPushButton[accent="true"] {{
        background: {p.accent};
        color: {p.accent_text};
        border: none;
    }}
    QToolButton[accent="true"]:hover, QPushButton[accent="true"]:hover {{
        background: {p.accent_hover};
    }}
    QPushButton[destructive="true"] {{
        background: {p.danger};
        color: {p.danger_text};
        border: none;
    }}
    QPushButton[destructive="true"]:hover {{
        background: {p.danger_hover};
    }}
    QToolButton#NavBurger {{
        background: transparent;
        border: none;
        color: {p.nav_text};
        padding: 6px;
    }}
    QToolButton#NavBurger:hover {{
        background: {p.nav_hover};
    }}
    QToolButton#PageButton {{
        padding: 6px 10px;
        min-width: 32px;
    }}
    QToolButton#OverlayBurger {{
        background: {p.surface};
        border: 1px solid {p.border};
        border-radius: 12px;
        padding: 6px 10px;
    }}
    QWidget#HeaderBar {{
        background-color: {p.header_background};
        border-bottom: 1px solid {p.header_border};
    }}
    QLabel#HeaderTitle {{
        font-size: 22px;
        font-weight: 600;
        color: {p.header_text};
    }}
    QLabel#HeaderSubtitle {{
        font-size: 13px;
        color: {p.text_secondary};
    }}
    QLabel#ModeBadge {{
        background: {p.badge_background};
        color: {p.badge_text};
        font-weight: 600;
        font-size: 12px;
        border-radius: 999px;
        padding: 4px 12px;
    }}
    QLabel#ModeBadge[mode="single"] {{
        background: {p.badge_alt_background};
        color: {p.badge_alt_text};
    }}
    QLabel#ModeBadge[mode="wall"] {{
        background: {p.accent_soft};
        color: {p.accent};
    }}
    QLabel#StatusBadge {{
        background: {p.badge_alt_background};
        color: {p.badge_alt_text};
        font-weight: 600;
        font-size: 12px;
        border-radius: 999px;
        padding: 4px 12px;
    }}
    QLabel#StatusBadge[status="kiosk"] {{
        background: {p.accent_soft};
        color: {p.accent};
    }}
    QFrame#ContentCard {{
        background: {p.surface};
        border: 1px solid {p.border};
        border-radius: 20px;
    }}
    QLabel#EmptySlot {{
        background: {p.placeholder_bg};
        color: {p.placeholder_text};
        border: 1px dashed {p.border_strong};
        border-radius: 16px;
        font-size: 16px;
        letter-spacing: 0.02em;
    }}
    QLabel#BrowserPlaceholder {{
        color: {p.placeholder_text};
    }}
    QLineEdit, QComboBox, QSpinBox, QTextEdit, QPlainTextEdit {{
        background: {p.surface_alt};
        border: 1px solid {p.border};
        border-radius: 10px;
        padding: 8px 10px;
        color: {p.text_primary};
    }}
    QLineEdit:focus, QComboBox:focus, QTextEdit:focus, QPlainTextEdit:focus {{
        border-color: {p.accent};
    }}
    QCheckBox {{
        spacing: 8px;
    }}
    QCheckBox::indicator {{
        width: 18px;
        height: 18px;
        border-radius: 6px;
        border: 1px solid {p.border_strong};
        background: {p.surface_alt};
    }}
    QCheckBox::indicator:checked {{
        background: {p.accent};
        border-color: {p.accent};
    }}
    QMenu {{
        background: {p.surface};
        border: 1px solid {p.border};
        padding: 6px 0px;
        border-radius: 10px;
    }}
    QMenu::item {{
        padding: 6px 18px;
        color: {p.text_primary};
    }}
    QMenu::item:selected {{
        background: {p.accent_soft};
        color: {p.accent};
    }}
    QScrollBar:vertical {{
        width: 10px;
        background: transparent;
        margin: 6px 2px 6px 2px;
    }}
    QScrollBar::handle:vertical {{
        background: {p.surface_strong};
        border-radius: 6px;
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
    }}
    QScrollBar:horizontal {{
        height: 10px;
        background: transparent;
        margin: 2px 6px 2px 6px;
    }}
    QScrollBar::handle:horizontal {{
        background: {p.surface_strong};
        border-radius: 6px;
    }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
        width: 0px;
    }}
    """


def build_dialog_stylesheet(palette: ThemePalette) -> str:
    """Alias for compatibility with dialogs (currently same as application)."""

    return build_application_stylesheet(palette)

