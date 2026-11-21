from __future__ import annotations

import argparse
import io
import json
import math
import os
import queue
import sys
import time
from pathlib import Path
from typing import Callable

try:
    import msvcrt
except Exception:
    msvcrt = None

try:
    from colorama import Fore, Style, init as colorama_init

    colorama_init(autoreset=True)
except Exception:
    class Fore:
        RED = "\x1b[31m"
        GREEN = "\x1b[32m"
        YELLOW = "\x1b[33m"
        BLUE = "\x1b[34m"
        MAGENTA = "\x1b[35m"
        CYAN = "\x1b[36m"
        WHITE = "\x1b[37m"

    class Style:
        RESET_ALL = "\x1b[0m"

from ..clients import (
    BaseClient,
    CLIENT_REGISTRY,
    COOKIE_BASED_SITES,
    JWT_BASED_SITES,
    available_sites,
    build_account_snapshot,
    currency_balance,
    get_client_class,
    site_metadata,
)
from ..config import DEFAULT_CURRENCIES, DEFAULT_SITE, lua_dir
from ..engine import BotEngine
from ..lua_support import get_global, load_lua_strategy
from ..models import AccountSnapshot, SessionConfig, SessionProfile, SessionSnapshot
from ..storage import (
    DEFAULT_SITE as STORAGE_DEFAULT_SITE,  # alias agar konsisten
    get_profile_entry,
    get_token_for,
    load_saved_token,
    load_settings_store,
    load_tokens,
    profile_to_dict,
    put_profile_entry,
    runtime_profile_key,
    runtime_profile_key_for_site,
    sanitize_session_profile,
    save_settings_store,
    save_token,
    set_token_for,
)
from ..ui import cyber as cyber_ui
from ..ui import event_log as event_log_mod
from ..ui import widgets as widgets_mod
from ..ui.strategy_meta import parse_strategy_meta
from ..ui.strings import S as STR
from ..ui.theme import (
    Theme,
    build_theme,
    pad_visible,
    terminal_caps,
    visible_len,
)


APP_NAME = "RAPTECH ENGINE"
MIN_BET = 0.00000001
TEST_MODE_SITE = "testmode"
TEST_MODE_DEFAULT_BALANCE = 1.0

from . import _state as _state_mod
from ._state import (
    get_theme,
    is_compact_mode,
    is_toast_enabled,
)

# Module-level theme di-track DUA tempat:
#   1. `_THEME` lokal di sini → dipakai semua fungsi legacy yang akses
#      langsung (table_row, table_sep, dll).
#   2. `_state._THEME` → dipakai sub-modul cli/* (layout.py dst.) supaya
#      tidak perlu import-cycle ke `__init__`.
# `set_theme()` di bawah sinkronkan keduanya, jadi cukup panggil setter
# ini dan tidak ada drift.
_THEME: Theme = _state_mod.get_theme()

# UI mode flags lokal — single source of truth tetap di `_state`,
# accessor lokal `is_compact_mode()` / `is_toast_enabled()` di-import.
_COMPACT_MODE: bool = _state_mod.is_compact_mode()
_TOAST_ENABLED: bool = _state_mod.is_toast_enabled()


def set_theme(theme: Theme) -> None:
    """Set theme aktif. Sinkron ke `_state` supaya sub-modul cli/* baca
    instance yang sama, dan ke `cyber_ui` supaya activation/license
    screen pakai tema yang sama."""
    global _THEME
    _THEME = theme
    _state_mod.set_theme(theme)


def set_compact_mode(enabled: bool) -> None:
    global _COMPACT_MODE
    _COMPACT_MODE = bool(enabled)
    _state_mod.set_compact_mode(enabled)


def set_toast_enabled(enabled: bool) -> None:
    global _TOAST_ENABLED
    _TOAST_ENABLED = bool(enabled)
    _state_mod.set_toast_enabled(enabled)




# Mapping legacy color name -> role semantik di theme.
# Diekstrak ke `cli/_console.py` (Step F). Di sini cuma re-export.
from ._console import (  # noqa: E402
    _FORE_TO_ROLE,
    clear_screen,
    color_text,
    normalize_token,
    pause,
    section,
    terminal_frame,
)


def site_requires_token(site: str) -> bool:
    try:
        client_cls = get_client_class(site)
    except Exception:
        return True
    return bool(getattr(client_cls, "requires_token", True))


def is_test_mode(site: str) -> bool:
    return (site or "").lower() == TEST_MODE_SITE


def test_mode_balance_from_ui(ui_store: dict) -> float:
    try:
        value = float(ui_store.get("testmode_balance", TEST_MODE_DEFAULT_BALANCE))
    except (TypeError, ValueError):
        value = TEST_MODE_DEFAULT_BALANCE
    return max(0.0, value)


def build_test_mode_token(ui_store: dict) -> str:
    return json.dumps(
        {"balance": test_mode_balance_from_ui(ui_store)},
        separators=(",", ":"),
    )


def credential_label(site: str) -> str:
    if not site_requires_token(site):
        return "Test Mode"
    if site.lower() in JWT_BASED_SITES:
        return "Auth Token"
    if site.lower() in COOKIE_BASED_SITES:
        return "Cookie"
    return "Web API"




def load_strategies(strategy_dir: Path) -> list[str]:
    if not strategy_dir.is_dir():
        return []
    return sorted([path.name for path in strategy_dir.glob("*.lua")], key=str.lower)


# ---- Layout helpers ----------------------------------------------------
# Diekstrak ke `cli/layout.py` (Fase 2 perapihan, Step C). Re-export di
# sini supaya import lama (`from corebot.cli import table_row`, dll.)
# tetap jalan — dipakai `tests/test_layout.py` dan `scripts/debug/preview_layout.py`.
from .layout import (  # noqa: E402
    _COL_KEYS,
    _COL_MAX,
    _COL_MIN,
    _COL_PRIORITY,
    _COL_WEIGHT,
    compute_table_widths,
    format_duration,
    responsive_width,
    pad,
    table_align_for,
    table_header_row,
    table_row,
    table_sep,
    truncate_visible_in_pad,
)


def ansi_move_up(lines: int) -> None:
    if lines > 0:
        sys.stdout.write(f"\x1b[{lines}A")


def ansi_clear_line() -> None:
    sys.stdout.write("\x1b[2K")


def ansi_move_to_col(col: int) -> None:
    sys.stdout.write(f"\x1b[{col}G")


def color_profit(text: str, value: float, no_color: bool = False) -> str:
    if no_color or not _THEME.use_color:
        return text
    return _THEME.by_sign(text, value)


def color_by_win(text: str, win: bool | None, no_color: bool = False) -> str:
    if no_color or not _THEME.use_color:
        return text
    return _THEME.by_win(text, win)


def print_main_menu(
    connected: bool,
    account: AccountSnapshot | None,
    no_color: bool = False,
    *,
    site: str = DEFAULT_SITE,
) -> int:
    # Pindah ke `cli/menu.py` (Step H).
    from .menu import print_main_menu as _impl
    return _impl(connected, account, no_color, site=site)


# Prompts diekstrak ke `cli/prompts.py` (Step F+H). Re-export di sini.
from .prompts import (  # noqa: E402
    _drain_input_buffer,
    prompt_float_default,
    prompt_select,
    prompt_select_site,
    prompt_web_api,
)

# Menu interaktif diekstrak ke `cli/menu.py` (Step H). Re-export di sini.
from .menu import (  # noqa: E402
    configure_runtime_settings,
    fmt_pct,
    print_account_status,
    print_strategy_block,
    profile_summary,
    show_dry_run_preview,
    quick_start_wizard,
    ui_store_default,
)


def apply_profile_args(profile: SessionProfile, args: argparse.Namespace) -> SessionProfile:
    # Pindah ke `cli/runner.py` (Fase 2 perapihan, Step G).
    from .runner import apply_profile_args as _impl
    return _impl(profile, args)


def _log_icon(level: str) -> tuple[str, str]:
    # Pindah ke `cli/_log.py` (Step I-1).
    from ._log import _log_icon as _impl
    return _impl(level)


def format_log_line(level: str, message: str) -> str:
    # Pindah ke `cli/_log.py` (Step I-1).
    from ._log import format_log_line as _impl
    return _impl(level, message)


def connect_account(
    token: str,
    currency: str | None = None,
    *,
    no_color: bool = False,
    site: str = DEFAULT_SITE,
) -> tuple[BaseClient, AccountSnapshot]:
    # Pindah ke `cli/account.py` (Step I-2).
    from .account import connect_account as _impl
    return _impl(token, currency, no_color=no_color, site=site)


def refresh_account(client: BaseClient, account: AccountSnapshot | None, currency: str | None = None) -> AccountSnapshot:
    # Pindah ke `cli/account.py` (Step I-2).
    from .account import refresh_account as _impl
    return _impl(client, account, currency)


def select_currency(
    account: AccountSnapshot,
    default_currency: str = "",
    *,
    no_color: bool = False,
    site: str = DEFAULT_SITE,
) -> str:
    # Pindah ke `cli/account.py` (Step I-2).
    from .account import select_currency as _impl
    return _impl(account, default_currency, no_color=no_color, site=site)


def resolve_strategy_name(value: str | None, strategies: list[str]) -> str:
    # Pindah ke `cli/account.py` (Step I-2).
    from .account import resolve_strategy_name as _impl
    return _impl(value, strategies)


def _script_check_globals(balance: float, currency: str) -> dict:
    # Pindah ke `cli/script_check.py` (Fase 2 perapihan, Step E).
    from .script_check import _script_check_globals as _impl
    return _impl(balance, currency)


def _as_finite_number(value, name: str) -> tuple[float | None, str | None]:
    from .script_check import _as_finite_number as _impl
    return _impl(value, name)


def _load_strategy_for_check(strategy_path: Path, currency: str, balance: float):
    from .script_check import _load_strategy_for_check as _impl
    return _impl(strategy_path, currency, balance)


def check_strategy_script(
    strategy_path: Path,
    *,
    currency: str = "BTC",
    balance: float = TEST_MODE_DEFAULT_BALANCE,
) -> dict:
    from .script_check import check_strategy_script as _impl
    return _impl(strategy_path, currency=currency, balance=balance)


def print_script_check_report(results: list[dict], *, no_color: bool = False) -> None:
    from .script_check import print_script_check_report as _impl
    return _impl(results, no_color=no_color)


def read_hotkey() -> str:
    # Pindah ke `cli/engine_view.py` (Step I-3).
    from .engine_view import read_hotkey as _impl
    return _impl()


def is_engine_bet_log(message: str) -> bool:
    from .engine_view import is_engine_bet_log as _impl
    return _impl(message)


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
    from .engine_view import snapshot_row as _impl
    return _impl(
        snapshot, widths, no_color,
        active_indices=active_indices,
        align=align,
        group_breaks=group_breaks,
        striped=striped,
    )


def print_summary(snapshot: SessionSnapshot | None, no_color: bool = False) -> None:
    from .engine_view import print_summary as _impl
    return _impl(snapshot, no_color)


def _maybe_profile_run(profile_out: str | None, fn, *args, **kwargs):
    from .engine_view import _maybe_profile_run as _impl
    return _impl(profile_out, fn, *args, **kwargs)


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
    # Pindah ke `cli/engine_view.py` (Step I-3).
    from .engine_view import run_engine as _impl
    return _impl(
        client, config, account, profile,
        sticky_footer=sticky_footer,
        quiet=quiet,
        no_color=no_color,
        confirm_quit=confirm_quit,
        toast_enabled=toast_enabled,
        json_log=json_log,
        write_report=write_report,
    )


def build_parser() -> argparse.ArgumentParser:
    # Definisi parser di-pindah ke `cli/args.py` (Fase 2 perapihan,
    # Step D). Re-export di sini untuk back-compat.
    from .args import build_parser as _bp
    return _bp()


def persist_runtime_profile(
    settings_store: dict,
    strategy_name: str,
    currency: str,
    profile: SessionProfile,
    *,
    site: str = DEFAULT_SITE,
    last_strategy: str | None = None,
    last_currency: str | None = None,
    last_site: str | None = None,
) -> None:
    # Pindah ke `cli/runner.py` (Step G).
    from .runner import persist_runtime_profile as _impl
    _impl(
        settings_store,
        strategy_name,
        currency,
        profile,
        site=site,
        last_strategy=last_strategy,
        last_currency=last_currency,
        last_site=last_site,
    )


def build_strategy_profiles_for_site(
    settings_store: dict,
    site: str,
    strategies: list[str],
    selected_strategy: str,
    currency: str,
    selected_profile: SessionProfile,
) -> dict[str, SessionProfile]:
    from .runner import build_strategy_profiles_for_site as _impl
    return _impl(
        settings_store, site, strategies, selected_strategy, currency, selected_profile
    )


def build_config(
    strategy_dir: Path,
    strategies: list[str],
    settings_store: dict,
    strategy_name: str,
    currency: str,
    profile: SessionProfile,
    *,
    site: str = DEFAULT_SITE,
) -> SessionConfig:
    from .runner import build_config as _impl
    return _impl(
        strategy_dir, strategies, settings_store, strategy_name, currency, profile, site=site
    )


def run_non_interactive(
    args: argparse.Namespace,
    strategy_dir: Path,
    strategies: list[str],
    settings_store: dict,
    token: str,
    *,
    site: str = DEFAULT_SITE,
) -> int:
    # Pindah ke `cli/runner.py` (Step J).
    from .runner import run_non_interactive as _impl
    return _impl(args, strategy_dir, strategies, settings_store, token, site=site)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    # Auto-enable compact mode untuk terminal pendek (≤29 baris)
    caps = terminal_caps(refresh=True)
    compact = bool(getattr(args, "compact", False)) or caps.height < 30
    set_compact_mode(compact)
    set_toast_enabled(bool(getattr(args, "toast", True)))

    set_theme(
        build_theme(
            no_color=bool(args.no_color),
            name=str(getattr(args, "theme", "cyber") or "cyber"),
            plain=bool(getattr(args, "plain", False)),
        )
    )

    try:
        strategy_dir = lua_dir()
        strategies = load_strategies(strategy_dir)
        if args.list_strategies:
            for strategy in strategies:
                print(strategy)
            return 0
        if args.list_sites:
            for slug in available_sites():
                meta = site_metadata(slug)
                print(f"{slug}\t{meta.display_name}")
            return 0
        if not strategies:
            raise RuntimeError(f"Tidak ada file Lua di {strategy_dir}")
        if args.check_script is not None:
            requested = str(args.check_script or "all")
            if requested.lower() in {"all", "*"}:
                names = strategies
            else:
                names = [resolve_strategy_name(requested, strategies)]
            currency = (args.currency or "BTC").upper()
            results = [
                check_strategy_script(strategy_dir / name, currency=currency)
                for name in names
            ]
            print_script_check_report(results, no_color=args.no_color)
            return 0 if all(result["ok"] for result in results) else 1

        settings_store = load_settings_store()
        ui_store = settings_store.setdefault("ui", {})

        # Resolve site aktif: argument > saved last_site > default
        site = (args.site or ui_store.get("last_site") or DEFAULT_SITE).lower()
        if site not in CLIENT_REGISTRY:
            site = DEFAULT_SITE
        ui_store["last_site"] = site

        token = normalize_token(args.token or get_token_for(site) or "")
        if is_test_mode(site) and not args.token:
            token = build_test_mode_token(ui_store)

        if args.non_interactive:
            if site_requires_token(site) and not token:
                raise RuntimeError(
                    f"Web API kosong untuk situs '{site}'. "
                    "Isi via menu, --token, atau apitokens.json."
                )
            return run_non_interactive(
                args,
                strategy_dir,
                strategies,
                settings_store,
                token,
                site=site,
            )

        # Quick-start wizard (Fase 4.3) — auto-launch saat user pass --quick-start
        if getattr(args, "quick_start", False):
            wizard_result = quick_start_wizard(
                settings_store=settings_store,
                strategy_dir=strategy_dir,
                strategies=strategies,
                no_color=args.no_color,
            )
            if wizard_result is not None:
                wsite, wstrategy, wprofile, wcurrency = wizard_result
                # Set ke args supaya run_non_interactive pakai pilihan wizard
                args.site = wsite
                args.strategy = wstrategy
                args.currency = wcurrency
                # Persist profile sebelum non_interactive jalan
                token_quick = normalize_token(get_token_for(wsite) or "")
                if is_test_mode(wsite):
                    token_quick = build_test_mode_token(ui_store)
                if site_requires_token(wsite) and not token_quick:
                    print(_THEME.c(
                        f"Web API kosong untuk '{wsite}'. Lengkapi dulu via menu utama.",
                        "warning",
                    ))
                    pause()
                else:
                    return run_non_interactive(
                        args,
                        strategy_dir,
                        strategies,
                        settings_store,
                        token_quick,
                        site=wsite,
                    )

        client: BaseClient | None = None
        account: AccountSnapshot | None = None

        # Multi-account: ambil token akun aktif untuk site yang butuh token.
        # Kalau `token` sudah di-set (dari args atau env), skip agar user
        # override tetap efektif.
        if site_requires_token(site) and not is_test_mode(site) and not token:
            from .account_manager import get_active_token
            _active_token = get_active_token(site)
            if _active_token:
                token = _active_token

        if token or not site_requires_token(site):
            try:
                clear_screen()
                client, account = connect_account(
                    token,
                    ui_store.get("last_currency"),
                    no_color=args.no_color,
                    site=site,
                )
                if not args.no_save_token and token and site_requires_token(site):
                    set_token_for(site, token)
                # Start background refresh untuk site yang punya endpoint
                # refresh-token (saat ini hanya Pasino). Call ini no-op
                # untuk site lain.
                from .account_manager import start_background_refresh_all
                start_background_refresh_all(site)
                time.sleep(0.8)
            except Exception as exc:
                token = ""
                clear_screen()
                section("WEB API ERROR", Fore.RED, args.no_color)
                print(exc)
                pause()

        while True:
            action = print_main_menu(
                client is not None and account is not None,
                account,
                args.no_color,
                site=site,
            )

            if action == 7:
                return 0

            # 0. Quick Start wizard (Fase 4.3 — discoverable via menu)
            if action == 0:
                wizard_result = quick_start_wizard(
                    settings_store=settings_store,
                    strategy_dir=strategy_dir,
                    strategies=strategies,
                    no_color=args.no_color,
                )
                if wizard_result is None:
                    pause()
                    continue
                wsite, wstrategy, wprofile, wcurrency = wizard_result
                args.site = wsite
                args.strategy = wstrategy
                args.currency = wcurrency
                token_quick = normalize_token(get_token_for(wsite) or "")
                if is_test_mode(wsite):
                    token_quick = build_test_mode_token(ui_store)
                if site_requires_token(wsite) and not token_quick:
                    print(_THEME.c(
                        f"Web API kosong untuk '{wsite}'. Isi dulu via menu 2.",
                        "warning",
                    ))
                    pause()
                    site = wsite
                    continue
                run_non_interactive(
                    args,
                    strategy_dir,
                    strategies,
                    settings_store,
                    token_quick,
                    site=wsite,
                )
                pause()
                continue

            # 1. Select Site
            if action == 1:
                new_site = prompt_select_site(site, no_color=args.no_color)
                if new_site != site:
                    site = new_site
                    ui_store["last_site"] = site
                    save_settings_store(settings_store)
                    # Site berubah → reset client/account, ambil token situs baru
                    client = None
                    account = None
                    token = normalize_token(get_token_for(site) or "")
                    if is_test_mode(site):
                        token = build_test_mode_token(ui_store)
                    if token or not site_requires_token(site):
                        try:
                            clear_screen()
                            client, account = connect_account(
                                token,
                                ui_store.get("last_currency"),
                                no_color=args.no_color,
                                site=site,
                            )
                        except Exception as exc:
                            token = ""
                            section("WEB API ERROR", Fore.RED, args.no_color)
                            print(exc)
                            pause()
                continue

            # 2. Paste Web API
            if action == 2:
                if is_test_mode(site):
                    current_balance = account.balance if account else test_mode_balance_from_ui(ui_store)
                    section("TEST MODE BALANCE", Fore.CYAN, args.no_color)
                    print(f"Current balance : {current_balance:.8f}")
                    print("Balance ini hanya untuk simulator lokal, bukan saldo real.")
                    next_balance = prompt_float_default("Starting balance", current_balance, 0.0)
                    ui_store["testmode_balance"] = float(next_balance)
                    save_settings_store(settings_store)
                    token = build_test_mode_token(ui_store)
                    try:
                        client, account = connect_account(
                            token,
                            ui_store.get("last_currency"),
                            no_color=args.no_color,
                            site=site,
                        )
                    except Exception as exc:
                        section("SESSION ERROR", Fore.RED, args.no_color)
                        print(exc)
                        pause()
                        continue
                    print(_THEME.c(f"Test Mode balance set: {next_balance:.8f}", "success"))
                    print_account_status(account, args.no_color, site=site)
                    pause()
                    continue
                token_candidate = prompt_web_api(token or "", args.no_color, site=site)
                if not token_candidate:
                    print("Web API kosong.")
                    pause()
                    continue
                try:
                    client, account = connect_account(
                        token_candidate,
                        ui_store.get("last_currency"),
                        no_color=args.no_color,
                        site=site,
                    )
                except Exception as exc:
                    section("WEB API ERROR", Fore.RED, args.no_color)
                    print(exc)
                    pause()
                    continue
                token = token_candidate
                if not args.no_save_token and site_requires_token(site):
                    # Semua site pakai multi-account storage generic.
                    # Kalau token sudah ada di storage, set jadi aktif.
                    # Kalau belum, tambah sebagai akun baru dengan label auto.
                    from .account_manager import (
                        _load_accounts_for,
                        _save_accounts_for,
                        start_background_refresh_all,
                    )
                    data = _load_accounts_for(site)
                    accounts = data.get("accounts", [])
                    existing = [i for i, a in enumerate(accounts) if a.get("token") == token]
                    if existing:
                        data["active"] = existing[0]
                        _save_accounts_for(site, data)
                        print(_THEME.c(
                            f"Web API sudah ada di akun ke-{existing[0]+1}, di-set aktif.",
                            "success",
                        ))
                    else:
                        label = f"Akun {len(accounts) + 1}"
                        accounts.append({"label": label, "token": token})
                        data["accounts"] = accounts
                        data["active"] = len(accounts) - 1
                        _save_accounts_for(site, data)
                        print(_THEME.c(
                            f"Web API tersimpan sebagai '{label}' untuk {site}.",
                            "success",
                        ))
                    # Start background refresh (no-op kalau site tidak support)
                    start_background_refresh_all(site)
                print_account_status(account, args.no_color, site=site)
                pause()
                continue

            # 4 / 5. Account Overview / Refresh Balance
            if action in {4, 5}:
                if client is None:
                    if site_requires_token(site):
                        print("Paste Web API dulu.")
                        pause()
                        continue
                    token = build_test_mode_token(ui_store) if is_test_mode(site) else token
                    try:
                        client, account = connect_account(
                            token,
                            ui_store.get("last_currency"),
                            no_color=args.no_color,
                            site=site,
                        )
                    except Exception as exc:
                        section("SESSION ERROR", Fore.RED, args.no_color)
                        print(exc)
                        pause()
                        continue
                try:
                    account = refresh_account(
                        client,
                        account,
                        account.currency if account else ui_store.get("last_currency"),
                    )
                except Exception as exc:
                    section("SESSION ERROR", Fore.RED, args.no_color)
                    print(exc)
                    pause()
                    continue
                print_account_status(account, args.no_color, site=site)
                pause()
                continue

            # 6. Check Script
            if action == 6:
                picked = prompt_select(
                    ["All Scripts", *strategies],
                    "Check script:",
                    "All Scripts",
                    show_list=True,
                    no_color=args.no_color,
                )
                names = strategies if picked == "All Scripts" else [picked]
                currency_for_check = (
                    account.currency
                    if account and account.currency
                    else str(ui_store.get("last_currency") or "BTC")
                ).upper()
                results = [
                    check_strategy_script(strategy_dir / name, currency=currency_for_check)
                    for name in names
                ]
                print_script_check_report(results, no_color=args.no_color)
                pause()
                continue

            # 8. Deposit (Pasino only)
            if action == 8:
                if site.lower() != "pasino":
                    print(_THEME.c("Menu Deposit hanya tersedia untuk Pasino.", "warning"))
                    pause()
                    continue
                if client is None:
                    print(_THEME.c("Paste Web API dulu (menu 2) sebelum deposit.", "warning"))
                    pause()
                    continue
                from .deposit import show_deposit_menu
                show_deposit_menu(client)
                continue

            # 9. Withdraw (Pasino only)
            if action == 9:
                if site.lower() != "pasino":
                    print(_THEME.c("Menu Withdraw hanya tersedia untuk Pasino.", "warning"))
                    pause()
                    continue
                if client is None:
                    print(_THEME.c("Paste Web API dulu (menu 2) sebelum withdraw.", "warning"))
                    pause()
                    continue
                from .withdraw import show_withdraw_menu
                show_withdraw_menu(client, account)
                # Refresh account balance setelah withdraw
                if account:
                    try:
                        account = refresh_account(client, account, account.currency)
                    except Exception:
                        pass
                continue

            # 10. Token Status (Pasino only)
            if action == 10:
                if site.lower() != "pasino":
                    print(_THEME.c("Menu Token Status hanya tersedia untuk Pasino.", "warning"))
                    pause()
                    continue
                if client is None:
                    print(_THEME.c("Paste Web API dulu (menu 2).", "warning"))
                    pause()
                    continue
                from .token_menu import show_token_status
                show_token_status(client)
                pause()
                continue

            # 11. Refresh Token (Pasino only)
            if action == 11:
                if site.lower() != "pasino":
                    print(_THEME.c("Menu Refresh Token hanya tersedia untuk Pasino.", "warning"))
                    pause()
                    continue
                if client is None:
                    print(_THEME.c("Paste Web API dulu (menu 2).", "warning"))
                    pause()
                    continue
                from .token_menu import show_refresh_token
                show_refresh_token(client)
                pause()
                continue

            # 13. Set Proxy (all sites)
            if action == 13:
                from .proxy_menu import show_proxy_menu
                changed = show_proxy_menu(site)
                # Kalau proxy diubah dan sudah connected, reconnect supaya
                # session pakai proxy baru
                if changed and client is not None:
                    print(_THEME.c("Reconnecting dengan proxy baru...", "dim"))
                    try:
                        client, account = connect_account(
                            token,
                            ui_store.get("last_currency"),
                            no_color=args.no_color,
                            site=site,
                        )
                        print(_THEME.c("Reconnected via proxy.", "success"))
                    except Exception as exc:
                        section("PROXY CONNECT ERROR", Fore.RED, args.no_color)
                        print(exc)
                        print()
                        print(_THEME.c("Cek proxy URL benar, akun aktif, dan proxy hidup.", "warning"))
                    pause()
                continue

            # 14. Change Email (Wolfbet only)
            if action == 14:
                if site.lower() != "wolfbet":
                    print(_THEME.c(
                        "Menu Change Email hanya tersedia untuk Wolfbet.",
                        "warning",
                    ))
                    pause()
                    continue
                if client is None:
                    print(_THEME.c("Paste Web API dulu (menu 2) sebelum ubah email.", "warning"))
                    pause()
                    continue
                from .wolfbet_email import show_change_email
                show_change_email(client)
                continue

            # 12. Account Manager (all sites yang butuh token)
            if action == 12:
                if not site_requires_token(site) or is_test_mode(site):
                    print(_THEME.c(
                        "Menu Account Manager tidak berlaku untuk site ini.",
                        "warning",
                    ))
                    pause()
                    continue
                from .account_manager import show_account_manager
                result = show_account_manager(site, client)
                if result and result.get("token"):
                    # User switched atau added akun → reconnect
                    new_token = result["token"]
                    try:
                        client, account = connect_account(
                            new_token,
                            ui_store.get("last_currency"),
                            no_color=args.no_color,
                            site=site,
                        )
                        token = new_token
                        # Token sudah disimpan oleh account_manager
                        print(_THEME.c(
                            f"Connected ke akun '{result.get('label', '?')}'.",
                            "success",
                        ))
                    except Exception as exc:
                        section("SESSION ERROR", Fore.RED, args.no_color)
                        print(exc)
                    pause()
                continue

            # 3. Start Engine
            if action != 3:
                print("Invalid option. Pilih nomor dari menu.")
                pause()
                continue

            if client is None or account is None:
                if not site_requires_token(site):
                    token = build_test_mode_token(ui_store) if is_test_mode(site) else token
                    try:
                        client, account = connect_account(
                            token,
                            ui_store.get("last_currency"),
                            no_color=args.no_color,
                            site=site,
                        )
                    except Exception as exc:
                        section("SESSION ERROR", Fore.RED, args.no_color)
                        print(exc)
                        pause()
                        continue
                else:
                    token_candidate = prompt_web_api(token or "", args.no_color, site=site)
                    if not token_candidate:
                        print("Web API kosong.")
                        pause()
                        continue
                    try:
                        client, account = connect_account(
                            token_candidate,
                            ui_store.get("last_currency"),
                            no_color=args.no_color,
                            site=site,
                        )
                    except Exception as exc:
                        section("WEB API ERROR", Fore.RED, args.no_color)
                        print(exc)
                        pause()
                        continue
                    token = token_candidate
                    if not args.no_save_token and site_requires_token(site):
                        set_token_for(site, token)

            try:
                account = refresh_account(
                    client, account, account.currency or ui_store.get("last_currency")
                )
            except Exception as exc:
                section("SESSION ERROR", Fore.RED, args.no_color)
                print(exc)
                pause()
                continue

            selected_currency = select_currency(
                account,
                str(ui_store.get("last_currency") or account.currency),
                no_color=args.no_color,
                site=site,
            )
            try:
                account = refresh_account(client, account, selected_currency)
            except Exception as exc:
                section("SESSION ERROR", Fore.RED, args.no_color)
                print(exc)
                pause()
                continue
            account.currency = selected_currency
            account.balance = currency_balance(account.balance_list, selected_currency)

            print_strategy_block(strategies, args.no_color)
            default_strategy = str(ui_store.get("last_strategy") or "")
            if default_strategy not in strategies:
                default_strategy = strategies[0]
            strategy_name = prompt_select(
                strategies,
                "Select strategy:",
                default_strategy,
                show_list=False,
                no_color=args.no_color,
            )

            profile_entry = get_profile_entry(
                settings_store, site, strategy_name, selected_currency
            )
            profile = sanitize_session_profile(profile_entry)
            profile = apply_profile_args(profile, args)

            site_for_save = site

            def save_current_profile(current_profile: SessionProfile) -> None:
                persist_runtime_profile(
                    settings_store,
                    strategy_name,
                    selected_currency,
                    current_profile,
                    site=site_for_save,
                    last_strategy=strategy_name,
                    last_currency=selected_currency,
                    last_site=site_for_save,
                )

            runtime_profile = configure_runtime_settings(
                strategy_name,
                selected_currency,
                profile,
                save_current_profile,
                no_color=args.no_color,
            )
            if runtime_profile is None:
                continue

            # Dry-run preview (Fase 5.2) — kasih user kesempatan abort/edit
            preview_decision = show_dry_run_preview(
                site=site,
                strategy_name=strategy_name,
                currency=selected_currency,
                profile=runtime_profile,
            )
            if preview_decision == "cancel":
                continue
            if preview_decision == "e":
                # Re-edit profile
                runtime_profile = configure_runtime_settings(
                    strategy_name,
                    selected_currency,
                    runtime_profile,
                    save_current_profile,
                    no_color=args.no_color,
                ) or runtime_profile

            if not args.no_save_token and token and site_requires_token(site):
                set_token_for(site, token)
            config = build_config(
                strategy_dir,
                strategies,
                settings_store,
                strategy_name,
                selected_currency,
                runtime_profile,
                site=site,
            )
            snapshot = _maybe_profile_run(
                getattr(args, "profile", None),
                run_engine,
                client,
                config,
                account,
                runtime_profile,
                sticky_footer=args.sticky_footer,
                quiet=args.quiet,
                no_color=args.no_color,
                confirm_quit=bool(getattr(args, "confirm_quit", True)),
                toast_enabled=bool(getattr(args, "toast", True)),
                json_log=(getattr(args, "log_format", "text") == "json"),
                write_report=bool(getattr(args, "write_report", True)),
            )
            if snapshot:
                account.balance = snapshot.current_balance
                account.currency = snapshot.currency
            pause()
    except KeyboardInterrupt:
        print("\nStopped by user.")
        return 130
    except Exception as exc:
        import traceback
        print(color_text(f"\nERROR: {exc}", Fore.RED, args.no_color), file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        print("\n[BOT] Kembali ke menu dalam 3 detik...")
        import time as _time
        _time.sleep(3)
        return 1
