"""LuaSyntaxHighlighter — highlight dasar untuk kode Lua di QPlainTextEdit.

Highlight: keyword, builtin, string, komentar (baris & blok), angka.
Cukup untuk baca/edit strategy — bukan parser penuh.
"""
from __future__ import annotations

import re

from PySide6.QtCore import QRegularExpression
from PySide6.QtGui import (
    QColor,
    QFont,
    QSyntaxHighlighter,
    QTextCharFormat,
)

from widgets.theme import COLORS, register_theme_listener


_LUA_KEYWORDS = [
    "and", "break", "do", "else", "elseif", "end", "false", "for",
    "function", "goto", "if", "in", "local", "nil", "not", "or",
    "repeat", "return", "then", "true", "until", "while",
]

# Nama global yang umum di strategy bot (highlight beda biar gampang dilihat).
_LUA_BUILTINS = [
    "print", "math", "string", "table", "pairs", "ipairs", "tonumber",
    "tostring", "type", "pcall", "select", "assert", "error",
    # Global khas strategy dice
    "chance", "basebet", "nextbet", "bethigh", "balance", "profit",
    "dobet", "currency", "win", "previousbet", "resetstats",
]


def _fmt(color: str, *, bold: bool = False, italic: bool = False) -> QTextCharFormat:
    f = QTextCharFormat()
    f.setForeground(QColor(color))
    if bold:
        f.setFontWeight(QFont.Weight.Bold)
    if italic:
        f.setFontItalic(True)
    return f


class LuaSyntaxHighlighter(QSyntaxHighlighter):
    """Highlighter Lua sederhana berbasis regex."""

    def __init__(self, document) -> None:
        super().__init__(document)
        self._rules: list[tuple[QRegularExpression, QTextCharFormat]] = []

        # Komentar blok --[[ ... ]]
        self._block_start = QRegularExpression(r"--\[\[")
        self._block_end = QRegularExpression(r"\]\]")

        self._build_rules()
        register_theme_listener(self.apply_theme)

    def _build_rules(self) -> None:
        """Bangun ulang aturan highlight memakai warna tema aktif."""
        self._rules = []

        kw_fmt = _fmt(COLORS["accent"], bold=True)
        for kw in _LUA_KEYWORDS:
            self._rules.append((QRegularExpression(rf"\b{kw}\b"), kw_fmt))

        builtin_fmt = _fmt(COLORS["accent_alt"])
        for b in _LUA_BUILTINS:
            self._rules.append((QRegularExpression(rf"\b{b}\b"), builtin_fmt))

        # Angka
        self._rules.append(
            (QRegularExpression(r"\b\d+(\.\d+)?([eE][+-]?\d+)?\b"), _fmt(COLORS["warning"]))
        )

        # String (double & single quote)
        str_fmt = _fmt(COLORS["success"])
        self._rules.append((QRegularExpression(r'"[^"\\]*(\\.[^"\\]*)*"'), str_fmt))
        self._rules.append((QRegularExpression(r"'[^'\\]*(\\.[^'\\]*)*'"), str_fmt))

        # Komentar baris tunggal -- ... (harus setelah rule lain supaya menang)
        self._comment_fmt = _fmt(COLORS["text_dim"], italic=True)
        self._rules.append((QRegularExpression(r"--[^\n]*"), self._comment_fmt))

    def apply_theme(self) -> None:
        """Rebuild aturan + rehighlight seluruh dokumen dengan warna baru."""
        self._build_rules()
        self.rehighlight()

    def highlightBlock(self, text: str) -> None:
        # Rules single-line
        for pattern, fmt in self._rules:
            it = pattern.globalMatch(text)
            while it.hasNext():
                m = it.next()
                self.setFormat(m.capturedStart(), m.capturedLength(), fmt)

        # Komentar blok multi-line
        self.setCurrentBlockState(0)
        start = 0
        if self.previousBlockState() != 1:
            m = self._block_start.match(text)
            start = m.capturedStart() if m.hasMatch() else -1
        while start >= 0:
            m_end = self._block_end.match(text, start)
            if m_end.hasMatch():
                end = m_end.capturedStart()
                length = end - start + m_end.capturedLength()
                self.setCurrentBlockState(0)
            else:
                self.setCurrentBlockState(1)
                length = len(text) - start
            self.setFormat(start, length, self._comment_fmt)
            nxt = self._block_start.match(text, start + length)
            start = nxt.capturedStart() if nxt.hasMatch() else -1
