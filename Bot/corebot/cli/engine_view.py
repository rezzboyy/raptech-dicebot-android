"""Engine display & live loop.

Diekstrak dari `cli/__init__.py` (Fase 2 perapihan, Step I-3).
Modul terbesar di paket `cli/` — berisi `run_engine` (main event loop)
plus rendering: `render_live_panel` (panel Live Session Stats yang
in-place update pakai diff-based rendering), `print_summary` (ringkasan
akhir sesi), plus utility `read_hotkey`, `is_engine_bet_log`,
`_maybe_profile_run`.

Fungsi legacy `snapshot_row` masih dipertahankan untuk tests dan
debug tool (`scripts/debug/preview_layout.py`), tapi tidak dipanggil
di run loop utama.

Pola akses theme: `_THEME = get_theme()` di awal tiap fungsi top-level.
Closure di dalam `run_engine` baca `_THEME` dari outer scope.

Public API (di-re-export oleh `cli/__init__.py`):
    - `read_hotkey()` -> str
    - `is_engine_bet_log(message)` -> bool
    - `snapshot_row(...)` -> str                      (legacy)
    - `render_live_panel(snapshot, ...)` -> list[str] (panel Live Session Stats)
    - `print_summary(snapshot, no_color)`
    - `_maybe_profile_run(profile_out, fn, *args, **kwargs)`
    - `run_engine(...)` -> SessionSnapshot | None
"""
from __future__ import annotations

import io
import queue
import sys
import threading
import time
from collections import deque as _deque

try:
    import msvcrt  # type: ignore
except Exception:
    msvcrt = None  # type: ignore

try:
    import termios as _termios
    import tty as _tty
    import select as _select
except Exception:
    _termios = None  # type: ignore
    _tty = None  # type: ignore
    _select = None  # type: ignore

from ..clients import BaseClient, currency_balance
from ..engine import BotEngine
from ..models import AccountSnapshot, SessionConfig, SessionProfile, SessionSnapshot
from ..ui import event_log as event_log_mod
from ..ui import widgets as widgets_mod
from ..ui.strings import S as STR
from ..ui.theme import pad_visible, terminal_caps, visible_len
from ._console import terminal_frame
from ._log import format_log_line
from ._state import get_theme, is_compact_mode
from ..ui.widgets import format_duration
from .layout import (
    compute_table_widths,
    responsive_width,
    table_align_for,
    table_header_row,
    table_row,
    table_sep,
)






def read_hotkey() -> str:
    """Read single keystroke non-blocking. Letters di-lower, simbol (+/-/?) tidak.

    Windows: pakai msvcrt.
    Linux/Mac: pakai termios raw mode + select untuk non-blocking.
    """
    if msvcrt is not None:
        # --- Windows path ---
        if not msvcrt.kbhit():
            return ""
        try:
            ch = msvcrt.getwch()
        except Exception:
            return ""
        # Drop arrow/function keys (prefix \x00 atau \xe0).
        if ch in ("\x00", "\xe0"):
            try:
                msvcrt.getwch()
            except Exception:
                pass
            return ""
        if ch.isalpha():
            return ch.lower()
        return ch

    if _termios is not None and _tty is not None and _select is not None:
        # --- Unix path: raw mode + select non-blocking ---
        fd = sys.stdin.fileno() if sys.stdin and sys.stdin.isatty() else -1
        if fd < 0:
            return ""
        old_settings = _termios.tcgetattr(fd)
        try:
            import os
            _tty.setraw(fd)
            ready, _, _ = _select.select([fd], [], [], 0)
            if not ready:
                return ""
            b = os.read(fd, 1)
            ch = b.decode("utf-8", errors="ignore")
        except Exception:
            return ""
        finally:
            _termios.tcsetattr(fd, _termios.TCSADRAIN, old_settings)
        # Drop escape sequences (arrow keys mulai dengan \x1b)
        if ch == "\x1b":
            return ""
        if ch.isalpha():
            return ch.lower()
        return ch

    return ""


def is_engine_bet_log(message: str) -> bool:
    return (
        "| size=" in message
        and "| threshold=" in message
        and "| result=" in message
    )


def snapshot_row(
    snapshot: SessionSnapshot,
    widths: list[int],
    no_color: bool = False,
    *,
    active_indices: list[int] | None = None,
    align: tuple[str, ...] | None = None,
    group_breaks: tuple[int, ...] = (),
    striped: bool = False,
) -> str:
    """Render satu baris stats per bet.

    Mendukung adaptive column visibility (Fase 1.2) lewat
    `active_indices` â€” list index kolom yang ditampilkan dari
    `_COL_KEYS`. Kalau None, fall back ke 7-kolom default legacy.
    """
    _THEME = get_theme()
    g = _THEME.glyphs

    if active_indices is None:
        active_indices = list(range(7))
    if align is None:
        align = ("right", "right", "right", "center", "center", "right", "right")
        align = tuple(align[i] for i in active_indices)

    # Build value per kolom (selalu hitung 7, pilih sesuai active)
    values_full: list[str] = [""] * 7

    # STEP â€” zero-pad subtle
    raw_step = str(snapshot.session_bets)
    step_w = widths[active_indices.index(0)] if 0 in active_indices else 6
    pad_len = max(0, step_w - len(raw_step))
    leading = _THEME.c("0" * pad_len, "dim")
    digits = _THEME.c(raw_step, "muted", bold=True)
    values_full[0] = leading + digits

    # BALANCE â€” smart precision (Fase 2.3) + decimal-aligned (Fase 2.1)
    bal_w = widths[active_indices.index(1)] if 1 in active_indices else 14
    bal_str = widgets_mod.smart_precision(snapshot.current_balance, max_chars=bal_w)
    values_full[1] = bal_str

    # DELTA% - heat indicator + optional IDR profit inline (build pribadi)
    role, bold = widgets_mod.heat_role(snapshot.profit_pct)
    arrow_char = (
        g.up if snapshot.profit_pct > 0
        else (g.down if snapshot.profit_pct < 0 else g.flat)
    )
    pct_str = f"{snapshot.profit_pct:+.4f}%"
    delta_w = widths[active_indices.index(2)] if 2 in active_indices else 11

    # IDR profit session — hanya kalau RAPTECH_IDR=1 dan currency supported.
    # Warna mengikuti sign profit (hijau/merah).
    import os as _os
    _idr_enabled = _os.getenv("RAPTECH_IDR") == "1"
    idr_profit_str = ""
    if _idr_enabled:
        try:
            from ..pricing import coin_to_idr, format_idr, is_supported
            if is_supported(snapshot.currency) and snapshot.session_profit != 0.0:
                v = coin_to_idr(snapshot.session_profit, snapshot.currency)
                if v is not None:
                    idr_profit_str = format_idr(v, sign=True)
        except Exception:
            pass

    # Susun konten kolom DELTA% dengan graceful fallback
    if idr_profit_str:
        full = f"{arrow_char} {pct_str}  {idr_profit_str}"
        if len(full) <= delta_w:
            raw_profit = full
        else:
            # Coba drop arrow
            compact = f"{pct_str}  {idr_profit_str}"
            if len(compact) <= delta_w:
                raw_profit = compact
            else:
                # Format IDR sangat kompak: k/jt/M suffix
                v = coin_to_idr(snapshot.session_profit, snapshot.currency) or 0
                sign = "+" if v > 0 else "-" if v < 0 else ""
                a = abs(v)
                if a >= 1_000_000_000:
                    idr_compact = f"{sign}Rp{a/1_000_000_000:.1f}M"
                elif a >= 1_000_000:
                    idr_compact = f"{sign}Rp{a/1_000_000:.1f}jt"
                elif a >= 1_000:
                    idr_compact = f"{sign}Rp{a/1_000:.0f}k"
                else:
                    idr_compact = f"{sign}Rp{a:.0f}"
                fallback = f"{pct_str} {idr_compact}"
                if len(fallback) <= delta_w:
                    raw_profit = fallback
                else:
                    raw_profit = pct_str  # last resort — pct only
    else:
        raw_profit = f"{arrow_char} {pct_str}"
        if len(raw_profit) > delta_w:
            raw_profit = pct_str

    values_full[2] = _THEME.c(raw_profit, role, bold=bold)

    # PARAM â€” side + chance, format ringkas (Fase 5.2)
    side_str = "HI" if snapshot.bethigh else "LO"
    param_raw = f"{side_str} {snapshot.chance:5.2f}".strip()
    values_full[3] = _THEME.by_win(param_raw, snapshot.last_bet_win)

    # RESULT â€” glyph distinct (Fase 5.1 roll value space-pad)
    glyph = (
        g.up if snapshot.last_bet_win is True
        else (g.down if snapshot.last_bet_win is False else g.flat)
    )
    result_w = widths[active_indices.index(4)] if 4 in active_indices else 10
    result_raw = f"{glyph} {snapshot.last_roll:5.2f}".strip()
    if len(result_raw) > result_w:
        result_raw = f"{snapshot.last_roll:5.2f}".strip()
    values_full[4] = _THEME.by_win(result_raw, snapshot.last_bet_win)

    # PEAKSIZE â€” smart precision
    peak_w = widths[active_indices.index(5)] if 5 in active_indices else 11
    values_full[5] = widgets_mod.smart_precision(snapshot.highest_bet, max_chars=peak_w)

    # SIZE â€” smart precision + win/lose color
    size_w = widths[active_indices.index(6)] if 6 in active_indices else 11
    size_str = widgets_mod.smart_precision(snapshot.last_bet_amount, max_chars=size_w)
    values_full[6] = _THEME.by_win(size_str, snapshot.last_bet_win)

    # Pilih hanya kolom aktif
    selected_values = [values_full[i] for i in active_indices]

    row = table_row(
        selected_values,
        widths,
        align=align,
        group_breaks=group_breaks,
        pad_inner=1,
    )

    # Fase 6.2: striped row (alternating dim) â€” saat striped=True dan
    # bet_n genap, wrap row dengan ANSI dim. Lebih ringan dari BG color.
    if striped and snapshot.session_bets % 2 == 0:
        return _THEME.c(row, "dim")
    return row


def print_summary(snapshot: SessionSnapshot | None, no_color: bool = False) -> None:
    if snapshot is None:
        return
    _THEME = get_theme()
    g = _THEME.glyphs
    width = 68

    # Fitur IDR hanya aktif di build pribadi (env RAPTECH_IDR=1)
    import os as _os
    _idr_enabled = _os.getenv("RAPTECH_IDR") == "1"
    currency = snapshot.currency or ""

    def idr_tag(amount: float, *, sign: bool = False) -> str:
        if not _idr_enabled:
            return ""
        try:
            from ..pricing import coin_to_idr, format_idr, is_supported
            if not is_supported(currency):
                return ""
            val = coin_to_idr(amount, currency)
            if val is None:
                return ""
            return f"  \u2248 {format_idr(val, sign=sign)}"
        except Exception:
            return ""

    print(_THEME.box_top(width))

    def line(label: str, value_text: str, value_role: str = "muted", *, bold: bool = True) -> None:
        lbl = _THEME.c(f"{label:<16}", "dim")
        val = _THEME.c(value_text, value_role, bold=bold)
        content = f" {lbl}{val}"
        print(_THEME.box_row(content, width))

    def line_with_idr(label: str, coin_amount: float, coin_text: str,
                      value_role: str = "muted", *, sign: bool = False) -> None:
        lbl = _THEME.c(f"{label:<16}", "dim")
        val = _THEME.c(coin_text, value_role, bold=True)
        idr = _THEME.c(idr_tag(coin_amount, sign=sign), "dim")
        content = f" {lbl}{val}{idr}"
        print(_THEME.box_row(content, width))

    title = _THEME.c("SESSION SUMMARY", "accent", bold=True)
    pad_total = max(0, width - 2 - visible_len(title))
    left = pad_total // 2
    right = pad_total - left
    v = _THEME.c(g.v, "dim")
    print(f"{v}{' ' * left}{title}{' ' * right}{v}")
    print(_THEME.box_mid(width))

    line("Strategy", snapshot.strategy_name, "primary")
    line("Currency", snapshot.currency, "accent")

    line_with_idr(
        "Start balance",
        snapshot.start_balance,
        f"{snapshot.start_balance:.8f}",
    )
    line_with_idr(
        "Final balance",
        snapshot.current_balance,
        f"{snapshot.current_balance:.8f}",
        "success" if snapshot.current_balance >= snapshot.start_balance else "danger",
    )

    profit_text = f"{snapshot.session_profit:+.8f} ({snapshot.profit_pct:+.4f}%)"
    profit_role = (
        "success" if snapshot.session_profit > 0
        else "danger" if snapshot.session_profit < 0
        else "muted"
    )
    line_with_idr(
        "Session profit",
        snapshot.session_profit,
        profit_text,
        profit_role,
        sign=True,
    )

    line("Cycles", f"{snapshot.session_bets:,}")
    wins_losses = (
        f"{_THEME.c(str(snapshot.session_wins), 'success', bold=True)}"
        f"{_THEME.c(' / ', 'dim')}"
        f"{_THEME.c(str(snapshot.session_losses), 'danger', bold=True)}"
    )
    lbl = _THEME.c(f"{'Positive/Neg':<16}", "dim")
    print(_THEME.box_row(f" {lbl}{wins_losses}", width))

    line_with_idr(
        "Volume",
        snapshot.session_wagered,
        f"{snapshot.session_wagered:.8f}",
    )
    line_with_idr(
        "Peak size",
        snapshot.highest_bet,
        f"{snapshot.highest_bet:.8f}",
    )
    line("Max neg streak", f"{snapshot.max_lose_streak}", "warning")
    line("Runtime", format_duration(snapshot.runtime_seconds), "primary")

    # Kecepatan bet / detik
    if snapshot.runtime_seconds > 0 and snapshot.session_bets > 0:
        bps = snapshot.session_bets / snapshot.runtime_seconds
        line("Speed", f"{bps:.2f} bets/sec", "info")

    print(_THEME.box_bottom(width))


# Tinggi panel live tetap (fixed) supaya cursor management stabil.
# Kalau ubah baris panel, sesuaikan konstanta ini.
LIVE_PANEL_HEIGHT = 14


def render_live_panel(
    snapshot: SessionSnapshot | None,
    *,
    width: int = 68,
    idr_enabled: bool = False,
) -> list[str]:
    """Render panel Live Session Stats. Return list baris dengan tinggi
    tetap = LIVE_PANEL_HEIGHT supaya redraw in-place bisa cursor up N konsisten.

    Panel selalu diisi (kalau snapshot None, pakai placeholder).
    """
    _THEME = get_theme()
    g = _THEME.glyphs

    # Fallback snapshot placeholder saat pre-first-bet
    if snapshot is None:
        cycle_str = "#0"
        strategy = "-"
        currency = "-"
        balance_str = "0.00000000"
        profit_str = "+0.0000% (+0.00000000)"
        wl_wins = 0
        wl_losses = 0
        volume_str = "0.00000000"
        peak_str = "0.00000000"
        max_neg = 0
        runtime_str = "00:00:00"
        speed_str = "0.00 bets/sec"
        last_bet_win: bool | None = None
        last_side = "-"
        last_chance = 0.0
        last_roll = 0.0
        currency_lower = ""
        _bal_raw = 0.0
        _profit_raw = 0.0
        _volume_raw = 0.0
        _peak_raw = 0.0
        _profit_pct = 0.0
    else:
        strategy = snapshot.strategy_name or "-"
        currency = snapshot.currency or "-"
        cycle_str = f"#{snapshot.session_bets:,}"
        _bal_raw = snapshot.current_balance
        balance_str = f"{_bal_raw:.8f}"
        _profit_raw = snapshot.session_profit
        _profit_pct = snapshot.profit_pct
        profit_str = f"{_profit_pct:+.4f}% ({_profit_raw:+.8f})"
        wl_wins = snapshot.session_wins
        wl_losses = snapshot.session_losses
        _volume_raw = snapshot.session_wagered
        volume_str = f"{_volume_raw:.8f}"
        _peak_raw = snapshot.highest_bet
        peak_str = f"{_peak_raw:.8f}"
        max_neg = snapshot.max_lose_streak
        runtime_str = format_duration(snapshot.runtime_seconds)
        if snapshot.runtime_seconds > 0 and snapshot.session_bets > 0:
            bps = snapshot.session_bets / snapshot.runtime_seconds
            speed_str = f"{bps:.2f} bets/sec"
        else:
            speed_str = "0.00 bets/sec"
        last_bet_win = snapshot.last_bet_win
        last_side = "HI" if snapshot.bethigh else "LO"
        last_chance = snapshot.chance
        last_roll = snapshot.last_roll
        currency_lower = currency.lower()

    # IDR helper
    def idr_suffix(amount: float, *, sign: bool = False) -> str:
        if not idr_enabled or snapshot is None:
            return ""
        try:
            from ..pricing import coin_to_idr, format_idr, is_supported
            if not is_supported(currency):
                return ""
            v = coin_to_idr(amount, currency)
            if v is None:
                return ""
            return f"  \u2248 {format_idr(v, sign=sign)}"
        except Exception:
            return ""

    lines: list[str] = []

    # Baris 1: box top
    lines.append(_THEME.box_top(width))

    # Baris 2: title
    title = _THEME.c("LIVE SESSION STATS", "accent", bold=True)
    pad_total = max(0, width - 2 - visible_len(title))
    left = pad_total // 2
    right = pad_total - left
    v = _THEME.c(g.v, "dim")
    lines.append(f"{v}{' ' * left}{title}{' ' * right}{v}")

    # Baris 3: divider
    lines.append(_THEME.box_mid(width))

    # Helper: bikin baris label + value dengan formatting box
    def _row(label: str, value: str, role: str = "muted", *, bold: bool = True) -> str:
        lbl = _THEME.c(f"{label:<16}", "dim")
        val = _THEME.c(value, role, bold=bold)
        return _THEME.box_row(f" {lbl}{val}", width)

    def _row_with_idr(label: str, coin_amount: float, coin_text: str,
                      role: str = "muted", *, sign: bool = False, bold: bool = True) -> str:
        lbl = _THEME.c(f"{label:<16}", "dim")
        val = _THEME.c(coin_text, role, bold=bold)
        idr = _THEME.c(idr_suffix(coin_amount, sign=sign), "dim")
        return _THEME.box_row(f" {lbl}{val}{idr}", width)

    # Baris 4: Cycle + Strategy (di baris yang sama)
    strat_label = _THEME.c(f"{'Cycle':<16}", "dim")
    cycle_val = _THEME.c(cycle_str, "primary", bold=True)
    strat_val = _THEME.c(f"  \u2192  {strategy} [{currency}]", "dim")
    lines.append(_THEME.box_row(f" {strat_label}{cycle_val}{strat_val}", width))

    # Baris 5: Balance
    lines.append(_row_with_idr("Balance", _bal_raw, balance_str, "success"))

    # Baris 6: Profit (warna sesuai sign)
    profit_role = (
        "success" if _profit_raw > 0
        else "danger" if _profit_raw < 0
        else "muted"
    )
    lines.append(_row_with_idr("Profit", _profit_raw, profit_str, profit_role, sign=True))

    # Baris 7: Wins/Losses (compound colored)
    wl_lbl = _THEME.c(f"{'Wins/Losses':<16}", "dim")
    wl_val = (
        f"{_THEME.c(str(wl_wins), 'success', bold=True)}"
        f"{_THEME.c(' / ', 'dim')}"
        f"{_THEME.c(str(wl_losses), 'danger', bold=True)}"
    )
    lines.append(_THEME.box_row(f" {wl_lbl}{wl_val}", width))

    # Baris 8: Volume
    lines.append(_row_with_idr("Volume", _volume_raw, volume_str))

    # Baris 9: Peak size
    lines.append(_row_with_idr("Peak size", _peak_raw, peak_str))

    # Baris 10: Max neg streak
    mns_role = "danger" if max_neg > 0 else "muted"
    lines.append(_row("Max neg streak", str(max_neg), mns_role))

    # Baris 11: Runtime + Speed
    rt_lbl = _THEME.c(f"{'Runtime':<16}", "dim")
    rt_val = _THEME.c(runtime_str, "primary", bold=True)
    sp_val = _THEME.c(f"  \u2022  {speed_str}", "info")
    lines.append(_THEME.box_row(f" {rt_lbl}{rt_val}{sp_val}", width))

    # Baris 12: Last outcome
    lr_lbl = _THEME.c(f"{'Last outcome':<16}", "dim")
    if last_bet_win is None:
        lr_val = _THEME.c("(no cycle yet)", "dim")
    else:
        status_word = "POSITIVE" if last_bet_win else "NEGATIVE"
        role = "success" if last_bet_win else "danger"
        outcome_label = _THEME.c(status_word, role, bold=True)
        glyph = g.up if last_bet_win else g.down
        outcome_glyph = _THEME.c(glyph, role, bold=True)
        lr_val = (
            f"{_THEME.c(last_side, 'accent', bold=True)} "
            f"{_THEME.c(f'{last_chance:.2f}', 'muted')} "
            f"{_THEME.c('\u2192', 'dim')} "
            f"{_THEME.c(f'{last_roll:.2f}', 'primary', bold=True)}  "
            f"{outcome_glyph} {outcome_label}"
        )
    lines.append(_THEME.box_row(f" {lr_lbl}{lr_val}", width))

    # Baris 13: box bottom
    lines.append(_THEME.box_bottom(width))

    # Baris 14: spacing (blank line) — supaya jarak ke footer
    lines.append("")

    # Sanity: pastikan tinggi EXACT LIVE_PANEL_HEIGHT
    while len(lines) < LIVE_PANEL_HEIGHT:
        lines.append("")
    if len(lines) > LIVE_PANEL_HEIGHT:
        lines = lines[:LIVE_PANEL_HEIGHT]
    return lines


def _maybe_profile_run(profile_out: str | None, fn, *args, **kwargs):
    """Bungkus `fn(*args, **kwargs)` dengan cProfile + dump ke path
    kalau `profile_out` di-set. Return value `fn` tetap diteruskan.
    Helper untuk Fase 0 (profiling baseline).
    """
    if not profile_out:
        return fn(*args, **kwargs)
    import cProfile
    import pstats
    _THEME = get_theme()
    pr = cProfile.Profile()
    try:
        pr.enable()
        return fn(*args, **kwargs)
    finally:
        pr.disable()
        try:
            pr.dump_stats(profile_out)
            stats = pstats.Stats(pr).sort_stats("cumulative")
            print(_THEME.c(f"[PROFILE] dumped to {profile_out}", "info"))
            stats.print_stats(20)
        except Exception as exc:
            print(_THEME.c(f"[PROFILE] dump failed: {exc}", "warning"))


def run_engine(
    client: BaseClient,
    config: SessionConfig,
    account: AccountSnapshot,
    profile: SessionProfile,
    *,
    sticky_footer: bool = True,
    quiet: bool = False,
    no_color: bool = False,
    confirm_quit: bool = True,
    toast_enabled: bool = True,
    json_log: bool = False,
    write_report: bool = True,
) -> SessionSnapshot | None:
    _THEME = get_theme()
    events: queue.Queue[tuple[str, object]] = queue.Queue()

    def emit(event_type: str, payload: object) -> None:
        events.put((event_type, payload))

    # === ENGINE VALIDATION ===
    if account.balance is None:
        raise ValueError("Error: Balance cannot be None.")
    if isinstance(account.balance, str) and str(account.balance).strip() == "":
        raise ValueError("Error: Balance cannot be empty string.")
    
    try:
        bal_val = float(account.balance)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Error: Balance '{account.balance}' is not a valid number. Reason: {exc}")

    if not account.currency or not account.currency.strip():
        raise ValueError("Error: Currency could not be detected.")

    is_test = (client.__class__.__name__ == "TestModeClient") or (getattr(client, "display_name", "") == "Test Mode")
    if not is_test:
        if hasattr(client, "_balance_known") and not getattr(client, "_balance_known", False):
            reason = getattr(client, "_last_error", None) or "Timeout/kesalahan koneksi WebSocket."
            raise ValueError(f"Error: Gagal memuat saldo dari server. Alasan: {reason}")
        if bal_val <= 0.0:
            raise ValueError(f"Error: Saldo akun ({bal_val} {account.currency}) bernilai 0 atau kurang. Pastikan akun Anda memiliki saldo di situs tersebut.")

    engine = BotEngine(client, emit)
    last_snapshot: SessionSnapshot | None = None
    state = "starting"
    stop_on_success = bool(profile.pause_on_win)
    started_at = time.monotonic()
    wall_started_at = time.time()

    # Fase 1.1+1.2: width adaptive sesuai terminal saat ini.
    _term_w = responsive_width(max_width=140, min_width=50, padding=2)
    table_widths, active_idx, group_breaks = compute_table_widths(_term_w)
    table_align = table_align_for(active_idx)
    # Fase 7.1: hitung available scroll rows. Kalau terlalu sempit
    # (terminal sangat pendek), force disable sticky_footer biar tidak
    # nyelip ke header.
    _term_h = terminal_caps(refresh=True).height
    HEADER_RESERVE = 5
    FOOTER_RESERVE = 2
    available_scroll_rows = _term_h - HEADER_RESERVE - FOOTER_RESERVE
    if available_scroll_rows < 4:
        sticky_footer = False
    quit_armed_at: float | None = None
    restart_armed_at: float | None = None

    # Runtime state untuk hotkey baru (Fase 5.1)
    log_every_steps = (1, 5, 10, 25, 100)
    try:
        log_every_idx = log_every_steps.index(int(profile.log_every))
    except ValueError:
        log_every_idx = 0
    current_log_every = profile.log_every

    show_help = False
    # Fase 6.1: bounded buffer untuk profit-over-time sparkline.
    profit_series: _deque[float] = _deque(maxlen=5000)

    # Toast queue (Fase 3.6)
    toasts = widgets_mod.ToastQueue() if toast_enabled else None

    # JSON event log (Fase 7.1)
    jlog = event_log_mod.JsonEventLog(enabled=bool(json_log))
    if jlog.enabled:
        jlog.open()
        jlog.emit(
            "session_start",
            {
                "site": getattr(client, "display_name", "?"),
                "strategy": config.strategy_name,
                "currency": config.currency,
                "interval_ms": profile.interval_ms,
                "max_bets": profile.max_bets,
                "pause_on_win": stop_on_success,
            },
        )

    def build_footer_lines() -> tuple[str, str]:
        elapsed = (
            last_snapshot.runtime_seconds
            if last_snapshot
            else max(0.0, time.monotonic() - started_at)
        )
        run_state = format_duration(elapsed)
        strategy_name = last_snapshot.strategy_name if last_snapshot else config.strategy_name
        currency = last_snapshot.currency if last_snapshot else config.currency
        volume = last_snapshot.session_wagered if last_snapshot else 0.0
        max_lose_streak = last_snapshot.max_lose_streak if last_snapshot else 0

        status_dot, status_label = widgets_mod.state_marker(
            _THEME, state, tick=time.monotonic()
        )
        sep = _THEME.c("  " + _THEME.glyphs.v + "  ", "dim")

        line1_parts = [
            f"{status_dot} {pad_visible(status_label, 9)}",
            _THEME.pill_fixed("STRAT", strategy_name, role="accent", width=22),
            _THEME.pill_fixed("CUR", currency, role="primary", width=10),
            _THEME.pill_fixed("INT", f"{int(profile.interval_ms)}ms", role="info", width=12),
            _THEME.pill_fixed("RUN", run_state, role="success", width=14),
            _THEME.pill_fixed("VOL", f"{volume:.8f}", role="info", width=18),
        ]
        line1 = sep.join(line1_parts)

        sos_role = "success" if stop_on_success else "dim"
        sos_value = _THEME.c("ON" if stop_on_success else "OFF", sos_role, bold=True)
        mls_role = "danger" if max_lose_streak > 0 else "dim"
        mls_value = _THEME.c(str(max_lose_streak), mls_role, bold=True)
        log_value = _THEME.c(f"x{current_log_every}", "info", bold=True)

        if is_compact_mode():
            keys_short = _THEME.c("KEYS CÂ·RÂ·SÂ·AÂ·LÂ·+Â·-Â·?Â·Q", "accent", bold=True)
            line2_parts = [
                f"{_THEME.c('SOS', 'dim', bold=True)} {sos_value}",
                f"{_THEME.c('MLS', 'dim', bold=True)} {mls_value}",
                f"{_THEME.c('LOG', 'dim', bold=True)} {log_value}",
                keys_short,
            ]
        else:
            keys_label = _THEME.c(STR.KEYS_LABEL, "accent", bold=True)
            keys_body = (
                f"{_THEME.c('[C]', 'accent', bold=True)}{STR.KEY_PAUSE} "
                f"{_THEME.c('[R]', 'accent', bold=True)}{STR.KEY_RESUME} "
                f"{_THEME.c('[S]', 'accent', bold=True)}{STR.KEY_RESTART} "
                f"{_THEME.c('[A]', 'accent', bold=True)}{STR.KEY_STOP_ON_WIN} "
                f"{_THEME.c('[?]', 'accent', bold=True)}{STR.KEY_HELP} "
                f"{_THEME.c('[Q]', 'accent', bold=True)}{STR.KEY_QUIT}"
            )
            line2_parts = [
                f"{_THEME.c('SOS', 'dim', bold=True)} {sos_value}",
                f"{_THEME.c('MLS', 'dim', bold=True)} {mls_value}",
                f"{_THEME.c('LOG', 'dim', bold=True)} {log_value}",
                f"{keys_label}  {keys_body}",
            ]
        line2 = sep.join(line2_parts)
        return line1, line2

    def build_kpi_strip() -> str:
        """KPI strip 1-baris di atas tabel (Fase 3.3)."""
        snap = last_snapshot
        if snap is None:
            return ""
        return widgets_mod.kpi_strip(
            _THEME,
            balance=snap.current_balance,
            currency=snap.currency,
            profit_pct=snap.profit_pct,
            runtime_seconds=snap.runtime_seconds,
            bets=snap.session_bets,
            wins=snap.session_wins,
            losses=snap.session_losses,
            width=responsive_width(max_width=120, min_width=60),
            session_profit=snap.session_profit,
        )

    # Panel + footer full redraw di-throttle konstan. Cycle counter bisa
    # skip beberapa (misal 1 -> 3 -> 5) — trade-off untuk speed.
    # Default 15 fps: bot ngebut sesuai interval_ms, panel cukup smooth,
    # RDP masih ringan. Override via env RAPTECH_REDRAW_FPS.
    import os as _os_r
    try:
        _target_fps = float(_os_r.getenv("RAPTECH_REDRAW_FPS", "15"))
        _target_fps = min(max(_target_fps, 1.0), 60.0)
    except (ValueError, TypeError):
        _target_fps = 15.0
    _redraw_min_interval_s = 1.0 / _target_fps

    _last_redraw_at = [0.0]

    # IDR flag (aktif hanya di build pribadi)
    import os as _os
    _panel_idr_enabled = _os.getenv("RAPTECH_IDR") == "1"
    _panel_width = 68

    # Pre-warm IDR cache + start background refresher supaya HTTP fetch
    # ke CoinGecko tidak pernah block hot path (render panel).
    # Cache TTL 60s → refresh tiap 45s di background daemon thread.
    _idr_refresher_stop = threading.Event() if _panel_idr_enabled else None
    if _panel_idr_enabled:
        try:
            from ..pricing import get_prices_idr, is_supported
            if is_supported(config.currency):
                _idr_symbol = config.currency.upper()
                # Warm-up sync (satu kali di awal, log_line "session armed"
                # sudah kover latency ~1 detik ini).
                get_prices_idr([_idr_symbol])

                def _idr_refresher_loop():
                    while not _idr_refresher_stop.wait(45.0):
                        try:
                            get_prices_idr([_idr_symbol])
                        except Exception:
                            pass

                _t = threading.Thread(
                    target=_idr_refresher_loop,
                    name="idr-refresher",
                    daemon=True,
                )
                _t.start()
        except Exception:
            pass

    # Tinggi total area sticky di bawah cursor:
    #   panel_height + footer_2_lines
    _sticky_height = LIVE_PANEL_HEIGHT + 2

    def _render_panel_lines() -> list[str]:
        return render_live_panel(
            last_snapshot,
            width=_panel_width,
            idr_enabled=_panel_idr_enabled,
        )

    # Diff-based rendering — cache baris terakhir yang ditulis supaya
    # cuma line yang berubah yang di-clear+rewrite. Panel yang statis
    # tidak disentuh sama sekali → no flicker "disko".
    _last_rendered_lines: list[str] = []

    def redraw_sticky_area(force: bool = False) -> None:
        """Redraw panel + footer dengan diff-based approach.
        Cursor di top of panel, navigate ke line yang berubah saja,
        clear + write line itu, lalu kembali ke top.
        """
        if not sticky_footer:
            return
        now = time.monotonic()
        if not force and (now - _last_redraw_at[0]) < _redraw_min_interval_s:
            return
        _last_redraw_at[0] = now

        panel_lines = _render_panel_lines()
        footer1, footer2 = build_footer_lines()
        new_all = list(panel_lines) + [footer1, footer2]

        buf = io.StringIO()
        current_row = 0  # relatif ke top of panel

        # Kalau ini render pertama (belum ada cache) → tulis semua sekaligus.
        if not _last_rendered_lines:
            for line in new_all:
                buf.write("\r\x1b[2K")
                buf.write(line)
                buf.write("\n")
            # Cursor sekarang di bawah panel — balik ke top
            buf.write(f"\x1b[{len(new_all)}A\r")
        else:
            # Diff mode: hanya line yang berubah yang di-update.
            for i, new_line in enumerate(new_all):
                old_line = _last_rendered_lines[i] if i < len(_last_rendered_lines) else ""
                if new_line == old_line:
                    continue
                # Navigate cursor ke row i
                delta = i - current_row
                if delta > 0:
                    buf.write(f"\x1b[{delta}B")
                elif delta < 0:
                    buf.write(f"\x1b[{-delta}A")
                # Clear line + tulis
                buf.write("\r\x1b[2K")
                buf.write(new_line)
                current_row = i
            # Kembali ke top of panel
            if current_row > 0:
                buf.write(f"\x1b[{current_row}A")
            buf.write("\r")

        _last_rendered_lines[:] = new_all
        sys.stdout.write(buf.getvalue())
        sys.stdout.flush()

    def write_live_line(line: str) -> None:
        """Tulis satu baris log (info/warn/error). Log line scroll di atas,
        panel & footer rewrite penuh karena scroll geser semua konten.
        """
        if not sticky_footer:
            print(line)
            return
        buf = io.StringIO()
        # Log line: clear current line + tulis + newline (scroll)
        buf.write("\x1b[2K\r")
        buf.write(line)
        buf.write("\n")
        # Panel + footer wajib full rewrite (scroll geser cache).
        # Tapi TIDAK pakai \x1b[J (clear-to-end) supaya minim flicker.
        panel_lines = _render_panel_lines()
        footer1, footer2 = build_footer_lines()
        new_all = list(panel_lines) + [footer1, footer2]
        for pline in new_all:
            buf.write("\r\x1b[2K")
            buf.write(pline)
            buf.write("\n")
        # Cursor kembali ke top of panel
        buf.write(f"\x1b[{len(new_all)}A\r")
        # Reset diff cache karena scroll geser konten
        _last_rendered_lines[:] = new_all
        sys.stdout.write(buf.getvalue())
        sys.stdout.flush()
        _last_redraw_at[0] = time.monotonic()

    def finish_footer() -> None:
        """Final render — flush panel + footer di posisi akhir. Cursor
        tidak restore supaya print_summary di bawahnya bisa jalan."""
        if not sticky_footer:
            return
        buf = io.StringIO()
        buf.write("\x1b[J")  # clear residu
        panel_lines = _render_panel_lines()
        for pline in panel_lines:
            buf.write(pline)
            buf.write("\n")
        footer1, footer2 = build_footer_lines()
        buf.write(footer1)
        buf.write("\n")
        buf.write(footer2)
        buf.write("\n")
        sys.stdout.write(buf.getvalue())
        sys.stdout.flush()

    def render_event_separator(label: str, *, role: str = "accent") -> str:
        """Fase 6.3: separator inline saat event spesial."""
        total_w = sum(table_widths) + len(table_widths) + 1
        g = _THEME.glyphs
        label_text = f" {label} "
        label_visible = visible_len(label_text)
        side_w = max(2, (total_w - label_visible) // 2)
        line = (g.h * side_w) + label_text + (g.h * (total_w - side_w - label_visible))
        return _THEME.c(line, role, bold=True)

    def render_event_separator_safe(label: str, *, role: str = "accent") -> str:
        try:
            return render_event_separator(label, role=role)
        except Exception:
            return _THEME.c(f"-- {label} --", role, bold=True)

    engine.start(config, account)
    engine.set_pause_on_win(stop_on_success)
    # Initial render: log "session armed" + panel placeholder + footer.
    # Cursor akan berada di top-of-panel untuk redraw berikutnya.
    with terminal_frame() as _f:
        _f.write(format_log_line("info", STR.SESSION_ARMED) + "\n")
        panel_lines = _render_panel_lines()
        for pline in panel_lines:
            _f.write(pline + "\n")
        footer1, footer2 = build_footer_lines()
        _f.write(footer1 + "\n")
        _f.write(footer2 + "\n")
        if sticky_footer:
            _f.write(f"\x1b[{_sticky_height}A")

    def drain_until_stopped() -> None:
        """Drain events sampai engine benar-benar berhenti."""
        nonlocal state, last_snapshot
        while state != "stopped":
            try:
                event_type, payload = events.get(timeout=0.5)
            except queue.Empty:
                if not engine.is_alive():
                    state = "stopped"
                    break
                continue
            if event_type == "state":
                state = str(payload)
            elif event_type == "stats" and isinstance(payload, SessionSnapshot):
                last_snapshot = payload
                if payload.state == "stopped":
                    state = "stopped"
            elif event_type == "log":
                data = (
                    payload if isinstance(payload, dict)
                    else {"level": "info", "message": str(payload)}
                )
                level = str(data.get("level", "info")).lower()
                message = str(data.get("message", ""))
                if not is_engine_bet_log(message):
                    write_live_line(format_log_line(level, message))

    def perform_restart() -> bool:
        """Stop engine, refresh balance, lalu start ulang dengan config sama.

        Mengembalikan True kalau berhasil di-restart, False kalau gagal.
        """
        nonlocal engine, state, last_snapshot, started_at
        write_live_line(format_log_line("warn", STR.LOG_RESTART_REQUESTED))
        engine.stop()
        drain_until_stopped()
        engine.wait(timeout=3.0)

        refreshed_account = account
        try:
            from ..clients import balance_list_from_response
            refreshed_balances = balance_list_from_response(client.balances())
            refreshed_balance = currency_balance(refreshed_balances, config.currency)
            refreshed_account.balance = refreshed_balance
            refreshed_account.balance_list = refreshed_balances
        except Exception as exc:
            write_live_line(format_log_line(
                "error",
                f"Balance refresh failed: {exc}. Using last known balance.",
            ))

        engine = BotEngine(client, emit)
        last_snapshot = None
        started_at = time.monotonic()
        state = "starting"
        try:
            engine.start(config, refreshed_account)
            engine.set_pause_on_win(stop_on_success)
        except Exception as exc:
            write_live_line(format_log_line("error", f"Restart failed: {exc}"))
            return False
        write_live_line(format_log_line("success", STR.SESSION_RESTARTED))
        return True

    try:
        while True:
            key = read_hotkey()
            now_t = time.monotonic()
            if quit_armed_at is not None:
                if key and key != "q":
                    quit_armed_at = None
                elif (now_t - quit_armed_at) > 2.0:
                    quit_armed_at = None
            if restart_armed_at is not None:
                if key and key != "s":
                    restart_armed_at = None
                elif (now_t - restart_armed_at) > 2.0:
                    restart_armed_at = None
            if key == "c":
                engine.pause()
            elif key == "r":
                engine.resume()
            elif key == "s":
                if confirm_quit and (
                    restart_armed_at is None or (now_t - restart_armed_at) > 2.0
                ):
                    restart_armed_at = now_t
                    write_live_line(format_log_line(
                        "warn",
                        STR.confirm_restart_hint(2),
                    ))
                else:
                    restart_armed_at = None
                    if not perform_restart():
                        break
            elif key == "a":
                stop_on_success = not stop_on_success
                engine.set_pause_on_win(stop_on_success)
                write_live_line(format_log_line(
                    "info",
                    f"Stop on success: {'ON' if stop_on_success else 'OFF'}",
                ))
            elif key == "?":
                show_help = not show_help
                if show_help:
                    for line in widgets_mod.render_help_overlay(
                        _THEME, STR.HOTKEY_HELP_LINES, title=STR.HOTKEY_HELP_TITLE
                    ):
                        write_live_line(line)
                else:
                    write_live_line(format_log_line("info", STR.LOG_HELP_DISMISSED))
            elif key == "l":
                log_every_idx = (log_every_idx + 1) % len(log_every_steps)
                current_log_every = log_every_steps[log_every_idx]
                write_live_line(format_log_line(
                    "info", f"log_every set to {current_log_every}.",
                ))
            elif key in ("+", "="):
                profile.interval_ms = max(0, int(profile.interval_ms) + 50)
                write_live_line(format_log_line(
                    "info", f"interval_ms = {profile.interval_ms}ms",
                ))
            elif key == "-":
                profile.interval_ms = max(0, int(profile.interval_ms) - 50)
                write_live_line(format_log_line(
                    "info", f"interval_ms = {profile.interval_ms}ms",
                ))
            elif key == "q":
                if confirm_quit:
                    if quit_armed_at is not None and (now_t - quit_armed_at) <= 2.0:
                        engine.stop()
                        quit_armed_at = None
                    else:
                        quit_armed_at = now_t
                        write_live_line(format_log_line(
                            "warn",
                            STR.confirm_quit_hint(2),
                        ))
                else:
                    engine.stop()

            try:
                event_type, payload = events.get(timeout=0.12)
            except queue.Empty:
                if state == "stopped":
                    break
                if not engine.is_alive() and state != "stopped":
                    state = "stopped"
                    write_live_line(format_log_line("error", STR.LOG_STOPPED_UNEXPECTEDLY))
                    break
                continue

            if event_type == "state":
                state = str(payload)
                if jlog.enabled:
                    jlog.emit("state", {"state": state})
            elif event_type == "stats" and isinstance(payload, SessionSnapshot):
                last_snapshot = payload
                profit_series.append(payload.profit_pct)
                if payload.state == "stopped":
                    state = "stopped"
                # Live panel — redraw setiap bet (throttled ~10 fps di dalam).
                if not quiet:
                    redraw_sticky_area()
                if jlog.enabled and payload.session_bets:
                    jlog.emit(
                        "bet",
                        {
                            "n": payload.session_bets,
                            "balance": payload.current_balance,
                            "profit_pct": payload.profit_pct,
                            "win": payload.last_bet_win,
                            "size": payload.last_bet_amount,
                            "roll": payload.last_roll,
                            "chance": payload.chance,
                        },
                    )
                if (
                    stop_on_success
                    and payload.last_bet_win is True
                    and state in {"running", "starting"}
                ):
                    engine.stop()
            elif event_type == "log":
                data = (
                    payload if isinstance(payload, dict)
                    else {"level": "info", "message": str(payload)}
                )
                level = str(data.get("level", "info")).lower()
                message = str(data.get("message", ""))
                if is_engine_bet_log(message):
                    continue
                if toasts is not None:
                    msg_lower = message.lower()
                    if "auto-switch" in msg_lower:
                        toasts.push(STR.TOAST_STRATEGY_SWITCH, message[:80], role="accent", duration=3.0)
                        write_live_line(render_event_separator_safe(
                            STR.TOAST_STRATEGY_SWITCH, role="accent"))
                    elif "flat allocation mode enabled" in msg_lower:
                        toasts.push(STR.TOAST_FLATBET_ON, message[:80], role="info", duration=3.0)
                        write_live_line(render_event_separator_safe(
                            STR.TOAST_FLATBET_ON, role="info"))
                    elif "flat allocation mode completed" in msg_lower:
                        toasts.push(STR.TOAST_FLATBET_OFF, message[:80], role="muted", duration=2.0)
                        write_live_line(render_event_separator_safe(
                            STR.TOAST_FLATBET_OFF, role="muted"))
                    elif "target growth reached" in msg_lower:
                        toasts.push(STR.TOAST_TAKE_PROFIT, message[:80], role="success", duration=4.0)
                        write_live_line(render_event_separator_safe(
                            STR.TOAST_TAKE_PROFIT, role="success"))
                if toasts is not None:
                    for tst in toasts.drain_alive():
                        if tst.expires_at - time.monotonic() > 2.5:
                            for ln in widgets_mod.render_toast(_THEME, tst, width=58):
                                write_live_line(ln)
                if jlog.enabled:
                    jlog.emit("log", {"message": message}, level=level)
                write_live_line(format_log_line(level, message))

            if state == "stopped" and events.empty():
                break
    except KeyboardInterrupt:
        write_live_line(format_log_line("warn", STR.STOP_REQUESTED))
        engine.stop()
        while state != "stopped":
            try:
                event_type, payload = events.get(timeout=0.5)
            except queue.Empty:
                if not engine.is_alive():
                    break
                continue
            if event_type == "state":
                state = str(payload)
            elif event_type == "stats" and isinstance(payload, SessionSnapshot):
                last_snapshot = payload
            elif event_type == "log":
                data = (
                    payload if isinstance(payload, dict)
                    else {"level": "info", "message": str(payload)}
                )
                level = str(data.get("level", "info")).lower()
                message = str(data.get("message", ""))
                if not is_engine_bet_log(message):
                    write_live_line(format_log_line(level, message))
    except Exception as exc:
        # Fase 8.1: tangkap SEMUA exception di main loop supaya bot
        # TIDAK force-close. Engine di-stop gracefully, error di-log,
        # user bisa lihat pesan lalu kembali ke menu utama.
        import traceback
        engine.stop()
        # Drain remaining events biar tidak stuck
        drain_deadline = time.monotonic() + 2.0
        while time.monotonic() < drain_deadline:
            try:
                event_type, payload = events.get(timeout=0.3)
            except queue.Empty:
                if not engine.is_alive():
                    break
                continue
            if event_type == "stats" and isinstance(payload, SessionSnapshot):
                last_snapshot = payload
            elif event_type == "state":
                state = str(payload)
        # Tampilkan traceback lengkap ke user
        tb_lines = traceback.format_exc().strip().split("\n")
        for line in tb_lines:
            write_live_line(format_log_line("error", f"TRACEBACK | {line}"))
        write_live_line(format_log_line("error", STR.LOG_ENGINE_CRASH))
        # Pastikan footer ter-render
        if not sticky_footer:
            for _ in range(2):
                print("")

    engine.wait(timeout=3.0)
    # Stop background IDR refresher (kalau ada)
    if _idr_refresher_stop is not None:
        _idr_refresher_stop.set()
    finish_footer()
    print("")
    print_summary(last_snapshot, no_color)

    # Tulis report akhir (Fase 7.2) â€” dibungkus try supaya tidak ganggu UX
    try:
        report_path = event_log_mod.write_session_report(
            snapshot=last_snapshot,
            profit_series=profit_series,
            started_at=wall_started_at,
            ended_at=time.time(),
            enabled=write_report,
        )
        if report_path is not None:
            print(_THEME.c(f"Report saved to {report_path}", "dim"))
    except Exception:
        pass

    if jlog.enabled:
        jlog.emit(
            "session_end",
            {"bets": last_snapshot.session_bets if last_snapshot else 0},
        )
        jlog.close()

    return last_snapshot


