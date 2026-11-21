"""Lua strategy runtime preparation.

Diekstrak dari `engine/__init__.py` (Fase 3 perapihan, Step L-D).
Bridge antara Lua strategy file dan engine event hooks. Tidak akses
state engine langsung — terima `client` & `stop_event` lewat parameter.

Public API:
    - `prepare_strategy_runtime(strategy_path, currency, balance, account, *,
        client, stop_event, remote_config, license_status)`
        -> (globs, chance, basebet, nextbet, bethigh)
"""
from __future__ import annotations

import threading
import time
from pathlib import Path

from ..clients.base import BaseClient
from ..lua_support import get_global, load_lua_strategy
from ..models import AccountSnapshot


def prepare_strategy_runtime(
    strategy_path: Path,
    currency: str,
    balance: float,
    account: AccountSnapshot,
    *,
    client: BaseClient,
    stop_event: threading.Event,
    remote_config: dict | None = None,
    license_status: dict | None = None,
):
    """Load Lua strategy + setup runtime globals + register helper hooks.

    Return tuple `(globs, chance, basebet, nextbet, bethigh)` siap dipakai
    main loop di engine.

    Helper hooks (`stop`, `resetseed`, `resetpartialprofit`, `resetchart`,
    `resetstats`, `invest`, `sleep`) diekspos ke Lua side. `stop` set
    `stop_event`; `resetseed` panggil `client.reset_seed()`; sisanya
    in-place mutate `runtime_globals`.
    """
    runtime_globals = None

    def stop():
        stop_event.set()

    def resetseed():
        try:
            client.reset_seed()
        except Exception:
            return None
        return None

    def resetpartialprofit():
        if runtime_globals is not None:
            runtime_globals["partialprofit"] = 0.0
        return None

    def resetchart():
        return None

    def resetstats():
        if runtime_globals is None:
            return None
        runtime_globals["partialprofit"] = 0.0
        runtime_globals["currentprofit"] = 0.0
        runtime_globals["currentstreak"] = 0
        runtime_globals["profit"] = 0.0
        return None

    def invest(_amount=None):
        return None

    def sleep(ms=0):
        try:
            delay = max(0.0, float(ms) / 1000.0)
        except (TypeError, ValueError):
            delay = 0.0
        if delay > 0:
            time.sleep(delay)
        return None

    initial_globals = {
        "balance": balance,
        "profit": 0.0,
        "wagered": 0.0,
        "bets": 0,
        "wins": 0,
        "losses": 0,
        "totalbets": int(account.total_bets),
        "totalwins": int(account.total_wins),
        "totallosses": int(account.total_losses),
        "totalprofit": float(account.total_profit),
        "totalwagered": float(account.total_wagered),
        "win": False,
        "currentprofit": 0.0,
        "currentstreak": 0,
        "previousbet": 0.0,
        "bethigh": False,
        "chance": 49.5,
        "nextbet": 0.0,
        "startbalance": balance,
        "partialprofit": 0.0,
        "level": 0,
        "levelmax": 0,
        "lastBet": {"Roll": 50.0, "Nonce": 0},
        "stop": stop,
        "resetseed": resetseed,
        "resetpartialprofit": resetpartialprofit,
        "resetchart": resetchart,
        "resetstats": resetstats,
        "invest": invest,
        "sleep": sleep,
        "remote_config": dict(remote_config or {}),
        "license_status": dict(license_status or {}),
    }

    lua = load_lua_strategy(strategy_path, initial_globals)
    runtime_globals = lua.globals()
    runtime_globals["stop"] = stop
    runtime_globals["resetseed"] = resetseed
    runtime_globals["resetpartialprofit"] = resetpartialprofit
    runtime_globals["resetchart"] = resetchart
    runtime_globals["resetstats"] = resetstats
    runtime_globals["invest"] = invest
    runtime_globals["sleep"] = sleep
    runtime_globals["currency"] = currency.lower()

    chance = float(get_global(runtime_globals, "chance", 49.5))
    basebet = float(get_global(
        runtime_globals, "basebet",
        get_global(runtime_globals, "base", 0.00000001),
    ))
    nextbet = float(get_global(runtime_globals, "nextbet", basebet))
    bethigh = bool(get_global(runtime_globals, "bethigh", False))
    if basebet <= 0:
        basebet = 0.00000001
    if nextbet <= 0:
        nextbet = basebet

    runtime_globals["chance"] = chance
    runtime_globals["basebet"] = basebet
    runtime_globals["base"] = basebet
    runtime_globals["nextbet"] = nextbet
    runtime_globals["bethigh"] = bethigh
    runtime_globals["previousbet"] = basebet
    return runtime_globals, chance, basebet, nextbet, bethigh
