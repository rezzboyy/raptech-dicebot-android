"""Loader SVG icon dengan auto-tint sesuai tema aktif.

- SVG monochrome di `assets/icons/*.svg`.
- `get_icon(name)` render SVG → pixmap, lalu tint ke warna (default =
  warna teks tema aktif) via QPainter CompositionMode_SourceIn.
- Hasil di-cache per (name, color, size) supaya ringan.
- Aman kalau file SVG tidak ada: return QIcon kosong (tidak crash).
"""
from __future__ import annotations

import sys
from functools import lru_cache
from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap

try:
    from PySide6.QtSvg import QSvgRenderer
    _HAS_SVG = True
except Exception:  # pragma: no cover - QtSvg harus ada, tapi jaga-jaga
    _HAS_SVG = False

from widgets.theme import COLORS


def _resolve_icon_dir() -> Path:
    """Cari folder assets/icons untuk mode dev maupun frozen (PyInstaller).

    - Frozen: data di-bundle via --add-data ke `sys._MEIPASS/assets/icons`.
      Fallback ke folder di samping exe (onedir _internal / root).
    - Dev: parent[2] dari file ini = root repo.
    """
    candidates: list[Path] = []
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidates.append(Path(meipass) / "assets" / "icons")
        exe_dir = Path(sys.executable).resolve().parent
        candidates.append(exe_dir / "assets" / "icons")
        candidates.append(exe_dir / "_internal" / "assets" / "icons")
    candidates.append(Path(__file__).resolve().parents[2] / "assets" / "icons")
    for c in candidates:
        if c.is_dir():
            return c
    return candidates[0]


_ICON_DIR = _resolve_icon_dir()

_DEFAULT_SIZE = 18


def _icon_path(name: str) -> Path:
    return _ICON_DIR / f"{name}.svg"


# Supersample factor: render SVG di resolusi lebih tinggi lalu set
# devicePixelRatio → icon tajam/HD di layar biasa maupun HiDPI (anti-burik).
_SS = 2.0


@lru_cache(maxsize=256)
def _tinted_pixmap(name: str, color: str, size: int) -> QPixmap:
    """Render SVG `name` lalu tint ke `color`, supersampled utk HD. Cached."""
    path = _icon_path(name)
    px = max(1, int(round(size * _SS)))
    pm = QPixmap(px, px)
    pm.fill(Qt.GlobalColor.transparent)
    if not _HAS_SVG or not path.is_file():
        pm.setDevicePixelRatio(_SS)
        return pm

    renderer = QSvgRenderer(str(path))
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    renderer.render(painter)
    painter.end()

    # Tint: recolor semua piksel non-transparan ke `color`.
    tint = QPainter(pm)
    tint.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
    tint.fillRect(pm.rect(), QColor(color))
    tint.end()

    # devicePixelRatio → Qt tampilkan pada ukuran logis `size` dengan detail 2x.
    pm.setDevicePixelRatio(_SS)
    return pm


def get_icon(name: str, color: str | None = None, size: int = _DEFAULT_SIZE) -> QIcon:
    """Return QIcon ter-tint. `color` default = warna teks tema aktif.

    Panggil ulang setelah ganti tema untuk dapat warna baru.
    """
    col = color or COLORS.get("text", "#000000")
    pm = _tinted_pixmap(name, col, size)
    return QIcon(pm)


def icon_size(size: int = _DEFAULT_SIZE) -> QSize:
    return QSize(size, size)


def clear_cache() -> None:
    """Bersihkan cache pixmap (mis. saat palet berubah drastis)."""
    _tinted_pixmap.cache_clear()
