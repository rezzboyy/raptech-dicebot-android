"""Account connect/refresh helpers untuk CLI.

Diekstrak dari `cli/__init__.py` (Fase 2 perapihan, Step I-2).
Bridge antara `corebot.client` builder dan UI status output.

Public API (di-re-export oleh `cli/__init__.py`):
    - `connect_account(token, currency, *, no_color, site)`
    - `refresh_account(client, account, currency)`
    - `select_currency(account, default_currency, *, no_color, site)`
    - `resolve_strategy_name(value, strategies)`
"""
from __future__ import annotations

import sys
from pathlib import Path

from ..clients import BaseClient, build_account_snapshot, get_client_class, site_metadata
from ..config import DEFAULT_CURRENCIES, DEFAULT_SITE
from ..models import AccountSnapshot
from ..storage import get_proxy_for
from ..ui.theme import visible_len
from ._log import format_log_line
from ._state import get_theme


def _site_requires_token(site: str) -> bool:
    """Sinkron dengan helper di `cli/menu.py`."""
    try:
        client_cls = get_client_class(site)
    except Exception:
        return True
    return bool(getattr(client_cls, "requires_token", True))


def connect_account(
    token: str,
    currency: str | None = None,
    *,
    no_color: bool = False,
    site: str = DEFAULT_SITE,
) -> tuple[BaseClient, AccountSnapshot]:
    """Connect ke situs target. Tampilkan spinner sampai snapshot ready."""
    theme = get_theme()
    stdout_encoding = (getattr(sys.stdout, "encoding", None) or "").lower()
    spinner = (
        "|/-\\" if no_color or "utf" not in stdout_encoding
        else "\u2807\u280B\u2819\u2838\u28B0\u28E0\u28C4\u2846"
    )
    site_label = site_metadata(site).display_name
    msg_text = (
        f"Starting {site_label}"
        if not _site_requires_token(site)
        else f"Connecting to {site_label} API"
    )
    msg = theme.c(msg_text, "primary")
    sys.stdout.write(f"\r {spinner[0]} {msg}...")
    sys.stdout.flush()
    try:
        client_cls = get_client_class(site)
        proxy = get_proxy_for(site)
        # Client constructor accept proxy sebagai dict {"http": url, "https": url}
        # atau None. Semua client (Wolfbet, Pasino, Betfury, dll) sudah
        # support signature (token, proxy=None).
        client = client_cls(token, proxy=proxy) if proxy else client_cls(token)
        account = build_account_snapshot(client, currency, include_profile=True)
    finally:
        sys.stdout.write("\r" + " " * (visible_len(msg) + 8) + "\r")
        sys.stdout.flush()

    # === TEMPORARY DEBUG LOG ===
    import json
    print("\n=== LOGIN SUCCESS ===")
    print(f"User : {account.username or '-'}")
    print(f"Site : {site}")
    print("")
    print("=== RAW API RESPONSE ===")
    if hasattr(client, "_raw_frames") and client._raw_frames:
        masked_frames = []
        for frame in client._raw_frames:
            try:
                frame_str = json.dumps(frame)
                if len(token) > 20 and token in frame_str:
                    frame_str = frame_str.replace(token, token[:10] + "..." + token[-6:])
                masked_frames.append(json.loads(frame_str))
            except Exception:
                masked_frames.append(frame)
        print(json.dumps(masked_frames, indent=2))
    else:
        try:
            raw_info = {"profile": client.profile(), "balances": client.balances()}
            print(json.dumps(raw_info, indent=2))
        except Exception as e:
            print(f"Failed to fetch raw API info: {e}")
    print("")
    print("=== PARSED BALANCE ===")
    print(f"balance: {account.balance}")
    print(f"currency: {account.currency}")
    if hasattr(client, "_last_error") and client._last_error:
        print(f"Parsing/Connection Error: {client._last_error}")
    print("")

    print(format_log_line("success", "Account connected."))
    return client, account


def refresh_account(
    client: BaseClient,
    account: AccountSnapshot | None,
    currency: str | None = None,
) -> AccountSnapshot:
    """Refresh balance + currency tanpa load profile/stats lagi."""
    refreshed = build_account_snapshot(client, currency, include_profile=False)
    if account:
        refreshed.username = account.username
        refreshed.email = account.email
    return refreshed


def select_currency(
    account: AccountSnapshot,
    default_currency: str = "",
    *,
    no_color: bool = False,
    site: str = DEFAULT_SITE,
) -> str:
    """Tampilkan account status + prompt pilih currency."""
    # Lazy import untuk hindari import-cycle dengan menu.
    from .menu import print_account_status
    from .prompts import prompt_select

    site_currencies = list(site_metadata(site).default_currencies) or list(DEFAULT_CURRENCIES)
    options = [currency for currency, _amount in account.balance_list] or site_currencies
    default = default_currency or account.currency or options[0]
    print_account_status(account, no_color, site=site)
    return prompt_select(options, "Select coin:", default, no_color=no_color).upper()


def resolve_strategy_name(value: str | None, strategies: list[str]) -> str:
    """Cocokkan input strategy ke nama file di folder strategies/."""
    if not strategies:
        return ""
    if not value:
        return strategies[0]
    requested = Path(value).name
    for strategy in strategies:
        if strategy.lower() == requested.lower():
            return strategy
    raise RuntimeError(f"Strategy tidak ditemukan: {value}")
