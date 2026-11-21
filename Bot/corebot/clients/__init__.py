"""Client registry untuk multi-situs.

Tiap situs memiliki module sendiri di package ini dengan class yang
mengimplementasi `BaseClient` Protocol dari `base.py`. Tambahkan situs
baru dengan import + registrasi di `_CLIENT_LAZY` di bawah.

Fase 5.1 (perf plan): per-site client modules di-import lazy via
`get_client_class()` saat user benar-benar pilih situs. Ini menghindari
cost startup `curl_cffi` + `socketio` saat user cuma masuk menu utama
atau cek lisensi.
"""

from __future__ import annotations

from importlib import import_module

from .base import (
    BaseClient,
    SiteMetadata,
    balance_list_from_response,
    build_account_snapshot,
    currency_balance,
    resolve_currency,
)


_CLIENT_LAZY: dict[str, tuple[str, str]] = {
    "wolfbet": (".wolfbet", "WolfBetClient"),
    "faucetpay": (".faucetpay", "FaucetPayClient"),
    "paradice": (".paradice", "ParaDiceClient"),
    "jacksclub": (".jacksclub", "JacksClubClient"),
    "stake": (".stake", "StakeClient"),
    "dogepick": (".dogepick", "DogePickClient"),
    "tronpick": (".tronpick", "TronPickClient"),
    "nuts": (".nuts", "NutsClient"),
    "betfury": (".betfury", "BetfuryClient"),
    "pasino": (".pasino", "PasinoClient"),
    "testmode": (".testmode", "TestModeClient"),
}

_CLIENT_RESOLVED: dict[str, type] = {}


class _LazyRegistry(dict):
    """Dict-like â€” `key in registry` dan iterasi pakai slug saja, tapi
    `registry[key]` lazy-resolve module + return class."""

    def __init__(self):
        super().__init__()

    def __contains__(self, key) -> bool:  # type: ignore[override]
        return key in _CLIENT_LAZY

    def __iter__(self):
        return iter(_CLIENT_LAZY)

    def __len__(self) -> int:
        return len(_CLIENT_LAZY)

    def keys(self):  # type: ignore[override]
        return _CLIENT_LAZY.keys()

    def __getitem__(self, key):  # type: ignore[override]
        return get_client_class(key)

    def get(self, key, default=None):  # type: ignore[override]
        try:
            return get_client_class(key)
        except KeyError:
            return default


CLIENT_REGISTRY = _LazyRegistry()

COOKIE_BASED_SITES: frozenset[str] = frozenset({"dogepick", "tronpick"})
JWT_BASED_SITES: frozenset[str] = frozenset({"nuts", "betfury", "pasino"})


def get_client_class(site: str) -> type:
    """Ambil class client berdasarkan slug situs (lazy-import)."""
    key = (site or "").lower().strip()
    if key in _CLIENT_RESOLVED:
        return _CLIENT_RESOLVED[key]
    if key not in _CLIENT_LAZY:
        available = ", ".join(sorted(_CLIENT_LAZY)) or "(empty)"
        raise KeyError(f"Unknown site '{site}'. Available: {available}")
    mod_rel, cls_name = _CLIENT_LAZY[key]
    module = import_module(mod_rel, package=__name__)
    cls = getattr(module, cls_name)
    _CLIENT_RESOLVED[key] = cls
    return cls


def available_sites() -> list[str]:
    """Return list of production sites yang bisa dipilih user.

    Untuk main licensed bot: semua site tersedia.
    Untuk nolicense build: di-patch oleh `buildnolicense.py` supaya
    hanya return ["pasino", "wolfbet"].
    """
    return [
        "wolfbet",
        "pasino",
        "nuts",
        "betfury",
        "stake",
        "jacksclub",
        "paradice",
        "faucetpay",
        "dogepick",
        "tronpick",
        "testmode",
    ]


def site_metadata(site: str) -> SiteMetadata:
    """Return metadata dasar tanpa import module penuh.

    `display_name`, `default_currencies`, dan `min_bet` di-cache di
    `_SITE_META_OVERRIDES` untuk site umum supaya menu utama tidak
    paksa import module berat. Untuk site yang tidak ada override,
    fall back ke import + introspeksi class.
    """
    key = site.lower()
    override = _SITE_META_OVERRIDES.get(key)
    if override is not None:
        return SiteMetadata(
            slug=key,
            display_name=override["display_name"],
            default_currencies=tuple(override.get("default_currencies", ())),
            min_bet=float(override.get("min_bet", 1e-8)),
        )
    cls = get_client_class(site)
    return SiteMetadata(
        slug=key,
        display_name=getattr(cls, "display_name", site.title()),
        default_currencies=tuple(getattr(cls, "default_currencies", ())),
        min_bet=float(getattr(cls, "min_bet", 1e-8)),
    )


_SITE_META_OVERRIDES: dict[str, dict] = {
    "wolfbet": {"display_name": "Wolf.bet", "default_currencies": ("BTC", "DOGE", "TRX"), "min_bet": 1e-8},
    "faucetpay": {"display_name": "FaucetPay", "default_currencies": ("DOGE",), "min_bet": 1e-8},
    "paradice": {"display_name": "ParaDice", "default_currencies": ("BTC",), "min_bet": 1e-8},
    "jacksclub": {"display_name": "JacksClub", "default_currencies": ("BTC",), "min_bet": 1e-8},
    "stake": {"display_name": "Stake", "default_currencies": ("BTC",), "min_bet": 1e-8},
    "dogepick": {"display_name": "DogePick", "default_currencies": ("DOGE",), "min_bet": 1e-8},
    "tronpick": {"display_name": "TronPick", "default_currencies": ("TRX",), "min_bet": 1e-8},
    "nuts": {"display_name": "Nuts.gg", "default_currencies": ("BTC",), "min_bet": 1e-8},
    "betfury": {"display_name": "Betfury", "default_currencies": ("BTC",), "min_bet": 1e-8},
    "pasino": {"display_name": "Pasino", "default_currencies": ("GEM", "BTC", "ETH", "USDT", "TRX", "DOGE", "LTC", "BCH", "POL", "BNB", "SOL", "XRP"), "min_bet": 1e-8},
    "testmode": {"display_name": "Test Mode", "default_currencies": ("BTC",), "min_bet": 1e-8},
}


def __getattr__(name: str):
    """Module-level lazy attribute: `from corebot.clients import WolfBetClient`
    tetap bekerja, tapi import-nya baru terjadi saat akses pertama.
    """
    for slug, (_mod, cls_name) in _CLIENT_LAZY.items():
        if cls_name == name:
            return get_client_class(slug)
    raise AttributeError(f"module 'corebot.clients' has no attribute {name!r}")


__all__ = [
    "BaseClient",
    "SiteMetadata",
    "CLIENT_REGISTRY",
    "COOKIE_BASED_SITES",
    "JWT_BASED_SITES",
    "get_client_class",
    "available_sites",
    "site_metadata",
    "balance_list_from_response",
    "build_account_snapshot",
    "currency_balance",
    "resolve_currency",
]
