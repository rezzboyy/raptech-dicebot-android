"""Nuts.gg dice client - WebSocket GraphQL.

Site: https://nuts.gg/dice
Backend: wss://nuts.tools/graphql (subprotocol: graphql-transport-ws)

Schema facts (verified via introspection 2026-07-04):
  - Subscription: balance { after }  -> AfterPayload { after: Float! }
    `after` = saldo dalam lamports (Float), 1 SOL = 1_000_000_000 lamports.
    Fire langsung saat subscribe.
  - Mutation: playDice(wager, dividingPoint, mode, clientSeed, autoplay)
    `wager` = amount dalam lamports (Float). Same convention seperti browser client.
  - Query `authenticate()` TIDAK ADA di schema saat ini — dikirim sebagai
    subscription frame yang server mungkin tolak dengan error. Non-fatal.
  - User type: { _id, username, role, league } — tidak ada `balance` di User.
  - HTTP POST ke nuts.tools diblok Cloudflare (403) — hanya WS yang bisa.

Auth flow (penting):
  connection_init payload harus include `authToken` supaya server otorisasi
  subscription balance. Tanpa itu, server mungkin tetap balas tapi return 0.

Token user paste:
  - JWT dari Local Storage -> nuts.gg -> key 'auth_token'.
  - Format JWT non-standard: header.userID.signature
    (payload = user ID numerik, misal '8937441')
"""

from __future__ import annotations

import base64
import json
import random
import string
import threading
import uuid
from typing import Any

try:
    import websocket  # websocket-client
except ImportError as exc:  # pragma: no cover
    raise RuntimeError(
        "websocket-client tidak terinstall. Tambahkan ke requirements.txt"
    ) from exc


WS_URL    = "wss://nuts.tools/graphql"
ORIGIN    = "https://nuts.gg"
SUBPROTO  = "graphql-transport-ws"

# 1 SOL = 1_000_000_000 lamports. Server pakai lamports as Float di semua field
# amount (wager, balance.after, profit, balanceAfter).
LAMPORTS_PER_SOL = 1_000_000_000


# ---- GraphQL documents ---------------------------------------------------

AUTHENTICATE_QUERY = (
    "query authenticate($authToken: String, $referralCode: String) {\n"
    "  authenticate(authToken: $authToken, referralCode: $referralCode) {\n"
    "    _id\n"
    "    username\n"
    "    authToken\n"
    "    email\n"
    "  }\n"
    "}"
)

# Subscription balance — server return `after` dalam lamports (Float)
BALANCE_SUBSCRIPTION = (
    "subscription balance {\n"
    "  balance {\n"
    "    after\n"
    "  }\n"
    "}"
)

PLAY_DICE_MUTATION = (
    "mutation playDice($wager: Float!, $dividingPoint: Float!, "
    "$mode: String!, $clientSeed: String!, $autoplay: Boolean!) {\n"
    "  playDice(\n"
    "    wager: $wager\n"
    "    dividingPoint: $dividingPoint\n"
    "    mode: $mode\n"
    "    clientSeed: $clientSeed\n"
    "    autoplay: $autoplay\n"
    "  ) {\n"
    "    id\n"
    "    isWin\n"
    "    profit\n"
    "    wager\n"
    "    multiplier\n"
    "    details {\n"
    "      ... on DiceGameDetails { __typename result }\n"
    "      __typename\n"
    "    }\n"
    "    __typename\n"
    "  }\n"
    "}"
)

RESET_SEED_MUTATION = "mutation { rotateSinglePlayerGameBetServerSeed }"


def _gen_client_seed() -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(random.choice(alphabet) for _ in range(16))


def _extract_user_id_from_jwt(jwt: str) -> str | None:
    """Nuts.gg JWT payload = plain user ID string (misal: '8937441')."""
    parts = jwt.split(".")
    if len(parts) < 2:
        return None
    try:
        pad = "=" * (-len(parts[1]) % 4)
        raw = base64.urlsafe_b64decode(parts[1] + pad)
        text = raw.decode("utf-8", errors="replace").strip()
        if text.isdigit():
            return text
        try:
            obj = json.loads(text)
            return str(obj.get("sub") or obj.get("id") or obj.get("_id") or "")
        except Exception:
            return text
    except Exception:
        return None


class NutsClient:
    """WebSocket GraphQL client untuk Nuts.gg dice."""

    display_name: str = "Nuts.gg"
    default_currencies: tuple[str, ...] = ("SOL",)
    min_bet: float = 1e-8
    requires_token: bool = True

    def __init__(self, token: str, proxy: dict[str, str] | None = None):
        self._jwt = token.split(";")[0].strip() if token else ""
        if not self._jwt:
            raise RuntimeError("Token nuts.gg kosong (paste JWT dari localStorage).")
        self._proxy = proxy or {}

        uid = _extract_user_id_from_jwt(self._jwt)

        # State — internal storage tetap dalam lamports (int) untuk presisi,
        # balances() convert ke SOL float saat return.
        self._lock = threading.RLock()
        self._balance_lamports: int = 0
        self._balance_known: bool = False
        self._username: str = f"user-{uid}" if uid else "nuts-user"
        self._user_id: str | None = uid
        self._last_error: str | None = None  # untuk debug internal saja

        # WS state
        self._ws: websocket.WebSocketApp | None = None
        self._ws_thread: threading.Thread | None = None
        self._ack_event = threading.Event()
        self._authed_event = threading.Event()
        self._balance_received_event = threading.Event()
        self._closed = threading.Event()
        self._pending: dict[str, dict] = {}
        self._auth_id: str | None = None
        self._balance_sub_id: str | None = None

        self._connect()

    # ---- Connection lifecycle --------------------------------------------

    def _connect(self) -> None:
        """Open WS, auth handshake, subscribe balance."""
        self._ack_event.clear()
        self._authed_event.clear()
        self._balance_received_event.clear()
        self._closed.clear()

        headers = [
            f"Origin: {ORIGIN}",
            "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        ]
        self._ws = websocket.WebSocketApp(
            WS_URL,
            header=headers,
            subprotocols=[SUBPROTO],
            on_open=self._on_open,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close,
        )

        kwargs: dict[str, Any] = {"ping_interval": 25, "ping_timeout": 10}
        if self._proxy:
            from urllib.parse import urlparse
            proxy_url = self._proxy.get("https") or self._proxy.get("http")
            if proxy_url:
                parsed = urlparse(proxy_url)
                kwargs["http_proxy_host"] = parsed.hostname
                kwargs["http_proxy_port"] = parsed.port

        self._ws_thread = threading.Thread(
            target=self._ws.run_forever, kwargs=kwargs,
            daemon=True, name="nuts-ws",
        )
        self._ws_thread.start()

        if not self._ack_event.wait(timeout=10):
            self._safe_close()
            raise RuntimeError("Timeout connect nuts.gg WebSocket (>10s).")

        # Auth query (optional — schema mungkin tolak, tapi kirim untuk dapat
        # username kalau server support)
        self._send_authenticate()
        self._authed_event.wait(timeout=5)

        # Subscribe balance — fire langsung saat subscribe kalau JWT di
        # connection_init valid.
        self._send_balance_subscription()
        self._balance_received_event.wait(timeout=6)

    def _on_open(self, ws: Any) -> None:
        """Kirim connection_init dengan JWT di payload. Server pakai token ini
        untuk authorize semua subscription selanjutnya (balance, dll)."""
        try:
            payload: dict = {}
            if self._jwt:
                payload["authToken"] = self._jwt
            ws.send(json.dumps({"type": "connection_init", "payload": payload}))
        except Exception:
            pass

    def _on_message(self, ws: Any, message: str) -> None:
        # fast_json_loads pakai orjson kalau tersedia (5x lebih cepat).
        try:
            from ..lua_support import fast_json_loads
            frame = fast_json_loads(message)
        except Exception:
            return

        ftype = frame.get("type")
        if ftype == "connection_ack":
            self._ack_event.set()
        elif ftype == "ping":
            try:
                ws.send(json.dumps({"type": "pong"}))
            except Exception:
                pass
        elif ftype in ("next", "error", "complete"):
            self._handle_data_frame(frame)

    def _handle_data_frame(self, frame: dict) -> None:
        rid   = frame.get("id")
        ftype = frame.get("type")
        if not rid:
            return

        payload = frame.get("payload") or {}

        # ---- Auth response ----
        if rid == self._auth_id:
            if ftype == "next":
                data = payload.get("data") or {}
                auth = data.get("authenticate") or {}
                uname = str(auth.get("username") or "")
                uid   = str(auth.get("_id") or "")
                with self._lock:
                    if uname:
                        self._username = uname
                    if uid:
                        self._user_id = uid
            # Set event di semua kondisi supaya _connect tidak hang
            self._authed_event.set()
            return

        # ---- Balance subscription ----
        if rid == self._balance_sub_id:
            if ftype == "next":
                data = payload.get("data") or {}
                bal  = data.get("balance") or {}
                after = bal.get("after")
                if after is not None:
                    try:
                        # `after` = lamports as Float, simpan sebagai int
                        lamports = int(round(float(after)))
                        with self._lock:
                            self._balance_lamports = lamports
                            self._balance_known    = True
                            self._last_error       = None
                        self._balance_received_event.set()
                    except (TypeError, ValueError) as exc:
                        with self._lock:
                            self._last_error = f"Parse balance error: {exc}"
                else:
                    with self._lock:
                        self._last_error = "Response balance tidak punya field 'after'"
            elif ftype == "error":
                with self._lock:
                    self._last_error = f"Subscription balance error: {payload}"
                # Signal supaya connect flow lanjut (jangan hang menunggu balance)
                self._balance_received_event.set()
            return

        # ---- Generic pending (bet / reset_seed) ----
        with self._lock:
            slot = self._pending.get(rid)
        if not slot:
            return

        if ftype == "next":
            errors = payload.get("errors")
            if errors:
                slot["error"] = errors
            else:
                slot["result"] = payload.get("data") or {}
            ev = slot.get("event")
            if ev is not None:
                ev.set()
        elif ftype == "error":
            slot["error"] = payload
            ev = slot.get("event")
            if ev is not None:
                ev.set()
        elif ftype == "complete":
            ev = slot.get("event")
            if ev is not None:
                ev.set()

    def _on_error(self, ws: Any, error: Any) -> None:
        with self._lock:
            for slot in self._pending.values():
                slot.setdefault("error", str(error))
                ev = slot.get("event")
                if ev:
                    ev.set()

    def _on_close(self, ws: Any, code: Any = None, msg: Any = None) -> None:
        self._closed.set()
        self._ack_event.clear()
        with self._lock:
            for slot in self._pending.values():
                slot.setdefault("error", "Connection closed")
                ev = slot.get("event")
                if ev:
                    ev.set()

    def _safe_close(self) -> None:
        try:
            if self._ws:
                self._ws.close()
        except Exception:
            pass

    # ---- Frame senders ---------------------------------------------------

    def _send_authenticate(self) -> None:
        self._auth_id = str(uuid.uuid4())
        self._ws.send(json.dumps({  # type: ignore[union-attr]
            "id": self._auth_id,
            "type": "subscribe",
            "payload": {
                "operationName": "authenticate",
                "query": AUTHENTICATE_QUERY,
                "variables": {"authToken": self._jwt, "referralCode": None},
            },
        }))

    def _send_balance_subscription(self) -> None:
        self._balance_sub_id = str(uuid.uuid4())
        self._ws.send(json.dumps({  # type: ignore[union-attr]
            "id": self._balance_sub_id,
            "type": "subscribe",
            "payload": {
                "operationName": "balance",
                "query": BALANCE_SUBSCRIPTION,
                "variables": {},
            },
        }))

    def _send_request(self, payload: dict, *, timeout: float = 15.0) -> dict:
        """Kirim subscribe frame, block sampai dapat next+complete atau error."""
        if not self._ack_event.is_set():
            self._connect()

        rid = str(uuid.uuid4())
        ev  = threading.Event()
        slot: dict = {"event": ev}
        with self._lock:
            self._pending[rid] = slot

        try:
            self._ws.send(json.dumps({  # type: ignore[union-attr]
                "id": rid, "type": "subscribe", "payload": payload,
            }))
        except Exception as exc:
            with self._lock:
                self._pending.pop(rid, None)
            raise RuntimeError(f"Gagal kirim frame: {exc}") from exc

        if not ev.wait(timeout=timeout):
            with self._lock:
                self._pending.pop(rid, None)
            raise RuntimeError(f"Timeout response server (>{timeout}s).")

        with self._lock:
            self._pending.pop(rid, None)

        if "error" in slot:
            err = slot["error"]
            if isinstance(err, list) and err:
                msg = (
                    err[0].get("message", str(err))
                    if isinstance(err[0], dict) else str(err[0])
                )
            else:
                msg = str(err)
            raise RuntimeError(f"Server error: {msg}")

        return slot.get("result") or {}

    # ---- BaseClient contract ---------------------------------------------

    def balances(self) -> dict:
        with self._lock:
            lamports = self._balance_lamports
        sol = float(lamports) / LAMPORTS_PER_SOL
        return {"balances": [{"currency": "SOL", "amount": sol}]}

    def stats(self) -> dict:
        return {}

    def profile(self) -> dict:
        with self._lock:
            return {"user": {"name": self._username}}

    def place_bet(
        self, currency: str, amount: float, chance: float, bethigh: bool
    ) -> dict:
        """Place dice bet. `wager` dikirim dalam lamports (Float),
        sesuai konvensi source nuts-dice console browser."""
        chance_clamped = max(0.01, min(98.0, float(chance)))
        chance_rounded = round(chance_clamped + 1e-12, 2)

        if bethigh:
            target = round(99.99 - chance_rounded + 1e-12, 2)
            mode   = "RollOver"
        else:
            target = chance_rounded
            mode   = "RollUnder"

        # Convert SOL amount ke lamports as Float
        wager_lamports = float(round(float(amount) * LAMPORTS_PER_SOL))
        if wager_lamports < 1:
            wager_lamports = 1.0  # min 1 lamport supaya tidak reject

        data = self._send_request({
            "operationName": "playDice",
            "query": PLAY_DICE_MUTATION,
            "variables": {
                "wager":         wager_lamports,
                "dividingPoint": float(target),
                "mode":          mode,
                "clientSeed":    _gen_client_seed(),
                "autoplay":      False,
            },
        }, timeout=15.0)

        bet_data = data.get("playDice")
        if not isinstance(bet_data, dict):
            raise RuntimeError(f"Response tidak punya 'playDice': {data}")

        return self._normalize_bet_response(bet_data, float(amount))

    def reset_seed(self) -> dict:
        try:
            self._send_request({
                "operationName": "rotateSeed",
                "query": RESET_SEED_MUTATION,
                "variables": {},
            }, timeout=10.0)
            return {"ok": True}
        except RuntimeError:
            return {"ok": False}

    # ---- Helpers ----------------------------------------------------------

    def _normalize_bet_response(self, raw: dict, wager_sol: float) -> dict:
        """Convert playDice response ke shape generic engine.

        Server fields di SinglePlayerGameBet (semua lamports as Float):
          isWin      : Boolean
          profit     : Float lamports (signed — positif=win, negatif=lose)
          wager      : Float lamports
          multiplier : Float
          details    : DiceGameDetails { result: Float, mode: String, dividingPoint: Float }

        Catatan: `balanceAfter` tidak ada di schema. Balance di-update
        via subscription `balance` push (background thread) + fallback
        hitung manual dari profit di sini.
        """
        is_win = bool(raw.get("isWin"))

        # Profit — server return lamports, convert ke SOL
        profit_sol: float = 0.0
        profit_raw = raw.get("profit")
        if profit_raw is not None:
            try:
                profit_sol = float(profit_raw) / LAMPORTS_PER_SOL
            except (TypeError, ValueError):
                pass

        # Fallback kalau server tidak return profit (jarang)
        if profit_sol == 0.0 and not is_win:
            profit_sol = -wager_sol

        # Balance: update dari profit dulu. Subscription balance mungkin
        # sudah push nilai yang lebih akurat di antara mutation call — tunggu
        # sebentar (100ms) supaya push tiba, lalu ambil nilai terkini.
        with self._lock:
            delta_lamports = int(round(profit_sol * LAMPORTS_PER_SOL))
            self._balance_lamports += delta_lamports
            new_bal_sol = float(self._balance_lamports) / LAMPORTS_PER_SOL

        details      = raw.get("details") or {}
        result_value = float(details.get("result") or 0)

        return {
            "bet": {
                "amount":       wager_sol,
                "state":        "win" if is_win else "lose",
                "result_value": result_value,
                "profit":       profit_sol,
            },
            "userBalance": {"amount": new_bal_sol},
        }
