"""Lua strategy script check (sandbox load + dry-run dobet).

Diekstrak dari `cli/__init__.py` (Fase 2 perapihan, Step E).
Self-contained: tidak menyentuh state UI selain `get_theme()` untuk
warna laporan.

Public API (di-re-export oleh `cli/__init__.py`):
    - `check_strategy_script(path, *, currency, balance) -> dict`
    - `print_script_check_report(results, *, no_color) -> None`
"""
from __future__ import annotations

import math
from pathlib import Path

from ..lua_support import get_global, load_lua_strategy
from ._state import get_theme

# Konstanta minimum bet (sinkron dengan `cli/__init__.py:MIN_BET`).
MIN_BET = 0.00000001


def _script_check_globals(balance: float, currency: str) -> dict:
    """Sediakan globals palsu untuk Lua sandbox saat dry-run check."""
    stopped = {"value": False}

    def stop():
        stopped["value"] = True
        return None

    def resetseed():
        return None

    def resetpartialprofit():
        return None

    def resetchart():
        return None

    def resetstats():
        return None

    def invest(_amount=None):
        return None

    def sleep(_ms=0):
        return None

    return {
        "balance": balance,
        "profit": 0.0,
        "wagered": 0.0,
        "bets": 0,
        "wins": 0,
        "losses": 0,
        "totalbets": 0,
        "totalwins": 0,
        "totallosses": 0,
        "totalprofit": 0.0,
        "totalwagered": 0.0,
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
        "currency": currency.lower(),
        "stop": stop,
        "resetseed": resetseed,
        "resetpartialprofit": resetpartialprofit,
        "resetchart": resetchart,
        "resetstats": resetstats,
        "invest": invest,
        "sleep": sleep,
        "_stopped": stopped,
    }


def _as_finite_number(value, name: str) -> tuple[float | None, str | None]:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None, f"{name} bukan angka: {value!r}"
    if not math.isfinite(number):
        return None, f"{name} bukan angka finite: {value!r}"
    return number, None


def _load_strategy_for_check(strategy_path: Path, currency: str, balance: float):
    lua = load_lua_strategy(strategy_path, _script_check_globals(balance, currency))
    globs = lua.globals()
    globs["currency"] = currency.lower()
    return globs


def check_strategy_script(
    strategy_path: Path,
    *,
    currency: str = "BTC",
    balance: float = 1.0,
) -> dict:
    """Cek satu file Lua: load, validasi global, dry-run dobet().

    Return dict `{name, ok, findings: list[(level, message)]}`.
    Level: PASS, WARN, FAIL.
    """
    findings: list[tuple[str, str]] = []

    def add(level: str, message: str) -> None:
        findings.append((level, message))

    if not strategy_path.is_file():
        return {
            "name": strategy_path.name,
            "ok": False,
            "findings": [("FAIL", f"File tidak ditemukan: {strategy_path}")],
        }

    try:
        globs = _load_strategy_for_check(strategy_path, currency, balance)
    except Exception as exc:
        return {
            "name": strategy_path.name,
            "ok": False,
            "findings": [("FAIL", f"Lua gagal load: {exc}")],
        }

    add("PASS", "Lua berhasil load.")

    chance_raw = get_global(globs, "chance", None)
    chance, err = _as_finite_number(chance_raw, "chance")
    if err:
        add("FAIL", err)
    elif not (0.01 <= chance <= 98.0):
        add("WARN", f"chance di luar range engine 0.01-98: {chance:.8f}")
    else:
        add("PASS", f"chance valid: {chance:.4f}")

    base_raw = get_global(globs, "basebet", get_global(globs, "base", None))
    basebet, err = _as_finite_number(base_raw, "basebet/base")
    if err:
        add("WARN", f"{err}; engine akan fallback ke minimum.")
        basebet = MIN_BET
    elif basebet <= 0:
        add("WARN", f"basebet <= 0 ({basebet:.8f}); engine akan fallback ke minimum.")
        basebet = MIN_BET
    else:
        add("PASS", f"basebet valid: {basebet:.8f}")

    next_raw = get_global(globs, "nextbet", None)
    nextbet, err = _as_finite_number(next_raw, "nextbet")
    if err:
        add("WARN", f"{err}; engine akan fallback ke basebet.")
        nextbet = basebet
    elif nextbet <= 0:
        add("WARN", f"nextbet <= 0 ({nextbet:.8f}); engine akan fallback ke basebet.")
        nextbet = basebet
    else:
        add("PASS", f"nextbet valid: {nextbet:.8f}")

    bethigh_raw = get_global(globs, "bethigh", None)
    if isinstance(bethigh_raw, bool):
        add("PASS", f"bethigh valid: {bethigh_raw}")
    else:
        add("WARN", f"bethigh bukan boolean ({bethigh_raw!r}); engine akan konversi bool().")

    dobet = get_global(globs, "dobet", None)
    if dobet is None:
        add("WARN", "dobet() tidak ditemukan; script akan flat-bet tanpa update logic.")
    elif not callable(dobet):
        add("FAIL", f"dobet bukan function/callable: {dobet!r}")
    else:
        add("PASS", "dobet() ditemukan.")
        for win_flag in (False, True):
            try:
                run_globs = _load_strategy_for_check(strategy_path, currency, balance)
                previous = max(float(get_global(run_globs, "nextbet", nextbet) or nextbet), MIN_BET)
                run_globs["previousbet"] = previous
                run_globs["win"] = win_flag
                run_globs["currentroll"] = 49.5 if win_flag else 99.0
                run_globs["currentprofit"] = previous if win_flag else -previous
                run_globs["currentstreak"] = 1 if win_flag else -1
                run_globs["balance"] = balance + (previous if win_flag else -previous)
                run_globs["bets"] = 1
                run_globs["wins"] = 1 if win_flag else 0
                run_globs["losses"] = 0 if win_flag else 1
                run_globs["profit"] = previous if win_flag else -previous
                run_globs["wagered"] = previous
                run_globs["lastBet"] = {"Roll": run_globs["currentroll"], "Nonce": 1}
                run_dobet = get_global(run_globs, "dobet", None)
                run_dobet()
                after_next, err_next = _as_finite_number(
                    get_global(run_globs, "nextbet", previous),
                    f"nextbet setelah {'win' if win_flag else 'lose'}",
                )
                after_chance, err_chance = _as_finite_number(
                    get_global(run_globs, "chance", chance or 49.5),
                    f"chance setelah {'win' if win_flag else 'lose'}",
                )
                if err_next:
                    add("FAIL", err_next)
                elif after_next <= 0:
                    add("FAIL", f"nextbet setelah {'win' if win_flag else 'lose'} <= 0.")
                if err_chance:
                    add("FAIL", err_chance)
                elif not (0.01 <= after_chance <= 98.0):
                    add("WARN", f"chance setelah {'win' if win_flag else 'lose'} di luar 0.01-98: {after_chance:.8f}")
                if not err_next and after_next > 0 and not err_chance:
                    add("PASS", f"dobet() OK untuk state {'win' if win_flag else 'lose'}.")
            except Exception as exc:
                add("FAIL", f"dobet() error untuk state {'win' if win_flag else 'lose'}: {exc}")

    return {
        "name": strategy_path.name,
        "ok": not any(level == "FAIL" for level, _message in findings),
        "findings": findings,
    }


def print_script_check_report(results: list[dict], *, no_color: bool = False) -> None:
    """Render hasil `check_strategy_script` ke stdout.

    `no_color` disisakan untuk back-compat; warna actual dikontrol
    oleh tema aktif via `get_theme()`.
    """
    # Lazy import section() untuk hindari import-cycle dengan __init__.
    from . import section
    from colorama import Fore  # type: ignore

    theme = get_theme()
    section("CHECK SCRIPT", Fore.CYAN, no_color)
    for index, result in enumerate(results):
        if index:
            print("")
        status = "PASS" if result["ok"] else "FAIL"
        role = "success" if result["ok"] else "danger"
        print(f"{theme.c(status, role, bold=True)}  {result['name']}")
        for level, message in result["findings"]:
            level_role = (
                "success" if level == "PASS"
                else ("warning" if level == "WARN" else "danger")
            )
            print(f"  {theme.c(level.ljust(4), level_role, bold=True)} {message}")
