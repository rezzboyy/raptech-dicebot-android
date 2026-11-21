"""Live crypto price fetcher (harga coin → IDR).

Ambil harga real-time dari CoinGecko public API. Sumber utama:
  https://api.coingecko.com/api/v3/simple/price?ids={coin_id}&vs_currencies=idr

Public API — tidak butuh API key, rate limit ~30 req/menit.
Cache in-memory 60 detik supaya tidak spam.

Contoh pakai:
    from corebot.pricing import get_price_idr, format_idr, sol_to_idr

    price = get_price_idr("SOL")           # -> 2_469_135.0 (Rp per 1 SOL)
    rp    = sol_to_idr(0.05, symbol="SOL") # -> 123_456.75
    text  = format_idr(rp)                 # -> "Rp 123.457"
"""
from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.request

COINGECKO_URL = "https://api.coingecko.com/api/v3/simple/price"
CACHE_TTL_SECONDS = 60.0
REQUEST_TIMEOUT = 8.0

# Peta symbol (uppercase) -> CoinGecko id.
# Coin utama di daftar bot ditambahkan di sini.
_COIN_MAP: dict[str, str] = {
    "BTC":  "bitcoin",
    "ETH":  "ethereum",
    "LTC":  "litecoin",
    "BCH":  "bitcoin-cash",
    "XRP":  "ripple",
    "DOGE": "dogecoin",
    "TRX":  "tron",
    "SOL":  "solana",
    "USDT": "tether",
    "USDC": "usd-coin",
    "BNB":  "binancecoin",
    "POL":  "polygon-ecosystem-token",   # (ex-MATIC)
    "MATIC": "polygon-ecosystem-token",
    "GEM":  "gem",                       # Pasino internal token (may not exist)
    "BTTC": "bittorrent",
    "BTT":  "bittorrent",
    "FEY":  "feyorra",
    "BFG":  "betfury",
}

# Cache: symbol_upper -> (price_idr, timestamp)
_cache: dict[str, tuple[float, float]] = {}
_cache_lock = threading.Lock()


def _fetch_prices(coin_ids: list[str]) -> dict[str, float]:
    """POST-less GET ke CoinGecko. Return {coin_id: price_idr}."""
    if not coin_ids:
        return {}
    ids_param = ",".join(coin_ids)
    url = f"{COINGECKO_URL}?ids={ids_param}&vs_currencies=idr"
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "RaptechBot/1.0 (harga IDR fetcher)",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError):
        return {}
    except json.JSONDecodeError:
        return {}

    result: dict[str, float] = {}
    if isinstance(data, dict):
        for cid, node in data.items():
            if isinstance(node, dict):
                val = node.get("idr")
                if isinstance(val, (int, float)):
                    result[cid] = float(val)
    return result


def get_price_idr(symbol: str) -> float | None:
    """Return harga 1 unit `symbol` dalam IDR. None kalau tidak diketahui / gagal fetch.

    Cache 60 detik per symbol. Thread-safe.
    """
    sym = (symbol or "").upper().strip()
    if not sym:
        return None
    coin_id = _COIN_MAP.get(sym)
    if not coin_id:
        return None

    now = time.monotonic()
    with _cache_lock:
        cached = _cache.get(sym)
        if cached is not None:
            price, ts = cached
            if now - ts < CACHE_TTL_SECONDS:
                return price

    # Fetch (di luar lock supaya tidak block thread lain)
    prices = _fetch_prices([coin_id])
    price = prices.get(coin_id)

    with _cache_lock:
        if price is not None:
            _cache[sym] = (price, now)
        else:
            # Kalau fetch gagal tapi cache lama masih ada, pakai yang lama
            cached = _cache.get(sym)
            if cached is not None:
                return cached[0]
    return price


def get_prices_idr(symbols: list[str]) -> dict[str, float]:
    """Fetch harga beberapa symbol sekaligus (1 request ke CoinGecko).

    Return dict {SYMBOL: price_idr}. Symbol yang tidak diketahui atau gagal
    di-skip dari hasil.
    """
    symbols_up = [(s or "").upper().strip() for s in symbols]
    now = time.monotonic()
    result: dict[str, float] = {}
    need_fetch: list[str] = []
    coin_id_to_sym: dict[str, str] = {}

    with _cache_lock:
        for sym in symbols_up:
            if not sym:
                continue
            cid = _COIN_MAP.get(sym)
            if not cid:
                continue
            cached = _cache.get(sym)
            if cached is not None and (now - cached[1]) < CACHE_TTL_SECONDS:
                result[sym] = cached[0]
            else:
                need_fetch.append(cid)
                coin_id_to_sym[cid] = sym

    if need_fetch:
        fetched = _fetch_prices(need_fetch)
        with _cache_lock:
            for cid, price in fetched.items():
                sym = coin_id_to_sym.get(cid)
                if sym:
                    _cache[sym] = (price, now)
                    result[sym] = price
            # Fallback ke cache lama kalau ada
            for cid, sym in coin_id_to_sym.items():
                if sym not in result:
                    old = _cache.get(sym)
                    if old is not None:
                        result[sym] = old[0]

    return result


def coin_to_idr(amount: float, symbol: str) -> float | None:
    """Convert jumlah coin ke IDR. Return None kalau harga tidak tersedia."""
    price = get_price_idr(symbol)
    if price is None:
        return None
    try:
        return float(amount) * price
    except (TypeError, ValueError):
        return None


def format_idr(amount: float | None, *, prefix: str = "Rp ", sign: bool = False) -> str:
    """Format nilai IDR ke string dengan pemisah ribuan titik.

    Contoh:
        format_idr(1234567.89)              -> "Rp 1.234.568"
        format_idr(-500)                     -> "Rp -500"
        format_idr(1500, sign=True)          -> "Rp +1.500"
        format_idr(None)                     -> "-"

    Args:
        amount: nilai IDR. None → return "-".
        prefix: prefix (default "Rp ").
        sign:   True → selalu tampilkan +/- di depan angka.
    """
    if amount is None:
        return "-"
    try:
        val = float(amount)
    except (TypeError, ValueError):
        return "-"

    # Bulatkan ke rupiah utuh (tidak ada sen di IDR)
    rounded = int(round(val))
    is_neg = rounded < 0
    abs_str = f"{abs(rounded):,}".replace(",", ".")
    if is_neg:
        return f"{prefix}-{abs_str}"
    if sign and rounded > 0:
        return f"{prefix}+{abs_str}"
    return f"{prefix}{abs_str}"


def clear_cache() -> None:
    """Force clear cache — dipakai kalau user ingin refresh harga manual."""
    with _cache_lock:
        _cache.clear()


def is_supported(symbol: str) -> bool:
    """Cek apakah symbol punya mapping ke CoinGecko id."""
    return (symbol or "").upper().strip() in _COIN_MAP
