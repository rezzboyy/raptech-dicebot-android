"""Kontrak generik untuk client situs gambling/dice.

Engine memanggil method berikut dari client aktif:
  - balances()      -> dict berisi list saldo per coin
  - stats()         -> dict statistik akun (boleh kosong jika API tak punya)
  - profile()       -> dict profil user (username/email/dll)
  - place_bet(currency, amount, chance, bethigh) -> dict shape:
        {
          "bet":  {"amount": float, "state": "win"|"lose", "result_value": float, "profit": float},
          "userBalance": {"amount": float},
        }
  - reset_seed()    -> dict (boleh dummy untuk situs yang tak support)

Tiap class client juga harus expose class-attribute:
  - display_name: str            (untuk UI)
  - default_currencies: tuple/list[str]
  - min_bet: float               (default sizing minimal)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from ..models import AccountSnapshot


@dataclass(frozen=True, slots=True)
class SiteMetadata:
    slug: str
    display_name: str
    default_currencies: tuple[str, ...]
    min_bet: float


@runtime_checkable
class BaseClient(Protocol):
    """Kontrak minimum yang harus dipenuhi oleh tiap site client."""

    display_name: str
    default_currencies: tuple[str, ...]
    min_bet: float

    def balances(self) -> dict: ...

    def stats(self) -> dict: ...

    def profile(self) -> dict: ...

    def place_bet(self, currency: str, amount: float, chance: float, bethigh: bool) -> dict: ...

    def reset_seed(self) -> dict: ...


# ---------- Helper umum (site-agnostic) -----------------------------------
# Helper di bawah ini bekerja di atas struktur dict generik.
# Tiap client bertanggung jawab menormalisasi response native situs ke
# bentuk yang dipahami helper ini. Untuk Wolf.bet itu cukup, untuk situs
# lain mungkin perlu transform di sisi client sebelum return.


def balance_list_from_response(balances: dict) -> list[tuple[str, float]]:
    """Ambil list (currency, amount) dari response generic balances dict.

    Response harus punya bentuk: {"balances": [{"currency": "...", "amount": "..."}, ...]}.
    """
    items: list[tuple[str, float]] = []
    for item in balances.get("balances", []):
        currency = str(item.get("currency", "")).upper()
        if not currency:
            continue
        try:
            amount = float(item.get("amount", 0))
        except (TypeError, ValueError):
            amount = 0.0
        items.append((currency, amount))
    return items


def currency_balance(balance_list: list[tuple[str, float]], currency: str) -> float:
    for current, amount in balance_list:
        if current.upper() == currency.upper():
            return amount
    return 0.0


def resolve_currency(
    balance_list: list[tuple[str, float]],
    preferred: str | None = None,
    *,
    fallback: str = "BTC",
) -> str:
    if preferred:
        preferred = preferred.upper()
        for current, _amount in balance_list:
            if current.upper() == preferred:
                return preferred
    for current, amount in balance_list:
        if amount > 0:
            return current
    if balance_list:
        return balance_list[0][0]
    return fallback


def build_account_snapshot(
    client: BaseClient,
    currency: str | None = None,
    *,
    include_profile: bool = True,
) -> AccountSnapshot:
    """Bangun AccountSnapshot generik dari kombinasi profile + balances + stats.

    Bentuk respons stats Wolfbet: {"dice": {"<coin_lower>": {...}}}.
    Untuk situs yang tidak punya stats per-coin, return {} dari `stats()`
    -> snapshot akan dibuat dengan total bets/wins/losses 0.
    """
    profile_data = client.profile() if include_profile else {}
    user_node = (
        profile_data.get("user", profile_data) if isinstance(profile_data, dict) else {}
    )
    balances = client.balances()
    balance_list = balance_list_from_response(balances)
    fallback_currency = (
        getattr(client, "default_currencies", None) or ("BTC",)
    )[0]
    resolved_currency = resolve_currency(balance_list, currency, fallback=fallback_currency)
    stats = client.stats() or {}
    stats_node = (stats.get("dice", {}) or {}).get(resolved_currency.lower(), {}) or {}
    return AccountSnapshot(
        username=str(
            user_node.get("login")
            or user_node.get("username")
            or user_node.get("name")
            or ""
        ),
        email=str(user_node.get("email") or ""),
        currency=resolved_currency,
        balance=currency_balance(balance_list, resolved_currency),
        balance_list=balance_list,
        total_bets=int(stats_node.get("total_bets", 0) or 0),
        total_wins=int(stats_node.get("win", 0) or 0),
        total_losses=int(stats_node.get("lose", 0) or 0),
        total_profit=float(stats_node.get("profit", 0) or 0),
        total_wagered=float(
            stats_node.get("waggered", stats_node.get("wagered", 0)) or 0
        ),
    )
