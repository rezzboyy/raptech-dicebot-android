"""AdvancedSettingsDialog — pengaturan strategi lanjutan (checklist on/off).

Tiap fitur punya checkbox ON/OFF + field nilai. Kalau OFF, nilainya
di-anggap 0 (nonaktif) saat diterapkan ke SessionProfile.

Fitur:
    - Take Profit %      : stop sesi saat profit capai target
    - Stop on Win        : stop saat menang (pause_on_win)
    - Max Cycles         : batasi jumlah bet
    - Auto Break         : jeda tiap N detik run (run/break seconds)
    - Flat Allocation    : mode flat bet saat trigger profit tercapai

State disimpan sebagai dict (key sinkron dgn SessionProfile).
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QGridLayout,
    QGroupBox,
    QLabel,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from widgets.theme import COLORS


DEFAULTS: dict = {
    "take_profit_enabled": False,
    "take_profit_pct": 10.0,
    "stop_on_win": False,
    "max_cycles_enabled": False,
    "max_cycles": 1000,
    "auto_break_enabled": False,
    "run_break_seconds": 60.0,
    "break_seconds": 10.0,
    "flat_enabled": False,
    "flat_trigger_pct": 5.0,
    "flat_minutes": 3.0,
    "flat_amount": 0.00000001,
}


class AdvancedSettingsDialog(QDialog):
    def __init__(self, current: dict | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Advanced Strategies")
        self.setMinimumWidth(420)
        self._state = dict(DEFAULTS)
        if current:
            self._state.update({k: v for k, v in current.items() if k in DEFAULTS})
        self._build()
        self._load_state()

    def _build(self) -> None:
        root = QVBoxLayout(self)

        # --- Take Profit ---
        self._grp_tp, tp_grid = self._group("Take Profit")
        self._chk_tp = self._grp_tp
        self._sp_tp = QDoubleSpinBox()
        self._sp_tp.setRange(0.0, 1_000_000.0)
        self._sp_tp.setDecimals(4)
        self._sp_tp.setSuffix(" %")
        tp_grid.addWidget(QLabel("Target profit"), 0, 0)
        tp_grid.addWidget(self._sp_tp, 0, 1)
        root.addWidget(self._grp_tp)

        # --- Stop on Win (checkbox only) ---
        self._chk_sow = QCheckBox("Stop on Win (berhenti saat menang)")
        root.addWidget(self._chk_sow)

        # --- Max Cycles ---
        self._grp_mc, mc_grid = self._group("Max Cycles")
        self._sp_mc = QSpinBox()
        self._sp_mc.setRange(1, 100_000_000)
        mc_grid.addWidget(QLabel("Jumlah bet maks"), 0, 0)
        mc_grid.addWidget(self._sp_mc, 0, 1)
        root.addWidget(self._grp_mc)

        # --- Auto Break ---
        self._grp_ab, ab_grid = self._group("Auto Break")
        self._sp_run = QDoubleSpinBox(); self._sp_run.setRange(0.0, 1e9); self._sp_run.setSuffix(" s")
        self._sp_break = QDoubleSpinBox(); self._sp_break.setRange(0.0, 1e9); self._sp_break.setSuffix(" s")
        ab_grid.addWidget(QLabel("Run selama"), 0, 0)
        ab_grid.addWidget(self._sp_run, 0, 1)
        ab_grid.addWidget(QLabel("Jeda selama"), 1, 0)
        ab_grid.addWidget(self._sp_break, 1, 1)
        root.addWidget(self._grp_ab)

        # --- Flat Allocation ---
        self._grp_flat, flat_grid = self._group("Flat Allocation")
        self._sp_ftrig = QDoubleSpinBox(); self._sp_ftrig.setRange(0.0, 1e6); self._sp_ftrig.setDecimals(4); self._sp_ftrig.setSuffix(" %")
        self._sp_fmin = QDoubleSpinBox(); self._sp_fmin.setRange(0.0, 1e6); self._sp_fmin.setSuffix(" m")
        self._sp_famt = QDoubleSpinBox(); self._sp_famt.setRange(0.0, 1e9); self._sp_famt.setDecimals(8)
        flat_grid.addWidget(QLabel("Trigger profit"), 0, 0)
        flat_grid.addWidget(self._sp_ftrig, 0, 1)
        flat_grid.addWidget(QLabel("Durasi"), 1, 0)
        flat_grid.addWidget(self._sp_fmin, 1, 1)
        flat_grid.addWidget(QLabel("Amount"), 2, 0)
        flat_grid.addWidget(self._sp_famt, 2, 1)
        root.addWidget(self._grp_flat)

        note = QLabel("Fitur yang checkbox-nya OFF tidak akan diterapkan.")
        note.setStyleSheet(f"color: {COLORS['text_dim']}; font-size: 11px;")
        root.addWidget(note)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Simpan")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _group(self, title: str) -> tuple[QGroupBox, QGridLayout]:
        """GroupBox checkable (checkbox = ON/OFF fitur) + grid isi."""
        box = QGroupBox(title)
        box.setCheckable(True)
        grid = QGridLayout(box)
        return box, grid

    def _load_state(self) -> None:
        s = self._state
        self._grp_tp.setChecked(bool(s["take_profit_enabled"]))
        self._sp_tp.setValue(float(s["take_profit_pct"]))
        self._chk_sow.setChecked(bool(s["stop_on_win"]))
        self._grp_mc.setChecked(bool(s["max_cycles_enabled"]))
        self._sp_mc.setValue(int(s["max_cycles"]))
        self._grp_ab.setChecked(bool(s["auto_break_enabled"]))
        self._sp_run.setValue(float(s["run_break_seconds"]))
        self._sp_break.setValue(float(s["break_seconds"]))
        self._grp_flat.setChecked(bool(s["flat_enabled"]))
        self._sp_ftrig.setValue(float(s["flat_trigger_pct"]))
        self._sp_fmin.setValue(float(s["flat_minutes"]))
        self._sp_famt.setValue(float(s["flat_amount"]))

    def result_state(self) -> dict:
        return {
            "take_profit_enabled": self._grp_tp.isChecked(),
            "take_profit_pct": self._sp_tp.value(),
            "stop_on_win": self._chk_sow.isChecked(),
            "max_cycles_enabled": self._grp_mc.isChecked(),
            "max_cycles": int(self._sp_mc.value()),
            "auto_break_enabled": self._grp_ab.isChecked(),
            "run_break_seconds": self._sp_run.value(),
            "break_seconds": self._sp_break.value(),
            "flat_enabled": self._grp_flat.isChecked(),
            "flat_trigger_pct": self._sp_ftrig.value(),
            "flat_minutes": self._sp_fmin.value(),
            "flat_amount": self._sp_famt.value(),
        }
