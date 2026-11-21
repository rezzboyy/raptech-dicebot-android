"""Stake.com client implementation.

Diadaptasi dari `bahanstakeclient.py` (StakeDice JS class) ke kontrak
`BaseClient`.

Endpoint: `https://api.stake.com/graphql`
Auth header: `x-access-token: <token>`
Currency native: lowercase (btc, eth, ltc, doge, bch, xrp, trx, eos).

GraphQL operations yang dipakai:
- `DiceBotGetBalance`  : fetch user/balances/statistic
- `DiceRoll`           : place bet, return CasinoBet + DiceState
- `DiceBotRotateSeed`  : reset server seed + change client seed

Catatan: source JS asli call `Bet` query setelah `DiceRoll` untuk dapat
`iid`. Engine Wolfengine tidak butuh field itu, jadi kita skip call kedua
agar lebih cepat dan hemat API.
"""

from __future__ import annotations

import secrets

import os

from ..http_client import build_http_session


# Endpoint GraphQL Stake. Default = endpoint yang dipakai website stake.com
# sendiri (`/_api/graphql`). Endpoint lama `api.stake.com/graphql` sudah
# mati (balas 404 "Cannot POST /graphql").
#
# Kalau ter-geo-block, set env RAPTECH_STAKE_URL ke mirror region kamu, mis:
#   https://stake.bet/_api/graphql   https://stake.games/_api/graphql
#   https://staketr.com/_api/graphql (dan mirror lain sesuai region)
API_URL = (
    os.getenv("RAPTECH_STAKE_URL")
    or os.getenv("STAKE_API_URL")
    or "https://stake.com/_api/graphql"
)
DEFAULT_TIMEOUT = 30

# Origin/Referer diturunkan dari API_URL supaya konsisten dengan mirror.
try:
    from urllib.parse import urlsplit as _urlsplit

    _p = _urlsplit(API_URL)
    _ORIGIN = f"{_p.scheme}://{_p.netloc}"
except Exception:
    _ORIGIN = "https://stake.com"


_QUERY_BALANCE = (
    "query DiceBotGetBalance{"
    "user{"
    "id "
    "name "
    "balances{available{currency amount}} "
    "statistic{game bets wins losses betAmount profit currency}"
    "}"
    "}"
)

_MUTATION_ROLL = (
    "mutation DiceRoll("
    "$amount: Float!, $target: Float!, $condition: CasinoGameDiceConditionEnum!, "
    "$currency: CurrencyEnum!, $identifier: String!"
    "){"
    "diceRoll("
    "amount:$amount,target:$target,condition:$condition,"
    "currency:$currency,identifier:$identifier"
    "){"
    "id active payoutMultiplier amount payout currency "
    "state{...on CasinoGameDice{result target condition}}"
    "}"
    "}"
)

_MUTATION_RESET = (
    "mutation DiceBotRotateSeed($seed: String!){"
    "rotateServerSeed{seed seedHash nonce} "
    "changeClientSeed(seed:$seed){seed}"
    "}"
)


class StakeClient:
    """Client untuk stake.com (GraphQL dice).

    Coin yang tersedia di akun user di-deteksi otomatis via `balances()`
    setelah login (lihat method tersebut). `default_currencies` di sini
    hanya berperan sebagai fallback display ketika:
      - Token belum di-set / login belum berhasil
      - API balance gagal di-fetch
      - Akun benar-benar tidak punya saldo apapun

    Setelah `balances()` sukses, engine akan pakai list coin yang
    sebenarnya ada di akun (sesuai response Stake).
    """

    display_name: str = "Stake"
    # Subset coin populer Stake. Bukan filter — cuma fallback agar menu coin
    # tetap berisi sesuatu kalau API balance gagal di-call.
    default_currencies: tuple[str, ...] = (
        "BTC",
        "ETH",
        "LTC",
        "DOGE",
        "BCH",
        "XRP",
        "TRX",
        "EOS",
        "USDT",
        "USDC",
        "BNB",
        "SOL",
        "MATIC",
        "DAI",
        "LINK",
        "AVAX",
        "ATOM",
        "ETC",
        "XMR",
        "XLM",
        "ZEC",
        "DASH",
        "SHIB",
        "PEPE",
        "TON",
        "APT",
        "NEAR",
        "ALGO",
        "AAVE",
        "UNI",
    )
    min_bet: float = 1e-8

    def __init__(self, token: str, proxy: dict[str, str] | None = None):
        self.token = (token or "").strip()
        # Stake didukung Cloudflare — prefer curl_cffi kalau env tidak
        # explicit set httpx. curl_cffi tetap default untuk backward compat.
        self.session, self._http_backend = build_http_session(prefer_curl_cffi=True)
        self.session.headers.update(
            {
                # UA browser-like: Cloudflare Stake lebih toleran daripada UA
                # custom. curl_cffi impersonate menangani TLS fingerprint.
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept": "*/*",
                "Content-Type": "application/json",
                "Origin": _ORIGIN,
                "Referer": f"{_ORIGIN}/",
                "x-access-token": self.token,
                "x-lockdown-token": "undefined",
            }
        )
        if proxy:
            self.session.proxies.update(proxy)

    # ---- HTTP layer ------------------------------------------------------

    def _graphql(self, query: str, variables: dict | None = None) -> dict:
        payload: dict = {"query": query}
        if variables is not None:
            payload["variables"] = variables
        try:
            resp = self.session.post(API_URL, json=payload, timeout=DEFAULT_TIMEOUT)
        except Exception as exc:
            raise RuntimeError(f"Network error: {exc}") from exc
        if resp.status_code >= 400:
            snippet = (resp.text or "")[:240].replace("\n", " ").strip()
            raise RuntimeError(f"HTTP {resp.status_code}: {snippet}")
        # fast_json_loads pakai orjson kalau tersedia (5x lebih cepat).
        try:
            from ..lua_support import fast_json_loads
            doc = fast_json_loads(resp.content)
        except Exception as exc:
            snippet = (resp.text or "")[:240].replace("\n", " ").strip()
            raise RuntimeError(f"Invalid JSON: {snippet}") from exc
        if isinstance(doc, dict) and doc.get("errors"):
            err = doc["errors"][0]
            msg = err.get("message", "Unknown API error") if isinstance(err, dict) else str(err)
            raise RuntimeError(msg)
        return (doc or {}).get("data") or {}

    # ---- BaseClient contract ---------------------------------------------

    def balances(self) -> dict:
        """Return shape Wolfbet-compatible: {"balances": [{currency, amount}, ...]}.

        Ngambil seluruh entry `user.balances[].available` apa adanya — tidak
        di-filter berdasarkan list default. Artinya semua coin yang user punya
        di Stake (termasuk yang aku ngga tau, mis. coin baru yang launching
        kemarin) akan otomatis muncul di menu pilih coin.
        """
        data = self._graphql(_QUERY_BALANCE)
        user = data.get("user") or {}
        items: list[dict] = []
        for entry in user.get("balances") or []:
            available = (entry or {}).get("available") or {}
            currency = str(available.get("currency") or "").upper()
            if not currency:
                continue
            try:
                amount = float(available.get("amount") or 0.0)
            except (TypeError, ValueError):
                amount = 0.0
            items.append({"currency": currency, "amount": amount})
        # Sort: yang punya saldo > 0 muncul duluan, lalu alphabet
        items.sort(key=lambda x: (0 if x["amount"] > 0 else 1, x["currency"]))
        return {"balances": items}

    def stats(self) -> dict:
        """Return shape Wolfbet-compatible: {"dice": {"<coin_lower>": {...}}}.

        Stake `user.statistic[]` mengembalikan stats per (game, currency).
        Kita filter game `dice` dan grup per currency agar sama dengan
        format yang diharapkan engine.
        """
        try:
            data = self._graphql(_QUERY_BALANCE)
        except Exception:
            return {}
        user = data.get("user") or {}
        dice_stats: dict[str, dict] = {}
        for entry in user.get("statistic") or []:
            if not isinstance(entry, dict):
                continue
            if str(entry.get("game") or "").lower() != "dice":
                continue
            currency = str(entry.get("currency") or "").lower()
            if not currency:
                continue
            try:
                bets = int(entry.get("bets") or 0)
                wins = int(entry.get("wins") or 0)
                losses = int(entry.get("losses") or 0)
                profit = float(entry.get("profit") or 0.0)
                wagered = float(entry.get("betAmount") or 0.0)
            except (TypeError, ValueError):
                bets = wins = losses = 0
                profit = wagered = 0.0
            dice_stats[currency] = {
                "total_bets": bets,
                "win": wins,
                "lose": losses,
                "profit": profit,
                "wagered": wagered,
            }
        return {"dice": dice_stats}

    def profile(self) -> dict:
        """Return shape Wolfbet-compatible: {"user": {...}}."""
        try:
            data = self._graphql(_QUERY_BALANCE)
        except Exception:
            return {"user": {}}
        user = data.get("user") or {}
        return {
            "user": {
                "id": user.get("id"),
                "username": user.get("name"),
            }
        }

    def place_bet(self, currency: str, amount: float, chance: float, bethigh: bool) -> dict:
        """Place a dice bet via `DiceRoll` mutation.

        Mengembalikan shape Wolfbet:
          {"bet": {amount, state, result_value, profit}, "userBalance": {amount}}
        """
        if chance <= 0 or chance >= 100:
            raise RuntimeError("Chance harus di antara 0 dan 100.")
        if amount <= 0:
            raise RuntimeError("Bet amount harus lebih dari 0.")

        # Target perhitungan sama dengan source JS:
        #   high: target = (999999 - chance*10000 + 1) / 10000, rounded 2 desimal
        #   low : target = (chance*10000 - 1) / 10000, rounded 2 desimal
        if bethigh:
            target_int = 999999 - int(chance * 10000) + 1
            condition = "above"
        else:
            target_int = int(chance * 10000) - 1
            condition = "below"
        target = round(target_int / 10000.0, 2)
        # Clamp ke range valid
        if target < 0.01:
            target = 0.01
        if target > 99.99:
            target = 99.99

        currency_lower = currency.lower()
        identifier = secrets.token_hex(10)  # mirip "d316d71e2f075a05339d" di source
        variables = {
            "amount": float(amount),
            "target": float(target),
            "condition": condition,
            "currency": currency_lower,
            "identifier": identifier,
        }
        data = self._graphql(_MUTATION_ROLL, variables)
        result = data.get("diceRoll") or {}

        try:
            placed_amount = float(result.get("amount") or amount)
        except (TypeError, ValueError):
            placed_amount = float(amount)
        try:
            payout = float(result.get("payout") or 0.0)
        except (TypeError, ValueError):
            payout = 0.0
        state = result.get("state") or {}
        try:
            roll = float(state.get("result") or 0.0)
        except (TypeError, ValueError):
            roll = 0.0
        profit = payout - placed_amount
        win_flag = profit > 0

        # Stake `DiceRoll` tidak return saldo terbaru langsung. Untuk konsistensi
        # dengan engine, fetch ulang sekali. Cost: 1 extra request per bet.
        # Kalau perlu lebih cepat, bisa diganti pakai snapshot lokal.
        new_balance = 0.0
        try:
            balances_doc = self.balances()
            for item in balances_doc.get("balances", []):
                if str(item.get("currency", "")).upper() == currency.upper():
                    new_balance = float(item.get("amount") or 0.0)
                    break
        except Exception:
            new_balance = 0.0

        return {
            "bet": {
                "amount": placed_amount,
                "state": "win" if win_flag else "lose",
                "result_value": roll,
                "profit": profit,
            },
            "userBalance": {"amount": new_balance},
        }

    def reset_seed(self) -> dict:
        """Rotate server seed + change client seed via `DiceBotRotateSeed`."""
        client_seed = secrets.token_hex(8)
        try:
            data = self._graphql(_MUTATION_RESET, {"seed": client_seed})
        except Exception:
            return {}
        rotate = (data or {}).get("rotateServerSeed") or {}
        change = (data or {}).get("changeClientSeed") or {}
        return {
            "seed": change.get("seed") or client_seed,
            "seedHash": rotate.get("seedHash"),
            "nonce": rotate.get("nonce"),
        }
