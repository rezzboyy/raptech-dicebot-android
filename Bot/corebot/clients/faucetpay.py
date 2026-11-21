"""FaucetPay client implementation.

Diadaptasi dari `clientfauchetpay.py` (standalone CLI) ke kontrak
`BaseClient` agar engine Corebot bisa pakai tanpa modifikasi.

Catatan:
- FaucetPay mendukung 2 mode auth:
    * API Bearer token (utama, recommended)
    * Cookie session (legacy, fallback)
  Untuk integrasi sini, kita pakai Bearer token saja agar UX seragam
  dengan Wolfbet.
- Response native FaucetPay bentuknya beragam. `place_bet()` di sini
  membungkus `place_dice_bet` + `parse_bet_result` lalu menormalisasi
  keluaran ke shape Wolfbet (`{"bet": {...}, "userBalance": {...}}`)
  agar engine ngga butuh tahu ini situs apa.

Token keep-alive (delay idle timeout):
  FaucetPay TIDAK punya endpoint refresh-token publik. Login flow
  butuh CAPTCHA puzzle slider + 2FA, jadi auto-login tidak praktis.
  Solusi pragmatis: background heartbeat thread yang panggil endpoint
  ringan `/wallet/get-information` (sudah dipakai untuk get balance)
  setiap N detik. Tujuan: reset idle-timeout server-side supaya server
  tidak invalidate token karena dianggap session idle.

  Heartbeat tidak mencegah expiry karena security event (force rotate
  oleh server) tapi observasi user "expired tiba-tiba random" mengarah
  ke idle-timeout sebagai penyebab utama.

  Override interval via env var `FAUCETPAY_HEARTBEAT_INTERVAL` (detik).
"""

from __future__ import annotations

import json
import os
import re
import threading
import time
from decimal import Decimal, InvalidOperation, ROUND_DOWN, ROUND_UP

from ..http_client import build_http_session


BASE_URL = "https://faucetpay.io"
API_BASE_URL = "https://api.faucetpay.io"
BALANCE_SCALE = 1_000_000
DEFAULT_BASEBET_FALLBACK = 0.00000001

# Heartbeat keep-alive: panggil endpoint authenticated ringan tiap N detik
# supaya server tidak idle-out token. Default 240s (4 menit). User bisa
# override via env supaya tuning tanpa edit kode.
def _heartbeat_interval_seconds() -> int:
    raw = os.getenv("FAUCETPAY_HEARTBEAT_INTERVAL", "240").strip()
    try:
        value = int(raw)
    except ValueError:
        return 240
    return max(30, value)  # minimum 30s biar tidak spam server


HEARTBEAT_PATH = "/wallet/get-information"

COIN_META_KEYS = {
    "SUCCESS",
    "MESSAGE",
    "DATA",
    "NAME",
    "IMAGE",
    "PRICE",
    "BALANCE",
    "COIN",
    "STATISTICS",
    "ERROR",
    "STATUS",
    "RESULT",
    "CODE",
}


class InsufficientFundsError(RuntimeError):
    """Dibanting saat saldo tidak cukup."""


class AuthTokenExpiredError(RuntimeError):
    """Dibanting saat token Bearer ditolak / kadaluarsa."""


def _to_decimal(value, default: str = "0") -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal(default)
    if not result.is_finite():
        return Decimal(default)
    return result


def _quantize_down(value, places: int) -> Decimal:
    quant = Decimal("1").scaleb(-int(places))
    return _to_decimal(value).quantize(quant, rounding=ROUND_DOWN)


def _format_decimal_down(value, places: int) -> str:
    return f"{_quantize_down(value, places):.{int(places)}f}"


def _quantize_up(value, places: int) -> Decimal:
    quant = Decimal("1").scaleb(-int(places))
    return _to_decimal(value).quantize(quant, rounding=ROUND_UP)


def _format_decimal_up(value, places: int) -> str:
    return f"{_quantize_up(value, places):.{int(places)}f}"


def _normalize_coin_symbol(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip().upper()
    if not text:
        return None
    if re.fullmatch(r"[A-Z0-9]{2,10}", text):
        return text
    return None


def _normalize_bearer_token(token) -> str | None:
    if token is None:
        return None
    raw = str(token).strip()
    if not raw:
        return None
    if raw.lower().startswith("bearer "):
        raw = raw[7:].strip()
    return raw or None


def _extract_number(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).replace(",", "")
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    if not match:
        return None
    try:
        return float(match.group(0))
    except Exception:
        return None


def _decode_json_like(text):
    if text is None:
        return None
    raw = text.strip()
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        pass
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end <= start:
        return None
    candidate = raw[start : end + 1]
    try:
        return json.loads(candidate)
    except Exception:
        pass
    fixed = re.sub(r"([{,]\s*)([A-Za-z_][A-Za-z0-9_]*)\s*:", r'\1"\2":', candidate)
    fixed = fixed.replace("'", '"')
    try:
        return json.loads(fixed)
    except Exception:
        return None


def _is_win_from_roll(roll: float, chance: float, bethigh: bool) -> bool:
    if bethigh:
        return roll > (100.0 - chance)
    return roll < chance


class FaucetPayClient:
    """Client FaucetPay untuk dice game.

    Kompatibel dengan kontrak `BaseClient`:
      balances(), stats(), profile(), place_bet(), reset_seed().

    Internal logic mengikuti `place_dice_bet` di source asli, dengan
    normalisasi output ke shape Wolfbet:
      {"bet": {...}, "userBalance": {...}}
    """

    display_name: str = "FaucetPay"
    default_currencies: tuple[str, ...] = (
        "FEY",
        "BTC",
        "ETH",
        "LTC",
        "DOGE",
        "TRX",
        "BCH",
        "XRP",
        "USDT",
        "USDC",
    )
    min_bet: float = DEFAULT_BASEBET_FALLBACK

    def __init__(
        self,
        token: str | None = None,
        proxy: dict[str, str] | None = None,
        *,
        coin: str = "FEY",
    ):
        self.base_url = BASE_URL.rstrip("/")
        self.api_base_url = API_BASE_URL.rstrip("/")
        self.coin = (_normalize_coin_symbol(coin) or "FEY")
        self.api_token: str | None = None
        # Shared HTTP factory — auto pilih backend sesuai env
        self.session, self._http_backend = build_http_session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/145.0.0.0 Safari/537.36"
                ),
                "X-Requested-With": "XMLHttpRequest",
                "Origin": self.base_url,
                "Referer": f"{self.base_url}/dice",
            }
        )
        if proxy:
            self.session.proxies.update(proxy)

        self.selected_payload_index: int | None = None
        self.last_balance: float | None = None
        self.last_wallet_payload: dict | None = None
        self.min_bet_by_coin: dict[str, Decimal] = {}

        # Heartbeat keep-alive state. Thread di-start saat token pertama
        # di-set (bisa dari __init__ ini, atau dari set_api_token() later).
        # Daemon thread, jadi otomatis ke-kill saat interpreter exit.
        self._heartbeat_stop = threading.Event()
        self._heartbeat_thread: threading.Thread | None = None

        if token:
            self.set_api_token(token)

    def set_api_token(self, token: str) -> str:
        normalized = _normalize_bearer_token(token)
        if not normalized:
            raise ValueError("Bearer token kosong atau tidak valid.")
        self.api_token = normalized
        # Start heartbeat sekali setelah token tersedia. _ensure_heartbeat
        # idempotent — kalau thread sudah jalan, no-op.
        self._ensure_heartbeat_running()
        return self.api_token

    def set_coin(self, coin: str) -> str:
        normalized = _normalize_coin_symbol(coin)
        if normalized:
            self.coin = normalized
        return self.coin

    def payout_factor(self) -> float:
        return 95.0 if self.api_token else 99.0

    def max_winning_chance(self) -> float:
        return 94.99 if self.api_token else 98.0

    def normalize_chance(self, chance: float) -> float:
        try:
            value = float(chance)
        except Exception:
            value = 49.5
        return max(0.01, min(self.max_winning_chance(), value))

    def _api_headers(self) -> dict:
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json",
            "Origin": self.base_url,
            "Referer": f"{self.base_url}/",
        }
        if self.api_token:
            headers["Authorization"] = f"Bearer {self.api_token}"
        return headers

    def _api_request(self, method: str, path: str, payload: dict | None = None) -> dict:
        kwargs = {"headers": self._api_headers(), "timeout": 30}
        if payload is not None:
            kwargs["json"] = payload
        resp = self.session.request(method, f"{self.api_base_url}{path}", **kwargs)
        if resp.status_code >= 400:
            snippet = (resp.text or "")[:240].replace("\n", " ").strip()
            if self.api_token and (
                resp.status_code in (401, 403)
                or self._is_auth_token_error_message(snippet)
            ):
                raise AuthTokenExpiredError(
                    f"HTTP {resp.status_code} for {path}: {snippet}"
                )
            raise RuntimeError(f"HTTP {resp.status_code} for {path}: {snippet}")
        obj = _decode_json_like(resp.text)
        if isinstance(obj, dict):
            return obj
        snippet = (resp.text or "")[:240].replace("\n", " ").strip()
        raise RuntimeError(f"Unexpected response from {path}: {snippet}")

    @staticmethod
    def _message_from_api(data) -> str | None:
        if not isinstance(data, dict):
            return None
        msg = (
            data.get("message")
            or data.get("mes")
            or data.get("error_description")
            or data.get("error")
        )
        if isinstance(msg, str):
            return msg
        if msg is not None:
            try:
                return json.dumps(msg, ensure_ascii=False)
            except Exception:
                return str(msg)
        errors = data.get("errors")
        if errors is not None:
            try:
                return json.dumps(errors, ensure_ascii=False)
            except Exception:
                return str(errors)
        return None

    @staticmethod
    def _is_insufficient_funds_message(message) -> bool:
        if not message:
            return False
        text = str(message).strip().lower()
        markers = (
            "not enough funds",
            "insufficient funds",
            "insufficient balance",
            "balance is too low",
            "do not have enough funds",
        )
        return any(m in text for m in markers)

    @staticmethod
    def _is_auth_token_error_message(message) -> bool:
        if not message:
            return False
        text = str(message).strip().lower()
        markers = (
            "unauthorized",
            "forbidden",
            "invalid token",
            "invalid jwt",
            "jwt expired",
            "token expired",
            "token is expired",
            "token is invalid",
            "expired token",
            "authentication failed",
            "invalid authorization",
            "not authenticated",
            "access denied",
        )
        return any(m in text for m in markers)

    @staticmethod
    def _is_success_response(data) -> bool:
        if not isinstance(data, dict):
            return False
        ret = data.get("ret")
        if ret in (1, True, "1"):
            return True
        if "success" in data:
            return bool(data.get("success"))
        if "ok" in data:
            return bool(data.get("ok"))
        status = data.get("status")
        if isinstance(status, str):
            n = status.strip().lower()
            if n in ("success", "ok", "true", "1"):
                return True
            if n in ("error", "failed", "fail", "false", "0"):
                return False
        elif isinstance(status, (bool, int, float)):
            return bool(status)
        if data.get("error") or data.get("errors"):
            return False
        if data.get("code") in (200, 201):
            return True
        if data.get("data") is not None or data.get("result") is not None:
            return True
        return True

    @staticmethod
    def _normalize_units(value):
        if value is None:
            return None
        try:
            number = float(value)
        except Exception:
            return None
        if abs(number) >= 10000 and number.is_integer():
            return number / BALANCE_SCALE
        return number

    @staticmethod
    def _iter_objects(value):
        if isinstance(value, dict):
            yield value
            for nested in value.values():
                yield from FaucetPayClient._iter_objects(nested)
        elif isinstance(value, list):
            for nested in value:
                yield from FaucetPayClient._iter_objects(nested)

    @staticmethod
    def _pick_number(obj, keys):
        if not isinstance(obj, dict):
            return None
        for key in keys:
            if key not in obj:
                continue
            number = _extract_number(obj.get(key))
            if number is not None:
                return number
        return None

    @staticmethod
    def _pick_bool(obj, keys):
        if not isinstance(obj, dict):
            return None
        for key in keys:
            if key not in obj:
                continue
            value = obj.get(key)
            if isinstance(value, bool):
                return value
            if isinstance(value, (int, float)):
                return bool(value)
            if isinstance(value, str):
                low = value.strip().lower()
                if low in ("true", "win", "won", "success", "1", "yes"):
                    return True
                if low in ("false", "lose", "lost", "failed", "0", "no"):
                    return False
        return None

    def _coin_min_bet(self) -> Decimal:
        coin = _normalize_coin_symbol(self.coin)
        if not coin:
            return Decimal(str(DEFAULT_BASEBET_FALLBACK))
        return self.min_bet_by_coin.get(coin, Decimal(str(DEFAULT_BASEBET_FALLBACK)))

    def _update_coin_min_bet_from_message(self, message):
        if not message:
            return None
        match = re.search(
            r"at least\s+([0-9]+(?:\.[0-9]+)?)", str(message), flags=re.IGNORECASE
        )
        if not match:
            return None
        amount = _to_decimal(match.group(1))
        if amount <= 0:
            return None
        coin = _normalize_coin_symbol(self.coin)
        if coin:
            current = self.min_bet_by_coin.get(coin)
            if current is None or amount > current:
                self.min_bet_by_coin[coin] = amount
        return amount

    def _normalize_bet_amount(self, amount: float) -> float:
        amount_dec = _to_decimal(amount, str(DEFAULT_BASEBET_FALLBACK))
        min_bet = self._coin_min_bet()
        if amount_dec < min_bet:
            amount_dec = min_bet
        amount_text = _format_decimal_up(amount_dec, 8)
        amount_dec = _to_decimal(amount_text)
        if amount_dec < min_bet:
            amount_text = _format_decimal_up(min_bet, 8)
            amount_dec = _to_decimal(amount_text)
        return float(amount_dec)

    def _extract_balance_from_api(self, payload):
        coin = (self.coin or "").upper()
        for obj in self._iter_objects(payload):
            if not isinstance(obj, dict):
                continue
            coin_name = str(
                obj.get("coin") or obj.get("symbol") or obj.get("currency") or ""
            ).upper()
            if coin and coin_name and coin_name == coin:
                number = self._pick_number(
                    obj,
                    ("balance", "available_balance", "wallet_balance", "amount", "value"),
                )
                if number is not None:
                    return self._normalize_units(number)

        generic_keys = (
            "balance",
            "wallet_balance",
            "available_balance",
            "coin_balance",
            "fey_balance",
            "amount",
            "value",
        )
        for obj in self._iter_objects(payload):
            number = self._pick_number(obj, generic_keys)
            if number is not None:
                return self._normalize_units(number)
        return None

    def _extract_coin_catalog_from_api(self, payload):
        balance_keys = (
            "balance",
            "available_balance",
            "wallet_balance",
            "coin_balance",
            "amount",
            "value",
        )
        catalog: dict[str, dict] = {}

        def _register(symbol, balance=None):
            code = _normalize_coin_symbol(symbol)
            if not code or code in COIN_META_KEYS:
                return
            item = catalog.get(code)
            if item is None:
                item = {"coin": code, "balance": None}
                catalog[code] = item
            if balance is not None:
                item["balance"] = self._normalize_units(balance)

        def _scan_symbol_map(mapping):
            if not isinstance(mapping, dict):
                return
            for key, value in mapping.items():
                key_symbol = _normalize_coin_symbol(key)
                if not key_symbol or key_symbol in COIN_META_KEYS:
                    continue
                if isinstance(value, dict):
                    balance = self._pick_number(value, balance_keys)
                else:
                    balance = _extract_number(value)
                if balance is None:
                    continue
                _register(key_symbol, balance)

        for obj in self._iter_objects(payload):
            if not isinstance(obj, dict):
                continue
            direct_symbol = _normalize_coin_symbol(
                obj.get("coin")
                or obj.get("symbol")
                or obj.get("currency")
                or obj.get("ticker")
                or obj.get("code")
                or obj.get("asset")
            )
            if direct_symbol:
                balance = self._pick_number(obj, balance_keys)
                _register(direct_symbol, balance)
                continue
            bucket_hit = False
            for bucket in ("balances", "wallet", "wallets", "coins", "assets"):
                bucket_value = obj.get(bucket)
                if isinstance(bucket_value, dict):
                    _scan_symbol_map(bucket_value)
                    bucket_hit = True
                elif isinstance(bucket_value, list):
                    for entry in bucket_value:
                        if not isinstance(entry, dict):
                            continue
                        symbol = _normalize_coin_symbol(
                            entry.get("coin")
                            or entry.get("symbol")
                            or entry.get("currency")
                            or entry.get("ticker")
                            or entry.get("code")
                            or entry.get("asset")
                        )
                        if not symbol or symbol in COIN_META_KEYS:
                            continue
                        _register(symbol, self._pick_number(entry, balance_keys))
                    bucket_hit = True
            if bucket_hit:
                continue
            _scan_symbol_map(obj)

        items = list(catalog.values())
        items.sort(key=lambda x: (0 if (x.get("balance") or 0) > 0 else 1, x["coin"]))
        return items

    def _fetch_wallet(self) -> dict:
        data = self._api_request("GET", "/wallet/get-information")
        self.last_wallet_payload = data
        return data

    # ---- Heartbeat keep-alive --------------------------------------------

    def _ensure_heartbeat_running(self) -> None:
        """Start heartbeat thread kalau belum jalan. Idempotent."""
        if self._heartbeat_thread is not None and self._heartbeat_thread.is_alive():
            return
        if not self.api_token:
            return  # tidak start tanpa token
        self._heartbeat_stop.clear()
        thread = threading.Thread(
            target=self._heartbeat_loop,
            name="faucetpay-keepalive",
            daemon=True,
        )
        thread.start()
        self._heartbeat_thread = thread

    def _heartbeat_loop(self) -> None:
        """Loop keep-alive: tunggu N detik, ping endpoint ringan, ulang.

        Pakai `self._fetch_wallet()` (GET /wallet/get-information) sebagai
        ping karena:
          1. Endpoint authenticated -> reset idle-timer server-side
          2. Sudah ada di codebase, tidak perlu endpoint baru
          3. Response ringan (~600-1000 byte)

        Kalau ping kembali AuthTokenExpiredError, stop thread supaya tidak
        spam server. Bet berikutnya akan trigger error normal yang
        di-handle engine.
        """
        interval = _heartbeat_interval_seconds()
        while not self._heartbeat_stop.wait(interval):
            if not self.api_token:
                # Token sudah dihapus / direset, exit thread.
                break
            try:
                self._fetch_wallet()
            except AuthTokenExpiredError:
                # Token expired dari server. Stop heartbeat — tidak ada
                # gunanya retry tanpa token baru. Engine akan detect saat
                # next bet via place_bet().
                break
            except Exception:
                # Network error / temporary glitch — silent, retry next
                # tick. Heartbeat tidak boleh crash.
                pass

    def _stop_heartbeat(self) -> None:
        """Sinyal shutdown ke heartbeat thread + tunggu join singkat."""
        self._heartbeat_stop.set()
        thread = self._heartbeat_thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=2.0)
        self._heartbeat_thread = None

    def close(self) -> None:
        """Graceful shutdown. Stop heartbeat thread."""
        self._stop_heartbeat()

    def __del__(self):
        # Best-effort cleanup. Daemon thread otomatis ke-kill saat
        # interpreter exit, tapi explicit stop lebih cepat.
        try:
            self._stop_heartbeat()
        except Exception:
            pass

    # ---- API logic --------------------------------------------------------

    def _build_api_payload_candidates(self, amount: float, chance: float, bethigh: bool):
        chance = self.normalize_chance(chance)
        payout_factor = self.payout_factor()
        bet_type = "2" if bethigh else "1"
        seed = f"{int(time.time() * 1000):x}{os.getpid():x}"
        amount_value = self._normalize_bet_amount(amount)
        amount_text = _format_decimal_up(amount_value, 8)
        amount_dec = _to_decimal(amount_text)

        chance_text = _format_decimal_down(max(0.01, chance), 2)
        chance_dec = _to_decimal(chance_text)
        payout_dec = _to_decimal(payout_factor) / chance_dec
        if payout_dec < Decimal("1.0001"):
            payout_dec = Decimal("1.0001")
        payout_text = _format_decimal_down(payout_dec, 5)
        payout_dec = _to_decimal(payout_text)
        payout_value = max(1.0001, float(payout_text))

        profit_dec = amount_dec * max(Decimal("0"), payout_dec - Decimal("1"))
        if profit_dec < Decimal("0.00000001"):
            profit_dec = Decimal("0.00000001")
        profit_text = _format_decimal_down(profit_dec, 8)
        profit_estimate = float(profit_text)

        base = {
            "client_seed": seed,
            "coin": self.coin,
            "bet_amt": amount_text,
            "winning_chance": chance_text,
            "payout": payout_text,
            "profit": profit_text,
            "type": bet_type,
        }
        return [
            dict(base),
            {**base, "type": int(bet_type)},
            {**base, "bet_amt": amount_value},
            {
                **base,
                "winning_chance": float(chance_text),
                "payout": payout_value,
                "profit": profit_estimate,
            },
        ]

    def _place_dice_bet_raw(self, amount: float, chance: float, bethigh: bool) -> dict:
        if not self.api_token:
            raise RuntimeError(
                "FaucetPay API token belum di-set. Pakai set_api_token() dulu."
            )
        amount = self._normalize_bet_amount(amount)
        chance = self.normalize_chance(chance)
        retried_for_minimum = False
        while True:
            candidates = self._build_api_payload_candidates(amount, chance, bethigh)
            last_error = None
            rejected = []
            retry_with_amount: float | None = None
            for idx, payload in enumerate(candidates):
                try:
                    data = self._api_request("POST", "/dice/play", payload=payload)
                except Exception as exc:
                    if isinstance(exc, AuthTokenExpiredError):
                        raise
                    if self._is_insufficient_funds_message(exc):
                        raise InsufficientFundsError(str(exc))
                    minimum = self._update_coin_min_bet_from_message(exc)
                    if (
                        minimum is not None
                        and not retried_for_minimum
                        and minimum > _to_decimal(amount)
                    ):
                        retry_with_amount = float(minimum)
                        last_error = None
                        break
                    last_error = f"Payload {idx + 1} failed: {exc}"
                    rejected.append(last_error)
                    continue
                if self._is_success_response(data):
                    return data
                msg = self._message_from_api(data)
                if msg:
                    if self._is_auth_token_error_message(msg):
                        raise AuthTokenExpiredError(str(msg))
                    if self._is_insufficient_funds_message(msg):
                        raise InsufficientFundsError(str(msg))
                    minimum = self._update_coin_min_bet_from_message(msg)
                    if (
                        minimum is not None
                        and not retried_for_minimum
                        and minimum > _to_decimal(amount)
                    ):
                        retry_with_amount = float(minimum)
                        last_error = None
                        break
                    last_error = f"Payload {idx + 1} rejected: {msg}"
                else:
                    last_error = f"Payload {idx + 1} rejected: {data}"
                rejected.append(last_error)
            if retry_with_amount is not None:
                amount = self._normalize_bet_amount(retry_with_amount)
                retried_for_minimum = True
                continue
            if rejected:
                condensed = " | ".join(rejected[-3:])
                raise RuntimeError(condensed)
            raise RuntimeError(last_error or "Unable to place bet: no accepted payload.")

    def _parse_bet_result(self, data: dict, fallback_amount: float, chance: float, bethigh: bool):
        containers = []
        if isinstance(data, dict):
            containers.append(data)
            for key in ("data", "result", "bet", "bet_data", "payload"):
                value = data.get(key)
                if isinstance(value, dict):
                    containers.append(value)

        placed_amount = None
        for obj in containers:
            placed_amount = self._pick_number(
                obj, ("bet_amt", "bet_amount", "amount", "wager", "stake")
            )
            if placed_amount is not None and placed_amount > 0:
                break
        if placed_amount is None or placed_amount <= 0:
            placed_amount = float(fallback_amount)

        roll = None
        for obj in containers:
            roll = self._pick_number(
                obj, ("roll", "number", "num", "lucky_number", "result_number")
            )
            if roll is not None:
                break
        if roll is None:
            roll = 0.0

        win = None
        for obj in containers:
            win = self._pick_bool(obj, ("win", "is_win", "won", "result", "status"))
            if win is not None:
                break

        currentprofit = None
        for obj in containers:
            currentprofit = self._pick_number(
                obj,
                (
                    "profit",
                    "profit_amount",
                    "net_profit",
                    "win_amount",
                    "amount_won",
                    "pnl",
                ),
            )
            if currentprofit is not None:
                break
        if currentprofit is not None:
            currentprofit = self._normalize_units(currentprofit)
        if currentprofit is None:
            if win is None and roll is not None:
                win = _is_win_from_roll(roll, chance, bethigh)
            if win is None:
                win = False
            multiplier = max(1.0001, self.payout_factor() / max(0.01, chance))
            currentprofit = (
                placed_amount * (multiplier - 1.0) if win else -placed_amount
            )
        elif win is None:
            win = currentprofit > 0

        balance_val = None
        for obj in containers:
            balance_val = self._pick_number(
                obj,
                (
                    "balance",
                    "new_balance",
                    "wallet_balance",
                    "coin_balance",
                    "available_balance",
                    "balance_after",
                ),
            )
            if balance_val is not None:
                break
        if balance_val is not None:
            balance_val = self._normalize_units(balance_val)

        return placed_amount, float(roll), float(currentprofit), bool(win), balance_val

    def balances(self) -> dict:
        """Return shape Wolfbet-compatible: {"balances": [{"currency": "...", "amount": ...}, ...]}."""
        if not self.api_token:
            return {"balances": []}
        try:
            payload = self._fetch_wallet()
        except Exception:
            return {"balances": []}
        catalog = self._extract_coin_catalog_from_api(payload)
        items = []
        for entry in catalog:
            currency = entry.get("coin")
            balance = entry.get("balance")
            if currency is None:
                continue
            items.append({"currency": currency, "amount": float(balance or 0.0)})
        return {"balances": items}

    def stats(self) -> dict:
        """FaucetPay tidak ekspos stats per-coin di API publik. Return kosong."""
        return {}

    def profile(self) -> dict:
        """Return shape Wolfbet-compatible: {"user": {"username": ..., "email": ...}}."""
        if not self.api_token:
            return {"user": {}}
        candidates = (
            ("POST", "/account/get-user-information", {}),
            ("GET", "/account/get-user-information", None),
        )
        for method, path, payload in candidates:
            try:
                data = self._api_request(method, path, payload=payload)
            except Exception:
                continue
            user = self._extract_identity_from_api(data)
            if user.get("username") or user.get("email"):
                return {"user": user}
        return {"user": {}}

    def _extract_identity_from_api(self, payload):
        result = {"username": None, "email": None}
        username_keys = ("username", "user_name", "name", "nickname", "display_name")
        email_keys = ("email", "mail", "user_email")
        for obj in self._iter_objects(payload):
            if not isinstance(obj, dict):
                continue
            if result["username"] is None:
                for key in username_keys:
                    value = obj.get(key)
                    if isinstance(value, str) and value.strip():
                        result["username"] = value.strip()
                        break
            if result["email"] is None:
                for key in email_keys:
                    value = obj.get(key)
                    if isinstance(value, str) and value.strip():
                        result["email"] = value.strip()
                        break
            if result["username"] and result["email"]:
                break
        return result

    def place_bet(self, currency: str, amount: float, chance: float, bethigh: bool) -> dict:
        """Tempatkan dice bet, return shape Wolfbet-compatible:
            {
              "bet": {
                "amount": <placed_amount>,
                "state": "win"|"lose",
                "result_value": <roll>,
                "profit": <pnl>,
              },
              "userBalance": {"amount": <balance_after>}
            }
        """
        normalized_coin = _normalize_coin_symbol(currency)
        if normalized_coin:
            self.coin = normalized_coin

        raw = self._place_dice_bet_raw(amount, chance, bethigh)
        placed_amount, roll, profit, win, balance_after = self._parse_bet_result(
            raw, amount, chance, bethigh
        )

        if balance_after is None:
            try:
                balance_after = self._extract_balance_from_api(self._fetch_wallet())
            except Exception:
                balance_after = None
        if balance_after is None:
            balance_after = float(self.last_balance) if self.last_balance is not None else 0.0
        else:
            self.last_balance = float(balance_after)

        return {
            "bet": {
                "amount": float(placed_amount),
                "state": "win" if win else "lose",
                "result_value": float(roll),
                "profit": float(profit),
            },
            "userBalance": {"amount": float(balance_after)},
        }

    def reset_seed(self) -> dict:
        return {"ret": 1, "message": "reset_seed not supported in API mode"}
