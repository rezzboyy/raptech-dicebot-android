"""Primitif console untuk CLI package.

Diekstrak dari `cli/__init__.py` (Fase 2 perapihan, Step F).
Berisi helper paling dasar: clear_screen, terminal_frame, color_text,
section, pause, normalize_token. Dipakai oleh `prompts.py`, `menu.py`
(nanti), dan `script_check.py`.

Tidak mengandung state â€” hanya utilitas.

Public API (di-re-export oleh `cli/__init__.py`):
    - `clear_screen`
    - `terminal_frame`
    - `color_text`
    - `section`
    - `pause`
    - `normalize_token`
"""
from __future__ import annotations

import io
import os
import sys

try:
    from colorama import Fore  # type: ignore
except Exception:
    class Fore:  # type: ignore[no-redef]
        RED = "\x1b[31m"
        GREEN = "\x1b[32m"
        YELLOW = "\x1b[33m"
        BLUE = "\x1b[34m"
        MAGENTA = "\x1b[35m"
        CYAN = "\x1b[36m"
        WHITE = "\x1b[37m"

from ..ui.strings import S as STR
from ._state import get_theme


# Mapping legacy color name -> role semantik di theme.
# Dipakai helper `color_text` lama agar tidak perlu refactor seluruh call site.
_FORE_TO_ROLE = {
    Fore.RED: "danger",
    Fore.GREEN: "success",
    Fore.YELLOW: "warning",
    Fore.BLUE: "info",
    Fore.MAGENTA: "accent",
    Fore.CYAN: "primary",
    Fore.WHITE: "muted",
}


def clear_screen() -> None:
    os.system("cls" if os.name == "nt" else "clear")


# Fase 7.3: terminal_frame ctx mgr â€” kumpulkan beberapa write ke
# StringIO, flush sekali saat exit. Mengurangi flicker awal & jumlah
# syscall di Windows console.
class terminal_frame:
    """Context manager: buffer write ke stdout sampai exit, satu flush.

    Pemakaian:

        with terminal_frame() as f:
            f.write("line1\\n")
            f.write("line2\\n")
        # satu syscall write+flush

    Aman untuk ANSI escape. Tidak nested-safe (tidak ada
    requirement untuk itu sekarang).
    """

    __slots__ = ("_buf",)

    def __init__(self) -> None:
        self._buf = io.StringIO()

    def write(self, text: str) -> None:
        self._buf.write(text)

    def writeln(self, text: str = "") -> None:
        self._buf.write(text)
        self._buf.write("\n")

    def __enter__(self) -> "terminal_frame":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        try:
            sys.stdout.write(self._buf.getvalue())
            sys.stdout.flush()
        except Exception:
            pass


def color_text(text: str, color: str, no_color: bool = False) -> str:
    """Wrapper kompatibilitas. `no_color` argumen lama dipertahankan tapi
    keputusan akhir warna mengikuti theme aktif (`set_theme`). Argumen
    `color` legacy diterjemahkan ke role semantik via `_FORE_TO_ROLE`.
    """
    theme = get_theme()
    if no_color or not theme.use_color:
        return text
    role = _FORE_TO_ROLE.get(color, "muted")
    return theme.c(text, role)


def section(title: str, color: str = Fore.CYAN, no_color: bool = False) -> None:
    theme = get_theme()
    role = _FORE_TO_ROLE.get(color, "accent")
    if no_color or not theme.use_color:
        print(f"[{title.upper()}]")
        print(theme.glyphs.h * 48)
        return
    print(theme.section(title, role=role))
    print(theme.divider(48))


def pause(message: str = STR.PAUSE_RETURN) -> None:
    input(message)


def normalize_token(token: str) -> str:
    token = (token or "").strip()
    if token.lower().startswith("bearer "):
        return token[7:].strip()
    return token

