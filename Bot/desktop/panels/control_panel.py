"""ControlPanel — User Control (mirror panel di referensi DiceBot).

Tombol:
    Reset Stats  — bersihkan tampilan stats/bets/chart (GUI-side)
    Reset Seed   — panggil client.reset_seed()
    Reset Chart  — kosongkan chart
    Hide Chart   — toggle sembunyikan/tampilkan chart
    Vault        — coming soon (disabled)
    Deposit      — coming soon (disabled)

Signals:
    reset_stats_requested()
    reset_seed_requested()
    reset_chart_requested()
    hide_chart_toggled(bool)   # True = hide
"""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QGridLayout, QPushButton, QWidget

from widgets.icons import get_icon, icon_size
from widgets.panel_frame import PanelFrame


class ControlPanel(PanelFrame):
    reset_stats_requested = Signal()
    reset_seed_requested = Signal()
    reset_chart_requested = Signal()
    hide_chart_toggled = Signal(bool)
    vault_requested = Signal()
    deposit_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("User Control", parent)
        self._build()

    def _build(self) -> None:
        grid_host = QWidget()
        grid = QGridLayout(grid_host)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(4)

        self._btn_reset_stats = QPushButton("Reset Stats")
        self._btn_reset_seed = QPushButton("Reset Seed")
        self._btn_reset_chart = QPushButton("Reset Chart")
        self._btn_hide_chart = QPushButton("Hide Chart")
        self._btn_hide_chart.setCheckable(True)
        self._btn_vault = QPushButton("Vault")
        self._btn_deposit = QPushButton("Deposit")

        # Vault hanya untuk site yang mendukung (mis. Wolfbet). Default
        # disabled sampai connect ke site yang punya kemampuan vault.
        for b in (self._btn_vault, self._btn_deposit):
            b.setEnabled(False)
            b.setToolTip("Hubungkan ke site yang mendukung Vault (Wolfbet).")

        # Layout 2 kolom
        grid.addWidget(self._btn_reset_stats, 0, 0)
        grid.addWidget(self._btn_reset_seed, 0, 1)
        grid.addWidget(self._btn_reset_chart, 1, 0)
        grid.addWidget(self._btn_hide_chart, 1, 1)
        grid.addWidget(self._btn_vault, 2, 0)
        grid.addWidget(self._btn_deposit, 2, 1)

        self.content_layout.addWidget(grid_host)
        self.content_layout.addStretch(1)

        for b in (
            self._btn_reset_stats, self._btn_reset_seed, self._btn_reset_chart,
            self._btn_hide_chart, self._btn_vault, self._btn_deposit,
        ):
            b.setIconSize(icon_size())

        # Wire
        self._btn_reset_stats.clicked.connect(self.reset_stats_requested.emit)
        self._btn_reset_seed.clicked.connect(self.reset_seed_requested.emit)
        self._btn_reset_chart.clicked.connect(self.reset_chart_requested.emit)
        self._btn_hide_chart.toggled.connect(self._on_hide_toggled)
        self._btn_vault.clicked.connect(self.vault_requested.emit)
        self._btn_deposit.clicked.connect(self.deposit_requested.emit)

        self.apply_theme()

    def apply_theme(self) -> None:
        super().apply_theme()
        if not hasattr(self, "_btn_reset_stats"):
            return
        self._btn_reset_stats.setIcon(get_icon("reset"))
        self._btn_reset_seed.setIcon(get_icon("refresh"))
        self._btn_reset_chart.setIcon(get_icon("chart"))
        self._btn_hide_chart.setIcon(get_icon("chart"))
        self._btn_vault.setIcon(get_icon("save"))
        self._btn_deposit.setIcon(get_icon("plug"))

    def _on_hide_toggled(self, checked: bool) -> None:
        self._btn_hide_chart.setText("Show Chart" if checked else "Hide Chart")
        self.hide_chart_toggled.emit(checked)

    def set_vault_enabled(self, enabled: bool) -> None:
        """Aktif/nonaktifkan tombol Vault & Deposit (dipanggil saat connect)."""
        for b in (self._btn_vault, self._btn_deposit):
            b.setEnabled(enabled)
            b.setToolTip(
                "Kelola Vault (Deposit/Withdraw)." if enabled
                else "Hubungkan ke site yang mendukung Vault (Wolfbet)."
            )
