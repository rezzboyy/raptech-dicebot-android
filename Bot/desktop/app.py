"""Entry point Raptech Dicebot (desktop GUI).

Jalankan:
    python desktop/app.py

Fase 0: buka jendela skeleton (menu bar + status bar + placeholder).

Catatan path: file ini menambahkan root repo ke sys.path supaya bisa
`import corebot` (engine/clients/lua) tanpa perlu install package.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Root repo = parent dari folder desktop/. Tambahkan ke sys.path supaya
# `import corebot` dan `import widgets`/`import main_window` (relatif ke
# folder desktop) sama-sama bisa di-resolve.
_DESKTOP_DIR = Path(__file__).resolve().parent
_ROOT_DIR = _DESKTOP_DIR.parent
for _p in (str(_ROOT_DIR), str(_DESKTOP_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# UTF-8 supaya konsisten dengan bot.py (Windows codepage safety).
os.environ.setdefault("PYTHONIOENCODING", "utf-8")


def _run_selftest() -> int:
    """Diagnostik: coba load semua client site, tulis hasil ke file
    'selftest.txt' di samping exe. Dipakai untuk verifikasi build frozen
    (apakah modul client lazy-import ikut ter-bundle).

    Jalankan: raptech-dicebot.exe --selftest
    """
    if getattr(sys, "frozen", False):
        out_dir = Path(sys.executable).parent
    else:
        out_dir = _DESKTOP_DIR
    report = out_dir / "selftest.txt"

    lines = ["Raptech Dicebot — self-test client import\n", "=" * 40 + "\n"]
    try:
        from corebot.clients import available_sites, get_client_class

        for slug in available_sites():
            try:
                cls = get_client_class(slug)
                lines.append(f"OK    {slug}: {cls.__name__}\n")
            except Exception as exc:
                lines.append(f"FAIL  {slug}: {type(exc).__name__}: {exc}\n")
    except Exception as exc:
        lines.append(f"FATAL: {exc}\n")

    report.write_text("".join(lines), encoding="utf-8")
    return 0


def main() -> int:
    if "--selftest" in sys.argv[1:]:
        return _run_selftest()

    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication

    from main_window import MainWindow
    from widgets.theme import APP_NAME, build_stylesheet, load_saved_theme

    # HD: pakai pixmap resolusi tinggi untuk icon di layar HiDPI (anti-burik).
    try:
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)
    except (AttributeError, Exception):
        pass

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    # Muat tema tersimpan (default: light) sebelum bangun stylesheet & widget.
    load_saved_theme()
    app.setStyleSheet(build_stylesheet())

    # Set icon kalau ada.
    icon_path = _ROOT_DIR / "assets" / "icon.ico"
    if icon_path.is_file():
        from PySide6.QtGui import QIcon

        app.setWindowIcon(QIcon(str(icon_path)))

    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
