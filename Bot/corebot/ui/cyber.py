"""Cyber terminal style helpers: ASCII logo, boot sequence, framed banners.

Module ini delegasi ke `theme.Theme` aktif untuk semua warna & glyph.
Tidak ada lagi ANSI literal di sini (kecuali RESET via theme.reset).

Public API:
  banner_logo, boot_step, boot_sequence, box,
  screen_activation_prompt, screen_verifying, screen_activation_success,
  screen_activation_error, screen_revoked, screen_warning_expiring,
  status_line, license_status_line, heartbeat_tick, cyber_input_prompt,
  visible_len
"""
from __future__ import annotations

import sys
import time
from typing import Iterable

try:
    from colorama import init as _colorama_init

    _colorama_init(autoreset=False, convert=True, wrap=True)
except Exception:
    pass

from . import theme as _theme_mod
from .theme import Theme, terminal_caps, visible_len


def _theme() -> Theme:
    """Ambil theme aktif. Konsumen lain (cli) bisa override
    via `theme.DEFAULT_THEME = ...` atau saat ini `cli.set_theme`. Modul cyber
    selalu re-resolve supaya theme switch live tetap nyambung."""
    # cli.set_theme update _THEME di cli, theme.DEFAULT_THEME tetap default.
    # Untuk konsistensi, kita pakai theme.DEFAULT_THEME sebagai fallback global
    # tapi cli akan inject theme via set_active_theme() di bawah.
    return _ACTIVE_THEME or _theme_mod.DEFAULT_THEME


_ACTIVE_THEME: Theme | None = None


def set_active_theme(theme: Theme) -> None:
    """Dipanggil oleh cli.set_theme agar cyber juga ikut tema aktif."""
    global _ACTIVE_THEME
    _ACTIVE_THEME = theme


# ASCII logo block. Width = 57 visible chars (per line).
LOGO_LINES = [
    "██████╗  █████╗ ██████╗ ████████╗███████╗ ██████╗██╗  ██╗",
    "██╔══██╗██╔══██╗██╔══██╗╚══██╔══╝██╔════╝██╔════╝██║  ██║",
    "██████╔╝███████║██████╔╝   ██║   █████╗  ██║     ███████║",
    "██╔══██╗██╔══██║██╔═══╝    ██║   ██╔══╝  ██║     ██╔══██║",
    "██║  ██║██║  ██║██║        ██║   ███████╗╚██████╗██║  ██║",
    "╚═╝  ╚═╝╚═╝  ╚═╝╚═╝        ╚═╝   ╚══════╝ ╚═════╝╚═╝  ╚═╝",
]

LOGO_LINES_ASCII = [
    "  ____             _           _     ",
    " |  _ \\ __ _ _ __ | |_ ___ ___| |__  ",
    " | |_) / _` | '_ \\| __/ _ / __| '_ \\ ",
    " |  _ < (_| | |_) | || (_/ (__| | | |",
    " |_| \\_\\__,_| .__/ \\__\\___\\___|_| |_|",
    "            |_|                       ",
]

LOGO_WIDTH = 57
DEFAULT_WIDTH = 64


def _w(text: str = "") -> None:
    try:
        sys.stdout.write(text)
        sys.stdout.flush()
    except UnicodeEncodeError:
        safe_text = text.encode("utf-8", errors="replace").decode("utf-8")
        sys.stdout.write(safe_text)
        sys.stdout.flush()


def _wln(text: str = "") -> None:
    sys.stdout.write(text + "\n")
    sys.stdout.flush()


def clear_line() -> None:
    _w("\r" + " " * terminal_caps().width + "\r")


def hr(width: int = DEFAULT_WIDTH, char: str | None = None, role: str = "primary") -> str:
    t = _theme()
    return t.c((char or t.glyphs.h) * width, role)


def banner_logo() -> None:
    """Cetak logo RAPTECH dengan tagline. Mengikuti theme aktif.

    Plain mode: skip ASCII art, tampil heading text saja.
    Non-Unicode terminal: pakai logo ASCII fallback.
    """
    t = _theme()
    pad = " " * 3

    if t.plain:
        _wln()
        _wln(f"{pad}{t.c('RAPTECH', 'primary', bold=True)} "
             f"{t.c('TERMINAL CORE', 'accent', bold=True)}")
        _wln(f"{pad}{t.c('License Gateway', 'dim')}")
        _wln()
        return

    # Fallback to ASCII if Unicode not supported by terminal
    lines = LOGO_LINES if _is_unicode_glyph_set(t) else LOGO_LINES_ASCII
    _wln()
    for line in lines:
        _wln(f"{pad}{t.c(line, 'primary', bold=True)}")
        time.sleep(0.04)
    _wln()
    tagline = f"{t.glyphs.arrow} TERMINAL CORE {t.glyphs.bullet} LICENSE GATEWAY"
    line2 = (t.glyphs.h * 56) if not t.use_color else ("\u2550" * 56)
    _wln(f"{pad}{t.c(tagline, 'accent', bold=True)}")
    _wln(f"{pad}{t.c(line2, 'dim')}")
    _wln()


def _is_unicode_glyph_set(t: Theme) -> bool:
    # Heuristik: kalau border vertical pakai non-ASCII char, anggap unicode set.
    return t.glyphs.v != "|"


def boot_step(label: str, *, delay: float = 0.4, ok: bool = True) -> None:
    """Cetak baris boot dengan spinner animasi lalu [ OK ] / [FAIL]."""
    t = _theme()
    if t.plain:
        badge = "OK" if ok else "FAIL"
        _wln(f"  [SYS] {label} ... {badge}")
        return

    spinner = "|/-\\" if not t.use_color else "\u280B\u2819\u2839\u2838\u283C\u2834\u2826\u2827\u2807\u280F"
    prefix = f"  {t.c('[SYS]', 'accent', bold=True)} {label}"
    start = time.monotonic()
    i = 0
    while time.monotonic() - start < delay:
        ch = spinner[i % len(spinner)]
        _w(f"\r{prefix}... {t.c(ch, 'warning', bold=True)}")
        time.sleep(0.05)
        i += 1
    if ok:
        badge = (
            f"{t.c('[ ', 'success')}"
            f"{t.c('OK', 'success', bold=True)}"
            f"{t.c(' ]', 'success')}"
        )
    else:
        badge = (
            f"{t.c('[', 'danger')}"
            f"{t.c('FAIL', 'danger', bold=True)}"
            f"{t.c(']', 'danger')}"
        )
    visible_left = visible_len(prefix) + 4  # "... "
    fill = max(2, 60 - visible_left)
    _w(f"\r{prefix}{t.c('.' * fill, 'dim')} {badge}\n")
    sys.stdout.flush()


def boot_sequence(steps: Iterable[tuple[str, float]] | None = None) -> None:
    """Render rangkaian boot lines. Default 4 baris realistis."""
    if steps is None:
        steps = [
            ("Initializing license vault", 0.35),
            ("Loading cryptographic modules", 0.45),
            ("Establishing secure channel", 0.55),
            ("Verifying server endpoint", 0.40),
        ]
    for label, delay in steps:
        boot_step(label, delay=delay, ok=True)


# --- Box drawing -----------------------------------------------------------



def _wrap_text(text: str, max_width: int, indent: str = "  ") -> list[str]:
    """Word-wrap text panjang ke multiple lines dengan indent.
    
    Preserve ANSI color codes dan break di word boundary.
    Return list of lines (tanpa trailing newline).
    """
    if visible_len(text) <= max_width:
        return [text]
    
    # Strip ANSI untuk word-breaking, tapi preserve di output
    words = text.split()
    lines = []
    current_line = ""
    
    for word in words:
        test_line = f"{current_line} {word}".strip() if current_line else word
        if visible_len(test_line) <= max_width:
            current_line = test_line
        else:
            if current_line:
                lines.append(current_line)
            # Word terlalu panjang? Hard-break
            if visible_len(word) > max_width:
                current_line = word[:max_width] + "..."
            else:
                current_line = word
    
    if current_line:
        lines.append(current_line)
    
    # Add indent untuk line ke-2 dst
    return [lines[0]] + [indent + line for line in lines[1:]] if lines else []

def _pad_line(text: str, width: int) -> str:
    pad = max(0, width - visible_len(text))
    return text + " " * pad


def box(
    lines: list[str],
    *,
    width: int = 60,
    role: str = "primary",
    indent: str = "  ",
) -> None:
    """Render boxed lines. Style border (rounded vs sharp) ditentukan oleh
    theme.glyphs (auto rounded di terminal modern, sharp di legacy).
    """
    t = _theme()
    if t.plain:
        # Plain mode: tidak gambar box, hanya header divider tipis
        _wln(t.c(("=" * (width - 2)), "dim"))
        for line in lines:
            _wln(f"{indent}{line}")
        _wln(t.c(("=" * (width - 2)), "dim"))
        return

    g = t.glyphs
    horiz = g.h
    vert = g.v
    inner_w = width - 2
    _wln(f"{indent}{t.c(g.tl + horiz * inner_w + g.tr, role)}")
    for line in lines:
        body = _pad_line(" " + line, inner_w)
        _wln(f"{indent}{t.c(vert, role)}{body}{t.c(vert, role)}")
    _wln(f"{indent}{t.c(g.bl + horiz * inner_w + g.br, role)}")


# --- Specific screens ------------------------------------------------------


def screen_activation_prompt(support_contact: str) -> None:
    """Render full activation screen: logo + boot + framed prompt."""
    t = _theme()
    banner_logo()
    boot_sequence()
    _wln()
    abort_text = "type 'cancel'"
    box(
        [
            f"{t.c(t.glyphs.flat + '  AUTHENTICATION REQUIRED', 'primary', bold=True)}",
            "",
            f"{t.c('Insert activation key to unlock terminal.', 'muted')}",
            "",
            f"  {t.c('Format    :', 'dim')}  "
            f"{t.c('XXXXX-XXXXX', 'warning', bold=True)}  "
            f"{t.c('(10 chars)', 'dim')}",
            f"  {t.c('Support   :', 'dim')}  "
            f"{t.c(support_contact, 'muted', bold=True)}",
            f"  {t.c('Abort     :', 'dim')}  "
            f"{t.c(abort_text, 'muted')}",
        ],
        width=DEFAULT_WIDTH,
        role="primary",
    )
    _wln()


def screen_verifying(code_pretty: str) -> None:
    t = _theme()
    _wln(
        f"  {t.c('[NET]', 'accent', bold=True)} "
        f"Submitting key {t.c(code_pretty, 'warning', bold=True)}...\n"
    )


def screen_activation_success(
    customer: str, expires_str: str, remaining: str, file_path: str
) -> None:
    t = _theme()
    _wln()
    box(
        [
            f"{t.c(t.glyphs.check + '  ACCESS GRANTED', 'success', bold=True)}",
            "",
            f"  {t.c('IDENTITY     ', 'dim')} {t.c(customer, 'muted', bold=True)}",
            f"  {t.c('EXPIRES      ', 'dim')} {t.c(expires_str, 'muted', bold=True)}",
            f"  {t.c('REMAINING    ', 'dim')} {t.c(remaining, 'success', bold=True)}",
        ],
        width=DEFAULT_WIDTH,
        role="success",
    )
    _wln()
    arrow = t.glyphs.arrow
    _wln(
        f"  {t.c(f'[{arrow}]', 'success')} License vault sealed "
        f"{t.glyphs.arrow} {t.c(file_path, 'dim')}"
    )
    _wln(
        f"  {t.c(f'[{arrow}]', 'success')} Heartbeat watcher armed "
        f"{t.glyphs.arrow} {t.c('3min interval', 'dim')}"
    )
    _wln()


def screen_activation_error(reason: str, support_contact: str) -> None:
    t = _theme()
    _wln()
    action_text = "Try again or type 'cancel' to exit"
    
    # Word-wrap reason text (max 48 chars after "Reason  : " prefix)
    reason_lines = _wrap_text(t.c(reason, 'muted'), max_width=48, indent="            ")
    
    # Build box content
    box_lines = [
        f"{t.c(t.glyphs.cross_mark + '  ACCESS DENIED', 'danger', bold=True)}",
        "",
    ]
    
    # Add wrapped reason lines
    for idx, line in enumerate(reason_lines):
        if idx == 0:
            box_lines.append(f"  {t.c('Reason  :', 'dim')} {line}")
        else:
            box_lines.append(f"  {line}")
    
    box_lines.extend([
        f"  {t.c('Support :', 'dim')} {t.c(support_contact, 'muted', bold=True)}",
        f"  {t.c('Action  :', 'dim')} {t.c(action_text, 'muted')}",
    ])
    
    box(
        box_lines,
        width=DEFAULT_WIDTH,
        role="danger",
    )
    _wln()
def screen_revoked(reason: str, support_contact: str) -> None:
    t = _theme()
    _wln()
    
    # Word-wrap reason text
    reason_lines = _wrap_text(t.c(reason, 'muted'), max_width=48, indent="            ")
    
    box_lines = [
        f"{t.c(t.glyphs.warn + '  LICENSE REVOKED', 'danger', bold=True)}",
        "",
    ]
    
    # Add wrapped reason lines
    for idx, line in enumerate(reason_lines):
        if idx == 0:
            box_lines.append(f"  {t.c('Reason  :', 'dim')} {line}")
        else:
            box_lines.append(f"  {line}")
    
    box_lines.extend([
        f"  {t.c('Support :', 'dim')} {t.c(support_contact, 'muted', bold=True)}",
        f"  {t.c('Action  :', 'dim')} {t.c('Returning to activation prompt...', 'muted')}",
    ])
    
    box(
        box_lines,
        width=DEFAULT_WIDTH,
        role="danger",
    )
    _wln()


def screen_warning_expiring(remaining: str, support_contact: str) -> None:
    t = _theme()
    _wln()
    box(
        [
            f"{t.c(t.glyphs.warn + '  LICENSE EXPIRING SOON', 'warning', bold=True)}",
            "",
            f"  {t.c('Remaining :', 'dim')} {t.c(remaining, 'warning', bold=True)}",
            f"  {t.c('Renewal   :', 'dim')} {t.c(support_contact, 'muted', bold=True)}",
        ],
        width=DEFAULT_WIDTH,
        role="warning",
    )
    _wln()


def status_line(label: str, value: str, *, ok: bool = True) -> str:
    t = _theme()
    icon = t.c(t.glyphs.dot_on, "success") if ok else t.c(t.glyphs.dot_on, "danger")
    return (
        f"  {icon} {t.c(f'{label:<14}', 'dim')} "
        f"{t.c(value, 'muted', bold=True)}"
    )


def license_status_line(customer: str, remaining: str, expires: str) -> None:
    """Print compact one-line status saat license OK."""
    t = _theme()
    _wln()
    _wln(status_line("IDENTITY", customer))
    _wln(status_line("REMAINING", remaining))
    _wln(status_line("EXPIRES", expires))
    _wln(
        f"  {t.c(t.glyphs.dot_on, 'success')} "
        f"{t.c('STATUS         ', 'dim')} "
        f"{t.c('ACTIVE', 'success', bold=True)}"
    )
    _wln()


def heartbeat_tick(timestamp: str) -> str:
    t = _theme()
    return (
        f"  {t.c(t.glyphs.dot_on, 'success')} {t.c('heartbeat', 'dim')} "
        f"{t.c('OK', 'success')} {t.c('@ ' + timestamp, 'dim')}"
    )


def cyber_input_prompt() -> str:
    """Returns the prompt string used by input()."""
    t = _theme()
    return (
        f"  {t.c('KEY', 'primary', bold=True)} "
        f"{t.c(t.glyphs.arrow, 'dim')} "
    )


# --- Backward-compat shim --------------------------------------------------
# Module `corebot/license/check.py` reference `ui.C.RED` & `ui.C.RESET`.
# Kita pertahankan attribute akses minimal supaya tidak putus, tapi sumber-nya
# tetap theme aktif (kalau no_color â†’ string kosong).


class _CompatColor:
    """Shim tipis untuk akses `ui.C.RED`, `ui.C.RESET`, dst.

    Kompat mode untuk `corebot/license/check.py` yang masih reference
    legacy attribute. Semua attribute return ANSI escape string sesuai
    theme aktif (kosong saat no-color).

    Attribute yang dicover (subset cyber lama):
      RESET, BOLD, DIM,
      RED, GREEN, YELLOW, BLUE, MAGENTA, CYAN, WHITE, GRAY,
      BRED, BGREEN, BYELLOW, BBLUE, BMAGENTA, BCYAN, BWHITE
    """

    @property
    def RESET(self) -> str:  # noqa: N802
        return _theme().reset

    @property
    def BOLD(self) -> str:  # noqa: N802
        t = _theme()
        return f"\x1b[{t.palette.bold}m" if t.use_color else ""

    @property
    def DIM(self) -> str:  # noqa: N802
        return _theme().code("dim")

    @property
    def RED(self) -> str:  # noqa: N802
        return _theme().code("danger", bold=True)

    @property
    def GREEN(self) -> str:  # noqa: N802
        return _theme().code("success", bold=True)

    @property
    def YELLOW(self) -> str:  # noqa: N802
        return _theme().code("warning", bold=True)

    @property
    def BLUE(self) -> str:  # noqa: N802
        return _theme().code("info", bold=True)

    @property
    def MAGENTA(self) -> str:  # noqa: N802
        return _theme().code("accent", bold=True)

    @property
    def CYAN(self) -> str:  # noqa: N802
        return _theme().code("primary", bold=True)

    @property
    def WHITE(self) -> str:  # noqa: N802
        return _theme().code("muted", bold=True)

    @property
    def GRAY(self) -> str:  # noqa: N802
        return _theme().code("dim")

    # Bright variants â€” alias ke role yang sama (theme palette sudah
    # pilih nilai SGR yang kontras saat preset menuntut).
    @property
    def BRED(self) -> str:  # noqa: N802
        return _theme().code("danger", bold=True)

    @property
    def BGREEN(self) -> str:  # noqa: N802
        return _theme().code("success", bold=True)

    @property
    def BYELLOW(self) -> str:  # noqa: N802
        return _theme().code("warning", bold=True)

    @property
    def BBLUE(self) -> str:  # noqa: N802
        return _theme().code("info", bold=True)

    @property
    def BMAGENTA(self) -> str:  # noqa: N802
        return _theme().code("accent", bold=True)

    @property
    def BCYAN(self) -> str:  # noqa: N802
        return _theme().code("primary", bold=True)

    @property
    def BWHITE(self) -> str:  # noqa: N802
        return _theme().code("muted", bold=True)

    # Last-resort: kalau ada attribute lain yang lupa di-cover, return
    # string kosong supaya tidak crash. Semua call site lama tujuannya
    # cuma sisip warna; missing attribute = no-color, tetap aman.
    def __getattr__(self, name: str) -> str:
        return ""


C = _CompatColor()

