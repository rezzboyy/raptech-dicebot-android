"""Theme & visual primitives untuk Raptech Engine.

Modul ini menyediakan:
- Palette warna semantik (primary, accent, success, danger, dll)
- Glyph set untuk box-drawing dan status (Unicode dengan fallback ASCII)
- Helper untuk membungkus teks dengan warna dan menggambar struktur visual
- TerminalCaps detection (size, color, unicode, tty, hyperlink)
- Theme presets: cyber, minimal, mono, accessible

Tujuan: jadi satu sumber kebenaran agar perubahan tema cukup di satu tempat.
"""

from __future__ import annotations

import os
import shutil
import sys
from dataclasses import dataclass

# ANSI escape constants (independen dari colorama, agar fallback rapi)
_ESC = "\x1b["
_RESET = f"{_ESC}0m"


def _supports_unicode() -> bool:
    """Best-effort check apakah terminal aktif mampu render Unicode box-drawing."""
    encoding = (getattr(sys.stdout, "encoding", None) or "").lower()
    if "utf" in encoding:
        return True
    # Windows Terminal / VS Code terminal set WT_SESSION / TERM_PROGRAM
    if os.getenv("WT_SESSION") or os.getenv("TERM_PROGRAM"):
        return True
    return False


def _supports_truecolor() -> bool:
    return (os.getenv("COLORTERM", "") or "").lower() in ("truecolor", "24bit")


def _supports_modern_box() -> bool:
    """Apakah terminal aktif kemungkinan render rounded box (`â•­â”€â•®`) dengan baik.

    Heuristik: Windows Terminal modern, VS Code, kitty, iTerm. Legacy cmd.exe
    sering mis-render glyph rounded â†’ kita fallback ke `â”Œâ”€â”`.
    """
    if os.getenv("WT_SESSION"):  # Windows Terminal
        return True
    if os.getenv("TERM_PROGRAM"):  # VS Code, iTerm, dll
        return True
    if os.getenv("KITTY_WINDOW_ID"):
        return True
    # Default conservative di Windows legacy
    if sys.platform == "win32":
        return False
    return True


@dataclass(frozen=True, slots=True)
class TerminalCaps:
    """Snapshot kemampuan terminal saat startup."""

    width: int
    height: int
    unicode: bool
    color: bool
    truecolor: bool
    is_tty: bool
    modern_box: bool

    @classmethod
    def detect(cls) -> "TerminalCaps":
        try:
            size = shutil.get_terminal_size(fallback=(80, 24))
        except Exception:
            class _S:
                columns = 80
                lines = 24
            size = _S()
        try:
            is_tty = bool(sys.stdout.isatty())
        except Exception:
            is_tty = False
        return cls(
            width=int(size.columns),
            height=int(size.lines),
            unicode=_supports_unicode(),
            color=is_tty,  # default: warna hanya kalau tty
            truecolor=_supports_truecolor(),
            is_tty=is_tty,
            modern_box=_supports_modern_box(),
        )


# Cached caps (refresh on-demand via terminal_caps(refresh=True))
_CAPS: TerminalCaps | None = None


def terminal_caps(*, refresh: bool = False) -> TerminalCaps:
    global _CAPS
    if _CAPS is None or refresh:
        _CAPS = TerminalCaps.detect()
    return _CAPS


@dataclass(frozen=True, slots=True)
class Palette:
    """Palette warna semantik. Nilainya adalah ANSI SGR (tanpa escape prefix)."""

    primary: str = "36"      # cyan
    accent: str = "35"       # magenta
    success: str = "32"      # green
    danger: str = "31"       # red
    warning: str = "33"      # yellow
    info: str = "34"         # blue
    muted: str = "37"        # white (default text)
    dim: str = "90"          # bright black / gray
    bold: str = "1"


# ---- Theme presets palettes ---------------------------------------------

_PALETTE_CYBER = Palette()  # default cyan/magenta

_PALETTE_MINIMAL = Palette(
    primary="94",   # bright blue
    accent="96",    # bright cyan
    success="32",
    danger="31",
    warning="33",
    info="37",
    muted="37",
    dim="90",
)

_PALETTE_ACCESSIBLE = Palette(
    primary="97",   # bright white as primary
    accent="93",    # bright yellow accent (tinggi kontras di bg gelap)
    success="92",   # bright green
    danger="91",    # bright red
    warning="93",
    info="96",
    muted="97",
    dim="37",       # white-ish dim, bukan gray gelap (kontras lebih baik)
)


@dataclass(frozen=True, slots=True)
class Glyphs:
    """Karakter visual: border, status, marker."""

    # Box-drawing
    h: str           # horizontal
    v: str           # vertical
    tl: str          # top-left corner
    tr: str          # top-right corner
    bl: str          # bottom-left corner
    br: str          # bottom-right corner
    t_down: str      # T pointing down
    t_up: str        # T pointing up
    t_right: str     # T pointing right
    t_left: str      # T pointing left
    cross: str       # +
    # Markers
    accent_bar: str  # vertical accent bar untuk section header
    bullet: str
    arrow: str
    dot_on: str      # status connected/active
    dot_off: str     # status idle/empty
    up: str          # delta naik
    down: str        # delta turun
    flat: str        # delta nol
    check: str
    cross_mark: str
    info: str
    warn: str
    prompt: str
    # Optional / extension glyphs (Fase 3.1, 6.1)
    v_double: str = "\u2551"   # double vertical untuk group divider
    h_dashed: str = "\u254C"   # dashed horizontal untuk style 'dashed'
    v_dashed: str = "\u254E"   # dashed vertical

    @classmethod
    def unicode(cls, *, rounded: bool = False) -> "Glyphs":
        if rounded:
            tl, tr, bl, br = "\u256D", "\u256E", "\u2570", "\u256F"
        else:
            tl, tr, bl, br = "\u250C", "\u2510", "\u2514", "\u2518"
        return cls(
            h="\u2500",
            v="\u2502",
            tl=tl,
            tr=tr,
            bl=bl,
            br=br,
            t_down="\u252C",
            t_up="\u2534",
            t_right="\u251C",
            t_left="\u2524",
            cross="\u253C",
            accent_bar="\u258E",
            bullet="\u2022",
            arrow="\u203A",
            dot_on="\u25CF",
            dot_off="\u25CB",
            up="\u25B2",
            down="\u25BC",
            flat="\u25C6",
            check="\u2713",
            cross_mark="\u2717",
            info="i",
            warn="!",
            prompt="\u203A",
        )

    @classmethod
    def ascii(cls) -> "Glyphs":
        return cls(
            h="-",
            v="|",
            tl="+",
            tr="+",
            bl="+",
            br="+",
            t_down="+",
            t_up="+",
            t_right="+",
            t_left="+",
            cross="+",
            accent_bar="|",
            bullet="*",
            arrow=">",
            dot_on="*",
            dot_off="o",
            up="^",
            down="v",
            flat="-",
            check="+",
            cross_mark="x",
            info="i",
            warn="!",
            prompt=">",
            v_double="||",
            h_dashed="-",
            v_dashed="|",
        )


@dataclass(frozen=True, slots=True)
class Theme:
    """Bundle palette + glyph set + flag visual."""

    palette: Palette
    glyphs: Glyphs
    use_color: bool
    name: str = "cyber"
    plain: bool = False  # skip ASCII-art logo, box drawing â†’ text-only hierarchy

    def code(self, role: str, *, bold: bool = False) -> str:
        """Return ANSI escape sequence untuk role tertentu, atau "" kalau no-color.

        Berguna untuk modul yang butuh sisip warna manual (mis. cyber.py logo
        animasi) tanpa wrap full string lewat .c().
        """
        if not self.use_color:
            return ""
        sgr = getattr(self.palette, role, None)
        if not sgr:
            return ""
        if bold:
            return f"{_ESC}{self.palette.bold};{sgr}m"
        return f"{_ESC}{sgr}m"

    @property
    def reset(self) -> str:
        return _RESET if self.use_color else ""

    def c(self, text: str, role: str, *, bold: bool = False) -> str:
        """Bungkus `text` dengan warna untuk peran semantik tertentu."""
        if not self.use_color:
            return text
        code = getattr(self.palette, role, None)
        if not code:
            return text
        prefix = f"{_ESC}{self.palette.bold};{code}m" if bold else f"{_ESC}{code}m"
        return f"{prefix}{text}{_RESET}"

    def by_sign(self, text: str, value: float) -> str:
        if value > 0:
            return self.c(text, "success")
        if value < 0:
            return self.c(text, "danger")
        return self.c(text, "muted")

    def by_win(self, text: str, win: bool | None) -> str:
        if win is True:
            return self.c(text, "success")
        if win is False:
            return self.c(text, "danger")
        return text

    def divider(self, width: int = 64, *, role: str = "dim") -> str:
        return self.c(self.glyphs.h * width, role)

    def section(self, title: str, *, role: str = "accent") -> str:
        bar = self.c(self.glyphs.accent_bar, role, bold=True)
        label = self.c(title.upper(), role, bold=True)
        return f"{bar} {label}"

    def box_top(self, width: int, *, role: str = "dim") -> str:
        g = self.glyphs
        return self.c(f"{g.tl}{g.h * (width - 2)}{g.tr}", role)

    def box_bottom(self, width: int, *, role: str = "dim") -> str:
        g = self.glyphs
        return self.c(f"{g.bl}{g.h * (width - 2)}{g.br}", role)

    def box_mid(self, width: int, *, role: str = "dim") -> str:
        g = self.glyphs
        return self.c(f"{g.t_right}{g.h * (width - 2)}{g.t_left}", role)

    def box_row(self, content: str, width: int, *, role: str = "dim") -> str:
        """Baris konten dalam box. Pad konten secara visible-aware (tetap fit width)."""
        g = self.glyphs
        v = self.c(g.v, role)
        # gunakan visible_len agar pad benar walau ada ANSI di content
        pad = max(0, width - 2 - visible_len(content))
        return f"{v}{content}{' ' * pad}{v}"

    def status_dot(self, connected: bool) -> str:
        if connected:
            return self.c(self.glyphs.dot_on, "success", bold=True)
        return self.c(self.glyphs.dot_off, "dim")

    def trend(self, value: float) -> str:
        g = self.glyphs
        if value > 0:
            return self.c(g.up, "success", bold=True)
        if value < 0:
            return self.c(g.down, "danger", bold=True)
        return self.c(g.flat, "dim")

    def pill(self, label: str, value: str, *, role: str = "primary") -> str:
        """[LABEL value] dengan label diwarnai role, value default."""
        return f"{self.c(f'[{label}]', role, bold=True)} {value}"

    def pill_fixed(
        self,
        label: str,
        value: str,
        *,
        role: str = "primary",
        width: int = 18,
    ) -> str:
        """Pill dengan total visible width tetap sehingga posisi tidak goyang
        saat angka berubah panjang. Truncate value bila perlu.
        """
        bracket = f"[{label}]"
        # Kompose tanpa warna dulu untuk hitung lebar
        plain = f"{bracket} {value}"
        plain_len = len(bracket) + 1 + len(value)
        if plain_len > width:
            # Potong value agar fit (sisakan ellipsis bila layak)
            keep = max(0, width - len(bracket) - 1)
            if keep >= 1:
                value = value[: keep - 1] + "â€¦" if keep >= 2 else value[:keep]
            else:
                value = ""
            plain = f"{bracket} {value}"
            plain_len = len(plain)
        pad = max(0, width - plain_len)
        styled_label = self.c(bracket, role, bold=True)
        return f"{styled_label} {value}{' ' * pad}"


def visible_len(text: str) -> int:
    """Hitung panjang teks tanpa ANSI escape sequences."""
    out = 0
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == "\x1b" and i + 1 < len(text) and text[i + 1] == "[":
            # skip sampai ketemu huruf akhir SGR
            j = i + 2
            while j < len(text) and not text[j].isalpha():
                j += 1
            i = j + 1
            continue
        out += 1
        i += 1
    return out


def pad_visible(text: str, width: int) -> str:
    """Pad agar visible-length tepat `width`. Truncate kalau lebih panjang.

    Truncate dilakukan secara ANSI-aware: escape sequence tidak dipotong
    di tengah sehingga tidak merusak warna terminal.
    """
    diff = width - visible_len(text)
    if diff > 0:
        return text + " " * diff
    if diff < 0:
        out: list[str] = []
        visible = 0
        i = 0
        while i < len(text) and visible < width:
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
            out.append("\x1b[0m")
        return "".join(out)
    return text


# ---- Factory --------------------------------------------------------------

THEME_PRESETS = ("cyber", "minimal", "mono", "accessible")


def _palette_for(name: str) -> Palette:
    if name == "minimal":
        return _PALETTE_MINIMAL
    if name == "accessible":
        return _PALETTE_ACCESSIBLE
    # cyber & mono share default palette (mono renders tanpa warna)
    return _PALETTE_CYBER


def build_theme(
    no_color: bool = False,
    force_ascii: bool = False,
    *,
    name: str = "cyber",
    plain: bool = False,
) -> Theme:
    """Bangun Theme aktif.

    Parameter:
      - `no_color`: paksa tanpa warna (mis. user pass `--no-color` atau output
        di-pipe ke file).
      - `force_ascii`: paksa glyph ASCII walau terminal support Unicode.
      - `name`: salah satu THEME_PRESETS. `mono` otomatis menyalakan no_color.
      - `plain`: text-only mode â€” caller (cyber, cli) skip ASCII art / box.
    """
    name = (name or "cyber").lower()
    if name not in THEME_PRESETS:
        name = "cyber"

    caps = terminal_caps()
    use_color = not no_color and caps.color and name != "mono"
    use_unicode = caps.unicode and not force_ascii
    rounded = caps.modern_box and use_unicode and name in ("cyber", "accessible")
    glyphs = Glyphs.unicode(rounded=rounded) if use_unicode else Glyphs.ascii()
    palette = _palette_for(name)
    return Theme(
        palette=palette,
        glyphs=glyphs,
        use_color=use_color,
        name=name,
        plain=plain,
    )


# Default theme instance untuk import cepat di tempat yang tidak menerima param.
DEFAULT_THEME: Theme = build_theme()

