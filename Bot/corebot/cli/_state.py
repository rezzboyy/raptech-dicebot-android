"""Module-level state untuk CLI package.

Sebelumnya semua flag global ada di `cli.py`. Setelah dipecah jadi
package, state ini diisolasi di sini supaya sub-modul (`layout.py`,
`menu.py`, dll.) bisa import accessor tanpa risiko import-cycle.

Public accessor: `set_theme`, `get_theme`, `set_compact_mode`,
`is_compact_mode`, `set_toast_enabled`, `is_toast_enabled`.
"""
from __future__ import annotations

from ..ui import cyber as cyber_ui
from ..ui.theme import Theme, build_theme

# Module-level theme. Di-set oleh main() berdasarkan flag --no-color / --theme.
# Semua helper visual mengacu ke instance ini lewat `get_theme()`.
_THEME: Theme = build_theme()
cyber_ui.set_active_theme(_THEME)

# UI mode flags (di-set oleh main berdasar argv / terminal caps)
_COMPACT_MODE: bool = False
_TOAST_ENABLED: bool = True


def set_theme(theme: Theme) -> None:
    """Set theme aktif. Cyber module ikut sinkron supaya activation/license
    screen tampil dengan tema yang sama."""
    global _THEME
    _THEME = theme
    cyber_ui.set_active_theme(theme)


def get_theme() -> Theme:
    return _THEME


def set_compact_mode(enabled: bool) -> None:
    global _COMPACT_MODE
    _COMPACT_MODE = bool(enabled)


def is_compact_mode() -> bool:
    return _COMPACT_MODE


def set_toast_enabled(enabled: bool) -> None:
    global _TOAST_ENABLED
    _TOAST_ENABLED = bool(enabled)


def is_toast_enabled() -> bool:
    return _TOAST_ENABLED
