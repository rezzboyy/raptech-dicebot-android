"""BetsPanel — tabel riwayat bet (QTableView + model).

Tiap snapshot dari engine di-append sebagai 1 baris. Kolom mirip
referensi: Bet#, Amount, Profit, Chance, Roll, Result, High.

Baris dibatasi `_MAX_ROWS` (default 1000) supaya memory & render tetap
ringan pada sesi panjang (buang baris terlama).
"""
from __future__ import annotations

import csv
from collections import deque

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QPushButton,
    QTableView,
    QWidget,
)

from corebot.models import SessionSnapshot
from widgets.icons import get_icon, icon_size
from widgets.panel_frame import PanelFrame
from widgets.theme import register_theme_listener

_MAX_ROWS = 1000
_HEADERS = ["Bet#", "Amount", "Profit", "Chance", "Roll", "Result", "High"]

# Gaya klasik DiceBot: seluruh baris berlatar SOLID pastel + teks gelap.
# Warna tetap (tidak ikut tema) supaya win/lose selalu jelas & konsisten.
_WIN_BG = QColor("#c6efce")   # hijau muda (win)
_LOSE_BG = QColor("#ffc7ce")  # merah muda / pink (lose)
_ROW_FG = QColor("#000000")   # teks HITAM di semua baris (tidak ikut background)


class BetsModel(QAbstractTableModel):
    def __init__(self) -> None:
        super().__init__()
        # tiap row: (bet_no, amount, profit, chance, roll, win, bethigh)
        self._rows: deque = deque(maxlen=_MAX_ROWS)

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self._rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(_HEADERS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return _HEADERS[section]
        return None

    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        bet_no, amount, profit, chance, roll, win, bethigh = self._rows[index.row()]
        col = index.column()
        if role == Qt.ItemDataRole.DisplayRole:
            return [
                str(bet_no),
                f"{amount:.8f}",
                f"{profit:+.8f}",
                f"{chance:.2f}",
                f"{roll:.2f}",
                "WIN" if win else "LOSE",
                "HI" if bethigh else "LO",
            ][col]
        if role == Qt.ItemDataRole.BackgroundRole:
            # Seluruh baris berlatar solid: WIN hijau muda, LOSE pink.
            return _WIN_BG if win else _LOSE_BG
        if role == Qt.ItemDataRole.ForegroundRole:
            # Teks hitam di semua baris (tidak ikut warna background).
            return _ROW_FG
        return None

    def append_row(self, row: tuple) -> None:
        at_cap = len(self._rows) >= _MAX_ROWS
        if at_cap:
            # Buang baris terlama; reset model untuk kesederhanaan
            self.beginResetModel()
            self._rows.append(row)
            self.endResetModel()
        else:
            pos = len(self._rows)
            self.beginInsertRows(QModelIndex(), pos, pos)
            self._rows.append(row)
            self.endInsertRows()

    def clear(self) -> None:
        self.beginResetModel()
        self._rows.clear()
        self.endResetModel()

    def rows(self) -> list[tuple]:
        return list(self._rows)


class BetsPanel(PanelFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Bets", parent)
        self._model = BetsModel()
        self._view = QTableView()
        self._view.setModel(self._model)
        # Alternating dimatikan: background win/lose per baris jadi indikator utama.
        self._view.setAlternatingRowColors(False)
        self._view.verticalHeader().setVisible(False)
        self._view.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self._view.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        header = self._view.horizontalHeader()
        header.setStretchLastSection(True)

        # Toolbar mini: Export CSV
        bar = QWidget()
        bar_l = QHBoxLayout(bar)
        bar_l.setContentsMargins(0, 0, 0, 4)
        bar_l.setSpacing(4)
        bar_l.addStretch(1)
        self._btn_export = QPushButton("Export CSV")
        self._btn_export.setIconSize(icon_size())
        self._btn_export.clicked.connect(self.export_csv)
        bar_l.addWidget(self._btn_export)
        self.content_layout.addWidget(bar)

        self.content_layout.addWidget(self._view)

        self._last_bet_no = 0

        register_theme_listener(self.apply_theme)

    def apply_theme(self) -> None:
        super().apply_theme()
        if hasattr(self, "_view"):
            # Foreground role baca COLORS live → cukup repaint.
            self._view.viewport().update()
            self._view.horizontalHeader().viewport().update()
        if hasattr(self, "_btn_export"):
            self._btn_export.setIcon(get_icon("save"))

    def export_csv(self) -> None:
        """Ekspor riwayat bet ke file CSV."""
        rows = self._model.rows()
        if not rows:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Bets CSV", "bets.csv", "CSV (*.csv)"
        )
        if not path:
            return
        if not path.lower().endswith(".csv"):
            path += ".csv"
        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(_HEADERS)
                for bet_no, amount, profit, chance, roll, win, bethigh in rows:
                    writer.writerow([
                        bet_no, f"{amount:.8f}", f"{profit:+.8f}", f"{chance:.2f}",
                        f"{roll:.2f}", "WIN" if win else "LOSE", "HI" if bethigh else "LO",
                    ])
        except OSError:
            pass

    def add_snapshot(self, snap: SessionSnapshot, prev_profit: float) -> None:
        """Append 1 baris kalau ada bet baru (session_bets bertambah)."""
        if snap.session_bets <= self._last_bet_no:
            return
        self._last_bet_no = snap.session_bets
        per_bet_profit = snap.session_profit - prev_profit
        row = (
            snap.session_bets,
            snap.last_bet_amount,
            per_bet_profit,
            snap.chance,
            snap.last_roll,
            bool(snap.last_bet_win),
            snap.bethigh,
        )
        self._model.append_row(row)
        # Auto-scroll ke bawah
        self._view.scrollToBottom()

    def reset(self) -> None:
        self._model.clear()
        self._last_bet_no = 0
