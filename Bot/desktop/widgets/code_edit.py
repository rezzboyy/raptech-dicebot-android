"""CodeEdit — QPlainTextEdit dengan line number area + monospace font.

Pola standar Qt: widget line-number di sebelah kiri viewport editor,
di-repaint sinkron dengan scroll/update editor.
"""
from __future__ import annotations

from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QTextFormat
from PySide6.QtWidgets import QPlainTextEdit, QTextEdit, QWidget

from widgets.theme import COLORS, register_theme_listener


class _LineNumberArea(QWidget):
    def __init__(self, editor: "CodeEdit") -> None:
        super().__init__(editor)
        self._editor = editor

    def sizeHint(self) -> QSize:
        return QSize(self._editor.line_number_area_width(), 0)

    def paintEvent(self, event) -> None:
        self._editor.line_number_area_paint(event)


class CodeEdit(QPlainTextEdit):
    """Editor kode dengan nomor baris + highlight baris aktif."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        font = QFont("Consolas", 10)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.setFont(font)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.setTabStopDistance(4 * self.fontMetrics().horizontalAdvance(" "))

        self._error_lines: set[int] = set()  # 1-indexed baris error (lint)

        self._line_area = _LineNumberArea(self)
        self.blockCountChanged.connect(self._update_line_area_width)
        self.updateRequest.connect(self._update_line_area)
        self.cursorPositionChanged.connect(self._highlight_current_line)
        # Edit apa pun → bersihkan tanda error lama (biar tidak menyesatkan).
        self.textChanged.connect(self._on_text_changed)
        self._update_line_area_width(0)
        self._highlight_current_line()

        register_theme_listener(self.apply_theme)

    # ---- Error line highlight (lint) ------------------------------------

    def set_error_lines(self, lines) -> None:
        self._error_lines = {int(n) for n in lines if n}
        self._highlight_current_line()

    def clear_error_lines(self) -> None:
        if self._error_lines:
            self._error_lines = set()
            self._highlight_current_line()

    def _on_text_changed(self) -> None:
        if self._error_lines:
            self._error_lines = set()

    # ---- Theming ---------------------------------------------------------

    def apply_theme(self) -> None:
        """Repaint line-number area + highlight baris aktif dgn warna baru."""
        self._line_area.update()
        self._highlight_current_line()

    # ---- Line number area ------------------------------------------------

    def line_number_area_width(self) -> int:
        digits = max(2, len(str(max(1, self.blockCount()))))
        return 12 + self.fontMetrics().horizontalAdvance("9") * digits

    def _update_line_area_width(self, _count: int) -> None:
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)

    def _update_line_area(self, rect: QRect, dy: int) -> None:
        if dy:
            self._line_area.scroll(0, dy)
        else:
            self._line_area.update(0, rect.y(), self._line_area.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self._update_line_area_width(0)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        cr = self.contentsRect()
        self._line_area.setGeometry(
            QRect(cr.left(), cr.top(), self.line_number_area_width(), cr.height())
        )

    def line_number_area_paint(self, event) -> None:
        painter = QPainter(self._line_area)
        painter.fillRect(event.rect(), QColor(COLORS["bg"]))
        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = round(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + round(self.blockBoundingRect(block).height())
        pen_color = QColor(COLORS["text_dim"])
        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(block_number + 1)
                painter.setPen(pen_color)
                painter.drawText(
                    0, top, self._line_area.width() - 5,
                    self.fontMetrics().height(),
                    Qt.AlignmentFlag.AlignRight, number,
                )
            block = block.next()
            top = bottom
            bottom = top + round(self.blockBoundingRect(block).height())
            block_number += 1

    def _highlight_current_line(self) -> None:
        selections: list[QTextEdit.ExtraSelection] = []

        # Baris error (lint) — background merah transparan.
        if self._error_lines:
            err_bg = QColor(COLORS["danger"])
            err_bg.setAlpha(60)
            doc = self.document()
            for line_no in self._error_lines:
                block = doc.findBlockByNumber(line_no - 1)
                if not block.isValid():
                    continue
                sel = QTextEdit.ExtraSelection()
                sel.format.setBackground(err_bg)
                sel.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
                cur = self.textCursor()
                cur.setPosition(block.position())
                sel.cursor = cur
                sel.cursor.clearSelection()
                selections.append(sel)

        # Highlight baris aktif.
        if not self.isReadOnly():
            sel = QTextEdit.ExtraSelection()
            sel.format.setBackground(QColor(COLORS["bg_alt"]))
            sel.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
            sel.cursor = self.textCursor()
            sel.cursor.clearSelection()
            selections.append(sel)
        self.setExtraSelections(selections)
