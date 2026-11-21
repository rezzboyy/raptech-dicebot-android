"""Builder & profile helpers untuk runner non-interaktif.

Diekstrak dari `cli/__init__.py` (Fase 2 perapihan, Step G).
Berisi pure data/storage helpers — tidak ada UI, tidak akses theme.
`run_non_interactive` itu sendiri masih di `__init__` karena banyak
callback ke engine helpers yang belum diekstrak.

Public API (di-re-export oleh `cli/__init__.py`):
    - `apply_profile_args`
    - `persist_runtime_profile`
    - `build_strategy_profiles_for_site`
    - `build_config`
"""
from __future__ import annotations

import argparse
from pathlib import Path

from ..config import DEFAULT_SITE
from ..models import SessionConfig, SessionProfile
from ..storage import (
    get_profile_entry,
    profile_to_dict,
    put_profile_entry,
    sanitize_session_profile,
    save_settings_store,
)

# Konstanta minimum bet (sinkron dengan `cli/__init__.py:MIN_BET`).
MIN_BET = 0.00000001


def apply_profile_args(profile: SessionProfile, args: argparse.Namespace) -> SessionProfile:
    """Override field profile dari argument CLI yang non-None."""
    if args.interval_ms is not None:
        profile.interval_ms = max(0, args.interval_ms)
    if args.max_bets is not None:
        profile.max_bets = max(0, args.max_bets)
    if args.log_every is not None:
        profile.log_every = max(1, args.log_every)
    if args.take_profit_pct is not None:
        profile.take_profit_pct = max(0.0, args.take_profit_pct)
    if args.pause_on_win:
        profile.pause_on_win = True
    if args.auto_switch_profit_pct is not None:
        profile.auto_switch_profit_pct = max(0.0, args.auto_switch_profit_pct)
    if args.run_break_seconds is not None:
        profile.run_break_seconds = max(0.0, args.run_break_seconds)
    if args.break_seconds is not None:
        profile.break_seconds = max(0.0, args.break_seconds)
    if args.flatbet_trigger_pct is not None:
        profile.flatbet_trigger_pct = max(0.0, args.flatbet_trigger_pct)
    if args.flatbet_minutes is not None:
        profile.flatbet_minutes = max(0.0, args.flatbet_minutes)
    if args.flatbet_amount is not None:
        profile.flatbet_amount = max(0.0, args.flatbet_amount)
    if 0 < profile.flatbet_amount < MIN_BET:
        profile.flatbet_amount = MIN_BET
    return profile


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
    """Simpan profile runtime + update last_* selection di settings store."""
    put_profile_entry(settings_store, site, strategy_name, currency, profile_to_dict(profile))
    ui_store = settings_store.setdefault("ui", {})
    if last_strategy:
        ui_store["last_strategy"] = last_strategy
    if last_currency:
        ui_store["last_currency"] = last_currency
    if last_site:
        ui_store["last_site"] = last_site
    save_settings_store(settings_store)


def build_strategy_profiles_for_site(
    settings_store: dict,
    site: str,
    strategies: list[str],
    selected_strategy: str,
    currency: str,
    selected_profile: SessionProfile,
) -> dict[str, SessionProfile]:
    """Bangun map strategy_name -> SessionProfile untuk satu situs.

    Profile untuk `selected_strategy` pakai instance yang dikirim caller;
    sisanya di-load dari settings_store atau di-sanitize dari default.
    """
    profiles: dict[str, SessionProfile] = {}
    for strategy_name in strategies:
        if strategy_name == selected_strategy:
            profiles[strategy_name] = selected_profile
        else:
            entry = get_profile_entry(settings_store, site, strategy_name, currency)
            profiles[strategy_name] = sanitize_session_profile(entry)
    return profiles


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
    """Compose `SessionConfig` lengkap dari profile + storage."""
    strategy_profiles = build_strategy_profiles_for_site(
        settings_store, site, strategies, strategy_name, currency, profile
    )
    return SessionConfig(
        currency=currency,
        strategy_name=strategy_name,
        strategy_path=strategy_dir / strategy_name,
        strategy_order=tuple(strategies),
        strategy_profiles=strategy_profiles,
        interval_ms=profile.interval_ms,
        max_bets=profile.max_bets,
        log_every=profile.log_every,
        take_profit_pct=profile.take_profit_pct,
        pause_on_win=profile.pause_on_win,
        auto_switch_profit_pct=profile.auto_switch_profit_pct,
        run_break_seconds=profile.run_break_seconds,
        break_seconds=profile.break_seconds,
        flatbet_trigger_pct=profile.flatbet_trigger_pct,
        flatbet_minutes=profile.flatbet_minutes,
        flatbet_amount=profile.flatbet_amount,
        remote_config={},
        license_status={},
    )


def _site_requires_token(site: str) -> bool:
    """Sinkron dengan helper di `cli/account.py` & `cli/menu.py`."""
    from ..clients import get_client_class
    try:
        client_cls = get_client_class(site)
    except Exception:
        return True
    return bool(getattr(client_cls, "requires_token", True))


def run_non_interactive(
    args,
    strategy_dir,
    strategies: list[str],
    settings_store: dict,
    token: str,
    *,
    site: str = DEFAULT_SITE,
) -> int:
    """Jalur non-interaktif: connect → resolve currency/strategy →
    persist profile → run engine. Return exit code (selalu 0 saat sukses).

    Diekstrak dari `cli/__init__.py` (Fase 2 perapihan, Step J).
    """
    # Lazy imports karena module ini sengaja minim dependency di top-level
    # (biar import-nya cepat). `account` & `engine_view` hanya di-load saat
    # caller benar-benar butuh non-interactive jalan.
    from ..clients import currency_balance, site_metadata
    from ..config import DEFAULT_CURRENCIES
    from ..storage import (
        get_profile_entry,
        sanitize_session_profile,
        set_token_for,
    )
    from .account import (
        connect_account,
        refresh_account,
        resolve_strategy_name,
    )
    from .engine_view import _maybe_profile_run, run_engine

    client, account = connect_account(token, args.currency, no_color=args.no_color, site=site)
    site_currencies = list(site_metadata(site).default_currencies) or list(DEFAULT_CURRENCIES)
    requested_currency = (
        args.currency or account.currency or site_currencies[0]
    ).upper()
    account = refresh_account(client, account, requested_currency)
    currency = account.currency.upper()
    account.currency = currency
    account.balance = currency_balance(account.balance_list, currency)

    if args.strategy:
        strategy_name = resolve_strategy_name(args.strategy, strategies)
    else:
        saved_strategy = str(settings_store.get("ui", {}).get("last_strategy") or "")
        strategy_name = saved_strategy if saved_strategy in strategies else strategies[0]
    profile_entry = get_profile_entry(settings_store, site, strategy_name, currency)
    profile = sanitize_session_profile(profile_entry)
    profile = apply_profile_args(profile, args)
    persist_runtime_profile(
        settings_store,
        strategy_name,
        currency,
        profile,
        site=site,
        last_strategy=strategy_name,
        last_currency=currency,
        last_site=site,
    )
    if not args.no_save_token and _site_requires_token(site):
        set_token_for(site, token)
    config = build_config(
        strategy_dir,
        strategies,
        settings_store,
        strategy_name,
        currency,
        profile,
        site=site,
    )
    _maybe_profile_run(
        getattr(args, "profile", None),
        run_engine,
        client,
        config,
        account,
        profile,
        sticky_footer=args.sticky_footer,
        quiet=args.quiet,
        no_color=args.no_color,
        confirm_quit=bool(getattr(args, "confirm_quit", True)),
        toast_enabled=bool(getattr(args, "toast", True)),
        json_log=(getattr(args, "log_format", "text") == "json"),
        write_report=bool(getattr(args, "write_report", True)),
    )
    return 0
