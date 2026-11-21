"""Reusable terminal UI widgets: toast, KPI strip, dry-run panel,
hotkey help overlay, mini sparkline, state pulse renderer, and a small
inline form field helper.

Semua widget render via Theme aktif sehingga ikut tema yang dipilih
user (--theme cyber|minimal|mono|accessible).
"""
from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Iterable

from .theme import Theme, pad_visible, visible_len


# ---------- State pulse ---------------------------------------------------


def state_marker(theme: Theme, state: str, *, tick: float | None = None) -> tuple[str, str]:
    """Return (dot, label) untuk state engine, dengan animasi ringan.

    `tick` opsional â€” biasanya `time.monotonic()`. Saat None, render
    tanpa animasi (snapshot statis).
    """
    g = theme.glyphs
    state = (state or "").lower()
    if state in ("running", "starting"):
        # Pulse: alternasi dot_on dan dot_off setiap 1 detik
        if tick is not None and int(tick) % 2 == 0:
            ch = g.dot_on
        else:
            ch = g.dot_off if tick is not None else g.dot_on
        if state == "starting":
            label = "STARTING"
            role = "info"
        else:
            label = "RUNNING"
            role = "success"
        return theme.c(ch, role, bold=True), theme.c(label, role, bold=True)
    if state == "paused":
        # Bar statis â–®â–®â–® atau ASCII =||=
        bar = "\u25AE\u25AE\u25AE" if g.dot_on != "*" else "|||"
        return theme.c(bar, "warning", bold=True), theme.c("PAUSED", "warning", bold=True)
    if state == "stopped":
        return theme.c(g.dot_off, "dim"), theme.c("STOPPED", "dim", bold=True)
    if state == "error":
        return theme.c(g.warn, "danger", bold=True), theme.c("ERROR", "danger", bold=True)
    return theme.c(g.dot_off, "dim"), theme.c(state.upper() or "IDLE", "dim", bold=True)


# ---------- KPI strip -----------------------------------------------------


def kpi_strip(
    theme: Theme,
    *,
    balance: float,
    currency: str,
    profit_pct: float,
    runtime_seconds: float,
    bets: int,
    wins: int,
    losses: int,
    width: int = 96,
    session_profit: float = 0.0,
) -> str:
    """Satu baris KPI ringkas - sticky di atas tabel live.

    Format dipilih supaya tidak goyang (semua segmen fixed-width).
    Kalau env RAPTECH_IDR=1 dan currency supported, tampilkan estimasi
    IDR di dua tempat: (1) segment IDR balance, (2) di samping profit %.
    """
    import os as _os
    g = theme.glyphs
    _idr_enabled = _os.getenv("RAPTECH_IDR") == "1"

    bal_str = _format_amount(balance, max_chars=14)
    bal_segment = (
        f"{theme.c(g.dot_on, 'success', bold=True)} "
        f"{theme.c('BAL', 'dim', bold=True)} "
        f"{theme.c(pad_visible(bal_str, 14), 'muted', bold=True)} "
        f"{theme.c(currency or '-', 'accent', bold=True)}"
    )

    # Estimasi IDR untuk balance (cache 60s, non-blocking)
    idr_segment = ""
    profit_idr_str = ""
    if _idr_enabled:
        try:
            from ..pricing import coin_to_idr, format_idr, is_supported
            if is_supported(currency):
                # IDR untuk balance
                idr_val = coin_to_idr(balance, currency)
                if idr_val is not None:
                    idr_segment = (
                        f"{theme.c('IDR', 'dim', bold=True)} "
                        f"{theme.c(format_idr(idr_val), 'muted', bold=True)}"
                    )
                # IDR untuk profit (di samping presentase)
                if session_profit != 0.0:
                    p_idr = coin_to_idr(session_profit, currency)
                    if p_idr is not None:
                        profit_idr_str = f" ({format_idr(p_idr, sign=True)})"
        except Exception:
            pass

    profit_text = f"{profit_pct:+.4f}%"
    profit_arrow = g.up if profit_pct > 0 else (g.down if profit_pct < 0 else g.flat)
    profit_role = "success" if profit_pct > 0 else ("danger" if profit_pct < 0 else "muted")

    # Profit segment dengan IDR opsional di belakang %
    profit_pct_part = (
        f"{theme.c(profit_arrow, profit_role, bold=True)} "
        f"{theme.c(pad_visible(profit_text, 10), profit_role, bold=True)}"
    )
    if profit_idr_str:
        profit_segment = profit_pct_part + theme.c(profit_idr_str, "dim")
    else:
        profit_segment = profit_pct_part

    runtime_segment = (
        f"{theme.c('TIME', 'dim', bold=True)} "
        f"{theme.c(format_duration(runtime_seconds), 'primary', bold=True)}"
    )

    bets_segment = (
        f"{theme.c('BETS', 'dim', bold=True)} "
        f"{theme.c(f'{bets:,}', 'primary', bold=True)}"
    )

    wl_segment = (
        f"{theme.c(f'{wins}', 'success', bold=True)}"
        f"{theme.c('/', 'dim')}"
        f"{theme.c(f'{losses}', 'danger', bold=True)}"
    )

    sep = theme.c("  " + g.v + "  ", "dim")

    all_segs = [bal_segment]
    if idr_segment:
        all_segs.append(idr_segment)
    all_segs += [profit_segment, runtime_segment, bets_segment, wl_segment]

    body = sep.join(all_segs)
    # Graceful truncation kalau kepanjangan
    if visible_len(body) > width:
        # Level 1: drop IDR balance segment (tapi keep IDR di profit)
        body = sep.join([bal_segment, profit_segment, runtime_segment, bets_segment, wl_segment])
    if visible_len(body) > width:
        # Level 2: drop IDR di profit juga
        body = sep.join([bal_segment, profit_pct_part, runtime_segment, bets_segment, wl_segment])
    if visible_len(body) > width:
        # Level 3: minimal segments only
        body = sep.join([bal_segment, profit_pct_part, runtime_segment])
    return body

def _format_amount(value: float, *, max_chars: int = 12) -> str:
    abs_v = abs(value)
    if abs_v == 0:
        return "0.00000000"
    if abs_v >= 1000:
        return f"{value:,.2f}"
    if abs_v >= 1:
        return f"{value:.4f}"
    return f"{value:.8f}"


# ---------- Layout Fase 2: numeric formatting --------------------------


def smart_precision(value: float, *, max_chars: int | None = None) -> str:
    """Format angka dengan precision sesuai magnitude.

    Rules:
      - <1                -> 8 decimal (`0.00000123`)
      - 1-1000            -> 4 decimal (`12.3456`)
      - >=1000            -> 2 decimal + thousand separator koma (`1,234.57`)

    `max_chars` opsional - kalau di-set, output di-truncate dengan
    ellipsis ANSI-aware.
    """
    abs_v = abs(value)
    if abs_v == 0:
        out = "0.00000000"
    elif abs_v >= 1000:
        out = format_money(value, separator=",", dec=2)
    elif abs_v >= 1:
        out = f"{value:.4f}"
    else:
        out = f"{value:.8f}"
    if max_chars is not None and len(out) > max_chars:
        return truncate_visible(out, max_chars)
    return out


def format_money(value: float, *, int_width: int = 0, dec: int = 8,
                 separator: str = "") -> str:
    """Format money value dengan kontrol width integer + separator
    (Fase 2.1 + 2.2).

    `int_width=0` disable padding, otherwise pad integer part di kiri
    sampai panjang itu (decimal-aligned).
    `separator` opsional: pakai `"_"`, `","`, atau `"."` untuk thousand
    separator. `""` (default) = no separator.
    """
    sign = "-" if value < 0 else ""
    abs_v = abs(value)
    if separator:
        # Format integer part dengan separator
        int_part = int(abs_v)
        if separator == ",":
            int_str = f"{int_part:,}"
        else:
            int_str = f"{int_part:,}".replace(",", separator)
        # Decimal part: ambil .Nf full, drop integer.
        full = f"{abs_v:.{dec}f}"
        # full = "1234.56789012" â€” ambil setelah titik
        decimal_str = full.split(".", 1)[1] if "." in full else "0" * dec
        body = f"{int_str}.{decimal_str}"
    else:
        body = f"{abs_v:.{dec}f}"
    if int_width > 0:
        # Pad integer side (kiri dari titik) sampai int_width
        if "." in body:
            int_side, dec_side = body.split(".", 1)
        else:
            int_side, dec_side = body, ""
        if len(int_side) < int_width:
            int_side = " " * (int_width - len(int_side)) + int_side
        body = f"{int_side}.{dec_side}" if dec_side else int_side
    return f"{sign}{body}"


def truncate_visible(text: str, max_width: int, *, suffix: str = "\u2026") -> str:
    """Truncate `text` ke `max_width` visible chars, preserve ANSI
    escape sequences (Fase 5.3).

    Gunakan suffix `â€¦` (Unicode) atau `..` (ASCII) untuk indikasi.
    """
    from .theme import visible_len
    if visible_len(text) <= max_width:
        return text
    # Walk char-by-char, skip ANSI runs, accumulate sampai max_width-len(suffix)
    keep = max(0, max_width - len(suffix))
    out_parts: list[str] = []
    open_codes: list[str] = []
    visible = 0
    i = 0
    while i < len(text) and visible < keep:
        ch = text[i]
        if ch == "\x1b" and i + 1 < len(text) and text[i + 1] == "[":
            j = i + 2
            while j < len(text) and not text[j].isalpha():
                j += 1
            esc = text[i:j + 1]
            out_parts.append(esc)
            # Track open color codes (basic): \x1b[0m closes, lainnya buka
            if esc.endswith("m"):
                if "0m" in esc or "[m" == esc[-2:]:
                    open_codes.clear()
                else:
                    open_codes.append(esc)
            i = j + 1
            continue
        out_parts.append(ch)
        visible += 1
        i += 1
    out_parts.append(suffix)
    if open_codes:
        out_parts.append("\x1b[0m")
    return "".join(out_parts)


def format_duration(total_seconds: float) -> str:
    seconds = max(0, int(total_seconds))
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


# ---------- Toast ---------------------------------------------------------


@dataclass
class Toast:
    title: str
    message: str
    role: str = "info"  # info | success | warning | danger
    expires_at: float = 0.0


@dataclass
class ToastQueue:
    """Antrian toast aktif. Renderer (cli) ambil yang masih hidup tiap
    redraw cycle. Bukan sticky â€” toast adalah tulisan biasa di stream
    log dengan border accent.
    """

    items: deque[Toast] = field(default_factory=lambda: deque(maxlen=8))

    def push(self, title: str, message: str, *, role: str = "info", duration: float = 3.0) -> None:
        self.items.append(
            Toast(title=title, message=message, role=role, expires_at=time.monotonic() + duration)
        )

    def drain_alive(self) -> list[Toast]:
        now = time.monotonic()
        alive = [t for t in self.items if t.expires_at > now]
        self.items = deque(alive, maxlen=self.items.maxlen)
        return alive


def render_toast(theme: Theme, toast: Toast, *, width: int = 56) -> list[str]:
    """Render toast jadi list[str] siap di-print. 3 baris."""
    g = theme.glyphs
    inner = width - 2
    title = pad_visible(f" {theme.glyphs.bullet} {toast.title} ", inner)
    body = pad_visible(f" {toast.message} ", inner)
    top = theme.c(g.tl + g.h * inner + g.tr, toast.role)
    mid_title = theme.c(g.v, toast.role) + theme.c(title, toast.role, bold=True) + theme.c(g.v, toast.role)
    mid_body = theme.c(g.v, toast.role) + body + theme.c(g.v, toast.role)
    bot = theme.c(g.bl + g.h * inner + g.br, toast.role)
    return [top, mid_title, mid_body, bot]


# ---------- Hotkey help overlay -------------------------------------------


def render_help_overlay(theme: Theme, lines: Iterable[str], *, title: str = "RUNTIME KEYS") -> list[str]:
    """Mini panel help. Render via box drawing sesuai theme."""
    text_lines = list(lines)
    inner = max([visible_len(line) for line in text_lines] + [visible_len(title) + 2]) + 4
    g = theme.glyphs
    out = [theme.c(g.tl + g.h * inner + g.tr, "accent")]
    title_padded = pad_visible(f" {title} ", inner)
    out.append(theme.c(g.v, "accent") + theme.c(title_padded, "accent", bold=True) + theme.c(g.v, "accent"))
    out.append(theme.c(g.t_right + g.h * inner + g.t_left, "dim"))
    for line in text_lines:
        body = pad_visible(f"  {line}", inner)
        out.append(theme.c(g.v, "accent") + body + theme.c(g.v, "accent"))
    out.append(theme.c(g.bl + g.h * inner + g.br, "accent"))
    return out


# ---------- Dry-run preview -----------------------------------------------


def render_dry_run(
    theme: Theme,
    rows: list[tuple[str, str]],
    *,
    title: str = "READY TO ENGAGE",
    hint: str = "ENTER = launch Â· E = edit Â· ESC = cancel",
    width: int = 60,
) -> list[str]:
    """Render panel konfirmasi sebelum launch."""
    g = theme.glyphs
    inner = width - 2
    out = [theme.c(g.tl + g.h * inner + g.tr, "primary")]
    out.append(
        theme.c(g.v, "primary")
        + theme.c(pad_visible(f" {title} ", inner), "primary", bold=True)
        + theme.c(g.v, "primary")
    )
    out.append(theme.c(g.t_right + g.h * inner + g.t_left, "dim"))
    label_w = max((len(k) for k, _ in rows), default=10)
    for key, value in rows:
        body = f"  {theme.c(key.ljust(label_w), 'dim')}  {theme.c(value, 'muted', bold=True)}"
        # Pad visible
        body = body + " " * max(0, inner - visible_len(body))
        out.append(theme.c(g.v, "primary") + body + theme.c(g.v, "primary"))
    out.append(theme.c(g.bl + g.h * inner + g.br, "primary"))
    out.append(theme.c(hint, "dim"))
    return out


# ---------- Sparkline -----------------------------------------------------


def sparkline(values: list[float], *, width: int = 10) -> str:
    """Mini sparkline 1-baris dari list float. Pakai blok 1/8 height
    Unicode kalau tersedia, fallback ASCII bracket gradient.

    Untuk dice, value bisa profit per-bet atau roll value 0-99.99.
    """
    if not values:
        return ""
    sample = values[-width:] if len(values) > width else values
    if len(sample) == 0:
        return ""
    lo = min(sample)
    hi = max(sample)
    span = hi - lo if hi > lo else 1.0
    blocks = "\u2581\u2582\u2583\u2584\u2585\u2586\u2587\u2588"  # â–â–‚â–ƒâ–„â–…â–†â–‡â–ˆ
    out = []
    for v in sample:
        idx = int(((v - lo) / span) * (len(blocks) - 1))
        idx = max(0, min(len(blocks) - 1, idx))
        out.append(blocks[idx])
    return "".join(out).ljust(width)


# ---------- Inline form field --------------------------------------------


def prompt_field_inline(
    theme: Theme,
    label: str,
    *,
    default: float | int | str,
    hint: str = "",
    rules: str = "",
    parse: str = "float",  # "float" | "int" | "str"
    min_value: float | None = None,
    max_value: float | None = None,
):
    """Form field input dengan visual hint + rules + validasi inline.

    Return value yang di-parse, atau `default` saat user tekan Enter
    kosong.
    """
    g = theme.glyphs
    while True:
        head = theme.c(label.upper(), "primary", bold=True)
        hint_text = theme.c(f"hint  : {hint}", "dim") if hint else ""
        rules_text = theme.c(f"rules : {rules}", "dim") if rules else ""
        default_str = (
            theme.c(f"[Enter={default}]", "dim") if default not in ("", None) else ""
        )
        if hint_text:
            print(f"  {head}  {default_str}")
            print(f"  {hint_text}")
            if rules_text:
                print(f"  {rules_text}")
        else:
            print(f"  {head}  {default_str}")
        prompt = f"  {theme.c(g.prompt, 'accent', bold=True)} "
        try:
            raw = input(prompt).strip()
        except (EOFError, KeyboardInterrupt):
            return default
        if raw == "":
            return default
        if parse == "str":
            return raw
        try:
            value = float(raw) if parse == "float" else int(raw)
        except ValueError:
            print(theme.c("  ! invalid number, try again.", "warning"))
            continue
        if min_value is not None and value < min_value:
            print(theme.c(f"  ! minimum {min_value}, try again.", "warning"))
            continue
        if max_value is not None and value > max_value:
            print(theme.c(f"  ! maximum {max_value}, try again.", "warning"))
            continue
        return value


# ---------- Snapshot row helpers (Fase 3.2) -------------------------------


def heat_role(profit_pct: float) -> tuple[str, bool]:
    """Return (role, bold) for snapshot delta% sesuai magnitude."""
    abs_v = abs(profit_pct)
    if profit_pct > 0:
        return ("success", abs_v >= 0.5)
    if profit_pct < 0:
        return ("danger", abs_v >= 0.5)
    return ("muted", False)


def win_lose_glyph(theme: Theme, win: bool | None) -> str:
    """Glyph distinct untuk color-blind: win=â–², lose=â–½, none=â—†."""
    g = theme.glyphs
    if win is True:
        return theme.c(g.up, "success", bold=True)
    if win is False:
        return theme.c(g.down, "danger", bold=True)
    return theme.c(g.flat, "dim")


# ---------- Color-blind audit (Fase 6.1) ----------------------------------


def _ansi_to_rgb(sgr: str) -> tuple[int, int, int]:
    """Approx RGB untuk SGR foreground 30-37, 90-97."""
    table = {
        "30": (0, 0, 0),
        "31": (170, 0, 0),
        "32": (0, 170, 0),
        "33": (170, 85, 0),
        "34": (0, 0, 170),
        "35": (170, 0, 170),
        "36": (0, 170, 170),
        "37": (170, 170, 170),
        "90": (85, 85, 85),
        "91": (255, 85, 85),
        "92": (85, 255, 85),
        "93": (255, 255, 85),
        "94": (85, 85, 255),
        "95": (255, 85, 255),
        "96": (85, 255, 255),
        "97": (255, 255, 255),
    }
    return table.get(sgr, (170, 170, 170))


def _luminance(rgb: tuple[int, int, int]) -> float:
    r, g, b = (c / 255 for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(fg_sgr: str, bg_sgr: str = "30") -> float:
    """WCAG-style luminance contrast ratio."""
    l1 = _luminance(_ansi_to_rgb(fg_sgr)) + 0.05
    l2 = _luminance(_ansi_to_rgb(bg_sgr)) + 0.05
    if l1 < l2:
        l1, l2 = l2, l1
    return l1 / l2

