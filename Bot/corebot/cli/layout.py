"""Tabel layout & sizing helper untuk CLI.

Diekstrak dari `cli/__init__.py` (Fase 2 perapihan, Step C).
Hanya bergantung pada theme aktif (lewat `_state.get_theme()`) dan
helper visible-length dari `ui.theme`. Tidak menyentuh state lain.

Public API (di-re-export oleh `cli/__init__.py` untuk back-compat):
    - `compute_table_widths`
    - `table_sep`
    - `table_row`
    - `table_header_row`
    - `table_align_for`
    - `pad`
    - `truncate_visible_in_pad`
"""
from __future__ import annotations

from ..ui.theme import visible_len
from ..ui.widgets import format_duration
from ._state import get_theme


# ---- Definisi 7 kolom default dengan min/max + weight + priority ------
# Priority 0 = wajib, lebih besar = lebih dulu di-drop saat sempit.
_COL_KEYS: tuple[str, ...] = (
    "STEP", "BALANCE", "DELTA%", "PARAM", "RESULT", "PEAKSIZE", "SIZE",
)
_COL_MIN = (6, 12, 9, 9, 9, 11, 11)
_COL_MAX = (8, 18, 26, 11, 12, 14, 14)  # DELTA% diperluas untuk IDR profit inline
_COL_WEIGHT = (1, 3, 4, 1, 1, 2, 2)     # DELTA% weight naik supaya dapat width lebih
# Priority drop: PEAKSIZE first (3), PARAM (2), SIZE (1), sisanya P0 wajib.
_COL_PRIORITY = (0, 0, 0, 2, 0, 3, 1)


def table_sep(widths: list[int], position: str = "mid",
              *, group_breaks: tuple[int, ...] = ()) -> str:
    """Render separator tabel.

    `position`: 'top' | 'mid' | 'bottom' menentukan corner glyph.
    `group_breaks`: index kolom yang setelahnya pakai separator double
    (Fase 3.1 column group divider). Index 0-based, separator di antara
    kolom `i` dan `i+1` jika `i+1` ada di `group_breaks`.
    """
    theme = get_theme()
    g = theme.glyphs
    if position == "top":
        left, sep, right = g.tl, g.t_down, g.tr
    elif position == "bottom":
        left, sep, right = g.bl, g.t_up, g.br
    else:
        left, sep, right = g.t_right, g.cross, g.t_left
    parts = []
    for index, width in enumerate(widths):
        if index == 0:
            head = left
        elif index in group_breaks and index > 0:
            if g.v != "|":
                if position == "top":
                    head = "╥"
                elif position == "bottom":
                    head = "╨"
                else:
                    head = "╫"
            else:
                head = "++"
        else:
            head = sep
        parts.append(theme.c(head + g.h * width, "dim"))
    parts.append(theme.c(right, "dim"))
    return "".join(parts)


def table_row(values: list[object], widths: list[int],
              *, align: tuple[str, ...] | None = None,
              group_breaks: tuple[int, ...] = (),
              pad_inner: int = 0,
              header: bool = False) -> str:
    """Render satu baris tabel dengan alignment + group divider.

    `align`: tuple per-kolom dari `"left" | "right" | "center"`.
    Default semua left (legacy).
    `group_breaks`: index kolom yang setelahnya pakai separator
    `glyphs.v_double` (Fase 3.1).
    `pad_inner`: ekstra spasi di kiri/kanan content cell (Fase 3.2).
    `header`: kalau True, label di-bold accent (untuk header row).
    """
    theme = get_theme()
    g = theme.glyphs
    v_single = theme.c(g.v, "dim")
    v_double_glyph = getattr(g, "v_double", None) or g.v
    v_double = (
        theme.c(v_double_glyph, "accent", bold=True) if g.v != "|"
        else theme.c("||", "accent")
    )
    cells = []
    for idx, (value, width) in enumerate(zip(values, widths)):
        sep_glyph = v_double if idx in group_breaks and idx > 0 else v_single
        a = (align[idx] if align and idx < len(align) else "left")
        cell_text = pad(str(value), width, align=a, pad_inner=pad_inner)
        if header:
            cell_text = theme.c(cell_text, "accent", bold=True)
        cells.append(sep_glyph + cell_text)
    return "".join(cells) + v_single


def pad(text: str, width: int, *, align: str = "left",
        pad_inner: int = 0) -> str:
    """Pad text ke width tertentu, preserve visible-length untuk
    ANSI-aware sizing.

    `align`: 'left' | 'right' | 'center'.
    `pad_inner`: tambahan spasi di kiri (left-align) atau kanan
    (right-align) sebelum konten — buffer ke border (Fase 3.2).
    """
    plain_visible = visible_len(text)
    if plain_visible > width:
        text = truncate_visible_in_pad(text, width)
        plain_visible = visible_len(text)
    fill = max(0, width - plain_visible)
    if align == "right":
        return " " * fill + text
    if align == "center":
        left = fill // 2
        right = fill - left
        return " " * left + text + " " * right
    return text + " " * fill


def truncate_visible_in_pad(text: str, max_width: int) -> str:
    """Helper truncate visible-aware untuk `pad` hot path.

    Lebih sederhana dari `widgets.truncate_visible` — tidak append
    ellipsis (cukup hard-cut). Dipakai di `table_row` supaya cell
    tidak overflow.
    """
    if visible_len(text) <= max_width:
        return text
    out: list[str] = []
    visible = 0
    i = 0
    while i < len(text) and visible < max_width:
        ch = text[i]
        if ch == "\x1b" and i + 1 < len(text) and text[i + 1] == "[":
            j = i + 2
            while j < len(text) and not text[j].isalpha():
                j += 1
            out.append(text[i:j + 1])
            i = j + 1
            continue
        out.append(ch)
        visible += 1
        i += 1
    if out:
        out.append("[0m")
    return "".join(out)


def compute_table_widths(terminal_width: int) -> tuple[list[int], list[int], tuple[int, ...]]:
    """Hitung widths kolom adaptif + indeks kolom yang aktif.

    Return `(widths, active_indices, group_breaks)` untuk caller pakai
    di `table_sep` / `table_row`.

    Algoritma:
      1. Hitung budget = terminal_width - (border_count + buffer).
      2. Mulai dari semua kolom aktif.
      3. Kalau budget < sum(_COL_MIN aktif), drop kolom dengan
         priority tertinggi sampai cukup.
      4. Distribusi sisa ke kolom aktif sesuai weight, clamp ke max.
    """
    border_buffer = 2  # space utk border kanan + safety
    n = len(_COL_KEYS)
    active = list(range(n))

    def total_min(active_idx: list[int]) -> int:
        return sum(_COL_MIN[i] for i in active_idx) + len(active_idx) + 1 + border_buffer

    while total_min(active) > terminal_width and len(active) > 4:
        worst = max(active, key=lambda i: _COL_PRIORITY[i])
        if _COL_PRIORITY[worst] == 0:
            break
        active.remove(worst)

    widths = [_COL_MIN[i] for i in active]
    budget = terminal_width - (sum(widths) + len(active) + 1 + border_buffer)
    if budget > 0:
        weights = [_COL_WEIGHT[i] for i in active]
        total_w = sum(weights)
        for j, idx in enumerate(active):
            extra = (budget * weights[j]) // total_w
            cap = _COL_MAX[idx] - _COL_MIN[idx]
            widths[j] += min(extra, cap)

    # Group breaks (Fase 3.1): hitung relative ke active indices.
    # Group: STEP | BALANCE+DELTA% | PARAM..SIZE
    group_breaks_local = []
    for j, idx in enumerate(active):
        if idx in (1, 3) and j > 0:
            group_breaks_local.append(j)
    return widths, active, tuple(group_breaks_local)


def table_header_row(active_indices: list[int]) -> list[str]:
    """Kembalikan label header sesuai active columns."""
    return [_COL_KEYS[i] for i in active_indices]


def table_align_for(active_indices: list[int]) -> tuple[str, ...]:
    """Alignment per kolom (Fase 2.4): number=right, mixed=center."""
    align_map = ("right", "right", "right", "center", "center", "right", "right")
    return tuple(align_map[i] for i in active_indices)


# ---------- Shared formatting helpers ------------------------------------
# Dipindah ke sini agar engine_view.py & menu.py tidak perlu
# mendefinisikan ulang fungsi yang sama.



def responsive_width(
    *, max_width: int = 96, min_width: int = 56, padding: int = 2
) -> int:
    """Width adaptif sesuai terminal aktif."""
    from ..ui.theme import terminal_caps
    caps = terminal_caps(refresh=True)
    return max(min_width, min(max_width, caps.width - padding))
