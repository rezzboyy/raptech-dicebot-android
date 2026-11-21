"""JacksClub (jacksclub.io) client implementation.

Diadaptasi dari `clientjackclub.py` (standalone CLI) ke kontrak `BaseClient`.

JacksClub memakai action-batch protocol via POST ke `/api`:
- Body adalah JSON array `[{"name": "<action>", "payload": {...}}]`
- Header `X-Amz-Content-Sha256` berisi SHA256 dari body
- Header `Authentication` berisi token (JWT-like)
- Cookie berisi `access=<token>`, `store.currency=<CCY>`, `version=2`

Karena setiap session-action butuh body unik, kita serialize batch dan
hash body sebelum kirim. Currency aktif dimasukkan ke cookie agar server
bisa scope action ke wallet yang tepat.
"""

from __future__ import annotations

import copy
import hashlib
import json
import uuid
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from ..http_client import build_http_session


BASE_URL = "https://jacksclub.io/api"
ORIGIN = "https://jacksclub.io"
REFERER = "https://jacksclub.io/casino/games/dice"
DEFAULT_TIMEOUT = 30
MIN_BET = Decimal("0.00000001")
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"
)

DEFAULT_PROFILE_ACTIONS = ("getProfile", "getPlayer", "getAccount", "getMe")
DEFAULT_BALANCE_ACTIONS = ("wallets",)
DEFAULT_RESET_SEED_ACTIONS = ("resetSeed", "refreshSeed", "rotateSeed")


# ---- helpers --------------------------------------------------------------


def _parse_number(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return 0.0
        try:
            return float(value)
        except ValueError:
            return 0.0
    if isinstance(value, dict):
        for key in ("$bigfloat", "$numberDecimal", "$numberDouble", "$bigint", "$numberLong"):
            if key in value:
                return _parse_number(value.get(key))
        if "amount" in value and len(value) == 1:
            return _parse_number(value.get("amount"))
    return 0.0


def _wallet_candidate(node: dict) -> dict | None:
    if not isinstance(node, dict):
        return None
    currency = node.get("currency") or node.get("coin") or node.get("asset")
    if not currency:
        return None
    amount_value = None
    for key in ("amount", "balance", "available"):
        if key in node:
            amount_value = node.get(key)
            break
    if amount_value is None:
        return None
    return {
        "currency": str(currency).upper(),
        "amount": _parse_number(amount_value),
    }


def _extract_wallets(node: Any) -> list[dict]:
    """Cari semua object yang merepresentasikan wallet entry dari tree response."""
    candidates: list[tuple[int, dict]] = []

    def walk(value: Any, score: int = 0) -> None:
        if isinstance(value, dict):
            candidate = _wallet_candidate(value)
            if candidate:
                candidates.append((score, candidate))
            for key, child in value.items():
                next_score = score
                key_lower = str(key).lower()
                if "wallet" in key_lower or "balance" in key_lower:
                    next_score += 6
                if key_lower in ("bet", "seed", "game", "state"):
                    next_score -= 4
                walk(child, next_score)
        elif isinstance(value, list):
            for child in value:
                walk(child, score)

    walk(node)
    if not candidates:
        return []

    wallet_map: dict[str, tuple[int, float]] = {}
    for score, wallet in candidates:
        currency = wallet["currency"]
        existing = wallet_map.get(currency)
        if existing is None or score >= existing[0]:
            wallet_map[currency] = (score, wallet["amount"])

    rows = [
        {"currency": currency, "amount": amount}
        for currency, (_, amount) in wallet_map.items()
    ]
    rows.sort(key=lambda item: item["currency"])
    return rows


def _extract_profile(node: Any) -> dict | None:
    candidates: list[tuple[int, dict]] = []

    def walk(value: Any, score: int = 0) -> None:
        if isinstance(value, dict):
            name = value.get("name") or value.get("username") or value.get("login")
            email = value.get("email")
            identifier = value.get("id") or value.get("playerId") or value.get("userId")
            if name or email or identifier:
                candidates.append(
                    (
                        score,
                        {"id": identifier, "name": name, "email": email},
                    )
                )
            for key, child in value.items():
                next_score = score
                key_lower = str(key).lower()
                if key_lower in ("player", "user", "profile", "account", "me"):
                    next_score += 5
                walk(child, next_score)
        elif isinstance(value, list):
            for child in value:
                walk(child, score)

    walk(node)
    if not candidates:
        return None
    candidates.sort(
        key=lambda item: (item[0], bool(item[1].get("email")), bool(item[1].get("name"))),
        reverse=True,
    )
    return candidates[0][1]


def _serialize_batch_payload(payload: list[dict]) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def _merge_payload(base: dict, dynamic: dict) -> dict:
    merged = copy.deepcopy(base) if isinstance(base, dict) else {}
    merged.update(dynamic)
    return merged


# ---- Client ---------------------------------------------------------------


class JacksClubClient:
    """Client untuk jacksclub.io (action-batch protocol)."""

    display_name: str = "JacksClub"
    default_currencies: tuple[str, ...] = (
        "DOGE",
        "BTC",
        "ETH",
        "LTC",
        "TRX",
        "BCH",
        "XRP",
    )
    min_bet: float = float(MIN_BET)

    def __init__(self, token: str, proxy: dict[str, str] | None = None):
        self.token = (token or "").strip()
        # Shared HTTP factory — auto pilih backend sesuai env
        self.session, self._http_backend = build_http_session()
        self.session.headers.update(
            {
                "Accept": "*/*",
                "Accept-Language": "id;q=0.7",
                "Content-Type": "application/json",
                "Authentication": self.token,
                "Origin": ORIGIN,
                "Referer": REFERER,
                "User-Agent": DEFAULT_USER_AGENT,
            }
        )
        if proxy:
            self.session.proxies.update(proxy)

        # Default currency dipakai untuk cookie scoping. Akan di-update tiap
        # place_bet sesuai parameter `currency`.
        self.active_currency = self.default_currencies[0]
        # Snapshot terakhir wallet (cache untuk update saldo setelah bet).
        self._wallet_cache: dict[str, float] = {}

    # ---- HTTP layer ------------------------------------------------------

    def _cookie_header(self, currency: str | None = None) -> str:
        coin = (currency or self.active_currency or "DOGE").upper()
        return (
            f"access={self.token}; "
            f"store.currency=%22{coin}%22; "
            "version=2"
        )

    def _send_batch(
        self, actions: list[dict], currency: str | None = None
    ) -> list[dict]:
        if not actions:
            raise RuntimeError("Batch action kosong.")
        payload = []
        for action in actions:
            name = str(action.get("name", "")).strip()
            if not name:
                continue
            entry: dict = {"name": name}
            body = action.get("payload")
            if body is not None:
                entry["payload"] = body
            payload.append(entry)
        body_text = _serialize_batch_payload(payload)
        sha = hashlib.sha256(body_text.encode("utf-8")).hexdigest()
        headers = {
            "X-Amz-Content-Sha256": sha,
            "Cookie": self._cookie_header(currency),
        }
        resp = self.session.post(
            BASE_URL,
            data=body_text,
            headers=headers,
            timeout=DEFAULT_TIMEOUT,
        )
        if resp.status_code >= 400:
            snippet = (resp.text or "")[:240].replace("\n", " ").strip()
            raise RuntimeError(f"HTTP {resp.status_code}: {snippet}")
        # fast_json_loads pakai orjson kalau tersedia (5x lebih cepat).
        try:
            from ..lua_support import fast_json_loads
            data = fast_json_loads(resp.content)
        except Exception as exc:
            raise RuntimeError(f"Invalid JSON: {resp.text[:200]}") from exc
        if isinstance(data, dict):
            data = [data]
        if not isinstance(data, list):
            raise RuntimeError(f"Unexpected batch response: {data!r}")
        return data

    def _run_action(
        self,
        name: str,
        payload: dict | None = None,
        *,
        currency: str | None = None,
    ) -> Any:
        items = self._send_batch(
            [{"name": name, "payload": payload}], currency=currency
        )
        if not items:
            raise RuntimeError(f"Action {name} returned empty.")
        item = items[0]
        if not isinstance(item, dict):
            raise RuntimeError(f"Action {name} returned invalid item: {item!r}")
        if not item.get("ok", False):
            detail = item.get("error") or item.get("errors") or item
            raise RuntimeError(json.dumps(detail, ensure_ascii=False))
        return item.get("data")

    def _try_actions(
        self,
        action_names: tuple[str, ...] | list[str],
        label: str,
        *,
        currency: str | None = None,
        payload: dict | None = None,
    ) -> Any:
        attempts: list[str] = []
        for name in action_names:
            try:
                return self._run_action(name, payload, currency=currency)
            except Exception as exc:
                attempts.append(f"{name}: {exc}")
        raise RuntimeError(f"{label} failed -> {' | '.join(attempts)}")

    # ---- BaseClient contract ---------------------------------------------

    def balances(self) -> dict:
        """Return shape Wolfbet-compatible: {"balances": [{currency, amount}, ...]}."""
        try:
            data = self._try_actions(
                DEFAULT_BALANCE_ACTIONS,
                "balance",
                currency=self.active_currency,
                payload={"wallet": "main"},
            )
        except Exception:
            return {"balances": []}
        wallets = _extract_wallets(data)
        items = [
            {"currency": w["currency"], "amount": float(w["amount"])} for w in wallets
        ]
        self._wallet_cache = {w["currency"]: float(w["amount"]) for w in wallets}
        return {"balances": items}

    def stats(self) -> dict:
        return {}

    def profile(self) -> dict:
        try:
            data = self._try_actions(
                DEFAULT_PROFILE_ACTIONS,
                "profile",
                currency=self.active_currency,
            )
        except Exception:
            return {"user": _profile_from_token(self.token) or {}}
        profile = _extract_profile(data) or _profile_from_token(self.token) or {}
        return {"user": profile}

    def place_bet(self, currency: str, amount: float, chance: float, bethigh: bool) -> dict:
        currency_upper = currency.upper()
        self.active_currency = currency_upper

        amount_dec = Decimal(str(amount)).quantize(
            Decimal("0.00000001"), rounding=ROUND_HALF_UP
        )
        if amount_dec < MIN_BET:
            amount_dec = MIN_BET

        chance_dec = Decimal(str(chance))
        if chance_dec < Decimal("0.01"):
            chance_dec = Decimal("0.01")
        if chance_dec > Decimal("98.00"):
            chance_dec = Decimal("98.00")

        condition = "above" if bethigh else "below"
        target_dec = Decimal("100") - chance_dec if bethigh else chance_dec
        if target_dec < Decimal("0.01"):
            target_dec = Decimal("0.01")
        if target_dec > Decimal("99.99"):
            target_dec = Decimal("99.99")

        payload = _merge_payload(
            {},
            {
                "condition": condition,
                "target": float(
                    target_dec.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                ),
                "amount": {"$bigfloat": f"{amount_dec:.8f}"},
                "currency": currency_upper,
                "identifier": str(uuid.uuid4()),
            },
        )

        data = self._run_action("rollDice", payload, currency=currency_upper)
        if not isinstance(data, dict):
            raise RuntimeError(f"rollDice returned unexpected data: {data!r}")

        # Parse result. Bentuk response server bisa bervariasi; ambil dengan key umum.
        roll_value = _parse_number(
            data.get("roll") or data.get("number") or data.get("result")
        )
        win_flag = bool(
            data.get("win")
            if "win" in data
            else (data.get("isWin") if "isWin" in data else None)
        )
        # Profit: kalau API kasih `profit` langsung pakai, kalau ngga hitung dari
        # winAmount - amount.
        if "profit" in data:
            profit = _parse_number(data.get("profit"))
        elif "winAmount" in data or "payout" in data:
            win_amount = _parse_number(data.get("winAmount") or data.get("payout"))
            profit = win_amount - float(amount_dec)
        else:
            multiplier = 99.0 / max(0.01, float(chance_dec))
            profit = float(amount_dec) * (multiplier - 1.0) if win_flag else -float(amount_dec)

        # Update wallet cache.
        prev_balance = self._wallet_cache.get(currency_upper)
        if prev_balance is None:
            try:
                self.balances()
                prev_balance = self._wallet_cache.get(currency_upper, 0.0)
            except Exception:
                prev_balance = 0.0
        new_balance = prev_balance + profit
        self._wallet_cache[currency_upper] = new_balance

        return {
            "bet": {
                "amount": float(amount_dec),
                "state": "win" if win_flag else "lose",
                "result_value": float(roll_value),
                "profit": float(profit),
            },
            "userBalance": {"amount": float(new_balance)},
        }

    def reset_seed(self) -> dict:
        try:
            data = self._try_actions(
                DEFAULT_RESET_SEED_ACTIONS,
                "reset_seed",
                currency=self.active_currency,
            )
        except Exception:
            return {}
        return data if isinstance(data, dict) else {"data": data}


def _profile_from_token(token: str) -> dict | None:
    """Best-effort extract user info dari JWT-like token (tanpa verifikasi)."""
    if not token or token.count(".") < 2:
        return None
    import base64

    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        decoded = base64.urlsafe_b64decode(payload.encode("utf-8"))
        data = json.loads(decoded.decode("utf-8"))
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    player = data.get("player") or {}
    return {
        "id": player.get("id"),
        "name": player.get("name"),
        "email": data.get("email"),
    }
