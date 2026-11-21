"""ChartPanel — grafik real-time dengan ROLLING WINDOW + toggle metrik.

- Rolling window `_WINDOW` bet terakhir (default 200), auto-scroll.
- Segmen berwarna: HIJAU saat win, MERAH saat lose.
- Toggle metrik: Balance (nilai saldo) atau Profit (profit sesi kumulatif).
- Export chart ke PNG.
- Ringan di RDP (antialias off default; RAPTECH_CHART_AA=1 untuk aktif).
"""
from __future__ import annotations

import os
from collections import deque

import pyqtgraph as pg
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
)

from widgets.icons import get_icon, icon_size
from widgets.panel_frame import PanelFrame
from widgets.theme import COLORS, register_theme_listener

_WINDOW = 200          # jumlah bet terakhir yang ditampilkan
_REDRAW_MS = 50        # ~20 fps
_NAN = float("nan")

# Index tuple point untuk tiap mode metrik.
_METRIC_INDEX = {"Balance": 1, "Profit": 2}


class ChartPanel(PanelFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Chart", parent)

        pg.setConfigOption("background", COLORS["bg_input"])
        pg.setConfigOption("foreground", COLORS["text_dim"])
        # Antialias ON default → garis halus/HD. Set RAPTECH_CHART_AA=0 untuk
        # matikan (misal RDP sangat lambat).
        _aa = os.getenv("RAPTECH_CHART_AA", "1") != "0"
        pg.setConfigOptions(antialias=_aa)

        self._mode = "Balance"

        # --- Toolbar mini: metrik + export ---
        bar = QWidget()
        bar_l = QHBoxLayout(bar)
        bar_l.setContentsMargins(0, 0, 0, 4)
        bar_l.setSpacing(4)
        bar_l.addWidget(QLabel("Metric:"))
        self._metric = QComboBox()
        self._metric.addItems(["Balance", "Profit"])
        self._metric.currentTextChanged.connect(self._on_metric_changed)
        bar_l.addWidget(self._metric)
        bar_l.addStretch(1)
        self._btn_export = QPushButton("Export PNG")
        self._btn_export.setIconSize(icon_size())
        self._btn_export.clicked.connect(self.export_png)
        bar_l.addWidget(self._btn_export)
        self.content_layout.addWidget(bar)

        self._plot = pg.PlotWidget()
        self._plot.setAntialiasing(_aa)
        self._plot.showGrid(x=True, y=True, alpha=0.25)
        self._plot.setLabel("bottom", "Bet")
        self._plot.setLabel("left", "Balance")
        self._plot.setMouseEnabled(x=False, y=False)
        self._plot.setMenuEnabled(False)

        _pw = 2.4  # pen lebih tebal → tampak halus & HD
        green_pen = pg.mkPen(COLORS["success"], width=_pw)
        red_pen = pg.mkPen(COLORS["danger"], width=_pw)
        green_pen.setCosmetic(True)
        red_pen.setCosmetic(True)
        self._curve_win = self._plot.plot(pen=green_pen, connect="finite")
        self._curve_lose = self._plot.plot(pen=red_pen, connect="finite")
        # Garis nol (referensi profit) — disembunyikan di mode Balance.
        self._zero_line = pg.InfiniteLine(
            angle=0, pen=pg.mkPen(COLORS["text_dim"], width=1, style=Qt.PenStyle.DashLine)
        )
        self._plot.addItem(self._zero_line)
        self._zero_line.setVisible(False)

        self.content_layout.addWidget(self._plot, stretch=1)

        # Rolling window: (bet_no, balance, profit, win)
        self._points: deque = deque(maxlen=_WINDOW)
        self._dirty = False

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._flush)
        self._timer.start(_REDRAW_MS)

        register_theme_listener(self.apply_theme)

    # ---- Theming ---------------------------------------------------------

    def apply_theme(self) -> None:
        super().apply_theme()
        if not hasattr(self, "_plot"):
            return
        self._plot.setBackground(COLORS["bg_input"])
        for ax in ("bottom", "left"):
            axis = self._plot.getAxis(ax)
            axis.setPen(COLORS["text_dim"])
            axis.setTextPen(COLORS["text_dim"])
        gp = pg.mkPen(COLORS["success"], width=2.4)
        rp = pg.mkPen(COLORS["danger"], width=2.4)
        gp.setCosmetic(True)
        rp.setCosmetic(True)
        self._curve_win.setPen(gp)
        self._curve_lose.setPen(rp)
        self._zero_line.setPen(
            pg.mkPen(COLORS["text_dim"], width=1, style=Qt.PenStyle.DashLine)
        )
        self._btn_export.setIcon(get_icon("save"))

    # ---- Data ------------------------------------------------------------

    def add_point(self, bet_no: int, balance: float, win: bool | None = None,
                  profit: float = 0.0) -> None:
        self._points.append((float(bet_no), float(balance), float(profit), win))
        self._dirty = True

    def _on_metric_changed(self, mode: str) -> None:
        self._mode = mode if mode in _METRIC_INDEX else "Balance"
        self._plot.setLabel("left", self._mode)
        self._zero_line.setVisible(self._mode == "Profit")
        self._dirty = True

    def _flush(self) -> None:
        if not self._dirty:
            return
        self._dirty = False

        idx = _METRIC_INDEX[self._mode]
        pts = list(self._points)
        gx: list[float] = []
        gy: list[float] = []
        rx: list[float] = []
        ry: list[float] = []

        for i in range(1, len(pts)):
            prev = pts[i - 1]
            cur = pts[i]
            px, py = prev[0], prev[idx]
            cx, cy = cur[0], cur[idx]
            win = cur[3]
            is_win = win if win is not None else (cy >= py)
            if is_win:
                gx.extend((px, cx, _NAN))
                gy.extend((py, cy, _NAN))
            else:
                rx.extend((px, cx, _NAN))
                ry.extend((py, cy, _NAN))

        self._curve_win.setData(gx, gy, connect="finite")
        self._curve_lose.setData(rx, ry, connect="finite")

        if pts:
            x_first, x_last = pts[0][0], pts[-1][0]
            if x_last > x_first:
                self._plot.setXRange(x_first, x_last, padding=0.02)
            ys = [p[idx] for p in pts]
            lo, hi = min(ys), max(ys)
            if self._mode == "Profit":
                lo, hi = min(lo, 0.0), max(hi, 0.0)  # selalu tampilkan garis 0
            if hi > lo:
                pad = (hi - lo) * 0.08
                self._plot.setYRange(lo - pad, hi + pad, padding=0)

    def reset(self) -> None:
        self._points.clear()
        self._dirty = True
        self._curve_win.setData([], [])
        self._curve_lose.setData([], [])

    # ---- Export PNG (P6) -------------------------------------------------

    def export_png(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Chart PNG", "chart.png", "PNG Image (*.png)"
        )
        if not path:
            return
        if not path.lower().endswith(".png"):
            path += ".png"
        # QWidget.grab() → QPixmap (robust, tanpa dependency exporter ekstra).
        self._plot.grab().save(path, "PNG")
