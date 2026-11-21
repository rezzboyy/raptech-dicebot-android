"""Local dice simulator for testing Lua strategies without a real API."""

from __future__ import annotations

import json
import random
import time
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from ..config import DEFAULT_CURRENCIES


class TestModeClient:
    """Wolf.bet-shaped local simulator.

    The simulator mirrors Wolf.bet dice math closely enough for strategy tests:
    win multiplier is `99 / chance_used`, rounded to 4 decimals.
    """

    display_name: str = "Test Mode"
    default_currencies: tuple[str, ...] = tuple(DEFAULT_CURRENCIES) + ("TEST",)
    min_bet: float = 1e-8
    requires_token: bool = False

    def __init__(self, token: str = "", proxy: dict[str, str] | None = None):
        self._rng = random.Random()
        self._balances: dict[str, Decimal] = {}
        self._stats: dict[str, dict[str, Decimal | int]] = {}
        self._start_balance = Decimal("1.00000000")
        self._seed = ""
        self._configure(token)
        for currency in self.default_currencies:
            self._balances.setdefault(currency.upper(), self._start_balance)

    def _configure(self, token: str) -> None:
        raw = (token or "").strip()
        if not raw:
            self._seed = str(time.time_ns())
            self._rng.seed(self._seed)
            return
        self._seed = raw
        self._rng.seed(raw)
        if not raw.startswith("{"):
            return
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return
        if not isinstance(data, dict):
            return
        try:
            self._start_balance = Decimal(str(data.get("balance", self._start_balance)))
        except Exception:
            self._start_balance = Decimal("1.00000000")
        if self._start_balance < 0:
            self._start_balance = Decimal("0")
        seed = str(data.get("seed") or raw)
        self._seed = seed
        self._rng.seed(seed)

    def _ensure_currency(self, currency: str) -> str:
        key = (currency or self.default_currencies[0]).upper()
        self._balances.setdefault(key, self._start_balance)
        self._stats.setdefault(
            key,
            {
                "total_bets": 0,
                "win": 0,
                "lose": 0,
                "profit": Decimal("0"),
                "wagered": Decimal("0"),
            },
        )
        return key

    @staticmethod
    def _quant8(value: Decimal) -> Decimal:
        return value.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)

    @staticmethod
    def _wolfbet_dice_params(chance: float, bethigh: bool) -> tuple[Decimal, Decimal]:
        chance_dec = Decimal(str(max(0.01, min(98.0, chance))))
        if bethigh:
            game = 9999 - int(chance_dec * Decimal("100"))
            bet_value = Decimal(game) / Decimal("100")
            chance_used = Decimal("99.99") - bet_value
            if bet_value <= Decimal("5.0"):
                bet_value = Decimal("5.01")
                chance_used = Decimal("99.99") - bet_value
        else:
            game = int(chance_dec * Decimal("100"))
            bet_value = Decimal(game) / Decimal("100")
            chance_used = bet_value
            if bet_value >= Decimal("95.0"):
                bet_value = Decimal("94.99")
                chance_used = Decimal("94.99")
        if chance_used <= 0:
            chance_used = chance_dec
        multiplier = (Decimal("99") / chance_used).quantize(
            Decimal("0.0001"), rounding=ROUND_HALF_UP
        )
        return bet_value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), multiplier

    # ---- BaseClient contract ---------------------------------------------

    def balances(self) -> dict:
        ordered = []
        seen = set()
        for currency in self.default_currencies:
            key = currency.upper()
            if key in self._balances:
                ordered.append((key, self._balances[key]))
                seen.add(key)
        ordered.extend(
            (currency, amount)
            for currency, amount in sorted(self._balances.items())
            if currency not in seen
        )
        return {
            "balances": [
                {"currency": currency, "amount": float(amount)}
                for currency, amount in ordered
            ]
        }

    def stats(self) -> dict:
        dice: dict[str, dict[str, Any]] = {}
        for currency, item in self._stats.items():
            dice[currency.lower()] = {
                "total_bets": int(item["total_bets"]),
                "win": int(item["win"]),
                "lose": int(item["lose"]),
                "profit": float(item["profit"]),
                "wagered": float(item["wagered"]),
            }
        return {"dice": dice}

    def profile(self) -> dict:
        return {
            "user": {
                "username": "test-mode",
                "email": "",
                "id": f"local-{abs(hash(self._seed)) % 1000000}",
            }
        }

    def place_bet(self, currency: str, amount: float, chance: float, bethigh: bool) -> dict:
        key = self._ensure_currency(currency)
        amount_dec = self._quant8(max(Decimal(str(amount)), Decimal(str(self.min_bet))))
        if self._balances[key] < amount_dec:
            raise RuntimeError(
                f"insufficient balance: need {amount_dec:.8f} {key}, "
                f"available {self._balances[key]:.8f} {key}"
            )

        bet_value, multiplier = self._wolfbet_dice_params(chance, bethigh)
        roll_int = self._rng.randint(0, 9999)
        roll = (Decimal(roll_int) / Decimal("100")).quantize(Decimal("0.01"))
        win = roll > bet_value if bethigh else roll < bet_value

        if win:
            profit = self._quant8(amount_dec * (multiplier - Decimal("1")))
        else:
            profit = -amount_dec
        self._balances[key] = self._quant8(self._balances[key] + profit)

        stat = self._stats[key]
        stat["total_bets"] = int(stat["total_bets"]) + 1
        stat["win" if win else "lose"] = int(stat["win" if win else "lose"]) + 1
        stat["profit"] = Decimal(str(stat["profit"])) + profit
        stat["wagered"] = Decimal(str(stat["wagered"])) + amount_dec

        return {
            "bet": {
                "amount": float(amount_dec),
                "state": "win" if win else "lose",
                "result_value": float(roll),
                "profit": float(profit),
            },
            "userBalance": {"amount": float(self._balances[key])},
        }

    def reset_seed(self) -> dict:
        self._seed = str(time.time_ns())
        self._rng.seed(self._seed)
        return {"seed": self._seed}
