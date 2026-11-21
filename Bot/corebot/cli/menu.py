"""Menu interaktif & wizard untuk CLI.

Diekstrak dari `cli/__init__.py` (Fase 2 perapihan, Step H).

Public API (di-re-export oleh `cli/__init__.py`):
    - `print_main_menu`
    - `fmt_pct`
    - `profile_summary`
    - `show_dry_run_preview`
    - `quick_start_wizard`
    - `ui_store_default`
    - `configure_runtime_settings`
    - `print_strategy_block`
    - `print_account_status`
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable

try:
    from colorama import Fore  # type: ignore
except Exception:
    class Fore:  # type: ignore[no-redef]
        CYAN = "\x1b[36m"

from ..clients import (
    COOKIE_BASED_SITES,
    JWT_BASED_SITES,
    get_client_class,
    site_metadata,
)
from ..config import DEFAULT_SITE, lua_dir
from ..models import AccountSnapshot, SessionProfile
from ..storage import get_profile_entry, profile_to_dict, sanitize_session_profile
from ..ui import widgets as widgets_mod
from ..ui.strategy_meta import parse_strategy_meta
from ..ui.strings import S as STR
from ..ui.theme import terminal_caps, visible_len
from ._console import clear_screen, section
from ..ui.widgets import format_duration
from .layout import responsive_width
from ._state import get_theme
from .prompts import prompt_float_default, prompt_select


APP_NAME = "RAPTECH ENGINE"
MIN_BET = 0.00000001
TEST_MODE_SITE = "testmode"






def _site_requires_token(site: str) -> bool:
    """Sinkron dengan `cli/__init__.py:site_requires_token`."""
    try:
        client_cls = get_client_class(site)
    except Exception:
        return True
    return bool(getattr(client_cls, "requires_token", True))


def _is_test_mode(site: str) -> bool:
    return (site or "").lower() == TEST_MODE_SITE


def _credential_label(site: str) -> str:
    """Sinkron dengan `cli/__init__.py:credential_label`."""
    if not _site_requires_token(site):
        return "Test Mode"
    if site.lower() in JWT_BASED_SITES:
        return "Auth Token"
    if site.lower() in COOKIE_BASED_SITES:
        return "Cookie"
    return "Web API"


def print_main_menu(
    connected: bool,
    account: AccountSnapshot | None,
    no_color: bool = False,
    *,
    site: str = DEFAULT_SITE,
) -> int:
    """Render menu utama dengan grouping section.

    Section CONNECTION  : Select Site, Web API / Test Balance, Refresh Balance
    Section ENGINE      : Start Engine, Account Overview, Check Script
    Section EXIT        : Exit

    Width adaptif terhadap lebar terminal aktif.
    """
    show_error = False
    width = responsive_width(max_width=78, min_width=58)
    theme = get_theme()
    g = theme.glyphs
    border_top = theme.box_top(width)
    border_mid = theme.box_mid(width)
    border_bot = theme.box_bottom(width)

    def row(text: str = "") -> str:
        content = " " + text
        return theme.box_row(content, width)

    def center(text: str) -> str:
        styled = theme.c(text, "accent", bold=True)
        pad_total = max(0, width - 2 - visible_len(styled))
        left = pad_total // 2
        right = pad_total - left
        v = theme.c(g.v, "dim")
        return f"{v}{' ' * left}{styled}{' ' * right}{v}"

    def section_header(label: str) -> str:
        accent = theme.c(label.upper(), "accent", bold=True)
        bar = theme.c(g.accent_bar, "accent", bold=True)
        return row(f"{bar} {accent}")

    while True:
        clear_screen()
        site_label = site_metadata(site).display_name
        credential_name = _credential_label(site)
        status_dot = theme.status_dot(connected)
        api_status = "READY" if connected and not _site_requires_token(site) else (
            "CONNECTED" if connected else "EMPTY"
        )
        api_label = theme.c(api_status, "success" if connected else "dim", bold=True)
        site_styled = theme.c(site_label, "accent", bold=True)
        user = account.username if account and account.username else "-"
        active = "-"
        if account and account.currency:
            active = f"{account.balance:.8f} {account.currency}"
        muted_label = lambda s: theme.c(s, "dim")
        action_2_label = STR.MENU_SET_BALANCE if _is_test_mode(site) else STR.MENU_PASTE_API
        lines = [
            border_top,
            center(APP_NAME),
            border_mid,
            row(f"   {muted_label(STR.SITE_LABEL)}  {site_styled}"),
            row(f"{status_dot}  {muted_label(credential_name)}  {api_label}"),
            row(f"   {muted_label(STR.ACCOUNT_LABEL)}  {user}"),
            row(f"   {muted_label(STR.ACTIVE_LABEL)}  {active}"),
            border_mid,
            section_header(STR.MENU_SECTION_QUICK_LAUNCH),
            row(f" {theme.c('0', 'accent', bold=True)}  {STR.MENU_QUICK_START}"),
            border_mid,
            section_header(STR.MENU_SECTION_CONNECTION),
            row(f" {theme.c('1', 'accent', bold=True)}  {STR.MENU_SELECT_SITE}"),
            row(f" {theme.c('2', 'accent', bold=True)}  {action_2_label}"),
            row(f" {theme.c('5', 'accent', bold=True)}  {STR.MENU_REFRESH_BALANCE}"),
            row(f" {theme.c('13', 'accent', bold=True)} {STR.MENU_SET_PROXY}"),
        ]
        # Menu Multi-Account Manager — muncul untuk semua site yang butuh token
        # (kecuali test mode). Berlaku untuk Wolfbet, Pasino, Nuts, Betfury, dll.
        if _site_requires_token(site) and not _is_test_mode(site):
            lines.append(row(f" {theme.c('12', 'accent', bold=True)} {STR.MENU_ACCOUNT_MANAGER}"))
        lines += [
            border_mid,
            section_header(STR.MENU_SECTION_ENGINE),
            row(f" {theme.c('3', 'accent', bold=True)}  {STR.MENU_START_ENGINE}"),
            row(f" {theme.c('4', 'accent', bold=True)}  {STR.MENU_ACCOUNT_OVERVIEW}"),
            row(f" {theme.c('6', 'accent', bold=True)}  {STR.MENU_CHECK_SCRIPT}"),
        ]
        # Menu Wallet & Token khusus Pasino — hanya tampil kalau site = pasino
        # (Account Manager sudah ada di section Connection untuk semua site).
        if site.lower() == "pasino":
            lines.append(border_mid)
            lines.append(section_header("Wallet"))
            lines.append(row(f" {theme.c('8', 'accent', bold=True)}  {STR.MENU_DEPOSIT}"))
            lines.append(row(f" {theme.c('9', 'accent', bold=True)}  {STR.MENU_WITHDRAW}"))
            lines.append(border_mid)
            lines.append(section_header("Token"))
            lines.append(row(f" {theme.c('10', 'accent', bold=True)} {STR.MENU_TOKEN_STATUS}"))
            lines.append(row(f" {theme.c('11', 'accent', bold=True)} {STR.MENU_REFRESH_TOKEN}"))
        # Menu Account Settings khusus Wolfbet — Change Email.
        if site.lower() == "wolfbet":
            lines.append(border_mid)
            lines.append(section_header("Account Settings"))
            lines.append(row(f" {theme.c('14', 'accent', bold=True)} {STR.MENU_CHANGE_EMAIL}"))
        lines += [
            border_mid,
            row(f" {theme.c('7', 'accent', bold=True)}  {STR.MENU_SECTION_EXIT}"),
            border_bot,
        ]
        for line in lines:
            print(line)
        prompt_text = theme.c(f"{g.prompt} {STR.MENU_PROMPT} ", "accent", bold=True)
        if show_error:
            print(theme.c("Please enter a number.", "warning"))
        raw = input(prompt_text).strip()
        clear_screen()
        if raw.isdigit():
            return int(raw)
        show_error = True


def fmt_pct(value: float) -> str:
    return "OFF" if value <= 0 else f"{value:.4f}%"


def profile_summary(profile: SessionProfile, currency: str) -> list[str]:
    auto_break = profile.run_break_seconds > 0 and profile.break_seconds > 0
    flatbet = (
        profile.flatbet_trigger_pct > 0
        and profile.flatbet_minutes > 0
        and profile.flatbet_amount > 0
    )
    return [
        (
            f"Interval   : {profile.interval_ms} ms | "
            f"MaxCycles  : {profile.max_bets if profile.max_bets else 'OFF'} | "
            f"LogEvery   : {profile.log_every}"
        ),
        (
            f"AutoSwitch : {fmt_pct(profile.auto_switch_profit_pct)} | "
            f"Target     : {fmt_pct(profile.take_profit_pct)} | "
            f"StopSuccess: {'ON' if profile.pause_on_win else 'OFF'}"
        ),
        (
            f"AutoBreak  : {'ON' if auto_break else 'OFF'} "
            f"(run={profile.run_break_seconds:.2f}s, break={profile.break_seconds:.2f}s, resetseed=ON)"
        ),
        (
            f"FlatAlloc  : {'ON' if flatbet else 'OFF'} "
            f"(trigger={fmt_pct(profile.flatbet_trigger_pct)}, "
            f"dur={profile.flatbet_minutes:.2f}m, amt={profile.flatbet_amount:.8f} {currency})"
        ),
    ]


def show_dry_run_preview(
    *,
    site: str,
    strategy_name: str,
    currency: str,
    profile: SessionProfile,
) -> str:
    """Render dry-run preview panel sebelum launch (Fase 5.2).

    Return key input dari user: '' (Enter=launch), 'e' (edit), atau
    apa pun yang dianggap cancel.
    """
    rows = [
        ("Site", site_metadata(site).display_name),
        ("Strategy", strategy_name),
        ("Currency", currency.upper()),
        ("Interval", f"{int(profile.interval_ms)} ms"),
        ("Take profit", f"{profile.take_profit_pct:.4f} %" if profile.take_profit_pct else "off"),
        ("Max bets", f"{profile.max_bets:,}" if profile.max_bets else "unlimited"),
        ("Stop on win", "ON" if profile.pause_on_win else "OFF"),
        (
            "Auto-switch",
            f"{profile.auto_switch_profit_pct:.4f}%" if profile.auto_switch_profit_pct else "off",
        ),
    ]
    width = responsive_width(max_width=66, min_width=50)
    panel = widgets_mod.render_dry_run(
        get_theme(), rows, title=STR.DRY_RUN_TITLE, hint=STR.DRY_RUN_HINT, width=width
    )
    for ln in panel:
        print(ln)
    try:
        raw = input("  ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return "cancel"
    if raw == "":
        # User pilih launch - clear layar supaya engine live panel
        # tidak berdampingan dengan preview panel.
        clear_screen()
        return ""
    if raw in ("e", "edit"):
        return "e"
    return "cancel"


def ui_store_default(settings_store: dict) -> str:
    return str(settings_store.get("ui", {}).get("last_site") or "")


def quick_start_wizard(
    *,
    settings_store: dict,
    strategy_dir: Path,
    strategies: list[str],
    no_color: bool,
) -> tuple[str, str, SessionProfile, str] | None:
    """Wizard 4 step untuk new user (Fase 4.3).

    Return (site, strategy_name, profile, currency_or_empty) atau None
    bila user cancel. Currency final di-resolve setelah account
    connected; wizard hanya capture site + strategy + profile defaults.
    """
    # Lazy import untuk hindari import cycle dengan __init__ (yang
    # memanggil quick_start_wizard).
    from .prompts import prompt_select_site

    theme = get_theme()
    section("QUICK START", Fore.CYAN, no_color)
    print(theme.c("4 langkah singkat untuk siap nge-bot.", "dim"))
    print()

    # Step 1: site
    site = prompt_select_site(
        ui_store_default(settings_store) or DEFAULT_SITE, no_color=no_color
    )

    # Step 2: strategy
    print(theme.section("Step 2 â€” Strategy", role="primary"))
    print_strategy_block(strategies, no_color)
    last_strategy = str(settings_store.get("ui", {}).get("last_strategy") or "")
    if last_strategy not in strategies:
        last_strategy = strategies[0]
    strategy_name = prompt_select(
        strategies,
        "Pilih strategy:",
        last_strategy,
        show_list=False,
        no_color=no_color,
    )

    # Step 3: profile defaults â€” ambil entry tersimpan, atau default
    print(theme.section("Step 3 â€” Profile", role="primary"))
    currency_default = (settings_store.get("ui", {}).get("last_currency") or "BTC").upper()
    entry = get_profile_entry(settings_store, site, strategy_name, currency_default)
    profile = sanitize_session_profile(entry)
    for line in profile_summary(profile, currency_default):
        print(line)
    print(theme.c("Tekan Enter untuk pakai default, atau ketik 'edit' untuk ubah.", "dim"))
    try:
        raw = input(theme.c("  > ", "accent", bold=True)).strip().lower()
    except (EOFError, KeyboardInterrupt):
        return None
    if raw in ("e", "edit"):
        new_profile = configure_runtime_settings(
            strategy_name,
            currency_default,
            profile,
            lambda p: None,
            no_color=no_color,
        )
        if new_profile is not None:
            profile = new_profile

    # Step 4: konfirmasi via dry-run preview
    print(theme.section("Step 4 â€” Confirm", role="primary"))
    decision = show_dry_run_preview(
        site=site,
        strategy_name=strategy_name,
        currency=currency_default,
        profile=profile,
    )
    if decision == "cancel":
        return None
    return (site, strategy_name, profile, currency_default)


def configure_runtime_settings(
    strategy_name: str,
    currency: str,
    profile: SessionProfile,
    save_profile: Callable[[SessionProfile], None],
    *,
    no_color: bool = False,
) -> SessionProfile | None:
    profile = sanitize_session_profile(profile_to_dict(profile))
    save_profile(profile)
    while True:
        section("RUNTIME SETTINGS", Fore.CYAN, no_color)
        print(f"Strategy   : {strategy_name}")
        print(f"Currency   : {currency}")
        print("")
        for line in profile_summary(profile, currency):
            print(line)
        print("")
        picked = prompt_select(
            [
                "Start Session",
                "Set Interval (ms)",
                "Set Max Cycles",
                "Set Log Every",
                "Toggle Stop On Success",
                "Set Auto Switch Strategy Profit %",
                "Set Target Profit %",
                "Set Auto Break Run Seconds",
                "Set Auto Break Break Seconds",
                "Set Flat Allocation Trigger Profit %",
                "Set Flat Allocation Duration Minutes",
                "Set Flat Allocation Amount",
                "Back to Main Menu",
            ],
            "Runtime settings menu:",
            no_color=no_color,
        )
        if picked == "Start Session":
            save_profile(profile)
            return sanitize_session_profile(profile_to_dict(profile))
        if picked == "Back to Main Menu":
            save_profile(profile)
            return None
        if picked == "Set Interval (ms)":
            profile.interval_ms = int(prompt_float_default("Interval ms", profile.interval_ms, 0.0))
        elif picked == "Set Max Cycles":
            profile.max_bets = int(prompt_float_default("Max cycles (0=unlimited)", profile.max_bets, 0.0))
        elif picked == "Set Log Every":
            profile.log_every = max(1, int(prompt_float_default("Log every", profile.log_every, 1.0)))
        elif picked == "Toggle Stop On Success":
            profile.pause_on_win = not profile.pause_on_win
            clear_screen()
        elif picked == "Set Auto Switch Strategy Profit %":
            profile.auto_switch_profit_pct = prompt_float_default(
                "Auto switch strategy profit % (0=off)",
                profile.auto_switch_profit_pct,
                0.0,
            )
        elif picked == "Set Target Profit %":
            profile.take_profit_pct = prompt_float_default(
                "Target profit % (0=off)", profile.take_profit_pct, 0.0
            )
        elif picked == "Set Auto Break Run Seconds":
            profile.run_break_seconds = prompt_float_default(
                "Auto break run seconds (0=off)",
                profile.run_break_seconds,
                0.0,
            )
        elif picked == "Set Auto Break Break Seconds":
            profile.break_seconds = prompt_float_default(
                "Auto break break seconds (0=off)",
                profile.break_seconds,
                0.0,
            )
        elif picked == "Set Flat Allocation Trigger Profit %":
            profile.flatbet_trigger_pct = prompt_float_default(
                "Flat allocation trigger profit % (0=off)",
                profile.flatbet_trigger_pct,
                0.0,
            )
        elif picked == "Set Flat Allocation Duration Minutes":
            profile.flatbet_minutes = prompt_float_default(
                "Flat allocation duration minutes (0=off)",
                profile.flatbet_minutes,
                0.0,
            )
        elif picked == "Set Flat Allocation Amount":
            amount = prompt_float_default(
                f"Flat allocation amount ({currency}, 0=off)",
                profile.flatbet_amount,
                0.0,
            )
            profile.flatbet_amount = MIN_BET if 0 < amount < MIN_BET else amount
        save_profile(profile)


def print_strategy_block(strategies: list[str], no_color: bool = False) -> None:
    """Render daftar strategy dengan metadata komentar Lua (Fase 4.4)."""
    theme = get_theme()
    section("STRATEGY", Fore.CYAN, no_color)
    g = theme.glyphs
    width_idx = len(str(len(strategies)))
    base_dir = lua_dir()
    for index, strategy in enumerate(strategies, 1):
        bullet = theme.c(g.bullet, "accent", bold=True)
        num = theme.c(f"{str(index).rjust(width_idx)}", "accent")
        name = theme.c(strategy, "muted", bold=True)
        meta = parse_strategy_meta(base_dir / strategy)
        if meta.name:
            label = theme.c(f" â€” {meta.name}", "dim")
            print(f"  {bullet} [{num}] {name}{label}")
        else:
            print(f"  {bullet} [{num}] {name}")
        sub_parts: list[str] = []
        if meta.desc:
            sub_parts.append(theme.c(meta.desc[:80], "dim"))
        if meta.recommend:
            sub_parts.append(theme.c(f"({meta.recommend})", "info"))
        if meta.tags:
            tag_text = " ".join(f"#{t}" for t in meta.tags[:4])
            sub_parts.append(theme.c(tag_text, "accent"))
        if sub_parts:
            print(f"      {'  '.join(sub_parts)}")
    print(theme.divider(48))


def print_account_status(
    account: AccountSnapshot,
    no_color: bool = False,
    *,
    site: str = "",
) -> None:
    theme = get_theme()
    g = theme.glyphs

    active_coin = (account.currency or '-')
    active_upper = (account.currency or "").upper()

    # Filter wallet: untuk semua site KECUALI testmode, sembunyikan coin
    # yang saldonya 0. Testmode tetap tampilkan semua coin karena
    # simulator (user butuh lihat coin apa saja yang tersedia).
    site_lower = (site or "").lower()
    _hide_zero_wallets = site_lower != TEST_MODE_SITE and site_lower != ""
    if _hide_zero_wallets and account.balance_list:
        visible_wallets = [
            (cur, amt) for cur, amt in account.balance_list if amt and amt > 0
        ]
        # Pastikan active coin selalu tampil walau 0 (biar user tetap
        # tahu coin yang lagi dipilih).
        if active_upper and not any(
            cur.upper() == active_upper for cur, _ in visible_wallets
        ):
            for cur, amt in account.balance_list:
                if cur.upper() == active_upper:
                    visible_wallets.insert(0, (cur, amt))
                    break
    else:
        visible_wallets = list(account.balance_list)

    # Fitur IDR hanya aktif di build pribadi (RAPTECH_IDR=1)
    import os as _os
    _idr_enabled = _os.getenv("RAPTECH_IDR") == "1"

    price_map: dict[str, float] = {}
    active_price = None

    if _idr_enabled:
        try:
            from ..pricing import get_prices_idr
            wallet_symbols = [c.upper() for c, _ in account.balance_list]
            if active_upper and active_upper not in wallet_symbols:
                wallet_symbols.append(active_upper)
            price_map = get_prices_idr(wallet_symbols) if wallet_symbols else {}
            active_price = price_map.get(active_upper)
        except Exception:
            pass

    def idr_suffix(amount: float, symbol: str, *, sign: bool = False) -> str:
        """Suffix '  ≈ Rp ...' — hanya kalau IDR enabled dan harga tersedia."""
        if not _idr_enabled or not price_map:
            return ""
        try:
            from ..pricing import format_idr, is_supported
            if not is_supported(symbol):
                return ""
            price = price_map.get(symbol.upper())
            if price is None:
                return ""
            idr_val = float(amount) * price
            return theme.c(f"  \u2248 {format_idr(idr_val, sign=sign)}", "dim")
        except Exception:
            return ""

    # Identity card
    section("ACCOUNT", Fore.CYAN, no_color)
    label = lambda s: theme.c(f"{s:<11}", "dim")
    val = lambda s: theme.c(s, "muted")
    print(f"  {label('User')} {val(account.username or '-')}")
    print(f"  {label('Email')} {val(account.email or '-')}")

    # Active Coin + live price (jika IDR enabled dan supported)
    coin_line = theme.c(active_coin, 'accent', bold=True)
    if _idr_enabled and active_price is not None:
        try:
            from ..pricing import format_idr
            coin_line += theme.c(f"  @  {format_idr(active_price)}", "dim") + theme.c(" /coin", "dim")
        except Exception:
            pass
    print(f"  {label('Active Coin')} {coin_line}")

    # Balance line + IDR estimasi
    bal_str = f"{account.balance:.8f} {account.currency or ''}".rstrip()
    bal_line = theme.c(bal_str, 'success', bold=True) + idr_suffix(account.balance, active_upper)
    print(f"  {label('Balance')} {bal_line}")
    print("")

    # Wallet section
    print(theme.section(STR.ACCOUNT_SECTION_WALLETS, role="primary"))
    if not visible_wallets:
        # Kalau semua saldo 0 (hidden), kasih hint
        if _hide_zero_wallets and account.balance_list:
            print(f"  {theme.c('(semua saldo 0 - deposit dulu di site)', 'warning')}")
        else:
            print(f"  {theme.c(STR.ACCOUNT_NO_WALLET, 'warning')}")
    else:
        if _idr_enabled and price_map:
            head = (
                f"  {theme.c('COIN    ', 'dim', bold=True)} "
                f"{theme.c('BALANCE         ', 'dim', bold=True)} "
                f"{theme.c('\u2248 IDR              ', 'dim', bold=True)} "
                f"{theme.c('STATE', 'dim', bold=True)}"
            )
        else:
            head = (
                f"  {theme.c('COIN    ', 'dim', bold=True)} "
                f"{theme.c('BALANCE         ', 'dim', bold=True)} "
                f"{theme.c('STATE', 'dim', bold=True)}"
            )
        print(head)
        for currency, amount in visible_wallets:
            cur_up = currency.upper()
            is_active = cur_up == active_upper
            dot = (
                theme.c(g.dot_on, "success", bold=True)
                if is_active
                else theme.c(g.dot_off, "dim")
            )
            cur_label = theme.c(
                currency.ljust(8),
                "accent" if is_active else "muted",
                bold=is_active,
            )
            amt_role = "success" if is_active and amount > 0 else "muted"
            amt_text = theme.c(f"{amount:<16.8f}", amt_role, bold=is_active)
            tag = (
                theme.c("active", "accent", bold=True)
                if is_active
                else theme.c("idle", "dim")
            )

            if _idr_enabled and price_map:
                price = price_map.get(cur_up)
                try:
                    from ..pricing import format_idr
                    idr_text = format_idr(float(amount) * price) if price is not None else "-"
                except Exception:
                    idr_text = "-"
                idr_col = theme.c(f"{idr_text:<18}", "muted" if is_active else "dim")
                print(f"  {dot} {cur_label} {amt_text} {idr_col} {tag}")
            else:
                print(f"  {dot} {cur_label} {amt_text} {tag}")
    print("")

    # Lifetime metrics
    print(theme.section(STR.ACCOUNT_SECTION_LIFETIME, role="primary"))
    metric = lambda lbl, value, role="muted": (
        f"  {theme.c(f'{lbl:<10}', 'dim')} {theme.c(str(value), role, bold=True)}"
    )
    print(metric("Cycles", f"{account.total_bets:,}"))
    print(metric("Positive", f"{account.total_wins:,}", "success"))
    print(metric("Negative", f"{account.total_losses:,}", "danger"))

    profit_text = f"{account.total_profit:+.8f} {account.currency}"
    profit_line = theme.by_sign(profit_text, account.total_profit)
    profit_line += idr_suffix(account.total_profit, active_upper, sign=True)
    print("  " + theme.c(f"{'Profit':<10}", "dim") + " " + profit_line)

    volume_text = f"{account.total_wagered:.8f} {account.currency}"
    volume_line = theme.c(volume_text, "muted", bold=True)
    volume_line += idr_suffix(account.total_wagered, active_upper)
    print("  " + theme.c(f"{'Volume':<10}", "dim") + " " + volume_line)


