"""SessionToolbar — kontrol engine + pilihan strategy/currency/interval.

Signals:
    start_requested(str strategy, str currency, int interval_ms)
    pause_requested()
    resume_requested()
    stop_requested()
    pause_on_win_toggled(bool)
"""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QPushButton,
    QSpinBox,
    QWidget,
)

from widgets.icons import get_icon, icon_size
from widgets.theme import COLORS, register_theme_listener


class SessionToolbar(QWidget):
    start_requested = Signal(str, int)  # currency, interval_ms
    pause_requested = Signal()
    resume_requested = Signal()
    stop_requested = Signal()
    pause_on_win_toggled = Signal(bool)
    currency_changed = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build()

    def _build(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(6)

        # Strategy dijalankan dari isi CODE editor (bukan pilih file).
        self._currency = QComboBox()
        self._currency.setMinimumWidth(90)
        self._currency.currentTextChanged.connect(self._on_currency_changed)
        layout.addWidget(self._currency)

        self._interval = QSpinBox()
        self._interval.setRange(0, 600000)
        self._interval.setValue(120)
        self._interval.setSuffix(" ms")
        self._interval.setMinimumWidth(90)
        layout.addWidget(self._interval)

        layout.addStretch(1)

        self._btn_start = QPushButton("Start")
        self._btn_pause = QPushButton("Pause")
        self._btn_resume = QPushButton("Resume")
        self._btn_stop = QPushButton("Stop")
        self._btn_stop_win = QPushButton("Stop on Next Win")
        self._btn_stop_win.setCheckable(True)

        for b in (self._btn_start, self._btn_pause, self._btn_resume, self._btn_stop, self._btn_stop_win):
            b.setIconSize(icon_size())
            layout.addWidget(b)

        self._btn_start.clicked.connect(self._on_start)
        self._btn_pause.clicked.connect(self.pause_requested.emit)
        self._btn_resume.clicked.connect(self.resume_requested.emit)
        self._btn_stop.clicked.connect(self.stop_requested.emit)
        self._btn_stop_win.toggled.connect(self.pause_on_win_toggled.emit)

        self.apply_theme()
        register_theme_listener(self.apply_theme)
        self.set_state("idle")

    # ---- Theming ---------------------------------------------------------

    def apply_theme(self) -> None:
        """Warna aksen tombol Start/Stop + icon ter-tint sesuai tema."""
        self._btn_start.setStyleSheet(
            f"QPushButton {{ background-color: {COLORS['success']}; color: #ffffff; font-weight: bold; }}"
        )
        self._btn_stop.setStyleSheet(
            f"QPushButton {{ background-color: {COLORS['danger']}; color: #ffffff; font-weight: bold; }}"
        )
        # Icon Start/Stop putih (kontras di atas warna solid), sisanya ikut teks.
        self._btn_start.setIcon(get_icon("play", "#ffffff"))
        self._btn_stop.setIcon(get_icon("stop", "#ffffff"))
        self._btn_pause.setIcon(get_icon("pause"))
        self._btn_resume.setIcon(get_icon("resume"))

    def _on_start(self) -> None:
        currency = self._currency.currentText()
        interval = int(self._interval.value())
        self.start_requested.emit(currency, interval)

    # ---- API publik untuk shortcut keyboard -----------------------------

    def request_start(self) -> None:
        """Picu Start kalau tombolnya aktif (dipakai shortcut F5)."""
        if self._btn_start.isEnabled():
            self._on_start()

    def request_stop(self) -> None:
        """Picu Stop kalau aktif (shortcut F7)."""
        if self._btn_stop.isEnabled():
            self.stop_requested.emit()

    def request_pause_or_resume(self) -> None:
        """Toggle Pause/Resume sesuai tombol yang aktif (shortcut F6)."""
        if self._btn_pause.isEnabled():
            self.pause_requested.emit()
        elif self._btn_resume.isEnabled():
            self.resume_requested.emit()

    def _on_currency_changed(self, text: str) -> None:
        if text:
            self.currency_changed.emit(text)

    # ---- Populate --------------------------------------------------------

    def set_currencies(self, currencies: list[str], active: str = "") -> None:
        self._currency.blockSignals(True)
        self._currency.clear()
        self._currency.addItems(currencies)
        if active:
            idx = self._currency.findText(active.upper())
            if idx >= 0:
                self._currency.setCurrentIndex(idx)
        self._currency.blockSignals(False)

    def current_currency(self) -> str:
        return self._currency.currentText()

    # ---- State-driven enable/disable ------------------------------------

    def set_state(self, state: str) -> None:
        """Sesuaikan tombol berdasarkan state engine."""
        running = state in ("starting", "running")
        paused = state == "paused"
        active = running or paused
        self._btn_start.setEnabled(not active)
        self._btn_pause.setEnabled(running)
        self._btn_resume.setEnabled(paused)
        self._btn_stop.setEnabled(active)
        self._currency.setEnabled(not active)
        self._interval.setEnabled(not active)
