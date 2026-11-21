"""Betfury dice client - Socket.IO based.

Site: https://betfury.com/casino/games/dice

Auth flow (event-based, dari source bahanbetfury):
  1. Connect socket.io ke betfury.com (path /socket.io)
  2. emit("profile.token", {token, currency, fingerprint, tz: -420})
     -> response: { response: { user: { currencies: {btc: {balance, ...}}, ... } } }
  3. emit("auth.changeCurrency", {currency}) untuk pilih coin aktif
  4. emit("profile.token", {token, currency}) lagi (refresh balance per coin)
  5. emit("games.dice.join", {}) untuk join dice room

Place bet:
  emit("games.dice.bet", {
    amount: "0.00010000",          # string fixed 8 decimal
    frontID: <epoch ms>,
    isBonusBet: false,
    isFast: false,
    is_under: <bool>,
    prediction: <0..99 int>,        # bethigh ? 99 - chance : chance
    strategyName: "",
    version: "main"
  }, callback)

Response:
  callback(data) where data is one of:
    { response: { winAmount, roll_number, profit, ... } }   # success
    { error: "msg", code: <int> }                            # failure

Token + uid dari localStorage browser:
  - token = localStorage.getItem("token")
  - uid = localStorage.getItem("uid")
  - fingerprint = uid.split("_")[0]
"""

from __future__ import annotations

import json
import socket
import threading
import time
import urllib.request
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

import requests


_original_getaddrinfo = socket.getaddrinfo
_resolved_betfury_ip: str | None = None

def _patched_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    if host == "betfury.com" and _resolved_betfury_ip:
        return _original_getaddrinfo(_resolved_betfury_ip, port, family, type, proto, flags)
    return _original_getaddrinfo(host, port, family, type, proto, flags)

socket.getaddrinfo = _patched_getaddrinfo


def _resolve_via_doh(host: str, timeout: float = 8.0) -> str | None:
    url = f"https://cloudflare-dns.com/dns-query?name={host}&type=A"
    req = urllib.request.Request(url, headers={"accept": "application/dns-json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())
    except Exception:
        return None
    answers = [a.get("data") for a in data.get("Answer", []) if a.get("type") == 1 and a.get("data")]
    return answers[0] if answers else None

try:
    import socketio  # python-socketio
except ImportError as exc:
    raise RuntimeError(
        "python-socketio tidak terinstall. Tambahkan ke requirements.txt"
    ) from exc


BETFURY_URL = "https://betfury.com"
BETFURY_PATH = "/socket.io"
DEFAULT_CURRENCIES = ("BTC", "ETH", "USDT", "TRX", "BFG", "BTT", "DOGE", "LTC")


def _format_amount(value: float) -> str:
    """Format float SOL/BTC ke string fixed 8 decimal."""
    dec = Decimal(str(value)).quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)
    return f"{dec:.8f}"


def _parse_token_uid(raw: str) -> tuple[str, str, str]:
    """Parse user input. Format yang di-support:
      - "<token>;uid=<uid>"
      - JSON: {"token": "...", "uid": "..."}

    Return (token, uid, fingerprint).
    """
    raw = (raw or "").strip()
    if not raw:
        raise RuntimeError("Token Betfury kosong.")

    token = ""
    uid = ""

    if raw.startswith("{") and raw.endswith("}"):
        try:
            data = json.loads(raw)
            token = str(data.get("token") or "").strip()
            uid = str(data.get("uid") or "").strip()
        except (json.JSONDecodeError, ValueError):
            pass

    if not token and ";" in raw:
        parts = [p.strip() for p in raw.split(";") if p.strip()]
        token = parts[0]
        for part in parts[1:]:
            if "=" in part:
                key, value = part.split("=", 1)
                if key.strip().lower() == "uid":
                    uid = value.strip()

    if not token:
        token = raw

    if not token:
        raise RuntimeError("Token Betfury invalid.")

    if not uid:
        # Fallback: fingerprint kosong, tapi server kadang tetap accept
        fingerprint = ""
    else:
        fingerprint = uid.split("_", 1)[0] if "_" in uid else uid

    return token, uid, fingerprint


class BetfuryClient:
    """Socket.IO client untuk Betfury dice game."""

    display_name: str = "Betfury"
    default_currencies: tuple[str, ...] = DEFAULT_CURRENCIES
    min_bet: float = 1e-8
    requires_token: bool = True

    def __init__(self, token: str, proxy: dict[str, str] | None = None):
        self._token, self._uid, self._fingerprint = _parse_token_uid(token)
        self._proxy = proxy or {}

        global _resolved_betfury_ip
        if not _resolved_betfury_ip:
            _resolved_betfury_ip = _resolve_via_doh("betfury.com")

        # State
        self._lock = threading.RLock()
        self._balances: dict[str, float] = {}
        self._username: str = ""
        self._currency: str = "btc"  # default lowercase, diubah saat user pilih

        # Buat session HTTP khusus untuk Socket.IO agar mendukung proxy
        session = requests.Session()
        if self._proxy:
            session.proxies.update(self._proxy)

        # Socket.IO state
        self._sio = socketio.Client(
            reconnection=True,
            reconnection_attempts=0,  # infinite
            reconnection_delay=1,
            reconnection_delay_max=10,
            logger=False,
            engineio_logger=False,
            http_session=session,
        )
        self._connected_event = threading.Event()
        self._authed_event = threading.Event()

        self._setup_handlers()
        self._connect()

    # ---- Connection ------------------------------------------------------

    def _setup_handlers(self) -> None:
        @self._sio.on("connect")
        def _on_connect():
            self._connected_event.set()
            # Auth setelah connect
            self._sio.emit(
                "profile.token",
                {
                    "currency": self._currency,
                    "fingerprint": self._fingerprint,
                    "token": self._token,
                    "tz": -420,
                },
                callback=self._on_token_response,
            )

        @self._sio.on("disconnect")
        def _on_disconnect():
            self._connected_event.clear()

    def _on_token_response(self, *args: Any) -> None:
        """Server reply ke profile.token. Extract user balances.

        Selalu set _authed_event di semua jalur — termasuk error response
        dan unexpected shape — agar _connect() tidak hang sampai timeout.
        """
        try:
            if not args:
                return
            data = args[0] if len(args) == 1 else args
            if not isinstance(data, dict):
                return
            # Server bisa return {"error": "..."} kalau token salah
            if data.get("error"):
                return
            response = data.get("response") or {}
            user = response.get("user") or {}
            currencies = user.get("currencies") or {}
            with self._lock:
                self._balances = {
                    str(k).upper(): float((v or {}).get("balance") or 0)
                    for k, v in currencies.items()
                }
                self._username = str(user.get("login") or user.get("username") or "")
        finally:
            # Selalu set — tanpa ini, _connect() tunggu sampai timeout 10s
            # setiap kali server reply dengan shape yang tidak terduga.
            self._authed_event.set()

    def _connect(self) -> None:
        """Connect + auth handshake. Block sampai authenticated atau timeout.

        Coba WebSocket dulu. Kalau gagal (server butuh polling handshake atau
        ada proxy yang block upgrade), fallback ke polling+websocket otomatis.
        """
        self._connected_event.clear()
        self._authed_event.clear()

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36"
            ),
            "Origin": BETFURY_URL,
        }

        # Coba WebSocket dulu (lebih cepat), fallback ke polling kalau gagal.
        # Betfury kadang butuh HTTP polling handshake sebelum upgrade ke WS.
        last_exc: Exception | None = None
        for transports in (["websocket"], ["polling", "websocket"]):
            try:
                if self._sio.connected:
                    self._sio.disconnect()
                self._connected_event.clear()
                self._authed_event.clear()
                self._sio.connect(
                    BETFURY_URL,
                    socketio_path=BETFURY_PATH,
                    transports=transports,
                    headers=headers,
                    wait_timeout=15,
                )
                last_exc = None
                break
            except socketio.exceptions.ConnectionError as exc:
                last_exc = exc
                continue

        if last_exc is not None:
            raise RuntimeError(
                "Tidak bisa connect ke Betfury.\n"
                "Kemungkinan penyebab:\n"
                "  1. Koneksi internet terputus atau lambat\n"
                "  2. Betfury diblok oleh ISP/firewall\n"
                "  3. Server Betfury sedang down\n"
                f"Detail: {last_exc}"
            ) from last_exc

        if not self._connected_event.wait(timeout=10):
            raise RuntimeError(
                "Timeout connect ke Betfury Socket.IO (>10s).\n"
                "Periksa koneksi internet."
            )
        if not self._authed_event.wait(timeout=10):
            raise RuntimeError(
                "Betfury menolak token.\n"
                "Kemungkinan penyebab:\n"
                "  1. Token JWT sudah expired — login ulang di browser dan copy ulang\n"
                "  2. Format salah — harus: <token>;uid=<uid>\n"
                "     Contoh: eyJhbGc...xyz;uid=093c6d8e...545_1780470224539\n"
                "  3. UID tidak sesuai dengan token"
            )

    # ---- Helpers ---------------------------------------------------------

    def _emit_with_ack(self, event: str, payload: dict,
                      timeout: float = 15.0) -> dict:
        """Emit event, block sampai callback dipanggil. Return dict response."""
        result: dict = {}
        ev = threading.Event()

        def cb(*args: Any) -> None:
            if args:
                data = args[0] if len(args) == 1 else {"args": args}
                if isinstance(data, dict):
                    result.update(data)
            ev.set()

        try:
            self._sio.emit(event, payload, callback=cb)
        except socketio.exceptions.BadNamespaceError as exc:
            raise RuntimeError(f"Socket.IO error emit {event}: {exc}") from exc

        if not ev.wait(timeout=timeout):
            raise RuntimeError(f"Timeout response Betfury untuk event '{event}'.")

        if "error" in result and result["error"]:
            err_msg = result["error"]
            err_code = result.get("code")
            raise RuntimeError(f"Server error: {err_msg} (code={err_code})")

        return result

    def setCurrency(self, currency: str) -> None:
        """Ubah active currency + refresh balance via auth.changeCurrency."""
        self._currency = str(currency).lower()
        self._emit_with_ack(
            "auth.changeCurrency",
            {"currency": self._currency},
            timeout=10.0,
        )
        # Reload balance per coin
        result = self._emit_with_ack(
            "profile.token",
            {
                "token": self._token,
                "currency": self._currency,
            },
            timeout=10.0,
        )
        self._on_token_response(result)

    # ---- BaseClient contract ---------------------------------------------

    def balances(self) -> dict:
        with self._lock:
            return {
                "balances": [
                    {"currency": cur, "amount": amt}
                    for cur, amt in self._balances.items()
                ]
            }

    def stats(self) -> dict:
        return {}

    def profile(self) -> dict:
        with self._lock:
            return {"user": {"name": self._username or "betfury-user"}}

    def place_bet(
        self, currency: str, amount: float, chance: float, bethigh: bool
    ) -> dict:
        """Place dice bet. Convert generic params ke betfury payload."""
        target_currency = str(currency).lower()
        if target_currency != self._currency:
            self.setCurrency(target_currency)

        # Betfury convention: prediction integer 0..99
        chance_clamped = max(0.01, min(98.0, float(chance)))
        if bethigh:
            prediction = int(99 - chance_clamped)
        else:
            prediction = int(chance_clamped)

        amount_str = _format_amount(amount)

        # Try bet, kalau code 0x1c89 (kurang lebih 7305 = need re-join), join lalu retry sekali
        try:
            result = self._emit_with_ack(
                "games.dice.bet",
                {
                    "amount": amount_str,
                    "frontID": int(time.time() * 1000),
                    "isBonusBet": False,
                    "isFast": False,
                    "is_under": not bethigh,
                    "prediction": prediction,
                    "strategyName": "",
                    "version": "main",
                },
                timeout=15.0,
            )
        except RuntimeError as exc:
            if "code=7305" in str(exc) or "code=0x1c89" in str(exc):
                # Need to join dice room first
                self._emit_with_ack("games.dice.join", {}, timeout=5.0)
                result = self._emit_with_ack(
                    "games.dice.bet",
                    {
                        "amount": amount_str,
                        "frontID": int(time.time() * 1000),
                        "isBonusBet": False,
                        "isFast": False,
                        "is_under": not bethigh,
                        "prediction": prediction,
                        "strategyName": "",
                        "version": "main",
                    },
                    timeout=15.0,
                )
            else:
                raise

        bet_data = result.get("response") or {}
        if not bet_data:
            raise RuntimeError(f"Response Betfury tidak punya 'response': {result}")

        return self._normalize_bet_response(bet_data, amount, target_currency)

    def reset_seed(self) -> dict:
        # Betfury seed rotation tidak ada di source bahan. Skip dummy.
        return {"ok": True}

    # ---- Helpers ---------------------------------------------------------

    def _normalize_bet_response(
        self, raw: dict, wager: float, currency: str
    ) -> dict:
        """Convert response Betfury ke shape generic engine.

        Native shape (dari handleResult di source):
          {
            winAmount: <float, total payout kalau win, 0 kalau lose>,
            roll_number: <0..99.99>,
            ... (id, etc)
          }

        currentprofit = winAmount - amount
        """
        win_amount = float(raw.get("winAmount") or 0)
        roll_number = float(raw.get("roll_number") or 0)

        # Profit signed: kalau win, profit = win_amount - wager. Kalau lose
        # win_amount = 0 jadi profit = -wager.
        profit = win_amount - float(wager)
        is_win = profit > 0

        # Update tracked balance
        with self._lock:
            cur_upper = currency.upper()
            self._balances[cur_upper] = self._balances.get(cur_upper, 0.0) + profit
            new_balance = self._balances[cur_upper]

        return {
            "bet": {
                "amount": float(wager),
                "state": "win" if is_win else "lose",
                "result_value": roll_number,
                "profit": profit,
            },
            "userBalance": {"amount": new_balance},
        }
