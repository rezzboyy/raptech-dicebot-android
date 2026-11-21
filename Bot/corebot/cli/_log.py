"""Log line formatter untuk CLI runtime.

Diekstrak dari `cli/__init__.py` (Fase 2 perapihan, Step I-1).
Lightweight — cuma akses theme aktif untuk styling.

Public API (di-re-export oleh `cli/__init__.py`):
    - `format_log_line(level, message)` -> str
    - `_log_icon(level)` -> tuple[str, str]
"""
from __future__ import annotations

from ._state import get_theme


def _log_icon(level: str) -> tuple[str, str]:
    """Return (icon_glyph, theme_role) untuk pesan log."""
    g = get_theme().glyphs
    if level == "success":
        return g.check, "success"
    if level == "error":
        return g.cross_mark, "danger"
    if level == "warn":
        return g.warn, "warning"
    return g.info, "info"


def format_log_line(level: str, message: str) -> str:
    theme = get_theme()
    icon_char, role = _log_icon(level)
    icon = theme.c(icon_char, role, bold=True)
    body = theme.c(message, role) if level in {"success", "error"} else message
    return f" {icon}  {body}"
