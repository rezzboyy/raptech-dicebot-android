"""Tema visual untuk Raptech Dicebot — dua palet: Light (default) & Dark.

Arsitektur:
- `PALETTES` menyimpan dua palet warna (light + dark).
- `COLORS` adalah dict AKTIF yang dimutasi in-place saat ganti tema
  (bukan di-rebind) supaya semua modul yang `from ... import COLORS`
  tetap melihat warna terbaru tanpa perlu re-import.
- Widget berwarna mendaftarkan callback `apply_theme` via
  `register_theme_listener()`. Saat `set_active_theme()` dipanggil,
  semua listener dijalankan → live-apply tanpa restart.
- Preferensi tema disimpan di corebot.storage (key `ui.desktop_theme`).
"""
from __future__ import annotations

from typing import Callable

APP_NAME = "Raptech Dicebot"
APP_VERSION = "1.1.1"  # versi aplikasi desktop (GUI)


def engine_version() -> str:
    """Versi engine corebot (best-effort)."""
    try:
        from corebot import __version__ as _v

        return str(_v)
    except Exception:
        return "?"

# ---- Palet ---------------------------------------------------------------

PALETTES: dict[str, dict[str, str]] = {
    "light": {
        # Soft silver — putih tidak menyilaukan, nyaman di mata.
        "bg": "#e4e7ec",          # window (silver lembut)
        "bg_alt": "#f1f2f5",      # panel (off-white silver, sedikit lebih terang)
        "bg_input": "#f7f8fa",    # input/editor (paling terang, tetap bukan putih murni)
        "border": "#cdd2da",      # border silver (cukup terlihat)
        "text": "#1c2128",        # teks utama (hampir hitam)
        "text_dim": "#5e6772",    # teks redup (kontras cukup di atas silver)
        "accent": "#0969da",      # biru pekat (accent utama)
        "accent_alt": "#8250df",  # ungu (accent sekunder)
        "success": "#1a7f37",     # hijau (profit)
        "danger": "#cf222e",      # merah (loss)
        "warning": "#9a6700",     # kuning gelap (warning)
    },
    "dark": {
        "bg": "#0d1117",          # dark navy background
        "bg_alt": "#161b22",      # panel background
        "bg_input": "#0b0f14",    # input/editor background
        "border": "#232a33",      # border halus
        "text": "#d6dde5",        # teks utama (sedikit lebih terang)
        "text_dim": "#8b949e",    # teks redup — kontras dinaikkan agar terbaca
        "accent": "#22d3ee",      # cyan accent
        "accent_alt": "#e879f9",  # magenta accent
        "success": "#3fb950",     # hijau (profit positif)
        "danger": "#f85149",      # merah (loss)
        "warning": "#d29922",     # kuning (warning)
    },
    "midnight": {
        "bg": "#0a0e1a",          # biru sangat gelap
        "bg_alt": "#111629",
        "bg_input": "#080b14",
        "border": "#1e2540",
        "text": "#cdd6f4",
        "text_dim": "#7f8bb0",
        "accent": "#89b4fa",      # biru lembut
        "accent_alt": "#cba6f7",  # ungu lembut
        "success": "#a6e3a1",
        "danger": "#f38ba8",
        "warning": "#f9e2af",
    },
    "high-contrast": {
        "bg": "#000000",          # hitam pekat (aksesibilitas)
        "bg_alt": "#0a0a0a",
        "bg_input": "#000000",
        "border": "#ffffff",      # border putih tegas
        "text": "#ffffff",        # teks putih penuh
        "text_dim": "#e0e0e0",    # tetap terang
        "accent": "#ffed4e",      # kuning cerah (kontras tinggi)
        "accent_alt": "#00e5ff",  # cyan cerah
        "success": "#00ff66",
        "danger": "#ff5c5c",
        "warning": "#ffcc00",
    },
}

DEFAULT_THEME = "light"

# Skala font (px) untuk QSS global. Aksesibilitas: S/M/L.
_FONT_PX = {"S": 11, "M": 12, "L": 14}
DEFAULT_FONT_SCALE = "M"

# Dict AKTIF — dimutasi in-place, jangan di-rebind.
COLORS: dict[str, str] = dict(PALETTES[DEFAULT_THEME])

_active: str = DEFAULT_THEME
_accent_override: str | None = None     # override warna accent (custom)
_font_scale: str = DEFAULT_FONT_SCALE
_font_px: int = _FONT_PX[DEFAULT_FONT_SCALE]
_listeners: list[Callable[[], None]] = []


# ---- Registrasi listener (live-apply) ------------------------------------

def register_theme_listener(fn: Callable[[], None]) -> Callable[[], None]:
    """Daftarkan callback yang dipanggil tiap tema berganti.

    Return fn supaya bisa dipakai sebagai dekorator / disimpan.
    """
    if fn not in _listeners:
        _listeners.append(fn)
    return fn


def unregister_theme_listener(fn: Callable[[], None]) -> None:
    try:
        _listeners.remove(fn)
    except ValueError:
        pass


def _notify_listeners() -> None:
    for fn in list(_listeners):
        try:
            fn()
        except Exception:
            # Jangan biarkan satu widget rusak menghentikan yang lain.
            pass


# ---- Ganti / baca tema ---------------------------------------------------

def get_active_theme() -> str:
    return _active


def available_themes() -> list[str]:
    return list(PALETTES.keys())


def _set_colors(name: str) -> None:
    """Mutasi COLORS in-place ke palet `name` + terapkan accent override."""
    palette = PALETTES.get(name, PALETTES[DEFAULT_THEME])
    COLORS.clear()
    COLORS.update(palette)
    if _accent_override:
        COLORS["accent"] = _accent_override


def set_active_theme(name: str, *, persist: bool = True, notify: bool = True) -> None:
    """Aktifkan tema `name`. Mutasi COLORS + (opsional) notify listener + simpan."""
    global _active
    if name not in PALETTES:
        name = DEFAULT_THEME
    _active = name
    _set_colors(name)
    if persist:
        _persist_theme(name)
    if notify:
        _notify_listeners()


def toggle_theme(*, persist: bool = True, notify: bool = True) -> str:
    """Toggle light <-> dark. Return nama tema baru.

    Kalau tema aktif bukan light/dark (mis. midnight/high-contrast),
    toggle mengembalikan ke light.
    """
    new = "dark" if _active == "light" else "light"
    set_active_theme(new, persist=persist, notify=notify)
    return new


# ---- Custom accent color (P2) --------------------------------------------

def get_accent() -> str | None:
    return _accent_override


def set_accent(hex_color: str | None, *, persist: bool = True, notify: bool = True) -> None:
    """Set/override warna accent. `None` atau '' = kembali ke default palet."""
    global _accent_override
    _accent_override = hex_color if (hex_color and hex_color.startswith("#")) else None
    _set_colors(_active)  # re-apply palette + accent baru
    if persist:
        _persist_kv("desktop_accent", _accent_override or "")
    if notify:
        _notify_listeners()


# ---- Font scaling (P13) --------------------------------------------------

def get_font_scale() -> str:
    return _font_scale


def font_px() -> int:
    return _font_px


def set_font_scale(label: str, *, persist: bool = True, notify: bool = True) -> None:
    """Set skala font global (S/M/L)."""
    global _font_scale, _font_px
    if label not in _FONT_PX:
        label = DEFAULT_FONT_SCALE
    _font_scale = label
    _font_px = _FONT_PX[label]
    if persist:
        _persist_kv("desktop_font", label)
    if notify:
        _notify_listeners()


# ---- Persistensi (corebot.storage) ---------------------------------------

def load_saved_theme() -> str:
    """Baca tema + accent + font tersimpan dari storage. Set aktif TANPA
    notify (dipakai di startup sebelum widget dibuat). Return nama tema."""
    global _accent_override, _font_scale, _font_px
    name = DEFAULT_THEME
    try:
        from corebot.storage import load_settings_store

        ui = load_settings_store().get("ui", {})
        saved = ui.get("desktop_theme")
        if isinstance(saved, str) and saved in PALETTES:
            name = saved
        acc = ui.get("desktop_accent")
        if isinstance(acc, str) and acc.startswith("#"):
            _accent_override = acc
        f = ui.get("desktop_font")
        if isinstance(f, str) and f in _FONT_PX:
            _font_scale = f
            _font_px = _FONT_PX[f]
    except Exception:
        pass
    set_active_theme(name, persist=False, notify=False)
    return name


def _persist_theme(name: str) -> None:
    _persist_kv("desktop_theme", name)


def _persist_kv(key: str, value) -> None:
    """Simpan satu key di bawah `ui.*` di settings store."""
    try:
        from corebot.storage import load_settings_store, save_settings_store

        store = load_settings_store()
        store.setdefault("ui", {})[key] = value
        save_settings_store(store)
    except Exception:
        pass


# ---- Stylesheet global (QSS) ---------------------------------------------

def build_stylesheet(name: str | None = None) -> str:
    """Return QSS untuk tema `name` (default = tema aktif). Font mengikuti
    skala aktif (S/M/L)."""
    c = PALETTES.get(name, COLORS) if name else COLORS
    fp = _font_px
    return f"""
    QMainWindow, QWidget {{
        background-color: {c['bg']};
        color: {c['text']};
        font-family: 'Segoe UI', 'Consolas', monospace;
        font-size: {fp}px;
    }}
    QMenuBar {{
        background-color: {c['bg_alt']};
        color: {c['text']};
        border-bottom: 1px solid {c['border']};
    }}
    QMenuBar::item {{
        padding: 4px 10px;
        background: transparent;
    }}
    QMenuBar::item:selected {{
        background-color: {c['accent']};
        color: {c['bg_alt']};
    }}
    QMenu {{
        background-color: {c['bg_alt']};
        color: {c['text']};
        border: 1px solid {c['border']};
    }}
    QMenu::item:selected {{
        background-color: {c['accent']};
        color: {c['bg_alt']};
    }}
    QStatusBar {{
        background-color: {c['bg_alt']};
        color: {c['text_dim']};
        border-top: 1px solid {c['border']};
    }}
    QPushButton {{
        background-color: {c['bg_alt']};
        color: {c['text']};
        border: 1px solid {c['border']};
        border-radius: 4px;
        padding: 4px 10px;
    }}
    QPushButton:hover {{
        border-color: {c['accent']};
    }}
    QPushButton:pressed {{
        background-color: {c['accent']};
        color: {c['bg_alt']};
    }}
    QPushButton:disabled {{
        color: {c['text_dim']};
        border-color: {c['border']};
    }}
    QToolButton {{
        background-color: transparent;
        border: 1px solid transparent;
        border-radius: 4px;
        padding: 3px;
    }}
    QToolButton:hover {{
        border-color: {c['accent']};
        background-color: {c['bg_input']};
    }}
    QLabel {{
        color: {c['text']};
        background: transparent;
    }}
    QComboBox, QSpinBox, QLineEdit, QDoubleSpinBox {{
        background-color: {c['bg_input']};
        color: {c['text']};
        border: 1px solid {c['border']};
        border-radius: 4px;
        padding: 3px 6px;
    }}
    QComboBox:hover, QSpinBox:hover, QLineEdit:hover {{
        border-color: {c['accent']};
    }}
    QComboBox QAbstractItemView {{
        background-color: {c['bg_alt']};
        color: {c['text']};
        selection-background-color: {c['accent']};
        selection-color: {c['bg_alt']};
        border: 1px solid {c['border']};
    }}
    QTabWidget::pane {{
        border: 1px solid {c['border']};
    }}
    QTabBar::tab {{
        background-color: {c['bg_alt']};
        color: {c['text_dim']};
        padding: 5px 12px;
        border: 1px solid {c['border']};
    }}
    QTabBar::tab:selected {{
        background-color: {c['bg']};
        color: {c['accent']};
        border-bottom-color: {c['accent']};
    }}
    QTableView {{
        background-color: {c['bg_input']};
        alternate-background-color: {c['bg_alt']};
        gridline-color: {c['border']};
        selection-background-color: {c['accent']};
        selection-color: {c['bg_alt']};
    }}
    QHeaderView::section {{
        background-color: {c['bg_alt']};
        color: {c['text_dim']};
        border: 1px solid {c['border']};
        padding: 3px;
    }}
    QPlainTextEdit, QTextEdit {{
        background-color: {c['bg_input']};
        color: {c['text']};
        border: 1px solid {c['border']};
        selection-background-color: {c['accent']};
        selection-color: {c['bg_alt']};
    }}
    QSplitter::handle {{
        background-color: {c['border']};
    }}
    QScrollBar:vertical {{
        background: {c['bg']};
        width: 12px;
        margin: 0;
    }}
    QScrollBar::handle:vertical {{
        background: {c['border']};
        border-radius: 6px;
        min-height: 24px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: {c['text_dim']};
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0;
    }}
    QScrollBar:horizontal {{
        background: {c['bg']};
        height: 12px;
        margin: 0;
    }}
    QScrollBar::handle:horizontal {{
        background: {c['border']};
        border-radius: 6px;
        min-width: 24px;
    }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
        width: 0;
    }}
    """
