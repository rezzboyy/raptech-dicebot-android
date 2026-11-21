"""ParaDice client implementation.

Diadaptasi dari `clientparadice.py` (standalone CLI) ke kontrak `BaseClient`.

ParaDice memakai GraphQL via single endpoint (`https://api.paradice.in/api.php`).
Auth memakai header `x-access-token: <token>`. Tidak ada endpoint REST balance,
semua via GraphQL.

Karena response `rollDice` tidak mengembalikan saldo terbaru, client ini
menjaga snapshot balance lokal yang diupdate setiap bet (`balance += profit`),
dengan fallback fetch wallet kalau snapshot belum ada.
"""

from __future__ import annotations

import time

from ..http_client import build_http_session


API_URL = "https://api.paradice.in/api.php"
DEFAULT_TIMEOUT = 30


class ParaDiceClient:
    display_name: str = "ParaDice"
    default_currencies: tuple[str, ...] = (
        "BTC",
        "ETH",
        "DOGE",
        "LTC",
        "TRX",
        "BCH",
        "XRP",
    )
    min_bet: float = 1e-8

    def __init__(self, token: str, proxy: dict[str, str] | None = None):
        self.token = (token or "").strip()
        # Shared HTTP factory — auto pilih backend sesuai env
        self.session, self._http_backend = build_http_session()
        self.session.headers.update(
            {
                "User-Agent": "WolfengineCLI/Paradice",
                "Content-Type": "application/json",
                "x-access-token": self.token,
            }
        )
        if proxy:
            self.session.proxies.update(proxy)
        # Snapshot balance lokal per currency. Diisi dari balances() & diupdate
        # tiap place_bet supaya engine tidak butuh fetch ulang setiap cycle.
        self._balance_cache: dict[str, float] = {}

    # ---- HTTP layer ------------------------------------------------------

    def _graphql(self, query: str, variables: dict | None = None) -> dict:
        payload: dict = {"query": query}
        if variables is not None:
            payload["variables"] = variables
        try:
            resp = self.session.post(API_URL, json=payload, timeout=DEFAULT_TIMEOUT)
        except requests.RequestException as exc:
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

        Sekaligus refresh `_balance_cache`.
        """
        data = self._graphql("{me{ wallets{currency balance bonus}}}")
        wallets = (data.get("me") or {}).get("wallets") or []
        items: list[dict] = []
        cache: dict[str, float] = {}
        for wallet in wallets:
            currency = str(wallet.get("currency") or "").upper()
            if not currency:
                continue
            try:
                amount = float(wallet.get("balance") or 0.0)
            except (TypeError, ValueError):
                amount = 0.0
            items.append({"currency": currency, "amount": amount})
            cache[currency] = amount
        self._balance_cache = cache
        return {"balances": items}

    def stats(self) -> dict:
        """ParaDice butuh user_id + currency untuk fetch stats.

        Kita tidak punya keduanya saat dipanggil dari engine generic, jadi
        return kosong. Lifetime panel akan blank, tapi sesi-level stats
        (yang dihitung engine sendiri) tetap akurat.
        """
        return {}

    def profile(self) -> dict:
        """Return shape Wolfbet-compatible: {"user": {...}}."""
        try:
            data = self._graphql("{ me{ id username email serverSeed clientSeed } }")
        except Exception:
            data = {}
        me = data.get("me") or {}
        if not isinstance(me, dict):
            me = {}
        return {"user": me}

    def place_bet(self, currency: str, amount: float, chance: float, bethigh: bool) -> dict:
        """Place a dice bet via GraphQL `rollDice` mutation.

        Mengembalikan shape Wolfbet:
          {"bet": {amount, state, result_value, profit}, "userBalance": {amount}}
        """
        if chance <= 0 or chance >= 100:
            raise RuntimeError("Chance harus di antara 0 dan 100.")
        if amount <= 0:
            raise RuntimeError("Bet amount harus lebih dari 0.")

        target_int = 9999 - int(chance * 100) if bethigh else int(chance * 100)
        target = round(target_int / 100.0, 2)

        currency_upper = currency.upper()
        query = (
            "mutation rollDice("
            "$number: Float!, $betAmount: Float!, $side: RollSideEnum!, $currency: CurrencyEnum!) "
            "{ rollDice(number: $number, betAmount: $betAmount, side: $side, currency: $currency) "
            "{id betAmount winAmount number rollSide currency roll win multiplier }}"
        )
        variables = {
            "number": target,
            "betAmount": float(amount),
            "side": "ABOVE" if bethigh else "BELOW",
            "currency": currency_upper,
        }
        data = self._graphql(query, variables)
        result = data.get("rollDice") or {}

        # Normalize numbers
        try:
            placed_amount = float(result.get("betAmount") or amount)
        except (TypeError, ValueError):
            placed_amount = float(amount)
        try:
            win_amount = float(result.get("winAmount") or 0.0)
        except (TypeError, ValueError):
            win_amount = 0.0
        try:
            roll = float(result.get("roll") or 0.0)
        except (TypeError, ValueError):
            roll = 0.0
        win_flag = bool(result.get("win"))
        profit = (win_amount - placed_amount) if win_flag else -placed_amount

        # Update local balance snapshot. Kalau cache kosong (misal place_bet
        # dipanggil tanpa balances() lebih dulu), fallback fetch sekali.
        if currency_upper not in self._balance_cache:
            try:
                self.balances()
            except Exception:
                self._balance_cache.setdefault(currency_upper, 0.0)
        new_balance = self._balance_cache.get(currency_upper, 0.0) + profit
        self._balance_cache[currency_upper] = new_balance

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
        """Reset client seed via `setClientSeed` mutation."""
        client_seed = str(time.time()).replace(".", "")[-12:]
        query = (
            "mutation setClientSeed($seed: String!) "
            "{ setClientSeed(seed: $seed) { id clientSeed } }"
        )
        try:
            return self._graphql(query, {"seed": client_seed})
        except Exception:
            return {}
