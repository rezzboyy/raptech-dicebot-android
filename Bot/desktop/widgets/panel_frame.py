"""PanelFrame — kontainer standar dengan judul untuk tiap panel.

Dipakai supaya semua panel punya tampilan konsisten: border, judul di
atas, dan area konten di bawah.

Mendukung live theme: mendaftar `apply_theme` ke theme module sehingga
border + header ter-restyle otomatis saat tema diganti. Subclass yang
punya style inline tambahan sebaiknya override `apply_theme()` dan
memanggil `super().apply_theme()`.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from widgets.theme import COLORS, register_theme_listener


class PanelFrame(QWidget):
    """Kontainer panel dengan header judul + area konten.

    Gunakan `content_layout` untuk menambah widget ke area konten.
    """

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("panelFrame")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(1, 1, 1, 1)
        outer.setSpacing(0)

        # Header
        self._header = QLabel(title.upper())
        outer.addWidget(self._header)

        # Content area
        self._content = QWidget()
        self.content_layout = QVBoxLayout(self._content)
        self.content_layout.setContentsMargins(8, 8, 8, 8)
        outer.addWidget(self._content, stretch=1)

        self.apply_theme()
        register_theme_listener(self.apply_theme)

    # ---- Theming ---------------------------------------------------------

    def apply_theme(self) -> None:
        """Terapkan warna tema aktif ke frame + header."""
        self.setStyleSheet(
            f"#panelFrame {{ border: 1px solid {COLORS['border']}; "
            f"background-color: {COLORS['bg_alt']}; }}"
        )
        self._header.setStyleSheet(
            f"color: {COLORS['accent']}; font-weight: bold; "
            f"padding: 5px 8px; background-color: {COLORS['bg']}; "
            f"border-bottom: 1px solid {COLORS['border']};"
        )

    # ---- Helpers ---------------------------------------------------------

    def set_title(self, title: str) -> None:
        self._header.setText(title.upper())

    def add_placeholder(self, text: str) -> None:
        """Tambah label placeholder di tengah."""
        lbl = QLabel(text)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet(f"color: {COLORS['text_dim']}; font-style: italic;")
        self.content_layout.addWidget(lbl, stretch=1)
