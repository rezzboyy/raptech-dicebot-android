"""FindReplaceBar — bar cari & ganti untuk editor (QPlainTextEdit).

Tersembunyi secara default; ditampilkan via Ctrl+F. Beroperasi pada
sebuah CodeEdit yang di-set lewat `attach()`.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCursor, QTextDocument
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QWidget,
)


class FindReplaceBar(QWidget):
    """Bar find/replace ringan (find next/prev, replace, replace all)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._editor: QPlainTextEdit | None = None
        self._build()
        self.setVisible(False)

    def _build(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(4)

        self._find_input = QLineEdit()
        self._find_input.setPlaceholderText("Find...")
        self._find_input.returnPressed.connect(self.find_next)
        self._find_input.textChanged.connect(lambda: self._set_status(""))

        self._replace_input = QLineEdit()
        self._replace_input.setPlaceholderText("Replace...")
        self._replace_input.returnPressed.connect(self.replace_one)

        self._btn_prev = QPushButton("\u25b2")   # ▲
        self._btn_next = QPushButton("\u25bc")   # ▼
        self._btn_replace = QPushButton("Replace")
        self._btn_replace_all = QPushButton("All")
        self._btn_close = QPushButton("\u2715")  # ✕
        for b in (self._btn_prev, self._btn_next, self._btn_close):
            b.setFixedWidth(28)
        self._case = QCheckBox("Aa")
        self._case.setToolTip("Case sensitive")

        self._btn_prev.clicked.connect(self.find_prev)
        self._btn_next.clicked.connect(self.find_next)
        self._btn_replace.clicked.connect(self.replace_one)
        self._btn_replace_all.clicked.connect(self.replace_all)
        self._btn_close.clicked.connect(self.hide_bar)

        for w in (
            self._find_input, self._btn_prev, self._btn_next, self._case,
            self._replace_input, self._btn_replace, self._btn_replace_all,
            self._btn_close,
        ):
            layout.addWidget(w)
        layout.setStretch(0, 2)
        layout.setStretch(4, 2)

    # ---- Public API ------------------------------------------------------

    def attach(self, editor: QPlainTextEdit) -> None:
        self._editor = editor

    def show_bar(self) -> None:
        self.setVisible(True)
        if self._editor is not None:
            cur = self._editor.textCursor()
            if cur.hasSelection():
                self._find_input.setText(cur.selectedText())
        self._find_input.setFocus()
        self._find_input.selectAll()

    def hide_bar(self) -> None:
        self.setVisible(False)
        if self._editor is not None:
            self._editor.setFocus()

    def toggle(self) -> None:
        self.hide_bar() if self.isVisible() else self.show_bar()

    # ---- Operasi ---------------------------------------------------------

    def _flags(self, *, backward: bool = False) -> QTextDocument.FindFlag:
        flags = QTextDocument.FindFlag(0)
        if self._case.isChecked():
            flags |= QTextDocument.FindFlag.FindCaseSensitively
        if backward:
            flags |= QTextDocument.FindFlag.FindBackward
        return flags

    def _do_find(self, *, backward: bool = False) -> bool:
        if self._editor is None:
            return False
        text = self._find_input.text()
        if not text:
            return False
        found = self._editor.find(text, self._flags(backward=backward))
        if not found:
            # Wrap-around: pindah kursor ke ujung dokumen lalu cari lagi.
            cur = self._editor.textCursor()
            cur.movePosition(
                QTextCursor.MoveOperation.End if backward else QTextCursor.MoveOperation.Start
            )
            self._editor.setTextCursor(cur)
            found = self._editor.find(text, self._flags(backward=backward))
        self._set_status("" if found else "tidak ditemukan")
        return found

    def find_next(self) -> None:
        self._do_find(backward=False)

    def find_prev(self) -> None:
        self._do_find(backward=True)

    def replace_one(self) -> None:
        if self._editor is None:
            return
        cur = self._editor.textCursor()
        target = self._find_input.text()
        if cur.hasSelection() and target:
            sel = cur.selectedText()
            match = sel == target if self._case.isChecked() else sel.lower() == target.lower()
            if match:
                cur.insertText(self._replace_input.text())
        self.find_next()

    def replace_all(self) -> None:
        if self._editor is None:
            return
        target = self._find_input.text()
        if not target:
            return
        replacement = self._replace_input.text()
        doc = self._editor.document()
        count = 0
        cur = self._editor.textCursor()
        cur.beginEditBlock()
        find_cur = QTextCursor(doc)
        while True:
            find_cur = doc.find(target, find_cur, self._flags())
            if find_cur.isNull():
                break
            find_cur.insertText(replacement)
            count += 1
        cur.endEditBlock()
        self._set_status(f"{count} diganti")

    # ---- Status ----------------------------------------------------------

    def _set_status(self, msg: str) -> None:
        self._find_input.setToolTip(msg)
        # Warna border merah kalau tidak ditemukan (feedback ringan).
        if msg == "tidak ditemukan":
            self._find_input.setStyleSheet("border: 1px solid #cf222e;")
        else:
            self._find_input.setStyleSheet("")
