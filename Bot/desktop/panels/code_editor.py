"""CodeEditorPanel — editor Lua + tab Console/Variables/Check + Open/Save/Check/Find.

- Tab Code: editor Lua (syntax highlight + line number) + Find/Replace bar.
- Tab Console: output log read-only (di-append dari event engine).
- Tab Variables: nilai runtime engine LIVE (dari SessionSnapshot).
- Tab Check: hasil lint strategy (reuse corebot check_strategy_script).
"""
from __future__ import annotations

import re
from pathlib import Path

from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QPlainTextEdit,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from corebot.config import lua_dir
from widgets.code_edit import CodeEdit
from widgets.find_bar import FindReplaceBar
from widgets.icons import get_icon, icon_size
from widgets.lua_highlighter import LuaSyntaxHighlighter
from widgets.panel_frame import PanelFrame
from widgets.theme import COLORS

# Baris berlabel field snapshot untuk tab Variables (label, atribut, format).
_VAR_FIELDS = [
    ("State", "state", "{}"),
    ("Strategy", "strategy_name", "{}"),
    ("Currency", "currency", "{}"),
    ("Balance", "current_balance", "{:.8f}"),
    ("Profit", "session_profit", "{:+.8f}"),
    ("Profit %", "profit_pct", "{:+.4f}%"),
    ("Bets", "session_bets", "{:,}"),
    ("Wins", "session_wins", "{:,}"),
    ("Losses", "session_losses", "{:,}"),
    ("Max Lose Streak", "max_lose_streak", "{}"),
    ("Chance", "chance", "{:.4f}"),
    ("Bet High", "bethigh", "{}"),
    ("Last Roll", "last_roll", "{:.2f}"),
    ("Last Bet", "last_bet_amount", "{:.8f}"),
    ("Highest Bet", "highest_bet", "{:.8f}"),
    ("Wagered", "session_wagered", "{:.8f}"),
    ("Speed", "speed_bps", "{:.2f} b/s"),
    ("Runtime", "runtime_seconds", "{:.0f}s"),
]


class CodeEditorPanel(PanelFrame):
    """Panel editor kode kanan."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Code", parent)
        self._current_path: Path | None = None
        self._build()

    def _build(self) -> None:
        # --- Toolbar Open/Save/Check ---
        toolbar = QWidget()
        tb_layout = QHBoxLayout(toolbar)
        tb_layout.setContentsMargins(0, 0, 0, 4)
        tb_layout.setSpacing(4)
        self._btn_open = QPushButton("Open")
        self._btn_save = QPushButton("Save")
        self._btn_check = QPushButton("Check")
        self._btn_find = QPushButton("Find")
        for b in (self._btn_open, self._btn_save, self._btn_check, self._btn_find):
            b.setIconSize(icon_size())
        self._btn_open.clicked.connect(self.open_file)
        self._btn_save.clicked.connect(self.save_file)
        self._btn_check.clicked.connect(self.check_script)
        self._btn_find.clicked.connect(self.toggle_find)
        tb_layout.addWidget(self._btn_open)
        tb_layout.addWidget(self._btn_save)
        tb_layout.addWidget(self._btn_check)
        tb_layout.addWidget(self._btn_find)
        tb_layout.addStretch(1)
        self.content_layout.addWidget(toolbar)

        # --- Tabs ---
        self._tabs = QTabWidget()

        # Tab Code (editor + find bar)
        code_host = QWidget()
        code_layout = QVBoxLayout(code_host)
        code_layout.setContentsMargins(0, 0, 0, 0)
        code_layout.setSpacing(2)
        self._editor = CodeEdit()
        self._highlighter = LuaSyntaxHighlighter(self._editor.document())
        self._find_bar = FindReplaceBar()
        self._find_bar.attach(self._editor)
        code_layout.addWidget(self._find_bar)
        code_layout.addWidget(self._editor, stretch=1)
        self._tabs.addTab(code_host, "Code")

        # Tab Console (read-only log)
        self._console = QPlainTextEdit()
        self._console.setReadOnly(True)
        self._console.setMaximumBlockCount(2000)  # batasi biar ringan & tidak menumpuk
        self._tabs.addTab(self._console, "Console")

        # Tab Variables (live runtime dari snapshot)
        self._variables = QPlainTextEdit()
        self._variables.setReadOnly(True)
        self._variables.setPlaceholderText("(mulai sesi untuk melihat variabel runtime)")
        self._tabs.addTab(self._variables, "Variables")

        # Tab Check (hasil lint)
        self._check_out = QPlainTextEdit()
        self._check_out.setReadOnly(True)
        self._check_out.setPlaceholderText("(klik Check untuk validasi strategy)")
        self._tabs.addTab(self._check_out, "Check")

        self.content_layout.addWidget(self._tabs, stretch=1)

        self.apply_theme()

    # ---- Theming ---------------------------------------------------------

    def apply_theme(self) -> None:
        super().apply_theme()
        if not hasattr(self, "_btn_open"):
            return
        mono = (
            f"background-color: {COLORS['bg_input']}; color: {COLORS['text']}; "
            "font-family: Consolas, monospace;"
        )
        self._console.setStyleSheet(mono)
        self._variables.setStyleSheet(mono)
        self._check_out.setStyleSheet(mono)
        self._btn_open.setIcon(get_icon("folder-open"))
        self._btn_save.setIcon(get_icon("save"))
        self._btn_check.setIcon(get_icon("reset"))
        self._btn_find.setIcon(get_icon("chart"))

    # ---- Public API ------------------------------------------------------

    def load_path(self, path: Path) -> None:
        """Muat isi file ke editor."""
        try:
            text = Path(path).read_text(encoding="utf-8")
        except Exception as exc:
            self.append_console(f"[error] Gagal buka {path}: {exc}")
            return
        self._editor.setPlainText(text)
        self._editor.clear_error_lines()
        self._current_path = Path(path)
        self.set_title(f"Code — {self._current_path.name}")

    def current_text(self) -> str:
        return self._editor.toPlainText()

    def current_path(self) -> Path | None:
        return self._current_path

    def append_console(self, line: str) -> None:
        self._console.appendPlainText(line)

    def show_console_tab(self) -> None:
        self._tabs.setCurrentWidget(self._console)

    def toggle_find(self) -> None:
        self._tabs.setCurrentIndex(0)  # pastikan tab Code aktif
        self._find_bar.toggle()

    def update_variables(self, snap) -> None:
        """Render nilai runtime engine (dari SessionSnapshot) ke tab Variables."""
        lines = []
        for label, attr, fmt in _VAR_FIELDS:
            val = getattr(snap, attr, None)
            try:
                text = fmt.format(val) if val is not None else "-"
            except (ValueError, TypeError):
                text = str(val)
            lines.append(f"{label:<18}: {text}")
        # Pertahankan posisi scroll sederhana dgn setPlainText (cukup untuk read-only).
        self._variables.setPlainText("\n".join(lines))

    # ---- Lint / Check (P4) ----------------------------------------------

    def check_script(self) -> None:
        """Validasi strategy di editor via corebot check_strategy_script."""
        code = self._editor.toPlainText()
        if not code.strip():
            self._show_check("(editor kosong)")
            return

        # Tulis ke file temp di folder strategies supaya path konsisten.
        try:
            d = lua_dir()
            d.mkdir(parents=True, exist_ok=True)
            tmp = d / "_lint_check.lua"
            tmp.write_text(code, encoding="utf-8")
        except Exception as exc:
            self._show_check(f"[error] gagal siapkan file cek: {exc}")
            return

        try:
            from corebot.cli.script_check import check_strategy_script

            result = check_strategy_script(tmp, currency="BTC", balance=1.0)
        except Exception as exc:
            self._show_check(f"[error] check gagal: {exc}")
            return
        finally:
            try:
                tmp.unlink()
            except OSError:
                pass

        # Render laporan + kumpulkan baris error.
        status = "PASS" if result.get("ok") else "FAIL"
        report = [f"=== CHECK: {result.get('name', '?')} → {status} ==="]
        error_lines: set[int] = set()
        for level, message in result.get("findings", []):
            report.append(f"[{level}] {message}")
            if level == "FAIL":
                error_lines.update(self._extract_line_numbers(message))
        self._show_check("\n".join(report))
        self._editor.set_error_lines(error_lines)

    @staticmethod
    def _extract_line_numbers(message: str) -> list[int]:
        """Ambil nomor baris dari pesan error Lua (pola '...:<n>:')."""
        nums = re.findall(r":(\d+):", message)
        out = []
        for n in nums:
            try:
                out.append(int(n))
            except ValueError:
                pass
        return out

    def _show_check(self, text: str) -> None:
        self._check_out.setPlainText(text)
        self._tabs.setCurrentWidget(self._check_out)

    # ---- File actions ----------------------------------------------------

    def open_file(self) -> None:
        start_dir = str(lua_dir()) if lua_dir().is_dir() else ""
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Strategy", start_dir, "Lua files (*.lua);;All files (*.*)"
        )
        if path:
            self.load_path(Path(path))

    def save_file(self) -> None:
        if self._current_path is not None:
            target = str(self._current_path)
        else:
            start_dir = str(lua_dir()) if lua_dir().is_dir() else ""
            target, _ = QFileDialog.getSaveFileName(
                self, "Save Strategy", start_dir, "Lua files (*.lua);;All files (*.*)"
            )
            if not target:
                return
        try:
            Path(target).write_text(self._editor.toPlainText(), encoding="utf-8")
            self._current_path = Path(target)
            self.set_title(f"Code — {self._current_path.name}")
            self.append_console(f"[saved] {target}")
        except Exception as exc:
            self.append_console(f"[error] Gagal simpan {target}: {exc}")
